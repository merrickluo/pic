"""oci backend: podman/docker OCI containers with a prebuilt agent image.

`DRIVER run --rm -it [--userns=keep-id:uid=U,gid=G] --user U:G
 --network NET -v SHARE:SHARE... -e KEY=VALUE... -w WORKSPACE IMAGE
 pi INNER...`

The image must already contain the agent (there is no project-env mode:
a Dockerfile in the project is not built).  Env preserve regexps are
expanded against the host environment — guix accepts regexps natively,
OCI needs concrete -e KEY=VALUE pairs; and the container runs as the
host uid (keep-id for rootless podman), where guix keeps the host user
natively.  These are the semantic differences the spec absorbs.
"""

import os
import re
import shutil

from ..spec import ProjectEnv
from ..util import PicError, expand_path
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
        argv += identity_args(driver)
        argv += ["--network", config.oci_network]
        argv += [f"-v{p}:{p}" for p in spec.shares]
        # the image user (root) has a different home; point $HOME at the
        # mounted host home so pi finds ~/.pi, ~/.ssh, ~/.gitconfig, ...
        argv += ["-e", f"HOME={expand_path('~', env)}"]
        for key, value in expand_env(spec.preserves, env):
            argv += ["-e", f"{key}={value}"]
        argv += ["-w", str(spec.workspace)]
        argv += [spec.runtime or config.oci_image]
        argv += spec.command
        return argv


def identity_args(driver):
    """argv to run the container as the host uid:gid.

    OCI images default to root, so files created inside would get root
    ownership on the host (guix keeps the host user natively).  Docker
    and rootful podman map container uids to host uids 1:1; rootless
    podman maps container uids into a subuid range by default, so it
    needs keep-id to map our uid 1:1.
    """
    uid, gid = os.getuid(), os.getgid()
    user = ["--user", f"{uid}:{gid}"]
    if driver == "podman" and os.geteuid() != 0:
        return [f"--userns=keep-id:uid={uid},gid={gid}"] + user
    return user


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
