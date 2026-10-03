#!/usr/bin/env python3
"""Evaluate OCR accuracy against the corpus ground truth.

For each corpus image that has a matching transcript in
evaluation/ocr/corpus/expected/, this runs OCR and prints a summary table of
similarity scores. Use it to compare backends or tune Tesseract preprocessing
settings.

Usage:
    # Single backend (default: tesseract)
    tetrak-ocr evaluate
    tetrak-ocr evaluate --backend easyocr
    tetrak-ocr evaluate --backend tesseract --contrast 3.0 --psm 6
    tetrak-ocr evaluate --backend tesseract --auto

    # Compare all available backends side by side
    tetrak-ocr evaluate --all

    # Save results to evaluation/ as CSV and Markdown
    tetrak-ocr evaluate --all --save
    tetrak-ocr evaluate --backend marker --save

Ground-truth transcripts live at:
    evaluation/ocr/corpus/expected/<image-stem>.md

Saved files land at:
    evaluation/ocr/benchmark.csv                (--all)
    evaluation/ocr/benchmark.md                 (--all)
    evaluation/ocr/benchmark_<backend>.csv      (single backend)
    evaluation/ocr/benchmark_<backend>.md       (single backend)
    evaluation/ocr/runs/<timestamp>_<sha>*.{csv,md}   (versioned, with --save)
"""

import argparse
import csv
import subprocess
import time
from datetime import datetime
from pathlib import Path

from tetrak_ocr.accuracy import character_similarity, word_recall
from tetrak_ocr.backends.tesseract import DEFAULT_CONTRAST, DEFAULT_PSM, SUPPORTED_EXTENSIONS
from tetrak_ocr.registry import BACKENDS, get_backend
from tetrak_ocr.registry import available as registry_available

EVAL_DIR = Path(__file__).resolve().parent
# evaluation/ocr/ -> evaluation/ -> the repository root. Two levels, not one:
# `_display_path` printed "ocr/benchmark.csv" for a file that is actually at
# "evaluation/ocr/benchmark.csv", because this pointed at evaluation/.
REPO_ROOT = EVAL_DIR.parent.parent

# The corpus lives beside this harness: images plus a ground-truth
# transcript per image. Keeping them together means an evaluation run is
# self-contained rather than reaching into the test directory.
CORPUS_DIR = EVAL_DIR / "corpus"
FIXTURES_DIR = CORPUS_DIR / "images"
EXPECTED_DIR = CORPUS_DIR / "expected"


def available_pairs() -> list[tuple[Path, Path]]:
    """Return (image_path, expected_path) for each fixture with an expected file."""
    return sorted(
        (img, EXPECTED_DIR / f"{img.stem}.md")
        for img in FIXTURES_DIR.iterdir()
        if img.is_file()
        and img.suffix.lower() in SUPPORTED_EXTENSIONS
        and (EXPECTED_DIR / f"{img.stem}.md").exists()
    )


def _run_backend(
    backend: str, image_path: Path, contrast: float, psm: int, auto: bool
) -> tuple[str, float]:
    """Run the named backend on one image; return (text, wall-clock seconds).

    Resolution goes through the registry rather than an if/elif chain of
    imports, so a backend whose extra is not installed reports which extra to
    install instead of raising ImportError from inside the loop.

    The timing is wall clock and includes whatever the backend does lazily on
    its first call -- loading model weights, in particular. That is the honest
    number for "how long did this file take", but it means the first fixture a
    heavy backend sees is much slower than the rest. Compare backends on their
    totals over the corpus, not on a single row.
    """
    ocr = get_backend(backend)
    started = time.perf_counter()
    if backend == "tesseract":
        text = ocr(image_path, contrast=contrast, psm=psm, auto=auto)
    else:
        text = ocr(image_path)
    return text, time.perf_counter() - started


def collect_single(
    pairs: list[tuple[Path, Path]],
    backend: str,
    contrast: float,
    psm: int,
    auto: bool,
) -> list[tuple[str, float, float, float]]:
    """Run one backend against all fixtures.

    Returns (filename, char_sim, word_recall, seconds).
    """
    rows = []
    for image_path, expected_path in pairs:
        actual, seconds = _run_backend(backend, image_path, contrast, psm, auto)
        expected = expected_path.read_text(encoding="utf-8")
        rows.append(
            (
                image_path.name,
                character_similarity(actual, expected),
                word_recall(actual, expected),
                seconds,
            )
        )
    return rows


def _collect_all(
    pairs: list[tuple[Path, Path]],
    available: list[str],
) -> dict[str, list[tuple[float, float, float] | None]]:
    """Run all backends against all fixtures.

    Returns {backend: [(char_sim, word_recall, seconds)]}, with None for a
    fixture the backend failed on.
    """
    results: dict[str, list[tuple[float, float, float] | None]] = {}
    for backend in available:
        print(f"  Running {backend}...", end=" ", flush=True)
        scores = []
        for image_path, expected_path in pairs:
            try:
                actual, seconds = _run_backend(
                    backend, image_path, DEFAULT_CONTRAST, DEFAULT_PSM, False
                )
            except Exception as exc:
                print(f"\n    Warning: {backend} failed on {image_path.name}: {exc}")
                scores.append(None)
                continue
            expected = expected_path.read_text(encoding="utf-8")
            scores.append(
                (
                    character_similarity(actual, expected),
                    word_recall(actual, expected),
                    seconds,
                )
            )
        results[backend] = scores
        print("done")
    return results


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------


def _print_single(
    backend: str,
    contrast: float,
    psm: int,
    rows: list[tuple[str, float, float, float]],
) -> None:
    col = 42
    header = f"{'Image':<{col}}  {'Char Sim':>8}  {'Word Recall':>11}  {'Seconds':>8}"
    rule = "-" * len(header)

    label = backend
    if backend == "tesseract":
        label += f"  (contrast={contrast}, psm={psm})"
    elif backend == "tesseract-auto":
        label += "  (auto-configured)"

    print(f"\nOCR Accuracy Evaluation — {len(rows)} image(s)")
    print(f"\nBackend: {label}")
    print(header)
    print(rule)

    for name, sim, recall, seconds in rows:
        display = name if len(name) <= col else name[: col - 1] + "…"
        print(f"{display:<{col}}  {sim:>8.3f}  {recall:>11.3f}  {seconds:>8.2f}")

    print(rule)
    n = len(rows)
    print(
        f"{'Average':<{col}}  {sum(r[1] for r in rows) / n:>8.3f}  "
        f"{sum(r[2] for r in rows) / n:>11.3f}  {sum(r[3] for r in rows):>8.2f}"
    )
    print()


def _print_comparison(
    pairs: list[tuple[Path, Path]],
    results: dict[str, list[tuple[float, float, float] | None]],
    available: list[str],
) -> None:
    img_col = 30
    score_w = 13
    header = f"{'Image':<{img_col}}"
    for b in available:
        header += f"  {b[:score_w]:>{score_w}}"
    print(header)
    print("-" * len(header))

    sub = " " * img_col
    for _ in available:
        sub += f"  {'chr / wrd':>{score_w}}"
    print(sub)
    print("-" * len(header))

    totals: dict[str, list[float]] = {b: [0.0, 0.0, 0.0] for b in available}
    counts: dict[str, int] = {b: 0 for b in available}
    for i, (image_path, _) in enumerate(pairs):
        name = image_path.name
        if len(name) > img_col:
            name = name[: img_col - 1] + "…"
        row = f"{name:<{img_col}}"
        for b in available:
            entry = results[b][i]
            if entry is None:
                cell = "N/A"
            else:
                sim, rec, sec = entry
                totals[b][0] += sim
                totals[b][1] += rec
                totals[b][2] += sec
                counts[b] += 1
                cell = f"{sim:.2f}/{rec:.2f}"
            row += f"  {cell:>{score_w}}"
        print(row)

    print("-" * len(header))
    avg_row = f"{'Average':<{img_col}}"
    for b in available:
        n = counts[b]
        cell = f"{totals[b][0] / n:.2f}/{totals[b][1] / n:.2f}" if n else "N/A"
        avg_row += f"  {cell:>{score_w}}"
    print(avg_row)

    # Time is a total, not an average: the useful comparison is "what does a
    # full pass cost with this backend". Kept on its own row so the score grid
    # above stays narrow enough to read.
    time_row = f"{'Total seconds':<{img_col}}"
    for b in available:
        cell = f"{totals[b][2]:.1f}" if counts[b] else "N/A"
        time_row += f"  {cell:>{score_w}}"
    print(time_row)
    print()


# ---------------------------------------------------------------------------
# File output
# ---------------------------------------------------------------------------


def _git_info() -> tuple[str, str]:
    """Return (short_hash, timestamp_slug) for the current HEAD."""
    try:
        short_hash = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=True,
        ).stdout.strip()
    except Exception:
        short_hash = "unknown"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return short_hash, timestamp


def _write_single_csv(
    path: Path, backend: str, rows: list[tuple[str, float, float, float]]
) -> None:
    n = len(rows)
    avg_sim = sum(r[1] for r in rows) / n
    avg_rec = sum(r[2] for r in rows) / n
    total_sec = sum(r[3] for r in rows)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fixture", "char_sim", "word_recall", "seconds"])
        for name, sim, rec, sec in rows:
            w.writerow([name, f"{sim:.4f}", f"{rec:.4f}", f"{sec:.2f}"])
        # The seconds column totals rather than averages: "how long does this
        # backend take over the corpus" is the question people actually ask.
        w.writerow(["Average", f"{avg_sim:.4f}", f"{avg_rec:.4f}", f"{total_sec:.2f}"])


def _write_single_md(
    path: Path,
    backend: str,
    rows: list[tuple[str, float, float, float]],
    meta: str = "",
) -> None:
    n = len(rows)
    avg_sim = sum(r[1] for r in rows) / n
    avg_rec = sum(r[2] for r in rows) / n
    total_sec = sum(r[3] for r in rows)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# OCR Accuracy — {backend}\n\n")
        if meta:
            f.write(meta + "\n\n")
        f.write("Scores against Claude-generated ground truth (`claude-opus-4-8`).\n\n")
        f.write("| Fixture | Char Sim | Word Recall | Seconds |\n")
        f.write("|---|---:|---:|---:|\n")
        for name, sim, rec, sec in rows:
            f.write(f"| {name} | {sim:.3f} | {rec:.3f} | {sec:.2f} |\n")
        f.write(
            f"| **Average** | **{avg_sim:.3f}** | **{avg_rec:.3f}** | **{total_sec:.2f} total** |\n"
        )


def _display_path(path: Path) -> str:
    """Path relative to the repository root, falling back to the full path.

    `Path.relative_to` raises for anything outside the repository. That is only
    ever used to make a progress message tidier, so it must not be able to
    abort a save that has already written its files -- an hour of benchmark
    work should not be lost to a cosmetic string.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _save_single(
    output_dir: Path,
    backend: str,
    rows: list[tuple[str, float, float, float]],
    run_id: tuple[str, str] | None = None,
) -> None:
    """Write single-backend results to CSV and Markdown in output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = backend.replace("-", "_")

    csv_path = output_dir / f"benchmark_{slug}.csv"
    _write_single_csv(csv_path, backend, rows)
    md_path = output_dir / f"benchmark_{slug}.md"
    _write_single_md(md_path, backend, rows)
    print(f"Saved: {_display_path(csv_path)}")
    print(f"Saved: {_display_path(md_path)}")

    if run_id:
        runs_dir = output_dir / "runs"
        runs_dir.mkdir(exist_ok=True)
        short_hash, timestamp = run_id
        stem = f"{timestamp}_{short_hash}_{slug}"
        meta = f"**Date:** {timestamp[:10]}  \n**Git commit:** `{short_hash}`"
        v_csv = runs_dir / f"{stem}.csv"
        _write_single_csv(v_csv, backend, rows)
        v_md = runs_dir / f"{stem}.md"
        _write_single_md(v_md, backend, rows, meta=meta)
        print(f"Saved: {_display_path(v_csv)}")
        print(f"Saved: {_display_path(v_md)}")


def _write_comparison_csv(
    path: Path,
    pairs: list[tuple[Path, Path]],
    results: dict[str, list[tuple[float, float, float] | None]],
    available: list[str],
    totals: dict[str, list[float]],
    counts: dict[str, int],
) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # `_sec` is appended after the existing pair so column names stay
        # stable: the chart and presentation generators select by name.
        w.writerow(
            ["fixture"] + [col for b in available for col in (f"{b}_chr", f"{b}_wrd", f"{b}_sec")]
        )
        for i, (img, _) in enumerate(pairs):
            row = [img.name]
            for b in available:
                entry = results[b][i]
                row += (
                    ["N/A", "N/A", "N/A"]
                    if entry is None
                    else [f"{entry[0]:.4f}", f"{entry[1]:.4f}", f"{entry[2]:.2f}"]
                )
            w.writerow(row)
        avg_row = ["Average"]
        for b in available:
            nc = counts[b]
            avg_row += (
                [f"{totals[b][0] / nc:.4f}", f"{totals[b][1] / nc:.4f}", f"{totals[b][2]:.2f}"]
                if nc
                else ["N/A", "N/A", "N/A"]
            )
        w.writerow(avg_row)


def _merge_single_into_comparison(
    output_dir: Path,
    backend: str,
    rows: list[tuple[str, float, float, float]],
    pairs: list[tuple[Path, Path]],
    run_id: tuple[str, str] | None = None,
) -> None:
    """Splice one backend's column into the committed comparison table.

    Adding a backend does not require re-running every other one. A full
    `--all` pass costs hours and real API spend on `claude`, and re-measuring
    seven unchanged engines to publish an eighth is waste -- so a single
    backend can be measured on its own and merged here.

    The existing columns are read back and handed to the same writers
    `--all` uses, rather than this file learning a second way to format the
    table. That is the point: a bespoke splice would be a second definition
    of the CSV's shape, and the two would drift the first time a column was
    added.

    Refuses to merge across a changed corpus. Rows are matched by fixture
    name, and a fixture in one table and not the other means the two runs
    saw different material -- splicing that would align a score against the
    wrong image and look entirely plausible afterwards.
    """
    csv_path = output_dir / "benchmark.csv"
    if not csv_path.exists():
        raise SystemExit(
            f"{_display_path(csv_path)} does not exist -- run `evaluate --all --save` "
            f"first to create the comparison table this merges into."
        )

    with open(csv_path, newline="", encoding="utf-8") as f:
        existing = list(csv.reader(f))
    header, *body = existing
    prior = [c[: -len("_chr")] for c in header if c.endswith("_chr")]

    measured = {name: (sim, rec, sec) for name, sim, rec, sec in rows}
    fixtures = [r[0] for r in body if r[0] not in {"Average", "Total seconds"}]
    if set(fixtures) != set(measured):
        missing = ", ".join(sorted(set(fixtures) - set(measured))) or "none"
        extra = ", ".join(sorted(set(measured) - set(fixtures))) or "none"
        raise SystemExit(
            f"refusing to merge {backend}: the corpus does not match "
            f"{_display_path(csv_path)}. Missing from this run: {missing}. "
            f"Not in the table: {extra}. Re-run `evaluate --all --save`."
        )

    # Keep the registry's ordering so the new column lands in its natural
    # slot rather than after the strategies, and so the diff stays small.
    order = {name: i for i, name in enumerate(BACKENDS)}
    available = sorted(
        prior if backend in prior else [*prior, backend],
        key=lambda b: order.get(b, len(order)),
    )

    index = {name: i for i, name in enumerate(fixtures)}
    results: dict[str, list[tuple[float, float, float] | None]] = {}
    for b in available:
        if b == backend:
            results[b] = [measured[name] for name in fixtures]
            continue
        chr_i, wrd_i, sec_i = (header.index(f"{b}_{suffix}") for suffix in ("chr", "wrd", "sec"))
        column: list[tuple[float, float, float] | None] = []
        for name in fixtures:
            row = body[index[name]]
            column.append(
                None
                if row[chr_i] == "N/A"
                else (float(row[chr_i]), float(row[wrd_i]), float(row[sec_i]))
            )
        results[b] = column

    # The Average row is carried forward for every backend except the one
    # being merged, rather than recomputed.
    #
    # Recomputing looks harmless and is not: the per-fixture cells in the CSV
    # are already rounded to four and two places, so summing them back up
    # lands a hair away from the original full-precision total. Five `_sec`
    # averages shifted by 0.01 that way on the first real merge -- published
    # figures moving for engines nobody re-ran, which is exactly what this
    # whole file exists to prevent.
    #
    # The writer divides totals by counts, so seeding the total as
    # `stored x count` reproduces the stored value through its arithmetic.
    # Seconds are written as the total itself, so that one is seeded
    # directly.
    summary = next(r for r in body if r[0] == "Average")
    totals: dict[str, list[float]] = {b: [0.0, 0.0, 0.0] for b in available}
    counts: dict[str, int] = {b: 0 for b in available}
    for b in available:
        if b != backend and f"{b}_chr" in header:
            stored = [summary[header.index(f"{b}_{s}")] for s in ("chr", "wrd", "sec")]
            if "N/A" not in stored:
                n = sum(1 for entry in results[b] if entry is not None)
                counts[b] = n
                totals[b] = [float(stored[0]) * n, float(stored[1]) * n, float(stored[2])]
                continue
        for entry in results[b]:
            if entry is not None:
                totals[b][0] += entry[0]
                totals[b][1] += entry[1]
                totals[b][2] += entry[2]
                counts[b] += 1

    ordered_pairs = sorted(pairs, key=lambda pair: index[pair[0].name])
    _write_comparison_csv(csv_path, ordered_pairs, results, available, totals, counts)
    md_path = output_dir / "benchmark.md"
    _write_comparison_md(md_path, ordered_pairs, results, available, totals, counts)
    verb = "replaced" if backend in prior else "added"
    print(f"Merged: {backend} {verb} in {_display_path(csv_path)}")
    print(f"Saved: {_display_path(md_path)}")

    if run_id:
        short_hash, timestamp = run_id
        runs_dir = output_dir / "runs"
        runs_dir.mkdir(exist_ok=True)
        stem = f"{timestamp}_{short_hash}_merge-{backend}"
        meta = (
            f"**Date:** {timestamp[:10]}  \n**Git commit:** `{short_hash}`  \n"
            f"**Merged:** `{backend}` measured on its own; every other column "
            f"carried over from the previous run"
        )
        _write_comparison_csv(
            runs_dir / f"{stem}.csv", ordered_pairs, results, available, totals, counts
        )
        _write_comparison_md(
            runs_dir / f"{stem}.md", ordered_pairs, results, available, totals, counts, meta=meta
        )
        print(f"Saved: {_display_path(runs_dir / f'{stem}.csv')}")


def _write_comparison_md(
    path: Path,
    pairs: list[tuple[Path, Path]],
    results: dict[str, list[tuple[float, float, float] | None]],
    available: list[str],
    totals: dict[str, list[float]],
    counts: dict[str, int],
    meta: str = "",
) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("# OCR Accuracy Benchmark\n\n")
        if meta:
            f.write(meta + "\n\n")
        f.write(
            "Scores: character similarity / word recall against Claude-generated ground truth (`claude-opus-4-8`).\n\n"
        )
        f.write("| Fixture |" + "".join(f" {b} |" for b in available) + "\n")
        f.write("|---|" + "---:|" * len(available) + "\n")
        for i, (img, _) in enumerate(pairs):
            row = f"| {img.name} |"
            for b in available:
                entry = results[b][i]
                row += " N/A |" if entry is None else f" {entry[0]:.2f}/{entry[1]:.2f} |"
            f.write(row + "\n")
        avg_row = "| **Average** |"
        for b in available:
            nc = counts[b]
            avg_row += (
                f" **{totals[b][0] / nc:.2f}/{totals[b][1] / nc:.2f}** |" if nc else " **N/A** |"
            )
        f.write(avg_row + "\n")
        # Total rather than average: the question is what a full pass costs.
        time_row = "| **Total seconds** |"
        for b in available:
            time_row += f" **{totals[b][2]:.1f}** |" if counts[b] else " **N/A** |"
        f.write(time_row + "\n")


def _save_comparison(
    output_dir: Path,
    pairs: list[tuple[Path, Path]],
    results: dict[str, list[tuple[float, float, float] | None]],
    available: list[str],
    run_id: tuple[str, str] | None = None,
) -> None:
    """Write all-backends comparison to CSV and Markdown in output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Three wide: character similarity, word recall, seconds. The seconds slot
    # is easy to forget here -- this accumulator is a duplicate of the one in
    # _print_all_comparison, and when timing was added only that copy and the
    # two writers were widened. Nothing failed until `--save` ran, an hour into
    # a full benchmark, with every backend's work already done and discarded.
    totals: dict[str, list[float]] = {b: [0.0, 0.0, 0.0] for b in available}
    counts: dict[str, int] = {b: 0 for b in available}
    for b in available:
        for entry in results[b]:
            if entry is not None:
                totals[b][0] += entry[0]
                totals[b][1] += entry[1]
                totals[b][2] += entry[2]
                counts[b] += 1

    # Latest — stable reference for docs
    csv_path = output_dir / "benchmark.csv"
    _write_comparison_csv(csv_path, pairs, results, available, totals, counts)
    md_path = output_dir / "benchmark.md"
    _write_comparison_md(md_path, pairs, results, available, totals, counts)
    print(f"Saved: {_display_path(csv_path)}")
    print(f"Saved: {_display_path(md_path)}")

    # Versioned run — dated and git-linked for longitudinal tracking
    if run_id:
        short_hash, timestamp = run_id
        runs_dir = output_dir / "runs"
        runs_dir.mkdir(exist_ok=True)
        stem = f"{timestamp}_{short_hash}"
        meta = f"**Date:** {timestamp[:10]}  \n**Git commit:** `{short_hash}`"
        v_csv = runs_dir / f"{stem}.csv"
        _write_comparison_csv(v_csv, pairs, results, available, totals, counts)
        v_md = runs_dir / f"{stem}.md"
        _write_comparison_md(v_md, pairs, results, available, totals, counts, meta=meta)
        print(f"Saved: {_display_path(v_csv)}")
        print(f"Saved: {_display_path(v_md)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate OCR accuracy against expected outputs.")
    parser.add_argument(
        "--backend",
        choices=BACKENDS,
        default="tesseract",
        help="OCR backend to evaluate (default: tesseract).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_backends",
        help="Compare all available backends side by side.",
    )
    parser.add_argument(
        "--contrast",
        type=float,
        default=DEFAULT_CONTRAST,
        help=f"Contrast factor for the Tesseract backend (default: {DEFAULT_CONTRAST}).",
    )
    parser.add_argument(
        "--psm",
        type=int,
        default=DEFAULT_PSM,
        help=f"Tesseract PSM mode (default: {DEFAULT_PSM}). "
        "3=auto, 6=uniform block, 11=sparse text.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Let Tesseract auto-configure contrast and PSM per image.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help=(
            "Save results to evaluation/ as CSV and Markdown. "
            "Writes evaluation/ocr/benchmark.{csv,md} (latest, stable reference) and "
            "evaluation/ocr/runs/YYYY-MM-DD_HHMMSS_<git-hash>.{csv,md} (versioned history). "
            "Single-backend runs write benchmark_<backend>.{csv,md} and a versioned equivalent."
        ),
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help=(
            "Single-backend runs only: also splice this backend's column into "
            "evaluation/ocr/benchmark.{csv,md}, carrying every other column over "
            "from the previous run. Adds a backend to the published table without "
            "re-measuring seven unchanged engines, which costs hours and real API "
            "spend on `claude`. Refuses if the corpus has changed since."
        ),
    )
    args = parser.parse_args(argv)

    # `args.all_backends`, not `args.all`: --all sets dest="all_backends".
    # This read `args.all` until 2026-09-27, which raised AttributeError on
    # *every* --merge run rather than only on the combination it guards
    # against -- so the merge path had never once run from the command line.
    if args.merge and args.all_backends:
        parser.error("--merge applies to a single --backend run, not --all")
    if args.merge and not args.save:
        parser.error("--merge needs --save")

    pairs = available_pairs()

    if not pairs:
        print(
            "No ground-truth transcripts found in evaluation/ocr/corpus/expected/\n"
            "Add a <name>.md for each image in evaluation/ocr/corpus/images/ to enable "
            "evaluation, or generate them with tools/generate_expected.py."
        )
        # Returned rather than raised: `cli.main` calls this and owes its own
        # caller an int, so a SystemExit escaping here would bypass it.
        return 0

    run_id = _git_info() if args.save else None

    if args.all_backends:
        print(f"\nOCR Accuracy Comparison — {len(pairs)} image(s)\n")
        print("Detecting available backends...")
        # Which backends this machine can actually run. The registry is the
        # single source of that truth — this used to probe __import__ by hand,
        # a third copy of the backend list that could drift from the other two.
        available = registry_available()
        skipped = [b for b in BACKENDS if b not in available]
        for name in skipped:
            print(f"  Skipping {name} (extra not installed)")
        print()
        results = _collect_all(pairs, available)
        print()
        _print_comparison(pairs, results, available)
        if args.save:
            _save_comparison(EVAL_DIR, pairs, results, available, run_id=run_id)
    else:
        rows = collect_single(pairs, args.backend, args.contrast, args.psm, args.auto)
        _print_single(args.backend, args.contrast, args.psm, rows)
        if args.save:
            _save_single(EVAL_DIR, args.backend, rows, run_id=run_id)
            if args.merge:
                _merge_single_into_comparison(EVAL_DIR, args.backend, rows, pairs, run_id=run_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
