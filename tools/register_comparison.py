#!/usr/bin/env python3
"""One table per register: our model against every engine measured on it.

Brief 012 Stage 4. Until now every cross-engine number came from ten
pages of the Armenian Soviet Encyclopedia, so "ahead of every engine we
can measure" was an encyclopedia claim wearing a general one's clothes.
This assembles the per-register tables that either support the general
claim or replace it with a narrower true one.

Reported as separate tables rather than one average, deliberately and
for the reason the brief gives: an average would let a regression on the
new registers hide inside a gain on the old one. The registers differ in
kind, not merely in difficulty -- a bilingual dictionary defeats an
Armenian-only model in a way no amount of encyclopedia accuracy
predicts.

Two sources, because the two kinds of number are produced differently:

* **External engines** come from the CSVs
  ``tetrak-hy-trainer/scripts/evaluate_baselines.py`` writes into each
  evaluation set. They are read, never recomputed here.
* **Ours** is computed from the cached spans, through ``tetrak_hy.fold_script``
  and then ``layout.to_text`` -- the whole shipped serialisation, fold,
  XY-cut and de-hyphenation -- so the row says what a caller of this package actually gets rather
  than what the recogniser emits before the pipeline touches it.

That difference is worth stating wherever these tables are published.
The trainer's own evaluation applies no layout at all, so its figure for
the same weights is lower, and the two are not interchangeable.

    .venv/bin/python tools/register_comparison.py \\
        --spans evaluation/layout/spans \\
        --eval-root ../tetrak-hy-trainer/runs/eval

``--emit`` additionally writes the table to a CSV the site renders at
build time:

    .venv/bin/python tools/register_comparison.py \\
        --spans evaluation/layout/spans \\
        --eval-root ../tetrak-hy-trainer/runs/eval \\
        --emit evaluation/ocr/registers.csv

That file exists because neither input is in the repository: the
trainer's ``runs/`` is gitignored in full and so are the cached spans
under ``evaluation/layout/spans/``, so a Hugo build cannot recompute any
of this. Articles carried the table by hand instead, and by 22 September
both published copies disagreed with the harness -- the same failure
``partials/benchmark.html`` was written to delete. Regenerate the CSV
whenever a register is re-scored; do not edit it.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from tetrak_ocr.accuracy import character_similarity, word_recall  # noqa: E402
from tetrak_ocr.layout import TextSpan, to_text  # noqa: E402

OURS = "tetrak-hy v6 (ours)"

# Reading names for the evaluation-set directories. They live here rather
# than in the site so the CSV carries its own labels and the table has no
# second copy to drift from -- the whole point of emitting it.
REGISTER_LABELS = {
    "ase-vol2": "Encyclopedia (ASE vol. 2)",
    "baronian-vol10": "Baronian, Works",
    "dictionary-hy-en": "Dictionary (hy–en)",
    "faustus-1968": "Faustus of Byzantium (1968)",
    "medical-encyclopedia": "Medical encyclopedia",
    "otyan-works": "Otyan, Works",
    "totovents-works": "Totovents, Works",
    "tumanyan-elzh5": "Tumanyan (academic edition)",
}


def our_scores(spans_file: Path, eval_dir: Path) -> tuple[float, float, frozenset[str]] | None:
    """Score the shipped serialisation on one register's cached spans.

    Returns the pages alongside the means for the reason
    :func:`_scores_with_pages` does: our own column is held to the same
    coverage rule as every other, rather than exempted for being ours.
    """
    # The fold the shipped backend applies as text enters the pipeline
    # (``backends/armenian.py``). Until brief 013 this table skipped it, so the
    # published row was not what a caller gets. (It briefly cost word recall on
    # the medical encyclopedia, whose transcripts type ``:`` for ``։``, until
    # ``accuracy.normalise`` began scoring the two as the same character.)
    # Imported here rather than at module level so the rest of the tool, and
    # its tests, run without the ``armenian`` extra installed, as CI does.
    from tetrak_hy import fold_script

    payload = json.loads(spans_file.read_text(encoding="utf-8"))
    sims, recalls, pages = [], [], []
    for page, items in payload["pages"].items():
        truth_file = eval_dir / "text" / f"{page}.txt"
        if not truth_file.exists():
            continue
        truth = truth_file.read_text(encoding="utf-8")
        spans = [
            TextSpan(
                text=fold_script(item["text"]), bbox=tuple(item["bbox"]) if item["bbox"] else None
            )
            for item in items
        ]
        text = to_text(spans)
        sims.append(character_similarity(text, truth))
        recalls.append(word_recall(text, truth))
        pages.append(str(page))
    if not sims:
        return None
    return statistics.mean(sims), statistics.mean(recalls), frozenset(pages)


def external_scores(eval_dir: Path) -> dict[str, tuple[float, float]]:
    """Every engine's mean from the baselines CSVs in this evaluation set."""
    return {name: (chr_, wrd) for name, (chr_, wrd, _) in _scores_with_pages(eval_dir).items()}


def _scores_with_pages(eval_dir: Path) -> dict[str, tuple[float, float, frozenset[str]]]:
    """As :func:`external_scores`, plus the pages each engine actually scored.

    A page a backend failed on is written with empty scores rather than a
    zero, and is skipped here: a crashed engine has not been measured,
    and averaging a zero in would report a reading failure that never
    happened. An engine that failed on every page therefore does not
    appear at all.

    That skipping is why the page set is returned alongside the mean. An
    engine that failed nine pages of ten still *appears* in this mapping,
    with a mean over the single page it managed, and a caller checking
    only for presence would put that beside a ten-page mean and call the
    two comparable. :func:`emit_csv` needs the pages to refuse it.
    """
    per_engine: dict[str, list[tuple[float, float, str]]] = {}
    for path in sorted(eval_dir.glob("baselines*.csv")):
        with path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if not row["char_sim"] or not row["word_recall"]:
                    continue
                per_engine.setdefault(row["backend"], []).append(
                    (float(row["char_sim"]), float(row["word_recall"]), row["page"])
                )
    return {
        name: (
            statistics.mean(c for c, _, _ in rows),
            statistics.mean(w for _, w, _ in rows),
            frozenset(page for _, _, page in rows),
        )
        for name, rows in per_engine.items()
        if rows
    }


def emit_csv(
    path: Path,
    scored: list[tuple[str, dict[str, tuple[float, float]]]],
    pages: dict[str, dict[str, frozenset[str]]],
    *,
    allow_shrink: bool = False,
) -> list[str]:
    """Write the cross-engine table, restricted to engines measured everywhere.

    An engine that ran on some registers and not others cannot appear in a
    mean over registers without the mean quietly meaning a different set of
    pages per column. Until 22 September ``hye-paddle`` was exactly that
    -- encyclopedia-only -- so the rule is enforced here rather than left
    to whoever next reads the table.

    "Everywhere" means every *page* of every register, not merely a
    presence in each. ``_scores_with_pages`` drops pages a backend failed,
    so an engine that crashed on nine pages of ten still appears with a
    one-page mean; admitting that column would restate the very defect
    this file exists to prevent, one level down.

    Two ways a rerun can quietly narrow the table, both refused here:
    an engine missing pages (dropped, and named on stdout), and the whole
    run covering fewer registers than the committed CSV already holds
    (raises, unless *allow_shrink*). The second is the dangerous one --
    a missing spans file or eval directory shrinks the mean silently
    while every caption still says how many registers it covers.

    Returns the engines kept, so the caller can say what was dropped.
    """
    registers = [name for name, _ in scored]

    if path.exists() and not allow_shrink:
        with path.open(encoding="utf-8") as handle:
            previous = {
                row["register"] for row in csv.DictReader(handle) if row["register"] != "mean"
            }
        missing = previous - set(registers)
        if missing:
            raise SystemExit(
                f"refusing to write {path}: it already covers "
                f"{', '.join(sorted(missing))}, which this run does not. "
                f"Re-run over every register, or pass --allow-shrink if a "
                f"register has genuinely been retired."
            )

    # Full page coverage, per register, or the column is not comparable.
    # The reference set is the union of what any engine managed: a page no
    # engine could read penalises nobody, while a page one engine alone
    # failed excludes that engine rather than shortening everyone's mean.
    complete = []
    incomplete: dict[str, str] = {}
    for engine in sorted({e for _, rows in scored for e in rows}):
        if not all(engine in rows for _, rows in scored):
            continue
        short = [
            register
            for register in registers
            if pages[register][engine] != frozenset().union(*pages[register].values())
        ]
        if short:
            incomplete[engine] = ", ".join(short)
        else:
            complete.append(engine)
    for engine, where in incomplete.items():
        print(f"dropped {engine}: missing pages in {where}")
    everywhere = complete
    # Ours first, then the externals alphabetically: the column the reader
    # is comparing against belongs beside the register name.
    engines = ([OURS] if OURS in everywhere else []) + [e for e in everywhere if e != OURS]

    # Ordered by our own word recall, the ordering the published tables use.
    ordered = sorted(scored, key=lambda item: item[1].get(OURS, (0.0, 0.0))[1], reverse=True)

    header = ["register", "label"]
    for engine in engines:
        header += [f"{engine}_chr", f"{engine}_wrd"]

    rows = []
    for name, scores in ordered:
        row = [name, REGISTER_LABELS.get(name, name)]
        for engine in engines:
            chr_score, wrd_score = scores[engine]
            row += [f"{chr_score:.4f}", f"{wrd_score:.4f}"]
        rows.append(row)

    mean_row = ["mean", "Mean over registers"]
    for engine in engines:
        mean_row += [
            f"{statistics.mean(s[engine][0] for _, s in scored):.4f}",
            f"{statistics.mean(s[engine][1] for _, s in scored):.4f}",
        ]
    rows.append(mean_row)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"\nwrote {path} -- {len(registers)} registers, {len(engines)} engines")
    return engines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spans", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--sort", choices=["wrd", "chr"], default="wrd")
    parser.add_argument(
        "--emit",
        type=Path,
        help="also write the table to this CSV, for the site to render at build time",
    )
    parser.add_argument(
        "--allow-shrink",
        action="store_true",
        help="permit --emit to write fewer registers than the existing CSV holds",
    )
    args = parser.parse_args(argv)

    scored: list[tuple[str, dict[str, tuple[float, float]]]] = []
    pages: dict[str, dict[str, frozenset[str]]] = {}
    wins = {"chr": [], "wrd": []}
    for spans_file in sorted(args.spans.glob("*.json")):
        register = spans_file.stem
        eval_dir = args.eval_root / register
        if not eval_dir.is_dir():
            continue

        measured = _scores_with_pages(eval_dir)
        rows = {name: (chr_, wrd) for name, (chr_, wrd, _) in measured.items()}
        covered = {name: page_set for name, (_, _, page_set) in measured.items()}
        ours = our_scores(spans_file, eval_dir)
        if ours:
            rows[OURS] = (ours[0], ours[1])
            covered[OURS] = ours[2]
        if not rows:
            continue
        scored.append((register, rows))
        pages[register] = covered

        index = 1 if args.sort == "wrd" else 0
        ordered = sorted(rows.items(), key=lambda item: item[1][index], reverse=True)

        print(f"\n=== {register} ===")
        print(f"{'engine':<26}{'chr':>9}{'wrd':>9}")
        for name, (chr_score, wrd_score) in ordered:
            marker = "  <-" if name == OURS else ""
            print(f"{name:<26}{chr_score:>9.4f}{wrd_score:>9.4f}{marker}")

        for metric, position in (("chr", 0), ("wrd", 1)):
            best = max(rows.items(), key=lambda item: item[1][position])
            wins[metric].append((register, best[0], best[1][position]))

    print("\n=== who leads each register ===")
    print(f"{'register':<24}{'best chr':<28}{'best wrd':<28}")
    for (register, chr_name, chr_value), (_, wrd_name, wrd_value) in zip(
        wins["chr"], wins["wrd"], strict=True
    ):
        print(
            f"{register:<24}{chr_name + f' ({chr_value:.3f})':<28}"
            f"{wrd_name + f' ({wrd_value:.3f})':<28}"
        )

    if args.emit and scored:
        kept = emit_csv(args.emit, scored, pages, allow_shrink=args.allow_shrink)
        dropped = sorted({e for _, rows in scored for e in rows} - set(kept))
        if dropped:
            print(f"not measured on every register, so omitted: {', '.join(dropped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
