#!/usr/bin/env python3
"""Score every (contrast, psm) pair against every raster fixture.

The band fitter needs to know what each fixture would have scored under each
configuration. That is a grid, and it is cheap enough to measure exhaustively --
about eight minutes for the whole corpus -- so nothing here is inferred.

Usage:
    python -m evaluation.ocr.calibration.sweep              # measure, print
    python -m evaluation.ocr.calibration.sweep --save       # write sweep.csv/.md
    python -m evaluation.ocr.calibration.sweep --fixture greek-theatre-night --save

Requires Tesseract. Reads the ground truth in `evaluation/ocr/corpus/expected/`
and reuses `harness.collect_single`, so a sweep cell is scored by exactly the
code path the published benchmark uses.

Two things this deliberately does not do:

- **It does not touch `evaluation/ocr/runs/`.** The product team's ledger
  generator globs that directory and builds a performance ledger from whatever
  it finds. A sweep is 42 configurations of one backend, not a benchmark run, and
  writing dated copies there would corrupt the ledger.
- **It does not sweep the PDF.** `[excluded]` in the corpus manifest says why:
  the bands never run on the PDF path, so those cells would measure nothing the
  fit can change, at roughly 25 minutes' cost.
"""

import argparse
import csv
import sys
import time
from pathlib import Path

from evaluation.ocr.calibration import splits
from evaluation.ocr.harness import EXPECTED_DIR, FIXTURES_DIR, collect_single

CALIBRATION_DIR = Path(__file__).resolve().parent
SWEEP_CSV = CALIBRATION_DIR / "sweep.csv"
SWEEP_MD = CALIBRATION_DIR / "sweep.md"

# 1.0 is in the grid because nothing has ever tested whether contrast
# enhancement helps at all. inside-facts-1930-page-six is the first evidence it
# may not: it loses 0.09 to the contrast band alone.
CONTRAST_GRID: tuple[float, ...] = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0)

# PSM 4 (single column of variable-size text) has never been tried on a raster
# here, and is the strongest a-priori candidate for the programme column beside
# the headline on kinema-theater-ad-1920. PSM 1 and 11 are included because the
# docstring claims they were tested and never won outright -- a claim with no
# recorded measurement behind it.
PSM_GRID: tuple[int, ...] = (1, 3, 4, 6, 11, 12)

FIELDNAMES = ("fixture", "contrast", "psm", "char_sim", "word_recall", "seconds")


def sweep_pairs() -> list[tuple[Path, Path]]:
    """Return (image, expected) for every fixture the bands can actually affect."""
    excluded = splits.excluded()
    return sorted(
        (image, EXPECTED_DIR / f"{image.stem}.md")
        for image in FIXTURES_DIR.iterdir()
        if image.is_file()
        and image.stem not in excluded
        and (EXPECTED_DIR / f"{image.stem}.md").exists()
    )


def one_pair(stem: str) -> tuple[Path, Path]:
    """Resolve a fixture stem (or path) to its (image, expected) pair.

    Raises:
        SystemExit: If no such fixture is swept, naming the ones that are.
    """
    stem = Path(stem).stem
    for image, expected in sweep_pairs():
        if image.stem == stem:
            return image, expected
    known = ", ".join(sorted(i.stem for i, _ in sweep_pairs()))
    raise SystemExit(f"{stem!r} is not a swept fixture. Swept fixtures are: {known}")


def splice(fresh: list[dict[str, object]], path: Path = SWEEP_CSV) -> list[dict[str, object]]:
    """Return the committed sweep with `fresh`'s fixtures re-measured.

    A corrected ground-truth transcript invalidates only its own fixture's
    cells, and re-measuring the whole corpus to refresh 42 of 672 costs ten
    minutes for nothing. Ground truth is reviewed and corrected by hand -- the
    Claude-generated transcripts are a starting point, not an answer -- so
    this is the common case, not an optimisation.

    Rows for any fixture in `fresh` are dropped and replaced; every other row
    is carried through untouched, and the result is sorted the way a full run
    writes it, so the diff shows only the fixture that moved.
    """
    replaced = {str(row["fixture"]) for row in fresh}
    kept = [row for row in read(path) if str(row["fixture"]) not in replaced]
    return sorted(
        kept + fresh,
        key=lambda row: (float(row["contrast"]), int(row["psm"]), str(row["fixture"])),  # type: ignore[arg-type]
    )


def run(pairs: list[tuple[Path, Path]] | None = None) -> list[dict[str, object]]:
    """Measure every grid cell. Returns one row per (fixture, contrast, psm)."""
    pairs = pairs if pairs is not None else sweep_pairs()
    if not pairs:
        raise SystemExit(f"No fixtures with ground truth in {FIXTURES_DIR}")

    cells = len(CONTRAST_GRID) * len(PSM_GRID)
    print(f"{len(pairs)} fixtures x {cells} configurations = {len(pairs) * cells} OCR runs")

    rows: list[dict[str, object]] = []
    started = time.perf_counter()
    for index, contrast in enumerate(CONTRAST_GRID, start=1):
        for psm in PSM_GRID:
            print(f"  [{index}/{len(CONTRAST_GRID)}] contrast {contrast}, psm {psm}...", flush=True)
            # auto=False: the whole point is to measure this exact cell, not to
            # let analyse_image() choose one.
            scored = collect_single(pairs, "tesseract", contrast, psm, auto=False)
            for name, char_sim, word_recall, seconds in scored:
                rows.append(
                    {
                        "fixture": name,
                        "contrast": contrast,
                        "psm": psm,
                        "char_sim": round(char_sim, 4),
                        "word_recall": round(word_recall, 4),
                        "seconds": round(seconds, 2),
                    }
                )
    print(f"Swept {len(rows)} cells in {time.perf_counter() - started:.0f}s")
    return rows


# Tie-break order for PSM, most preferred first. PSM 1 and PSM 3 score
# *identically* on all 56 (fixture, contrast) cells measured -- not similarly,
# identically -- so "which one won" is otherwise decided by whichever the
# iteration happened to reach first. That artefact is worth designing out: it
# reported PSM 1 as the winner on two fixtures on the first run of this script,
# which reads as a finding and is not one.
#
# PSM 3 leads because it needs no orientation-and-script-detection data, so it
# has one fewer dependency on Tesseract's training set for the same score.
PSM_PREFERENCE: tuple[int, ...] = (3, 6, 12, 11, 4, 1)

# Contrast ties break towards the default, on the same principle: prefer the
# setting that intervenes least when the measurement cannot tell them apart.
DEFAULT_CONTRAST = 2.0


def _tie_break(row: dict[str, object]) -> tuple[float, int, float]:
    """Sort key: score first, then the least surprising configuration."""
    psm = int(row["psm"])  # type: ignore[call-overload]
    rank = PSM_PREFERENCE.index(psm) if psm in PSM_PREFERENCE else len(PSM_PREFERENCE)
    return (
        -float(row["char_sim"]),  # type: ignore[arg-type]
        rank,
        abs(float(row["contrast"]) - DEFAULT_CONTRAST),  # type: ignore[arg-type]
    )


def best_per_fixture(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    """Return the best cell for each fixture, by character similarity.

    Ties are broken deterministically rather than by iteration order -- see
    `PSM_PREFERENCE`.
    """
    by_fixture: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_fixture.setdefault(str(row["fixture"]), []).append(row)
    return {fixture: min(rows_, key=_tie_break) for fixture, rows_ in by_fixture.items()}


def read(path: Path = SWEEP_CSV) -> list[dict[str, object]]:
    """Read a committed sweep back, with its numeric columns typed.

    The fitter reads the sweep rather than re-measuring it, which is what makes
    a re-fit seconds rather than minutes.
    """
    with path.open(encoding="utf-8") as handle:
        return [
            {
                "fixture": row["fixture"],
                "contrast": float(row["contrast"]),
                "psm": int(row["psm"]),
                "char_sim": float(row["char_sim"]),
                "word_recall": float(row["word_recall"]),
                "seconds": float(row["seconds"]),
            }
            for row in csv.DictReader(handle)
        ]


def write(rows: list[dict[str, object]]) -> None:
    """Write the sweep as CSV, and a Markdown summary beside it."""
    with SWEEP_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    best = best_per_fixture(rows)
    lines = [
        "# Configuration sweep",
        "",
        "Generated by `python -m evaluation.ocr.calibration.sweep --save`. Do not edit.",
        "",
        "Every `(contrast, psm)` pair scored against every raster fixture. This is",
        "the input the band fitter reads; the bands themselves live in",
        "`tetrak_ocr.backends.tuning`.",
        "",
        "## Best configuration per fixture",
        "",
        "The ceiling a perfect selector could reach. Character similarity, since",
        "word recall is set membership and blind to reading-order scrambling.",
        "",
        "PSM 1 and PSM 3 score identically on every cell measured, so ties break",
        "towards PSM 3 -- same score, one fewer dependency on Tesseract's",
        'orientation-detection data. Read a PSM here as "this family", not as a',
        "unique winner.",
        "",
        "| Fixture | contrast | psm | char_sim | word_recall |",
        "|---|---:|---:|---:|---:|",
    ]
    for fixture in sorted(best):
        row = best[fixture]
        lines.append(
            f"| `{fixture}` | {row['contrast']} | {row['psm']} | "
            f"{row['char_sim']:.4f} | {row['word_recall']:.4f} |"
        )
    lines.append("")
    SWEEP_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {SWEEP_CSV.name} and {SWEEP_MD.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", action="store_true", help="write sweep.csv and sweep.md")
    parser.add_argument(
        "--fixture",
        help=(
            "re-measure one fixture and splice it into the committed sweep, "
            "leaving every other fixture's cells untouched. Use after correcting "
            "a ground-truth transcript by hand"
        ),
    )
    parser.add_argument(
        "--rebuild-summary",
        action="store_true",
        help="rewrite sweep.md from the committed sweep.csv, without re-measuring",
    )
    args = parser.parse_args(argv)

    if args.rebuild_summary:
        rows = read(SWEEP_CSV)
    elif args.fixture:
        rows = splice(run([one_pair(args.fixture)]))
    else:
        rows = run()
    if not rows:
        print("Sweep produced no rows", file=sys.stderr)
        return 1

    best = best_per_fixture(rows)
    print(f"\n{'fixture':<40} {'best cell':>18} {'char_sim':>9}")
    for fixture in sorted(best):
        row = best[fixture]
        cell = f"c{row['contrast']} psm{row['psm']}"
        print(f"{fixture:<40} {cell:>18} {row['char_sim']:>9}")

    if args.save:
        write(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
