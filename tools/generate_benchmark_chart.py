#!/usr/bin/env python3
"""Generate the backend comparison chart for the docs from the benchmark.

Reads `evaluation/ocr/benchmark.csv` -- the harness's own output -- and draws the
average character similarity and word recall for every backend. Nothing is
typed in by hand, so the chart cannot drift from the numbers it claims to
show. Re-run it after `tetrak-ocr evaluate --all --save`.

Two renditions are written, because the docs site follows the reader's colour
scheme and a white-background chart glares on a dark page:

    benchmark-comparison-light.png   used via #only-light
    benchmark-comparison-dark.png    used via #only-dark

Claude is drawn apart from the rest, hatched and greyed, behind a divider. It
generated the ground truth every backend is scored against, including its own,
so its bars are self-consistency rather than accuracy. A chart is the thing
that gets screenshotted into a slide deck without its caption, so that caveat
has to survive inside the image itself.

Requirements:
    pip install -e '.[docs]'

Usage:
    python tools/generate_benchmark_chart.py
    python tools/generate_benchmark_chart.py --dpi 200
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import tetrak_theme

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_CSV = REPO_ROOT / "evaluation" / "ocr" / "benchmark.csv"
# Written into the Hugo site, which lives in site/.
OUTPUT_DIR = REPO_ROOT / "site" / "assets" / "images" / "evaluation"

# Local backends in the order the benchmark table lists them, then the ceiling
# reference last. Names are the canonical backend identifiers -- the strings a
# reader types after `--backend` -- rather than prettified display names, since
# the point of the chart is to tell you which one to reach for.
LOCAL_BACKENDS = [
    "tesseract",
    "tesseract-auto",
    "easyocr",
    "paddle",
    "marker",
    "vision",
    "auto-local",
]
CEILING_BACKEND = "claude"

CEILING_NOTE = (
    "Ceiling reference, not a measurement.\n"
    "Claude generated the ground truth every\n"
    "backend is scored against, including its\n"
    "own, so this is self-consistency."
)

# The palette and the faces come from tetrak_theme, which is the one port of
# site/assets/scss/_tokens.scss into Python. The slide deck draws from the same
# module, so the chart and the deck cannot end up in different designs -- which
# is exactly what had happened before it existed.
#
# The role mapping is documented on tetrak_theme.chart_theme: character
# similarity takes an engine colour, word recall takes the accent, and the
# ceiling reference is set back in --ink-soft, exactly as the site's benchmark
# table sets back its claude column.
THEMES = {mode: tetrak_theme.chart_theme(mode) for mode in ("light", "dark")}

# The site sets prose in a serif and anything tabular in a mono, and the chart
# is drawn in the faces the page is actually set in rather than in a lookalike.
SERIF = tetrak_theme.BODY_STACK
DISPLAY = tetrak_theme.DISPLAY_STACK
MONO = tetrak_theme.MONO_STACK


def read_averages(path: Path) -> tuple[dict[str, tuple[float, float]], int]:
    """Average each backend's two metrics over the corpus.

    Recomputed from the per-fixture rows rather than read from the CSV's own
    Average row, so the chart agrees with the fixtures even if that row is ever
    stale. Backends that cannot read a fixture leave the cell blank or N/A and
    are averaged over what they did run -- the same convention the table uses.
    """
    # newline="" is the csv module's documented requirement and what the rest of
    # the repository already does; without it, a quoted field containing a line
    # break is split differently depending on the platform.
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [
            r for r in csv.DictReader(fh) if not r["fixture"].strip().lower().startswith("average")
        ]

    if not rows:
        raise SystemExit(f"No fixture rows found in {path}")

    averages: dict[str, tuple[float, float]] = {}
    for backend in [*LOCAL_BACKENDS, CEILING_BACKEND]:
        # A backend the benchmark does not cover is skipped rather than fatal.
        # The CSV reflects whatever was installed on the machine that produced
        # it, so a newly added backend has no column until someone re-runs the
        # evaluation -- the chart should still draw in the meantime.
        pair = []
        for metric in ("chr", "wrd"):
            values = [
                float(r[f"{backend}_{metric}"])
                for r in rows
                if r.get(f"{backend}_{metric}", "").strip() not in ("", "N/A")
            ]
            if not values:
                break
            pair.append(sum(values) / len(values))
        if len(pair) == 2:
            averages[backend] = (pair[0], pair[1])

    if CEILING_BACKEND not in averages:
        raise SystemExit(f"No scores for {CEILING_BACKEND} in {path}")

    return averages, len(rows)


def draw(averages: dict[str, tuple[float, float]], fixtures: int, theme: str, out: Path, dpi: int):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    c = THEMES[theme]
    locals_present = [b for b in LOCAL_BACKENDS if b in averages]
    names = [*locals_present, CEILING_BACKEND]
    width = 0.38

    # Every annotation is placed relative to the tallest bar rather than at a
    # fixed height. Hard-coding positions to today's numbers would mean a future
    # benchmark with higher scores silently pushes bars underneath the note --
    # which is exactly the drift this script exists to prevent.
    bar_top = max(v for pair in averages.values() for v in pair)
    label_top = bar_top + 0.045  # clears the value labels above each bar
    note_bottom = label_top + 0.04
    note_top = note_bottom + 0.215  # four lines at this font size
    header_y = note_top + 0.03
    y_limit = header_y + 0.09

    # Serif for prose, mono for anything numeric -- the split the site itself
    # uses, and the reason the value labels and axis ticks read as tabular.
    tetrak_theme.register_matplotlib_fonts()
    plt.rcParams["font.serif"] = SERIF
    plt.rcParams["font.monospace"] = MONO
    plt.rcParams["font.family"] = "serif"

    fig, ax = plt.subplots(figsize=(12.5, 7), dpi=dpi)
    fig.patch.set_facecolor(c["ground"])
    ax.set_facecolor(c["ground"])

    for i, name in enumerate(names):
        chr_v, wrd_v = averages[name]
        ceiling = name == CEILING_BACKEND
        for offset, value, colour in (
            (-width / 2, chr_v, c["chr"]),
            (width / 2, wrd_v, c["wrd"]),
        ):
            # The ceiling bars are drawn hollow and hatched rather than filled.
            # Colour alone would make Claude look like one more measurement in a
            # different shade; a bar that is visibly not solid says "different
            # kind of thing" before anyone reads the note explaining why.
            ax.bar(
                i + offset,
                value,
                width,
                facecolor=c["ground"] if ceiling else colour,
                edgecolor=c["ceiling"] if ceiling else "none",
                hatch="////" if ceiling else None,
                linewidth=1.0,
                zorder=3,
            )
            ax.text(
                i + offset,
                value + 0.018,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=10,
                family="monospace",
                color=c["ink_soft"] if ceiling else c["ink"],
                zorder=4,
            )

    # The divider is the argument: everything left of it is a measurement,
    # everything right of it is not. Both it and its label are skipped when
    # there are no local backends to separate -- possible now that missing
    # backends are tolerated, and it would otherwise draw the rule at -0.5 and
    # push the label off the canvas.
    if locals_present:
        split = len(locals_present) - 0.5
        ax.axvline(split, color=c["grid"], linestyle="-", linewidth=1.2, zorder=2)
        ax.text(
            split / 2,
            header_y,
            "LOCAL BACKENDS — MEASURED",
            ha="center",
            fontsize=9,
            family="monospace",
            color=c["accent"],
        )
    ax.text(
        len(names) - 1,
        header_y,
        "CEILING REF",
        ha="center",
        fontsize=9,
        family="monospace",
        color=c["accent"],
    )
    # Sits above every bar and its label, so it cannot cover the data whatever
    # the scores turn out to be.
    ax.text(
        1.55,
        note_bottom,
        CEILING_NOTE,
        ha="left",
        va="bottom",
        fontsize=9.5,
        color=c["ink_soft"],
        zorder=5,
    )

    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, fontsize=11, family="monospace", color=c["ink"])
    ax.set_ylim(0, y_limit)
    # Ticks stop at 1.0: the metrics are bounded there, and the headroom above
    # is annotation space rather than chart space.
    ax.set_yticks([i / 10 for i in range(0, 11, 2)])
    ax.set_ylabel("Average score over the corpus (0–1)", fontsize=11, color=c["ink"])
    ax.set_xlabel("Backend", fontsize=11, color=c["ink_soft"], labelpad=10)
    ax.set_title(
        "No local backend wins outright — routing per file beats picking one",
        fontsize=15,
        fontfamily=DISPLAY,
        fontweight="bold",
        color=c["ink"],
        pad=38,
    )

    ax.tick_params(colors=c["ink_soft"])
    ax.grid(axis="y", color=c["grid"], linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(c["grid"])

    ax.legend(
        handles=[
            Patch(facecolor=c["chr"], label="Character similarity — order-sensitive"),
            Patch(facecolor=c["wrd"], label="Word recall — order-insensitive"),
            Patch(
                facecolor=c["ground"],
                hatch="////",
                edgecolor=c["ceiling"],
                label="Ceiling reference — not a measurement",
            ),
        ],
        loc="upper left",
        fontsize=10,
        frameon=False,
        labelcolor=c["ink"],
    )

    fig.text(
        0.5,
        0.015,
        f"Generated from evaluation/ocr/benchmark.csv — {fixtures} fixtures. "
        "Regenerate with tools/generate_benchmark_chart.py",
        ha="center",
        fontsize=8.5,
        family="monospace",
        color=c["ink_soft"],
    )

    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(out, facecolor=c["ground"])
    plt.close(fig)
    return out.stat().st_size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dpi", type=int, default=140, help="Output resolution (default: 140).")
    parser.add_argument(
        "--output-dir", type=Path, default=OUTPUT_DIR, help="Where to write the PNGs."
    )
    args = parser.parse_args(argv)

    if not BENCHMARK_CSV.is_file():
        print(f"Benchmark not found at {BENCHMARK_CSV}", file=sys.stderr)
        print("Run `tetrak-ocr evaluate --all --save` first.", file=sys.stderr)
        return 1

    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print("This needs matplotlib:  pip install -e '.[docs]'", file=sys.stderr)
        return 1

    averages, fixtures = read_averages(BENCHMARK_CSV)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for theme in THEMES:
        out = args.output_dir / f"benchmark-comparison-{theme}.png"
        size = draw(averages, fixtures, theme, out, args.dpi)
        print(f"  {out.relative_to(REPO_ROOT)}  {size / 1024:.0f} KB")

    print(f"\n{len(averages)} backends over {fixtures} fixtures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
