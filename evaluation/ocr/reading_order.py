#!/usr/bin/env python3
"""Score the column-aware reading order a positioned output would carry.

Brief 008 built a word-positioned text layer for the searchable PDF,
measured it and dropped it: on the two *Inside Facts* newsprint pages it
cost about 0.27 character similarity against the plain transcript, because
a layer laid down word by word reads back top to bottom across the page
and interleaves the columns. The figures are in the docstring of
:mod:`tetrak_ocr.pdf_output`. ALTO and hOCR are positioned by definition,
so before either is written the question is whether the column-aware pass
in :mod:`tetrak_ocr.layout` closes that gap. This harness answers it.

For every backend that carries spans and every raster fixture, the *same*
spans are serialised four ways and each is scored against the ground truth
in ``evaluation/ocr/corpus/expected/``:

    engine      the regions in the order the engine reported them -- the
                floor, and the only order a backend has without layout
    linesort    visual lines top to bottom and left to right, with no
                column awareness: what a word-positioned layer reads back
                as, and the construction brief 008 measured
    column      ``layout.reading_order`` -- recursive XY-cut, the pass a
                positioned writer would apply before emitting its regions
    transcript  what ``ocr_image`` returns today: the plain-text output.
                For ``vision`` that is already column-ordered and
                de-hyphenated; for ``easyocr`` and ``paddle`` it is engine
                order, so those two columns coincide

Two metrics, and the pairing is the point. Character similarity is
order-sensitive and is what reading order exists to move. Word recall is
order-insensitive and must be **identical** across the first three
serialisations, which emit the same tokens in a different sequence; a
column that moves it is losing or duplicating text, not reordering it. It
is printed beside every score as that tripwire. The transcript column may
differ by de-hyphenation, which puts words back.

Fixtures are the raster corpus: the three span-carrying backends read no
PDFs, so the newsprint PDFs cannot be measured here. The multi-column
fixtures are named in :data:`MULTI_COLUMN`; the rest are the control, where
a column-aware pass has nothing to find and must change nothing.

Usage:
    python -m evaluation.ocr.reading_order                 # measure, print
    python -m evaluation.ocr.reading_order --save          # write reading_order.{csv,md}
    python -m evaluation.ocr.reading_order --backend paddle --fixture kinema-theater-ad-1920

Writes ``evaluation/ocr/reading_order.csv``, which the site renders through
the ``{{< reading-order >}}`` shortcode, and a Markdown summary beside it.
It does not touch ``evaluation/ocr/runs/``: that directory is the
benchmark's versioned history and the product ledger is built from it.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections.abc import Callable
from pathlib import Path

from tetrak_ocr.accuracy import character_similarity, word_recall
from tetrak_ocr.layout import TextSpan, group_lines, reading_order, spans_of
from tetrak_ocr.registry import get_backend, is_available

from .harness import EVAL_DIR, available_pairs

RESULTS_CSV = EVAL_DIR / "reading_order.csv"
RESULTS_MD = EVAL_DIR / "reading_order.md"

# The backends whose ocr_image returns a Transcript carrying spans, and read
# the corpus's language. `easyocr-hy` carries spans too, but it is the
# Armenian recogniser and these fixtures are English: it would measure the
# ordering of text it cannot read.
SPAN_BACKENDS: tuple[str, ...] = ("vision", "easyocr", "paddle")

# The raster fixtures with more than one column of text, by inspection.
# Everything else in the raster corpus -- postcards, posters, the playbill,
# which is one centred column with dot-leader cast lists -- is the control.
MULTI_COLUMN: frozenset[str] = frozenset(
    {
        # Dense newsprint: a masthead over classified-style column blocks.
        "inside-facts-1930-cover",
        # The same issue's inside page: running columns of trade news.
        "inside-facts-1930-page-six",
        # A display ad: a narrow programme column in small type beside the
        # headline block, with prose fragments set around the illustration.
        "kinema-theater-ad-1920",
    }
)

STRATEGIES: dict[str, Callable[[list[TextSpan]], str]] = {
    "engine": lambda spans: "\n".join(span.text for span in spans),
    "linesort": lambda spans: "\n".join(
        " ".join(span.text for span in line) for line in group_lines(spans)
    ),
    "column": lambda spans: " ".join(span.text for span in reading_order(spans)),
}
# Scored alongside the three above, from the text rather than the spans.
TRANSCRIPT = "transcript"
COLUMNS: tuple[str, ...] = (*STRATEGIES, TRANSCRIPT)
LAYOUTS: tuple[str, ...] = ("multi-column", "single-column")
MEAN = "mean"

FIELDNAMES: tuple[str, ...] = (
    "fixture",
    "backend",
    "layout",
    *(f"{name}_{metric}" for name in COLUMNS for metric in ("chr", "wrd")),
)


def layout_of(stem: str) -> str:
    return "multi-column" if stem in MULTI_COLUMN else "single-column"


def raster_pairs() -> list[tuple[Path, Path]]:
    """Every corpus fixture the span-carrying backends can read: no PDFs."""
    return [(image, expected) for image, expected in available_pairs() if image.suffix != ".pdf"]


def score(spans: list[TextSpan], transcript: str, expected: str) -> dict[str, float]:
    """Both metrics for every serialisation of one page's spans."""
    texts = {name: strategy(spans) for name, strategy in STRATEGIES.items()}
    texts[TRANSCRIPT] = transcript
    scores: dict[str, float] = {}
    for name, text in texts.items():
        scores[f"{name}_chr"] = character_similarity(text, expected)
        scores[f"{name}_wrd"] = word_recall(text, expected)
    return scores


def measure(
    pairs: list[tuple[Path, Path]], backends: tuple[str, ...] | list[str]
) -> list[dict[str, object]]:
    """Run each backend over each fixture and score every serialisation."""
    rows: list[dict[str, object]] = []
    for backend in backends:
        if not is_available(backend):
            print(f"  {backend}: not installed, skipped", file=sys.stderr)
            continue
        ocr = get_backend(backend)
        for image, expected_path in pairs:
            print(f"  {backend:<8} {image.name}", end=" ", flush=True)
            transcript = ocr(image)
            spans = spans_of(transcript)
            if spans is None:
                print("-- no spans, skipped")
                continue
            expected = expected_path.read_text(encoding="utf-8")
            scores = score(spans, transcript, expected)
            print(f"column {scores['column_chr']:.3f} vs linesort {scores['linesort_chr']:.3f}")
            rows.append(
                {"fixture": image.stem, "backend": backend, "layout": layout_of(image.stem)}
                | scores
            )
    return rows


def with_means(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """*rows* with a mean row per backend and layout appended after its group.

    The means are computed here and written out, rather than left to the
    site to derive: the page then holds no arithmetic, only the CSV's cells.
    """
    out: list[dict[str, object]] = []
    for backend in dict.fromkeys(str(row["backend"]) for row in rows):
        for layout in LAYOUTS:
            group = [row for row in rows if row["backend"] == backend and row["layout"] == layout]
            if not group:
                continue
            out.extend(sorted(group, key=lambda row: str(row["fixture"])))
            out.append(
                {"fixture": MEAN, "backend": backend, "layout": layout}
                | {
                    key: statistics.fmean(float(row[key]) for row in group)
                    for key in FIELDNAMES[3:]
                }
            )
    return out


def _format(row: dict[str, object]) -> dict[str, str]:
    return {
        key: f"{value:.4f}" if isinstance(value, float) else str(value)
        for key, value in row.items()
    }


def write(rows: list[dict[str, object]], csv_path: Path, md_path: Path) -> None:
    """Write the table as CSV, and a Markdown summary beside it."""
    rows = with_means(rows)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(_format(row) for row in rows)

    def table(selected: list[dict[str, object]], first: str) -> list[str]:
        lines = [
            f"| {first} | " + " | ".join(COLUMNS) + " |",
            "|---|" + "---:|" * len(COLUMNS),
        ]
        for row in selected:
            label = str(row[first.lower()])
            label = f"*{label}, {row['layout']}*" if label == MEAN else f"`{label}`"
            cells = " | ".join(
                f"{float(row[f'{name}_chr']):.3f} / {float(row[f'{name}_wrd']):.3f}"
                for name in COLUMNS
            )
            lines.append(f"| {label} | {cells} |")
        return lines

    lines = [
        "# Reading order of positioned output",
        "",
        "Generated by `python -m evaluation.ocr.reading_order --save`. Do not edit.",
        "",
        "The same spans serialised four ways and scored against the ground",
        "truth: character similarity / word recall. `engine` is the order the",
        "engine reported, `linesort` is lines top to bottom with no column",
        "awareness (what a word-positioned layer reads back as), `column` is",
        "`layout.reading_order`, and `transcript` is what `ocr_image` returns.",
        "Word recall must not move between the first three.",
        "",
        "## Multi-column fixtures, mean per backend",
        "",
        *table(
            [row for row in rows if row["fixture"] == MEAN and row["layout"] == "multi-column"],
            "Backend",
        ),
    ]
    for backend in dict.fromkeys(str(row["backend"]) for row in rows):
        lines += [
            "",
            f"## {backend}",
            "",
            *table([row for row in rows if row["backend"] == backend], "Fixture"),
        ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print(rows: list[dict[str, object]]) -> None:
    for backend in dict.fromkeys(str(row["backend"]) for row in rows):
        print(f"\n{backend}")
        header = f"  {'fixture':<36}" + "".join(f"{name:>22}" for name in COLUMNS)
        print(header)
        print(f"  {'':<36}" + "".join(f"{'chr / wrd':>22}" for _ in COLUMNS))
        print("  " + "-" * (len(header) - 2))
        for row in with_means(rows):
            if row["backend"] != backend:
                continue
            label = str(row["fixture"])
            if label == MEAN:
                label = f"MEAN {row['layout']}"
            cells = "".join(
                f"{float(row[f'{name}_chr']):>12.4f} /{float(row[f'{name}_wrd']):>8.4f}"
                for name in COLUMNS
            )
            print(f"  {label:<36}{cells}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--save", action="store_true", help="write reading_order.csv and .md")
    parser.add_argument(
        "--backend", action="append", choices=SPAN_BACKENDS, help="only this backend; repeatable"
    )
    parser.add_argument("--fixture", action="append", help="only this fixture stem; repeatable")
    args = parser.parse_args(argv)

    if args.save and (args.backend or args.fixture):
        # A partial table would overwrite the full one and look complete.
        print("--save measures everything; drop --backend and --fixture", file=sys.stderr)
        return 2

    pairs = raster_pairs()
    if args.fixture:
        wanted = {Path(name).stem for name in args.fixture}
        pairs = [pair for pair in pairs if pair[0].stem in wanted]
        if not pairs:
            known = ", ".join(image.stem for image, _ in raster_pairs())
            print(f"no such raster fixture; known: {known}", file=sys.stderr)
            return 2

    rows = measure(pairs, args.backend or SPAN_BACKENDS)
    if not rows:
        print("nothing measured", file=sys.stderr)
        return 1
    _print(rows)
    if args.save:
        write(rows, RESULTS_CSV, RESULTS_MD)
        print(f"\nWrote {RESULTS_CSV.name} and {RESULTS_MD.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
