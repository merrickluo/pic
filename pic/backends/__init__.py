"""Backend registry.  Add new backends here (see README.md)."""

from ..util import die
from .base import Backend
from .guix import GuixBackend
from .oci import OciBackend

BACKENDS = {
    "guix": GuixBackend(),
    "oci": OciBackend(),
}


def select_backend(config, env=None):
    """Resolve config.backend ('auto' or a name) to a Backend instance.

    'auto' prefers guix (the primary runtime), then any available
    backend.  Be explicit with --backend for anything else.
    """
    name = config.backend or "auto"
    if name != "auto":
        backend = BACKENDS.get(name)
        if backend is None:
            die(f"pic: unknown backend: {name} "
                f"(known: {', '.join(BACKENDS)})")
        return backend
    for candidate in ("guix", "oci"):
        backend = BACKENDS[candidate]
        if backend.available():
            return backend
    die("pic: no backend available (guix shell or podman/docker required)")
