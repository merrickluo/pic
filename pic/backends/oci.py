"""oci backend: podman/docker OCI containers with a prebuilt agent image.

`DRIVER run --rm -it --network NET -v SHARE:SHARE... -e KEY=VALUE...
 -w WORKSPACE IMAGE pi INNER...`

The image must already contain the agent (there is no project-env mode:
a Dockerfile in the project is not built).  Env preserve regexps are
expanded against the host environment — guix accepts regexps natively,
OCI needs concrete -e KEY=VALUE pairs; this is the one semantic
difference the spec absorbs.
"""

import os
import re
import shutil

from ..spec import ProjectEnv
from ..util import PicError
from .base import Backend


class OciBackend(Backend):
    name = "oci"
    platforms = ("linux", "darwin")   # darwin: via docker/podman on macOS

    def available(self):
        return self._driver(None, None) is not None

    def _driver(self, config, env):
        want = (config.oci_driver if config is not None else "auto") or "auto"
        if want != "auto":
            return want                      # explicit: trust the user
        for candidate in ("podman", "docker"):
            if shutil.which(candidate):
                return candidate
        return None

    def project_env(self, workspace, config):
        return None                          # prebuilt image; no project env

    def validate(self, spec, config, env):
        if self._driver(config, env) is None:
            raise PicError(
                "pic: no OCI driver found (install podman or docker, or set "
                "backend.oci.driver in the configuration)")

    def build_argv(self, spec, config, env):
        driver = self._driver(config, env)
        argv = [driver, "run", "--rm", "-it"]
        argv += ["--network", config.oci_network]
        argv += [f"-v{p}:{p}" for p in spec.shares]
        for key, value in expand_env(spec.preserves, env):
            argv += ["-e", f"{key}={value}"]
        argv += ["-w", str(spec.workspace)]
        argv += [spec.runtime or config.oci_image]
        argv += spec.command
        return argv


def expand_env(preserves, env=None):
    """Expand PRESERVES (regexps) into the matching (KEY, VALUE) pairs.

    Iteration order follows the host environment order, which keeps the
    argv deterministic for a given environment.
    """
    env = env if env is not None else os.environ
    patterns = [re.compile(regexp) for regexp in preserves]
    result = []
    for key, value in env.items():
        if any(p.match(key) for p in patterns):
            result.append((key, value))
    return result
