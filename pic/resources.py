"""Paths to resources shipped with pic (the example guix manifest).

Two layouts are supported: the repository checkout (<repo>/guix) and
an installed package (data files under <prefix>/share/pic).  The
user's ~/.config/pic/manifest.scm overrides both.
"""

import os
import sys
from pathlib import Path

from .util import die, expand_path


def _resource(name):
    # checkout layout: <repo>/<name>, next to the pic package
    path = Path(__file__).resolve().parent.parent / name
    if path.is_file():
        return path
    # installed layout: <prefix>/share/pic/<name>  (wheel data files);
    # walk up the ancestors: the package sits at
    # <prefix>/lib/python3.X/site-packages/pic/, so <prefix> is a few
    # levels up, depending on the layout.
    for parent in Path(__file__).resolve().parents:
        path = parent / "share" / "pic" / name
        if path.is_file():
            return path
    die(f"pic: resource not found: {name}")


def default_manifest(env=None):
    """The default guix agent manifest: the user's
    ~/.config/pic/manifest.scm when present, else the shipped example."""
    env = env if env is not None else os.environ
    user_manifest = Path(expand_path("~/.config/pic/manifest.scm", env))
    if user_manifest.is_file():
        return user_manifest
    return _resource("guix/manifest.scm")
