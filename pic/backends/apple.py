"""apple backend: Apple's `container` (macOS 26, Apple silicon).

OCI-compatible; runs Linux containers as per-container VMs.  Same
image and docker-shaped flags as the oci backend, with three
differences: `-e KEY` inherits its value from the host (no expansion),
`--init` runs an init process that forwards signals, and `--ssh`
forwards the SSH agent socket.  Like oci, the container runs as the
host uid:gid (--user) so files keep host ownership.
"""

import shutil

from ..util import PicError
from .base import Backend, home_env, match_env, run_tail
from .oci import identity_args


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
        argv += identity_args("docker")   # container is docker-shaped
        argv += ["--network", config.apple_network]
        if config.apple_init:
            argv.append("--init")
        if config.apple_ssh:
            argv.append("--ssh")
        # apple `container` has no `-v` shorthand; only `--volume`
        argv += [f"--volume={p}:{p}" for p in spec.shares]
        # the Linux image user (root) has a different home; point $HOME at
        # the mounted host home so pi finds ~/.pi, ~/.ssh, ~/.gitconfig, ...
        argv += ["-e", home_env(env)]
        # `-e KEY` inherits the value from the host; only the key is passed
        for key, _value in match_env(spec.preserves, env):
            argv += ["-e", key]
        argv += run_tail(spec, spec.runtime or config.apple_image)
        return argv

