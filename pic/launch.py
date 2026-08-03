"""Orchestration: config -> backend selection -> spec -> exec."""

import os
import shlex
import shutil

import os
import shutil

from .backends import BACKENDS, select_backend
from .config import load_config
from .spec import assemble, inner_command
from .util import PicError, die


def run_pic(parsed, env=None):
    """Resolve the backend and launch the container.  Never returns on
    success (os.execv replaces the process)."""
    env = env if env is not None else os.environ
    config = load_config(parsed.project_dir, env=env, parsed=parsed)
    backend = select_backend(config, env)
    spec = assemble(config, parsed.project_dir,
                    inner_command(config.command, parsed.inner), env=env)
    if not config.no_project:
        spec.project = backend.project_env(spec.workspace, config)
    try:
        backend.validate(spec, config, env)
    except PicError as e:
        die(str(e))
    if parsed.dry_run:
        print(shlex.join(backend.build_argv(spec, config, env)))
        return 0
    launch(backend, spec, config, env)


def launch(backend, spec, config, env=None):
    """Run the container command assembled by BACKEND; never returns."""
    env = env if env is not None else os.environ
    argv = backend.build_argv(spec, config, env)
    binary = shutil.which(argv[0])
    if binary is None:
        die(f"pic: command not found: {argv[0]}")
    os.chdir(spec.workspace)
    os.execv(binary, [binary] + argv[1:])


def list_backends():
    """Name, availability and platforms of every registered backend."""
    for name, backend in BACKENDS.items():
        yield name, backend.available(), backend.platforms
