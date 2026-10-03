#!/usr/bin/env python3
"""Generate web renditions of the corpus for the documentation site.

The corpus lives in evaluation/ocr/corpus/images/ and totals around 6 MB at full
resolution -- fine as OCR input, far too heavy to inline on a documentation
page, and outside assets/ where Hugo's pipeline cannot reach it. This writes two
renditions of each item into site/assets/images/corpus/, which the site does serve:

    <name>.webp         thumbnail, shown in the grid on the corpus page
    <name>-large.webp   opened in the lightbox when the thumbnail is clicked

Two sizes rather than one because the two jobs genuinely differ. The thumbnail
only has to show what kind of document an item *is* -- a poster, a newspaper
page, a postcard. The large rendition has to be legible enough to judge the OCR
difficulty being claimed for it, which is the whole argument of the evaluation
pages, and that needs the type readable.

The outputs are committed. Generating them at build time would mean CI needs
poppler installed before Hugo runs, for images that change roughly never;
committing them keeps the site build a pure Hugo step and lets GitHub render
the page too. The {{< lightbox >}} shortcode links the pair as-is rather than
putting them back through .Resize, so the sizes chosen here are the sizes
shipped.

Requirements:
    pip install -e '.[docs]'     # Pillow, pdf2image
    poppler installed            # brew install poppler / apt install poppler-utils

Usage:
    python tools/generate_corpus_thumbnails.py
    python tools/generate_corpus_thumbnails.py --width 800 --large-width 1800
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "evaluation" / "ocr" / "corpus" / "images"
# Written into the Hugo site, which lives in site/.
OUTPUT_DIR = REPO_ROOT / "site" / "assets" / "images" / "corpus"

# Wide enough to stay sharp on a high-density display at the ~350 px the corpus
# grid actually renders them at, small enough that the whole set is a few
# hundred kilobytes.
DEFAULT_WIDTH = 600

# The lightbox rendition. 1400 px matches the resolution the corpus itself was
# normalised to, so this is the source image rather than an upscale -- there is
# nothing to gain by going higher.
DEFAULT_LARGE_WIDTH = 1400

# WebP at this quality is visually indistinguishable from the source at
# thumbnail scale and roughly a fifth of the equivalent JPEG.
WEBP_QUALITY = 82

# The lightbox rendition carries slightly more, since the point of opening it
# is to read the type and judge the difficulty claim.
LARGE_WEBP_QUALITY = 88


def _load(path: Path) -> Image.Image:
    """Open an image, rendering the first page if the item is a PDF."""
    if path.suffix.lower() != ".pdf":
        # Closed explicitly rather than left to the garbage collector: Pillow
        # holds the file handle open until then, and `convert` returns a new
        # image that no longer needs it.
        with Image.open(path) as image:
            return image.convert("RGB")

    try:
        from pdf2image import convert_from_path
    except ImportError:  # pragma: no cover - depends on installed extras
        raise SystemExit(
            "Rendering the PDF item needs pdf2image and poppler.\n"
            "  pip install -e '.[docs]'  and  brew install poppler"
        ) from None

    # Only the first page: these renditions exist to show what the document is,
    # not to reproduce all 21 pages of it.
    #
    # 150 dpi rather than the 100 that would suffice for the thumbnail, because
    # the same render is downscaled twice and the lightbox copy needs the type
    # to hold up.
    pages = convert_from_path(path, dpi=150, first_page=1, last_page=1)
    if not pages:
        raise SystemExit(f"No pages rendered from {path.name}")
    return pages[0].convert("RGB")


def _write(image: Image.Image, out: Path, width: int, quality: int) -> int:
    """Downscale a copy to `width` and save it, returning the size in bytes."""
    if image.width > width:
        height = round(image.height * width / image.width)
        image = image.resize((width, height), Image.LANCZOS)

    image.save(out, "WEBP", quality=quality, method=6)
    return out.stat().st_size


def build(path: Path, width: int, large_width: int) -> tuple[int, int]:
    """Write both renditions of one item, returning their sizes in bytes."""
    # Loaded once -- rendering the PDF page is the slow part, and both
    # renditions come from the same source.
    image = _load(path)

    thumb = _write(image, OUTPUT_DIR / f"{path.stem}.webp", width, WEBP_QUALITY)
    large = _write(image, OUTPUT_DIR / f"{path.stem}-large.webp", large_width, LARGE_WEBP_QUALITY)
    return thumb, large


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        metavar="PX",
        help=f"Thumbnail width in pixels (default: {DEFAULT_WIDTH}).",
    )
    parser.add_argument(
        "--large-width",
        type=int,
        default=DEFAULT_LARGE_WIDTH,
        metavar="PX",
        help=f"Lightbox rendition width in pixels (default: {DEFAULT_LARGE_WIDTH}).",
    )
    args = parser.parse_args(argv)

    if not CORPUS_DIR.is_dir():
        print(f"Corpus not found at {CORPUS_DIR}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    items = sorted(f for f in CORPUS_DIR.iterdir() if f.is_file() and not f.name.startswith("."))
    if not items:
        print(f"No corpus items in {CORPUS_DIR}", file=sys.stderr)
        return 1

    total = 0
    for item in items:
        thumb, large = build(item, args.width, args.large_width)
        total += thumb + large
        print(f"  {item.name:38} {thumb / 1024:6.0f} KB thumb  {large / 1024:6.0f} KB large")

    print(
        f"\n{len(items)} items, {len(items) * 2} files, "
        f"{total / 1024:.0f} KB total, in {OUTPUT_DIR}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
