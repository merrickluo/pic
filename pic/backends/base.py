"""The Backend contract: one implementation per container technology.

A backend translates a RuntimeSpec (pure data) into a native command
line and is responsible for discovering project dev environments
(e.g. guix.scm for guix).  The frontend never mentions a backend by
name except through the registry in pic/backends/__init__.py.
"""

from abc import ABC, abstractmethod

import re

from ..util import PicError, expand_path


def match_env(preserves, env):
    """(KEY, VALUE) pairs from ENV whose key matches a PRESERVES regexp.

    Order follows the host environment, which keeps the argv
    deterministic.  Raises PicError on a malformed regexp.
    """
    patterns = []
    for regexp in preserves:
        try:
            patterns.append(re.compile(regexp))
        except re.error as e:
            raise PicError(f"pic: bad preserve regexp: {regexp!r}: {e}")
    return [(key, value) for key, value in env.items()
            if any(p.match(key) for p in patterns)]


def home_env(env):
    """The -e HOME=... value pointing at the mounted host home."""
    return f"HOME={expand_path('~', env)}"


def run_tail(spec, image):
    """Shared docker-shaped argv tail: workdir, image, inner command."""
    return ["-w", str(spec.workspace), image, *spec.command]


class Backend(ABC):
    """A container technology that can host the agent."""

    name: str = ""
    platforms: tuple[str, ...] = ("linux",)

    @abstractmethod
    def available(self):
        """True when the runtime is installed and usable on this machine."""

    @abstractmethod
    def project_env(self, workspace, config):
        """Return a ProjectEnv for WORKSPACE, or None when the project has
        no dev environment this backend understands."""

    @abstractmethod
    def validate(self, spec, config, env):
        """Raise PicError with a helpful message when the runtime cannot
        satisfy the spec (e.g. a missing agent profile)."""

    @abstractmethod
    def build_argv(self, spec, config, env):
        """Return the full argv to execute (spec.command is the inner
        command, already resolved by the CLI)."""
