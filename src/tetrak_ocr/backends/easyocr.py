#!/usr/bin/env python3
"""OCR a single image file using EasyOCR and return the extracted text.

EasyOCR uses deep learning models (CRAFT for detection, CRNN for recognition)
and works well on complex layouts, curved text, and images where Tesseract
struggles.  Unlike Tesseract it requires no system-level installation —
everything runs through pip.

On first run the model weights are downloaded automatically (~100 MB).  They
are cached in ~/.EasyOCR/ and reused on subsequent calls.

Requires:
    pip install easyocr

Usage (standalone):
    tetrak-ocr ocr workspace/scans/my-postcard.jpg --backend easyocr

No preprocessing is applied; EasyOCR handles varied contrast and layouts
internally via its neural network pipeline.
PDF support is not included; convert PDFs to images first.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from ..imaging import reject_multi_page

try:
    import easyocr
except ImportError:  # pragma: no cover - depends on installed extras
    _IMPORT_OK = False
else:
    _IMPORT_OK = True

# File extensions this backend can handle.
# PDFs are not supported natively; convert pages to images first.
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# Module-level reader singleton.  Initialising EasyOCR loads the model weights
# into memory (~300 MB), so we create it once and reuse it for the process
# lifetime.  This means the first call is slow (~5–30 s), subsequent calls fast.
_reader: easyocr.Reader | None = None


def _get_reader() -> easyocr.Reader:
    """Return (and lazily initialise) the module-level EasyOCR reader."""
    global _reader
    if _reader is None:
        # verbose=False silences the download/load progress bars.
        _reader = easyocr.Reader(["en"], verbose=False)
    return _reader


def ocr_image(path: Path) -> str:
    """Extract text from an image file using EasyOCR.

    Text regions are detected by CRAFT and recognised by a CRNN model.
    Results are returned in reading order (top-to-bottom, left-to-right)
    with a newline between each recognised region.

    TIFF files are converted to PNG in memory before processing because
    EasyOCR can have trouble reading multi-strip TIFF files directly.

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
    reject_multi_page(path, "easyocr")

    # Convert TIFF to PNG bytes in memory for reliable loading.
    if path.suffix.lower() in {".tif", ".tiff"}:
        import io

        buf = io.BytesIO()
        Image.open(path).convert("RGB").save(buf, format="PNG")
        image_input = buf.getvalue()
    else:
        image_input = str(path)

    reader = _get_reader()
    results = reader.readtext(image_input, detail=0, paragraph=False)
    return "\n".join(results)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCR a single image file using EasyOCR.")
    parser.add_argument("path", type=Path, help="Path to the image file.")
    args = parser.parse_args()

    print(ocr_image(args.path))
