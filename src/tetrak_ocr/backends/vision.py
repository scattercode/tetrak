#!/usr/bin/env python3
"""OCR a single image using Apple's Vision framework, on macOS.

Vision ships with every Mac since 10.15. It is free, needs no API key, no
model download and no network, and Apple states plainly that "all of Vision's
processing happens on the user's device" — so it sits inside the local-first
guarantee exactly as Tesseract does, with none of Tesseract's system-package
installation.

That makes it the cheapest backend in the set for the machines that have it:
no weights to fetch on first run, no gigabyte of PyTorch, and a first call
that is fast rather than slow. On clean modern typescript it is expected to be
strong. On degraded historical print it is **unmeasured** — there is no
published benchmark comparing Vision against Tesseract on archival material,
which is the gap this backend exists to close. Run `evaluate --all` and find
out; that is the point of adding it.

Two limits worth knowing before reading its scores:

**Languages.** Apple publishes no list and the set grows with each OS release,
so it must be queried at runtime — :func:`supported_languages` does that, and
is the only answer worth trusting on a given machine. As a guide to the shape
of it, a macOS 15 machine reported 30 codes in August 2026: Latin, Cyrillic,
CJK, Thai, Vietnamese and Arabic (`ar-SA`, `ars-SA`), with no Armenian, Greek,
Hebrew, Georgian or Indic support. For the English-language
collections this package was built around that is no constraint; for anything
in one of those scripts it is absolute, and the other backends remain the only
answer. Armenian in particular is unavailable here, which matters given the
open question about Armenian-script material.

**Handwriting.** Apple has never documented handwriting recognition in Vision.
The word does not appear in the API references or the WWDC sessions, and every
Apple example is printed matter. Do not read a good score on a typed page as
evidence about a manuscript one.

Requires macOS and:
    pip install 'tetrak-ocr[vision]'

Usage:
    tetrak-ocr ocr workspace/scans/my-postcard.jpg --backend vision

No preprocessing is applied. Vision's `.accurate` path is a neural detector
that handles rotation, perspective and stylised type itself, so the contrast
and page-segmentation work `tesseract-auto` does has no equivalent here.
PDF support is not included: Vision takes images, not documents. Convert
pages to images first.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

from ..imaging import reject_multi_page
from ..layout import TextSpan, to_text

# Two separate reasons this backend may be unavailable, and they need to be
# distinguished: `ocrmac` is importable on any platform but only *works* on
# macOS, because it calls the Vision framework through PyObjC. Importing it
# elsewhere may succeed and then fail at call time, which is the failure mode
# the registry's _IMPORT_OK contract exists to prevent.
_IS_MACOS = sys.platform == "darwin"

if _IS_MACOS:
    try:
        from ocrmac import ocrmac
    except ImportError:  # pragma: no cover - depends on installed extras
        _IMPORT_OK = False
    else:
        _IMPORT_OK = True
else:  # pragma: no cover - platform-dependent
    _IMPORT_OK = False

# Vision takes images. PDFs are not supported natively; rasterise first.
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# Apple's neural path. `.fast` is a per-character classifier, closer to
# traditional OCR and materially worse on anything stylised or rotated —
# which is most of an ephemera corpus. Measured runtime difference is tens of
# milliseconds per image, so there is no case for defaulting to it here.
DEFAULT_RECOGNITION_LEVEL = "accurate"


def supported_languages() -> list[str]:
    """Language codes this Mac's Vision build can recognise.

    Apple publishes no list — the supported set grows with each OS release and
    is only discoverable at runtime. Exposed as a function so the answer comes
    from the machine rather than from documentation that may be stale.

    Returns an empty list where Vision is unavailable, so callers can treat
    "no languages" and "no Vision" the same way.
    """
    if not _IMPORT_OK:
        return []
    try:
        # Asked of Vision directly rather than through ocrmac, which exposes no
        # such helper -- ocrmac.OCR.supported_languages() does not exist in
        # 1.0.1 and raised AttributeError into a bare `except`, so this
        # returned [] on every call while appearing to have consulted the OS.
        from Vision import VNRecognizeTextRequest

        request = VNRecognizeTextRequest.alloc().init()
        languages, error = request.supportedRecognitionLanguagesAndReturnError_(None)
        if error is not None:
            return []
        return list(languages)
    except Exception:
        # PyObjC missing, or Apple moved the selector. An empty list is the
        # honest answer to "which languages does this build support" when we
        # cannot ask, and it keeps `backends` from failing over a diagnostic.
        return []


def ocr_image(
    path: Path,
    *,
    languages: list[str] | None = None,
    recognition_level: str = DEFAULT_RECOGNITION_LEVEL,
) -> str:
    """Extract text from an image using Apple's Vision framework.

    Recognised regions are returned in reading order, one per line, matching
    what the other backends emit so the accuracy metrics compare like with
    like.

    Args:
        path: Path to the image file.
        languages: Vision language codes to prefer, e.g. ``["en-GB"]``. When
            omitted Vision decides. Naming a language is usually worth it on
            archival material, because auto-detection on a page with little
            text can pick wrongly and the failure is silent.
        recognition_level: ``"accurate"`` (default) or ``"fast"``.

    Returns:
        Extracted text, one recognised region per line.

    Raises:
        RuntimeError: If Vision is not available on this machine.
        ValueError: If the file extension is not supported.
        FileNotFoundError: If the file does not exist.
        MultiPageNotSupportedError: If the file holds more than one page.
    """
    path = Path(path)

    if not _IMPORT_OK:
        # Reached only by importing this module directly; the registry raises
        # MissingBackendError first and names the extra. Kept so the direct
        # caller gets a reason rather than a NameError.
        reason = (
            f"Apple's Vision framework is macOS-only and this is {sys.platform}."
            if not _IS_MACOS
            else "the 'ocrmac' package is not installed."
        )
        raise RuntimeError(f"The 'vision' backend is unavailable: {reason}")

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{path.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Multi-page TIFF: this backend reads one image, so refuse rather than
    # return page one as though it were the document. Vision could in
    # principle be run per frame — see tetrak_ocr.imaging.iter_frames — but
    # that is a change to make once the single-page scores are known, not
    # before.
    reject_multi_page(path, "vision")

    # Hand Pillow's decoded image over rather than the path. Vision reads a
    # narrower set of TIFF variants than Pillow does, and the conversion is
    # the same one the EasyOCR backend makes for the same reason.
    with Image.open(path) as image:
        prepared = image.convert("RGB")
        # Captured inside the block: the boxes Vision returns are normalised,
        # and turning them back into pixels needs the size they were measured
        # against.
        width, height = prepared.size

        annotations = ocrmac.OCR(
            prepared,
            recognition_level=recognition_level,
            language_preference=languages,
        ).recognize()

    return _to_reading_order(annotations, width, height)


def to_spans(annotations: list, width: int, height: int) -> list[TextSpan]:
    """Convert Vision's annotations into the package's coordinate convention.

    Vision returns ``(text, confidence, bounding_box)`` per region, with the box
    as ``(x, y, w, h)`` **normalised to 0-1 with the origin at the bottom left**
    -- the opposite of every image convention in the rest of this package. So
    the topmost region is the one with the *largest* y, and sorting naively puts
    the document upside down. That is not hypothetical; it shipped once.

    The inversion happens here, at the boundary, and exactly once. Everything
    downstream sees pixels with a top-left origin like Pillow.
    """
    spans: list[TextSpan] = []
    for annotation in annotations:
        text = annotation[0]
        if not text:
            continue
        confidence = float(annotation[1]) * 100 if len(annotation) > 1 else None
        box = annotation[2] if len(annotation) > 2 else None
        if box is None:
            spans.append(TextSpan(text=text, bbox=None, confidence=confidence))
            continue
        x, y, w, h = (float(v) for v in box[:4])
        spans.append(
            TextSpan(
                text=text,
                # y is the *bottom* edge going up; 1 - (y + h) is the top edge
                # going down.
                bbox=(x * width, (1.0 - (y + h)) * height, (x + w) * width, (1.0 - y) * height),
                confidence=confidence,
            )
        )
    return spans


def _to_reading_order(annotations: list, width: int = 1, height: int = 1) -> str:
    """Join recognised regions top-to-bottom, then left-to-right.

    The ordering itself lives in :mod:`tetrak_ocr.layout` now, because the PDF
    writer needs the same rule -- the order text is emitted in *is* the order a
    screen reader announces it. Multi-column layouts are no better solved here
    than by the other single-pass backends; that is what `marker` is for.
    """
    # 1% of page height, the constant this backend arrived at by experiment on
    # its own material, passed explicitly rather than left to layout's adaptive
    # default. The default is finer, and on a dense multi-column page it splits
    # lines this backend has always merged -- a real change to a published
    # score, which does not belong in a refactor. Revisit it as a measured
    # change if it is worth making.
    return to_text(to_spans(annotations, width, height), line_tolerance=0.01 * height)
