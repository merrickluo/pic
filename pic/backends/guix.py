"""guix backend: `guix shell -C` containers.

The agent comes from a manifest (`-m AGENT-MANIFEST`); local channels
that provide agent packages are passed with `-L` (`[backend.guix]
channels`).  When the project has a dev environment it is added on
top: `guix.scm` is loaded in development mode (`-D -f`), `manifest.scm`
as a manifest (`-m`).
"""

import os
import shutil

from ..spec import ProjectEnv
from ..util import PicError, expand_path
from .base import Backend


class GuixBackend(Backend):
    name = "guix"
    platforms = ("linux",)

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
        if not os.path.isfile(config.guix_manifest):
            raise PicError(
                f"pic: agent manifest not found: {config.guix_manifest}\n"
                f"  Point [backend.guix].manifest at an existing file.")
        for channel in config.guix_channels:
            if not os.path.isdir(expand_path(channel, env)):
                raise PicError(
                    f"pic: guix channel not found: {channel}\n"
                    f"  Point [backend.guix].channels at an existing "
                    f"channel checkout (clone it with `git clone`).")

    def build_argv(self, spec, config, env):
        argv = ["guix", "shell", "-C"]
        if config.guix_network:
            argv.append("--network")
        # the workspace is guix's cwd; do not share it twice
        argv += [f"--share={p}" for p in spec.shares if p != spec.workspace]
        argv += [f"--preserve={r}" for r in spec.preserves]
        for channel in config.guix_channels:
            argv += ["-L", expand_path(channel, env)]
        argv += ["-m", str(config.guix_manifest)]
        if spec.project is not None:
            argv += spec.project.container_args
        argv += ["--"] + spec.command
        return argv

