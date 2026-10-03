#!/usr/bin/env python3
"""Measure the pixel statistics the auto-configuration bands are fitted to.

The bands in `tetrak_ocr.backends.tuning` read two numbers per image: the
greyscale standard deviation, and `dark_pct`, the share of the frame below
luminance 128. This writes both for every corpus fixture, so the fitter and the
sweep read the same measured values rather than recomputing them and drifting.

It also records a third feature that nothing is fitted on yet -- see
`interior_gutters` below.

Usage:
    python -m evaluation.ocr.calibration.features            # print
    python -m evaluation.ocr.calibration.features --write    # write features.csv

Pillow only, about a second for the whole corpus. The PDF fixture is skipped:
the bands never run on the PDF path, so it has no features to fit to.
"""

import argparse
import csv
import sys
from pathlib import Path

from PIL import Image, ImageStat

CALIBRATION_DIR = Path(__file__).resolve().parent
CORPUS_DIR = CALIBRATION_DIR.parent / "corpus"
IMAGES_DIR = CORPUS_DIR / "images"
FEATURES_CSV = CALIBRATION_DIR / "features.csv"

# The bands only ever see rasters. _ocr_pdf() passes concrete values through
# and ignores auto entirely, so including the PDF would fit to material the
# result cannot affect.
RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}

FIELDNAMES = ("fixture", "stddev", "dark_pct", "interior_gutters", "width", "height")


def interior_gutters(grey: Image.Image, min_width_pct: float = 2.0) -> int:
    """Count vertical bands of clear paper that do not touch either edge.

    A page with a column beside a headline has at least one interior gutter; a
    photograph has none. That is the causally correct signal for the fixture
    the current bands get backwards -- `kinema-theater-ad-1920` is sent to
    PSM 6 ("no page structure") because a large illustration makes the frame
    42.9% dark, when the page does have structure.

    **Recorded, not fitted on.** Eight raster fixtures cannot support a third
    feature; fitting on one this thin is how the current bands came to be
    overfitted. It is here so the next phase opens with data rather than a
    hypothesis.

    The image is collapsed to a single row with a box filter, which averages
    each column over the full height. Columns brighter than the midpoint
    between the row's darkest and lightest values count as paper, and a run of
    them at least `min_width_pct` of the width wide counts as a gutter.

    Margins are excluded by construction: only runs with ink on *both* sides
    are counted, so the white border around a scan is never a gutter.
    """
    width = grey.width
    profile = list(grey.resize((width, 1), Image.BOX).getdata())
    if not profile:
        return 0

    darkest, lightest = min(profile), max(profile)
    if lightest - darkest < 8:  # a blank or near-uniform frame has no structure
        return 0
    threshold = (darkest + lightest) / 2
    min_run = max(1, int(width * min_width_pct / 100))

    gutters = 0
    run = 0
    seen_ink = False
    for value in profile:
        if value > threshold:
            run += 1
        else:
            # A run only counts once ink has been seen to its left, and this
            # column is the ink on its right.
            if seen_ink and run >= min_run:
                gutters += 1
            run = 0
            seen_ink = True
    return gutters


def measure(path: Path) -> dict[str, object]:
    """Return the feature row for one raster fixture."""
    with Image.open(path) as image:
        image.load()
        grey = image.convert("L")
        stddev = ImageStat.Stat(grey).stddev[0]
        histogram = grey.histogram()
        dark_pct = sum(histogram[:128]) / sum(histogram) * 100
        return {
            "fixture": path.name,
            "stddev": round(stddev, 4),
            "dark_pct": round(dark_pct, 4),
            "interior_gutters": interior_gutters(grey),
            "width": grey.width,
            "height": grey.height,
        }


def measure_corpus() -> list[dict[str, object]]:
    """Return feature rows for every raster fixture, sorted by name."""
    return [
        measure(path)
        for path in sorted(IMAGES_DIR.iterdir())
        if path.is_file() and path.suffix.lower() in RASTER_SUFFIXES
    ]


def write(rows: list[dict[str, object]], destination: Path = FEATURES_CSV) -> None:
    """Write the feature rows as CSV."""
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help=f"write {FEATURES_CSV.name}")
    args = parser.parse_args(argv)

    rows = measure_corpus()
    if not rows:
        print(f"No raster fixtures found in {IMAGES_DIR}", file=sys.stderr)
        return 1

    print(f"{'fixture':<40} {'stddev':>8} {'dark_pct':>9} {'gutters':>8}")
    for row in rows:
        print(
            f"{row['fixture']:<40} {row['stddev']:>8} {row['dark_pct']:>9} "
            f"{row['interior_gutters']:>8}"
        )

    if args.write:
        write(rows)
        print(f"\nWrote {FEATURES_CSV.relative_to(FEATURES_CSV.parents[3])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
