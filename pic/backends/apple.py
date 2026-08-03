"""apple backend: Apple's `container` (macOS 26, Apple silicon).

OCI-compatible; runs Linux containers as per-container VMs.  Same
image and docker-shaped flags as the oci backend, with three
differences: `-e KEY` inherits its value from the host (no expansion),
`--init` runs an init process that forwards signals, and `--ssh`
forwards the SSH agent socket.
"""

import os
import re
import shutil

from ..spec import ProjectEnv
from ..util import PicError
from .base import Backend


class AppleBackend(Backend):
    name = "apple"
    platforms = ("darwin",)

    def available(self):
        return shutil.which("container") is not None

    def project_env(self, workspace, config):
        return None  # prebuilt image; no project env

    def validate(self, spec, config, env):
        if shutil.which("container") is None:
            raise PicError(
                "pic: apple `container` not found (install it from "
                "https://github.com/apple/container)")

    def build_argv(self, spec, config, env):
        argv = ["container", "run", "--rm", "-it"]
        argv += ["--network", config.apple_network]
        if config.apple_init:
            argv.append("--init")
        if config.apple_ssh:
            argv.append("--ssh")
        argv += [f"-v{p}:{p}" for p in spec.shares]
        for key in inherit_env(spec.preserves, env):
            argv += ["-e", key]
        argv += ["-w", str(spec.workspace)]
        argv += [spec.runtime or config.apple_image]
        argv += spec.command
        return argv


def inherit_env(preserves, env=None):
    """Keys from ENV matching PRESERVES, for `-e KEY` host inheritance.

    The container tool copies the value from the host environment, so
    only the key is passed.  Order follows the host environment, which
    keeps the argv deterministic.
    """
    env = env if env is not None else os.environ
    patterns = [re.compile(regexp) for regexp in preserves]
    return [key for key in env if any(p.match(key) for p in patterns)]
