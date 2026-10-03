#!/usr/bin/env python3
"""OCR a single image file using Tesseract and return the extracted text.

Supports JPEG, PNG, TIFF, and PDF (including multi-page PDFs).
Requires Tesseract to be installed on the system (brew install tesseract).
PDF support also requires Poppler (brew install poppler).

Usage:
    tetrak-ocr ocr <path-to-image>
    tetrak-ocr ocr <path-to-image> --contrast 3.0 --psm 6
    tetrak-ocr ocr <path-to-image> --backend tesseract-auto       # auto-configure
"""

from __future__ import annotations

from pathlib import Path

import pytesseract
from PIL import Image, ImageEnhance, ImageOps, ImageStat

from ..imaging import frame_count, iter_frames, pdf_renderer
from . import tuning

# File extensions this module can handle.
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".pdf"}

# Default contrast enhancement factor.  1.0 = no change; 2.0 is a good
# starting point for faded postcards and handwritten text.  Increase toward
# 3.0 for very low-contrast originals; reduce toward 1.0 if dark originals
# are losing detail.
DEFAULT_CONTRAST = 2.0

# Default Tesseract page segmentation mode.
# PSM 3 = fully automatic page segmentation (Tesseract default).
# Override with --psm or let analyse_image() pick one automatically.
DEFAULT_PSM = 3


def analyse_image(image: Image.Image) -> dict:
    """Inspect image characteristics and suggest Tesseract configuration.

    This does a fast, cheap analysis of the greyscale image to determine
    appropriate contrast and PSM settings without any OCR.

    Heuristics
    ----------
    **The band edges are not written out here.** They live in
    `tetrak_ocr.backends.tuning`, are fitted from a measured configuration
    sweep by `evaluation/ocr/calibration/fit.py`, and they move — the
    2026-09-27 re-fit changed every one of them. This docstring held a copy
    until then, and the copy would have been wrong the same afternoon. Call
    `tuning.describe()` for the current values, or read the table on
    https://tetrak.dev/reference/routing/, which is generated from the module.

    Contrast boost
        Based on the standard deviation of pixel intensities in the greyscale
        image.  A low stddev means the image is tonally flat — ink and
        background are similar in brightness.  We compensate with a higher
        contrast factor.

    Page segmentation mode (PSM)
        Based on `dark_pct`, the share of the frame below luminance 128.

        Read `dark_pct` as "how much of the frame is not paper", NOT as text
        density — it cannot tell ink from imagery.  A night-scene postcard
        reads 56% dark because of the photograph, not because it is covered
        in text.  That turns out to be the useful signal anyway: a frame
        dominated by a dark image has little page structure for layout
        analysis to work with, whichever way the darkness got there.

        PSM 3  — fully automatic page segmentation; finds and orders columns
        PSM 6  — assumes one uniform block; right when there is no real layout
        PSM 12 — sparse text with orientation detection; the OSD is what reads
                 the 90-degree rotated imprint on a postcard reverse

        These bands were fitted to measured results, not guessed: every
        (contrast, PSM) pair was scored against the committed ground truth and
        the bands chosen to select the winner for each fixture.  Re-fit them if
        the fixture set changes materially.

        Note PSM 11 (sparse, no OSD) and PSM 1 (auto, with OSD) were both
        tested and never won outright — PSM 1 tied PSM 3 exactly on all three
        document-like fixtures, so PSM 3 is preferred here to avoid depending
        on the OSD training data.

    Returns
    -------
    dict with keys:
        "contrast"  (float)  — suggested contrast enhancement factor
        "psm"       (int)    — suggested Tesseract PSM value
        "stddev"    (float)  — greyscale standard deviation (for diagnostics)
        "dark_pct"  (float)  — % of pixels below luminance 128 (for diagnostics)
    """
    grey = image.convert("L")
    stat = ImageStat.Stat(grey)
    stddev = stat.stddev[0]

    hist = grey.histogram()
    total = sum(hist)
    dark_pct = sum(hist[:128]) / total * 100

    contrast, psm = tuning.suggest(stddev, dark_pct)

    return {"contrast": contrast, "psm": psm, "stddev": stddev, "dark_pct": dark_pct}


def preprocess(image: Image.Image, contrast: float = DEFAULT_CONTRAST) -> Image.Image:
    """Prepare an image for OCR by converting to greyscale and boosting contrast.

    Why greyscale?
        Tesseract operates on greyscale luminance internally.  Converting
        first strips colour noise (e.g. postcard backgrounds, stamps) and
        gives the engine a clean single-channel signal.

    Why contrast enhancement?
        Postcards and handwritten documents often have faded ink or uneven
        lighting.  Boosting contrast widens the gap between dark text and
        light background, sharpening the edges that Tesseract relies on.

    Args:
        image:    The PIL Image to preprocess.
        contrast: Contrast enhancement factor.  1.0 = no change.
                  Use DEFAULT_CONTRAST as a starting point.

    Returns:
        A new greyscale PIL Image with enhanced contrast.
    """
    grey = ImageOps.grayscale(image)
    return ImageEnhance.Contrast(grey).enhance(contrast)


def ocr_image(
    path: Path,
    contrast: float | None = None,
    psm: int | None = None,
    auto: bool = False,
    lang: str | None = None,
) -> str:
    """Extract text from an image or PDF file.

    Images are preprocessed (greyscale + contrast boost) before being passed
    to Tesseract.  For PDFs, each page is preprocessed and processed separately
    and the results are joined with a blank line between pages.

    Args:
        path:     Path to the image or PDF file.
        contrast: Contrast enhancement factor passed to preprocess().
                  If None and auto=False, uses DEFAULT_CONTRAST.
                  If None and auto=True, inferred from image characteristics.
        psm:      Tesseract page segmentation mode (0–13).
                  If None and auto=False, uses DEFAULT_PSM (3).
                  If None and auto=True, inferred from image characteristics.
        auto:     If True, call analyse_image() to pick contrast and psm
                  automatically when those values are not explicitly provided.
        lang:     Tesseract language code(s), e.g. "hye" for Armenian or
                  "hye+eng" for mixed material. None uses Tesseract's default
                  (English). The named traineddata must be installed — on
                  Homebrew that is the tesseract-lang formula — or Tesseract
                  errors. Added for the Armenian baseline measurements
                  (brief 011, the Armenian recogniser); deliberately
                  not surfaced in the CLI until a measured reason exists.

    Returns:
        The extracted text as a single string.

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

    if path.suffix.lower() == ".pdf":
        return _ocr_pdf(path, contrast, psm, auto=auto, lang=lang)

    # For raster images, optionally run auto-analysis to fill in unspecified
    # params. On a multi-page TIFF this reads frame 0 and applies its settings
    # to every page -- see _ocr_image_file for why that is the conservative
    # choice rather than a measured one.
    if auto and (contrast is None or psm is None):
        with Image.open(path) as image:
            config = analyse_image(image)
        contrast = contrast if contrast is not None else config["contrast"]
        psm = psm if psm is not None else config["psm"]

    # `is None`, not `or`: psm=0 is a documented Tesseract mode (OSD only)
    # and a falsy-check would silently replace it with the default.
    if contrast is None:
        contrast = DEFAULT_CONTRAST
    if psm is None:
        psm = DEFAULT_PSM
    return _ocr_image_file(path, contrast, psm, lang=lang)


def _ocr_image_file(
    path: Path,
    contrast: float = DEFAULT_CONTRAST,
    psm: int = DEFAULT_PSM,
    lang: str | None = None,
) -> str:
    """Run Tesseract on a raster image, reading every page of a multi-page TIFF.

    TIFF can hold many frames and archival TIFF often does. Pillow opens such a
    file at frame 0, so the previous single `Image.open` here transcribed page
    one and discarded the rest without saying so -- see
    :mod:`tetrak_ocr.imaging`.

    Pages are joined the same way ``_ocr_pdf`` joins its own, because they are
    the same thing: one document arriving as a sequence of page images.

    The contrast and PSM settled by the caller apply to every page. That is the
    conservative choice rather than a measured one: per-page auto-configuration
    is what lost badly on the PDF fixture (see ``_ocr_pdf``), and there is no
    multi-page TIFF in the corpus to fit anything better against. Revisit it if
    one is added.
    """
    pages = frame_count(path)

    if pages == 1:
        with Image.open(path) as image:
            return pytesseract.image_to_string(
                preprocess(image, contrast), config=f"--psm {psm}", lang=lang
            )

    page_texts = [
        pytesseract.image_to_string(preprocess(page, contrast), config=f"--psm {psm}", lang=lang)
        for page in iter_frames(path)
    ]
    return "\n\n".join(page_texts)


def _ocr_pdf(
    path: Path,
    contrast: float | None = None,
    psm: int | None = None,
    auto: bool = False,
    lang: str | None = None,
) -> str:
    """Convert each PDF page to an image, then run Tesseract on each page.

    `auto` is accepted and deliberately ignored: PDFs use the fixed defaults.
    That is a measured decision, not an oversight.  On the king-of-kings
    fixture, scored against ground truth, every adaptive strategy lost to the
    plain defaults (character similarity, word recall roughly flat at ~0.93
    throughout):

        PSM 3 + contrast 2.0 (these defaults)        0.377   <- best
        PSM 1 + contrast auto per page               0.341
        PSM 3 + contrast auto per page               0.338
        PSM 6 for dark plates, else 3, contrast auto 0.259
        PSM + contrast both auto per page            0.060
        PSM 4 + contrast auto per page               0.018

    The reason is that analyse_image()'s dark_pct bands are fitted to
    tightly-cropped standalone images.  A typeset page with generous margins is
    only a few percent dark, so it falls in the sparsest band and gets PSM 12 —
    but it is a document page and wants page segmentation.  The 2026-09-27
    re-fit did not change that: no PDF is in any split, precisely because the
    bands never run on this path.  Adapting contrast
    alone does not help either; fixed 2.0 beats per-page contrast.

    Caveat: this rests on a single PDF fixture.  If more PDFs are added, re-run
    the comparison before assuming the defaults still win — a PDF-specific band
    set may become worth fitting once there is enough material to fit it to.
    """
    # Imported through the shared helper so a missing renderer is explained
    # the same way wherever it is hit.
    convert_from_path = pdf_renderer()

    # `auto` is intentionally unused here — see the docstring for the measured
    # comparison that settled it.
    contrast = contrast if contrast is not None else DEFAULT_CONTRAST
    psm = psm if psm is not None else DEFAULT_PSM

    pages = convert_from_path(path)
    page_texts = [
        pytesseract.image_to_string(preprocess(page, contrast), config=f"--psm {psm}", lang=lang)
        for page in pages
    ]
    return "\n\n".join(page_texts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCR a single image or PDF file.")
    parser.add_argument("path", type=Path, help="Path to the image or PDF file.")
    parser.add_argument(
        "--contrast",
        type=float,
        default=None,
        help=f"Contrast enhancement factor (default: {DEFAULT_CONTRAST}). "
        "1.0 = no change; try 3.0 for very faded originals.",
    )
    parser.add_argument(
        "--psm",
        type=int,
        default=None,
        help=f"Tesseract page segmentation mode (default: {DEFAULT_PSM}). "
        "3=auto, 6=uniform block, 11=sparse text.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Automatically choose contrast and PSM from image characteristics.",
    )
    parser.add_argument(
        "--analyse",
        action="store_true",
        help="Print image analysis results without running OCR.",
    )
    parser.add_argument(
        "--lang",
        type=str,
        default=None,
        help='Tesseract language code(s), e.g. "hye" or "hye+eng". '
        "Requires the matching traineddata to be installed.",
    )
    args = parser.parse_args()

    if args.analyse:
        img = Image.open(args.path)
        info = analyse_image(img)
        print(f"Image analysis: {args.path.name}")
        print(f"  StdDev:   {info['stddev']:.1f}  (contrast → {info['contrast']})")
        print(f"  Dark%:    {info['dark_pct']:.1f}%  (PSM → {info['psm']})")
    else:
        result = ocr_image(
            args.path, contrast=args.contrast, psm=args.psm, auto=args.auto, lang=args.lang
        )
        print(result)
