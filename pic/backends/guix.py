"""guix backend: `guix shell -C` containers.

Two modes, decided by project detection:

- profile mode (no guix.scm/manifest.scm in the project):
  `guix shell -C --network -p PROFILE -- pi ...`
- project-env mode:
  `guix shell -C --network -L CHANNEL... -m AGENT-MANIFEST [-D -f guix.scm
  | -m manifest.scm] -- pi ...`

When the agent profile exists (spec.runtime or guix_profile), it is the
whole environment: guix shell cannot combine `--profile` with package
options (-f/-m), so a profile wins over the manifest path.  `guix.scm`
is loaded in development mode (`-D -f`); `manifest.scm` as a manifest
(`-m`).  The agent profile is never built on demand; validate() errors
with the exact build command instead.
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
        if spec.project is None:
            profile = spec.runtime or expand_path(config.guix_profile, env)
            if not os.path.isdir(profile):
                raise PicError(
                    f"pic: agent profile not found: {profile}\n"
                    f"  Build it with `guix package -p {profile} -m "
                    f"{config.guix_manifest}` (or let `guix home "
                    f"reconfigure` manage it).")

    def build_argv(self, spec, config, env):
        argv = ["guix", "shell", "-C"]
        if config.guix_network:
            argv.append("--network")
        # the workspace is guix's cwd; do not share it twice
        argv += [f"--share={p}" for p in spec.shares if p != spec.workspace]
        argv += [f"--preserve={r}" for r in spec.preserves]
        profile = spec.runtime or expand_path(config.guix_profile, env)
        if spec.project is not None and not os.path.isdir(profile):
            # no agent profile: combine the agent manifest with the
            # project's dev environment
            for channel in config.guix_channels:
                argv += ["-L", channel]
            argv += ["-m", str(config.guix_manifest)]
            argv += spec.project.container_args
        else:
            argv += ["-p", profile]
        argv += ["--"] + spec.command
        return argv

