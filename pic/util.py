"""Small shared helpers."""

import os
import sys
from pathlib import Path


class PicError(Exception):
    """A user-facing failure with a helpful message."""


def die(message):
    """Print MESSAGE to stderr and exit with status 1."""
    print(message, file=sys.stderr)
    sys.exit(1)


def expand_path(value, env=None):
    """Expand a leading `~` and any $HOME in VALUE."""
    env = env if env is not None else os.environ
    home = env.get("HOME", str(Path.home()))
    if value.startswith("~"):
        value = home + value[1:]
    return value.replace("$HOME", home)
