#!/usr/bin/env python3
"""OCR a single image or PDF file using Marker (marker-pdf).

Marker is a document-to-Markdown converter built on Surya layout and text
recognition models.  It produces clean, structured Markdown from PDFs and
common image formats, preserving headings, tables, and column order better
than traditional OCR pipelines.

Model weights (~500 MB–1 GB total) are downloaded on first use and cached
at ~/.cache/marker/ (or the platform default for HuggingFace Hub).  Each
subsequent call reuses the in-memory singleton, so only the first call in a
process is slow.

Requires:
    pip install marker-pdf

Usage (standalone):
    tetrak-ocr ocr workspace/scans/my-document.pdf --backend marker
    tetrak-ocr ocr workspace/scans/my-postcard.jpg --backend marker
"""

from __future__ import annotations

from pathlib import Path

from ..imaging import reject_multi_page

try:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
except ImportError:  # pragma: no cover - depends on installed extras
    _IMPORT_OK = False
else:
    _IMPORT_OK = True


# Marker supports PDFs and common raster image formats.
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".pdf"}

# Module-level model dictionary singleton.  Building the model dict loads
# Surya layout, detection, and recognition models (~500 MB–1 GB).  Creating
# it once and passing artifact_dict= to every PdfConverter avoids reloading
# weights on each call.
_models: dict | None = None


def _get_models() -> dict:
    """Return (and lazily initialise) the module-level Marker model dict."""
    global _models
    if _models is None:
        _models = create_model_dict()
    return _models


def ocr_image(path: Path) -> str:
    """Extract text from an image or PDF using Marker.

    Marker converts the document to Markdown.  Page layout, columns, and
    tables are detected automatically.  For multi-page PDFs each page is
    processed and the results concatenated in reading order.

    Args:
        path: Path to the file (PDF or image).

    Returns:
        Extracted text as a Markdown string.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is not supported.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{path.suffix}' for Marker backend. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Multi-page TIFF: this backend reads frame 0 only, so refuse rather than
    # return page one as though it were the document. See tetrak_ocr.imaging.
    reject_multi_page(path, "marker")

    converter = PdfConverter(artifact_dict=_get_models())
    rendered = converter(str(path))
    text, _, _ = text_from_rendered(rendered)
    return text.strip()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCR a single image or PDF file using Marker.")
    parser.add_argument("path", type=Path, help="Path to the image or PDF file.")
    args = parser.parse_args()

    print(ocr_image(args.path))
