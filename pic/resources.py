"""Paths to resources shipped with pic (the example guix manifest).

Two layouts are supported: the repository checkout (<repo>/guix) and
an installed package (data files under <prefix>/share/pic).
"""

import sys
from pathlib import Path

from .util import die


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


def default_manifest():
    """The example agent manifest for the guix backend."""
    return _resource("guix/manifest.scm")
