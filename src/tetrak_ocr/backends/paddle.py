#!/usr/bin/env python3
"""OCR a single image file using PaddleOCR and return the extracted text.

PaddleOCR is Baidu's open-source OCR toolkit, based on the PaddlePaddle deep
learning framework.  It uses a three-stage pipeline: text detection (DBNet),
text orientation classification, and text recognition (SVTR/PP-OCRv4).

On first run the model weights are downloaded automatically (~100 MB).  They
are cached in ~/.paddleocr/ and reused on subsequent calls.

Requires:
    pip install paddleocr paddlepaddle

Usage (standalone):
    tetrak-ocr ocr workspace/scans/my-postcard.jpg --backend paddle

No preprocessing is applied; PaddleOCR's neural pipeline handles varied
contrast and layouts internally.
PDF support is not included; convert PDFs to images first.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from PIL import Image

from ..imaging import reject_multi_page

# PaddlePaddle's C++ layer reads these as glog initialises, which happens
# during the import below -- so they are set before it rather than after, where
# they had nothing left to suppress. They name only paddle's own logging, so
# they cost nothing on a machine that never loads it.
os.environ.setdefault("GLOG_v", "0")
os.environ.setdefault("GLOG_logtostderr", "0")

try:
    from paddleocr import PaddleOCR
except ImportError:  # pragma: no cover - depends on installed extras
    _IMPORT_OK = False
else:
    _IMPORT_OK = True

# PaddleOCR's Python side emits a wall of INFO while it initialises, which
# would otherwise land in the middle of a transcript.
#
# Silenced by name, and at construction rather than at import. It was
# previously `logging.disable(logging.WARNING)` at module scope -- a global
# kill switch for every library in the process, reached by merely importing
# this module. The registry imports every backend to report which are
# installed, so `tetrak-ocr backends`, `evaluate --all` and `auto-local` each
# muted warnings from transformers, Pillow and reportlab as a side effect,
# including on machines with no paddleocr installed at all.
_NOISY_LOGGERS = ("ppocr", "paddle", "paddleocr")

# File extensions this backend can handle.
# PDFs are not supported natively; convert pages to images first.
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# Module-level OCR instance singleton.  Creating a PaddleOCR object loads
# model weights into memory; we create it once and reuse it.
_ocr_instance: PaddleOCR | None = None


def _get_ocr() -> PaddleOCR:
    """Return (and lazily initialise) the module-level PaddleOCR instance."""
    global _ocr_instance
    if _ocr_instance is None:
        for name in _NOISY_LOGGERS:
            logging.getLogger(name).setLevel(logging.ERROR)
        _ocr_instance = PaddleOCR(
            use_textline_orientation=True,
            lang="en",
        )
    return _ocr_instance


def ocr_image(path: Path) -> str:
    """Extract text from an image file using PaddleOCR.

    Text regions are detected, orientation-corrected, and recognised by
    PaddleOCR's PP-OCRv4 pipeline.  Results are returned in reading order
    (top-to-bottom, left-to-right) with a newline between each region.

    TIFF files are converted to PNG in memory before processing because
    PaddleOCR expects standard image formats.

    Args:
        path: Path to the image file.

    Returns:
        Extracted text as a single string, one recognised region per line.

    Raises:
        ValueError: If the file extension is not supported.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{path.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Multi-page TIFF: this backend reads frame 0 only, so refuse rather than
    # return page one as though it were the document. See tetrak_ocr.imaging.
    reject_multi_page(path, "paddle")

    # Convert TIFF to a temp PNG path because PaddleOCR needs a file path
    # and may not handle all TIFF variants.
    if path.suffix.lower() in {".tif", ".tiff"}:
        import io
        import tempfile

        buf = io.BytesIO()
        Image.open(path).convert("RGB").save(buf, format="PNG")
        buf.seek(0)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(buf.read())
            tmp_path = tmp.name
        image_input = tmp_path
        cleanup = True
    else:
        image_input = str(path)
        cleanup = False

    try:
        ocr = _get_ocr()
        results = ocr.predict(image_input)
    finally:
        if cleanup:
            os.unlink(image_input)

    texts = []
    if results:
        for page in results:
            if isinstance(page, dict) and "rec_texts" in page:
                texts.extend(page["rec_texts"])

    return "\n".join(texts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCR a single image file using PaddleOCR.")
    parser.add_argument("path", type=Path, help="Path to the image file.")
    args = parser.parse_args()

    print(ocr_image(args.path))
