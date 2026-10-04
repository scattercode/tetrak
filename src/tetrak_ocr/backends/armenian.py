#!/usr/bin/env python3
"""OCR Armenian text with the project's own EasyOCR recognition model.

Stock EasyOCR does not read Armenian: it scores 0.03 word recall on the
evaluation pages, which is a polite way of saying it reads nothing. This
backend swaps in `tetrak_hy`, a recogniser trained for the script by
`tetrak-hy-trainer` and published as the `tetrak-easyocr-armenian`
package. Detection is untouched -- EasyOCR's CRAFT detector already finds
Armenian text; reading it was the missing half.

Registered as `easyocr-hy` rather than folded into the `easyocr` backend,
for the same reason `tesseract-auto` is its own name: the harness scores
backends, so the difference between stock EasyOCR and this one is a
measurement rather than a claim.

Two things happen to the recogniser's output here, and both matter more
than they look:

**The homoglyph fold.** The recognition head has no language model, so
inside an Armenian word it sometimes emits the visually identical Latin
twin of an Armenian character -- `h` for `հ`, a colon for the Armenian
full stop `։`. `tetrak_hy.fold_script` folds those back within any token
that already holds an Armenian letter. It is worth about +0.035 word
recall and costs one function call.

**The word list.** Where the installed `tetrak-easyocr-armenian` has
released one, `tetrak_hy.lexicon` corrects out-of-vocabulary words from
the recogniser's own n-best readings (brief 013: 465 words fixed, 13
broken on the held-out registers; mean word recall +0.012). It needs the
recogniser's probabilities, which EasyOCR hands over only to its
beam-search hook, so `readtext` is then called with
`decoder="beamsearch"`. Without a released list, decoding stays greedy.

**Reading order.** The pages this exists for are set in two columns, and
joining detected regions in detector order interleaves them. That is
invisible to word recall and ruinous to character similarity -- the same
text in the wrong order scores 0.12 against 0.70. Output is therefore
serialised through `tetrak_ocr.layout`, which reads each column to its
foot before starting the next. Not a midline split: that mishandles
running headers, and measurably hurt two of the ten evaluation pages when
it was tried.

Requires:
    pip install "tetrak[armenian]"

The recogniser's weights (~15 MB) download on first use from the Hugging
Face model repository, pinned to one immutable revision per release and
checksum-verified; EasyOCR's own detector weights (~80 MB) download
alongside them. Both are cached and reused.

Usage (standalone):
    tetrak-ocr ocr workspace/scans/page.jpg --backend easyocr-hy

PDF support is not included; convert PDFs to images first.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from ..imaging import reject_multi_page
from ..layout import TextSpan, to_text

try:
    import tetrak_hy
except ImportError:  # pragma: no cover - depends on installed extras
    _IMPORT_OK = False
else:
    _IMPORT_OK = True

# File extensions this backend can handle. PDFs are not supported
# natively; convert pages to images first. Same set as the stock EasyOCR
# backend, because it is the same detector and the same loader.
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# Module-level reader singleton. Constructing it loads the recognition and
# detection weights (~300 MB resident), so it is built once and reused for
# the process lifetime: the first call is slow, the rest are not. Same
# pattern as the easyocr, paddle and marker backends.
_reader = None
_decoder = "greedy"


def _get_reader():
    """Return (and lazily build) the module-level Armenian reader.

    `tetrak_hy.reader()` hides the custom-network plumbing EasyOCR needs --
    including that the language list must be `["en"]` and never `["hy"]`,
    since EasyOCR ships no Armenian character file and the setting is inert
    for a custom model anyway. That quirk is the library's to hide, not
    this backend's to repeat.
    """
    global _reader, _decoder
    if _reader is None:
        try:
            _reader = tetrak_hy.reader(verbose=False, lexicon=True)
            _decoder = "beamsearch"
        except (TypeError, tetrak_hy.WeightsNotAvailableError):
            # An older library with no word list support, or one that has
            # released no list yet: read greedily, as before.
            _reader = tetrak_hy.reader(verbose=False)
            _decoder = "greedy"
    return _reader


def _spans(results) -> list[TextSpan]:
    """Turn EasyOCR's detailed output into positioned, folded spans.

    EasyOCR gives each region as a four-point polygon; `TextSpan` wants an
    axis-aligned box, so the polygon's extent is taken. The fold is applied
    here, at the point the text enters the pipeline, so everything
    downstream sees Armenian rather than a mixture of scripts.
    """
    spans = []
    for box, text, confidence in results:
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        spans.append(
            TextSpan(
                text=tetrak_hy.fold_script(text),
                bbox=(min(xs), min(ys), max(xs), max(ys)),
                # EasyOCR reports 0-1; TextSpan documents 0-100.
                confidence=float(confidence) * 100,
            )
        )
    return spans


def ocr_image(path: Path) -> str:
    """Extract Armenian text from an image file.

    Regions are detected by CRAFT, read by the `tetrak_hy` recogniser,
    folded onto consistent Armenian script, and serialised in reading
    order -- column by column where the page has columns.

    TIFF files are converted to PNG in memory first, because EasyOCR can
    have trouble reading multi-strip TIFFs directly.

    Args:
        path: Path to the image file.

    Returns:
        The page's text, one recognised line per line of output.

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

    # Multi-page TIFF: this backend reads frame 0 only, so refuse rather
    # than return page one as though it were the document. See
    # tetrak_ocr.imaging.
    reject_multi_page(path, "easyocr-hy")

    if path.suffix.lower() in {".tif", ".tiff"}:
        import io

        buf = io.BytesIO()
        Image.open(path).convert("RGB").save(buf, format="PNG")
        image_input = buf.getvalue()
    else:
        image_input = str(path)

    reader = _get_reader()
    results = reader.readtext(image_input, detail=1, paragraph=False, decoder=_decoder)
    return to_text(_spans(results))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCR Armenian text in a single image file.")
    parser.add_argument("path", type=Path, help="Path to the image file.")
    args = parser.parse_args()

    print(ocr_image(args.path))
