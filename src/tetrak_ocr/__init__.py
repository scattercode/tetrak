"""Batch OCR pipeline and backend comparison harness for archival images.

Every backend exposes ``ocr_image(path) -> str``. Resolve one by name through
:mod:`tetrak_ocr.registry` rather than importing it directly, so that a
missing optional dependency reports which extra to install.

    >>> from tetrak_ocr.registry import get_backend
    >>> ocr = get_backend("tesseract")
    >>> text = ocr(Path("scan.jpg"))
"""

from .errors import MissingBackendError, OcrPipelineError, UnknownBackendError

try:
    # Written by hatch-vcs at build time from the git tag, and gitignored. A
    # literal here went stale -- it read 0.2.2 in the 5.14.0 wheel -- because
    # nothing updates it. Absent only when running from an unbuilt checkout.
    from ._version import __version__
except ImportError:
    __version__ = "0+unknown"

__all__ = [
    "MissingBackendError",
    "OcrPipelineError",
    "UnknownBackendError",
    "__version__",
]
