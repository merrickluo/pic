"""guix backend: `guix shell -C` containers.

The agent comes from a manifest (`-m AGENT-MANIFEST`); local channels
that provide agent packages are passed with `-L` (`[backend.guix]
channels`).  When the project has a dev environment it is added on
top: `guix.scm` is loaded in development mode (`-D -f`), `manifest.scm`
as a manifest (`-m`).

Profile cache: evaluating the manifest and channels costs several
seconds per launch, so by default the profile is materialized once per
cache key (`guix shell --root=PROFILE ... -- true`) and containers
launch with `-p PROFILE`.  The key covers the guix store path, the
agent manifest, the project env file, and each channel's HEAD commit.
Uncommitted channel changes do not invalidate the cache: commit them
(or set `profile_cache = false`) to pick them up.  Profiles live at
ROOT/BASE-KEY/PROJECT-KEY; after a profile is built, every other
base dir is pruned, so only per-project profiles of the current
guix/manifest/channels remain.  Disable with
`[backend.guix] profile_cache = false`.
"""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from ..spec import ProjectEnv
from ..util import PicError, expand_path
from .base import Backend, shimmed


def profiles_root(env):
    """Directory holding the cached agent profiles (one per cache key)."""
    xdg = env.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path(expand_path("~", env)) / ".local/share"
    return base / "pic" / "profiles"


def _guix_id(env):
    """Store path of the guix being run; changes on `guix pull`."""
    guix = shutil.which("guix", path=env.get("PATH"))
    return os.path.realpath(guix) if guix else ""


def _channel_state(path):
    """HEAD commit of the channel checkout; uncommitted changes are
    deliberately ignored."""
    try:
        return subprocess.run(
            ["git", "-C", path, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        # not a git checkout (or no git): the dir mtime is all we have
        return f"mtime:{os.stat(path).st_mtime_ns}"


def _project_env_parts(spec):
    """(mode, path) for the discovered project env, if any."""
    if spec.project is None:
        return []
    args = spec.project.container_args  # ["-D", "-f", path] | ["-m", path]
    return [(" ".join(args[:-1]), args[-1])]


def profile_path(spec, config, env):
    """The cached profile `ROOT/BASE-KEY/PROJECT-KEY` for these inputs,
    or None to run uncached (`profile_cache = false`).  BASE-KEY covers
    what all projects share; PROJECT-KEY the project env file."""
    if not config.guix_profile_cache:
        return None
    base = hashlib.sha256()
    base.update(f"guix\0{_guix_id(env)}\0".encode())
    manifest = expand_path(str(config.guix_manifest), env)
    base.update(b"manifest\0")
    base.update(Path(manifest).read_bytes())
    for channel in config.guix_channels:
        path = expand_path(channel, env)
        base.update(f"channel\0{path}\0{_channel_state(path)}\0".encode())
    project = hashlib.sha256()
    for mode, path in _project_env_parts(spec):
        project.update(f"project\0{mode}\0".encode())
        project.update(Path(path).read_bytes())
    return profiles_root(env) / base.hexdigest() / project.hexdigest()


def prune_stale_bases(profile):
    """Remove every entry of the profiles root except PROFILE's base
    dir.  Entries are GC roots only; `guix gc` frees the store."""
    for entry in profile.parent.parent.iterdir():
        if entry == profile.parent:
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)


class GuixBackend(Backend):
    name = "guix"
    platforms = ("linux",)
    _UNSET = object()

    def __init__(self):
        self._profile = self._UNSET

    def available(self):
        return shutil.which("guix") is not None

    def project_env(self, workspace, config):
        guix_scm = workspace / "guix.scm"
        manifest_scm = workspace / "manifest.scm"
        if guix_scm.is_file():
            return ProjectEnv(container_args=["-D", "-f", str(guix_scm)])
        if manifest_scm.is_file():
            return ProjectEnv(container_args=["-m", str(manifest_scm)])
        return None

    def validate(self, spec, config, env):
        manifest = expand_path(str(config.guix_manifest), env)
        if not os.path.isfile(manifest):
            raise PicError(
                f"pic: agent manifest not found: {manifest}\n"
                f"  Point [backend.guix].manifest at an existing file.")
        for channel in config.guix_channels:
            if not os.path.isdir(expand_path(channel, env)):
                raise PicError(
                    f"pic: guix channel not found: {channel}\n"
                    f"  Point [backend.guix].channels at an existing "
                    f"channel checkout (clone it with `git clone`).")

    def prepare(self, spec, config, env):
        """Build the cached profile when missing.  Concurrent builds of
        the same key are harmless: the daemon locks and both write the
        same symlink."""
        profile = self._cached_profile(spec, config, env)
        if profile is None or os.path.lexists(profile):
            return
        profile.parent.mkdir(parents=True, exist_ok=True)
        argv = ["guix", "shell", f"--root={profile}"]
        argv += self._package_args(spec, config, env)
        argv += ["--", "true"]
        try:
            subprocess.run(argv, check=True)
        except subprocess.CalledProcessError as e:
            raise PicError(
                f"pic: building the agent profile failed "
                f"(guix exited {e.returncode})") from e
        prune_stale_bases(profile)

    def build_argv(self, spec, config, env):
        argv = ["guix", "shell", "-C"]
        if config.guix_network:
            argv.append("--network")
        # the workspace is guix's cwd; do not share it twice
        argv += [f"--share={p}" for p in spec.shares if p != spec.workspace]
        argv += [f"--preserve={r}" for r in spec.preserves]
        profile = self._cached_profile(spec, config, env)
        if profile is not None:
            argv += ["-p", str(profile)]
        else:
            argv += self._package_args(spec, config, env)
        argv += ["--", *shimmed(spec.command)]
        return argv

    def _cached_profile(self, spec, config, env):
        if self._profile is self._UNSET:
            self._profile = profile_path(spec, config, env)
        return self._profile

    def _package_args(self, spec, config, env):
        """The `-L/-m/-D -f` argv fragment selecting the profile content."""
        argv = []
        for channel in config.guix_channels:
            argv += ["-L", expand_path(channel, env)]
        argv += ["-m", expand_path(str(config.guix_manifest), env)]
        if spec.project is not None:
            argv += spec.project.container_args
        return argv
