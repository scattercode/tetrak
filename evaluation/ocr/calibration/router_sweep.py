#!/usr/bin/env python3
"""Sweep candidate length-weight rules for auto-local's backend selection.

`auto_local.ocr_image()` ranks local backends by
`combined_score * (0.5 + 0.5 * words / max_words)` -- a reference-free quality
score adjusted for relative transcript length, so a backend that recovers more
text is preferred when raw quality is close. The error taxonomy (product analytics)
("The router's own error rate") found the multiplier too weak on
`carthay-circle-premiere.jpg`: it picks a short, clean tesseract-auto fragment
(0.49 char_sim) over a longer, more complete EasyOCR transcript (0.87) -- a
0.38 loss from the scoring rule, not an engine limitation. This sweeps
replacement rules against the same evidence the rest of
`evaluation/ocr/calibration/` uses: mean *regret*
(brief 007, the calibration toolkit), fit on `splits.toml`'s
`original-corpus` split, held-out fixtures scored but never fit to.

Two phases, both driven by this script:

  --measure   Run every local backend `auto_local` would actually consider,
              once per fixture, and cache the raw transcript text under
              `router_cache/<fixture-stem>/<backend>.txt`. Skips a
              (fixture, backend) pair whose cache file already exists, so a
              second run only fills gaps in -- useful because Marker alone
              costs over twenty minutes across the corpus.
  (default)   Score every cached transcript (`combined_score`, `char_sim`,
              word count), sweep the rule family, print the regret table.
  --save      As above, and write `router_sweep.csv` and `router_sweep.md`.

Usage:
    python -m evaluation.ocr.calibration.router_sweep --measure   # cache transcripts
    python -m evaluation.ocr.calibration.router_sweep             # print, no write
    python -m evaluation.ocr.calibration.router_sweep --save      # write CSV + MD

Why the cache is committed: `router_cache/*.txt` is generated, not
hand-written -- the same status as `sweep.csv` and `features.csv` -- and
committing it is what lets `tests/ocr/test_auto_local.py`'s slow test check the
shipped rule against real transcripts without seven extras and twenty minutes
on every CI run of the `corpus` job. `router_sweep.csv` is the derived scores
table (`combined_score`, `char_sim`, `word_count` per fixture/backend); it, not
the raw text or `qa_score.combined_score()`, is what the rule sweep and the
slow test actually read, because CI's `corpus` job installs `.[dev]` only --
no `qa` extra, and GPT-2 perplexity has no business running inside a test even
where it is installed.

Scope: the 9 fixtures with ground truth in `corpus/expected/` -- the same set
`tetrak-ocr evaluate --all` and the error taxonomy use. `splits.toml`'s
`original-corpus` split gives the fit set (6 rasters, the "honest baseline")
and held-out set (2 rasters); the held-out fixtures are scored and reported
but never used to choose a rule. `king-of-kings-souvenir-1927` sits in
`[excluded]` -- a PDF, excluded from the raster-only band-fitting splits for a
reason that does not obviously carry over here, since the router does route
PDFs. It is measured and reported like any other fixture, just not folded into
`fit` or `held_out`: `splits.toml` owns that classification and this script
does not invent a new one.
"""

import argparse
import csv
import sys
from pathlib import Path

from evaluation.ocr.calibration import splits
from evaluation.ocr.harness import EXPECTED_DIR, FIXTURES_DIR
from tetrak_ocr.accuracy import character_similarity
from tetrak_ocr.auto_local import _build_candidates
from tetrak_ocr.qa_score import combined_score

CALIBRATION_DIR = Path(__file__).resolve().parent
CACHE_DIR = CALIBRATION_DIR / "router_cache"
ROUTER_SWEEP_CSV = CALIBRATION_DIR / "router_sweep.csv"
ROUTER_SWEEP_MD = CALIBRATION_DIR / "router_sweep.md"

FIELDNAMES = ("fixture", "backend", "combined_score", "word_count", "char_sim")

# ---------------------------------------------------------------------------
# Phase 1: cache every local backend's transcript, once.
# ---------------------------------------------------------------------------


def published_pairs() -> list[tuple[Path, Path]]:
    """Return (image, expected) for every fixture with committed ground truth.

    This is the corpus `tetrak-ocr evaluate --all` and the error taxonomy
    already use -- every fixture in `corpus/expected/`, currently 9.
    """
    return sorted(
        (image, EXPECTED_DIR / f"{image.stem}.md")
        for image in FIXTURES_DIR.iterdir()
        if image.is_file() and (EXPECTED_DIR / f"{image.stem}.md").exists()
    )


def cache_path(stem: str, backend: str) -> Path:
    return CACHE_DIR / stem / f"{backend}.txt"


def measure(pairs: list[tuple[Path, Path]] | None = None) -> None:
    """Run every eligible local backend on every fixture, once, and cache it.

    Eligibility comes from `auto_local._build_candidates()` itself -- the same
    function the router calls in production -- so this can never sweep a
    backend the router would not actually have considered, or miss one it
    would.
    """
    pairs = pairs if pairs is not None else published_pairs()
    for image, _ in pairs:
        candidates = _build_candidates(image)
        for name, fn in candidates:
            dest = cache_path(image.stem, name)
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"  [{image.stem}] running {name}...", flush=True)
            try:
                text = fn(image)
            except Exception as exc:  # a failed backend is data, not a crash
                print(f"    {name} failed: {exc}", file=sys.stderr)
                continue
            dest.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 2: score the cache.
# ---------------------------------------------------------------------------


def score_cache(pairs: list[tuple[Path, Path]] | None = None) -> list[dict[str, object]]:
    """Score every cached transcript: combined_score, word count, char_sim.

    One row per (fixture, backend) actually cached. A fixture whose
    `--measure` run has not happened yet, or whose backend failed, simply
    contributes no row for that backend -- `evaluate_family` treats a fixture
    with fewer than two scored candidates as uninformative rather than
    erroring, since a single-candidate fixture has no routing decision to get
    wrong.
    """
    pairs = pairs if pairs is not None else published_pairs()
    rows: list[dict[str, object]] = []
    for image, expected_path in pairs:
        expected = expected_path.read_text(encoding="utf-8")
        candidates = _build_candidates(image)
        for name, _fn in candidates:
            cached = cache_path(image.stem, name)
            if not cached.exists():
                continue
            text = cached.read_text(encoding="utf-8")
            rows.append(
                {
                    "fixture": image.stem,
                    "backend": name,
                    "combined_score": round(combined_score(text), 6),
                    "word_count": len(text.split()),
                    "char_sim": round(character_similarity(text, expected), 4),
                }
            )
    return rows


def read(path: Path = ROUTER_SWEEP_CSV) -> list[dict[str, object]]:
    """Read a committed router_sweep.csv back, with numeric columns typed."""
    with path.open(encoding="utf-8") as handle:
        return [
            {
                "fixture": row["fixture"],
                "backend": row["backend"],
                "combined_score": float(row["combined_score"]),
                "word_count": int(row["word_count"]),
                "char_sim": float(row["char_sim"]),
            }
            for row in csv.DictReader(handle)
        ]


def write_csv(rows: list[dict[str, object]], path: Path = ROUTER_SWEEP_CSV) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# The rule family.
# ---------------------------------------------------------------------------
#
# The shipped rule is linear in the word-count ratio:
#
#     effective = score * (weight + (1 - weight) * words / max_words)
#
# `weight` is what a zero-word transcript still gets credited (0.5 before
# this sweep; the shipped value now lives in auto_local.LENGTH_WEIGHT); a
# transcript at max_words always gets the full `score`
# regardless of `weight`. Lowering `weight` punishes a short transcript
# harder relative to a longer one at the same combined_score -- which is
# exactly the lever the taxonomy names, so it is swept across its full range
# first. `POWER_GRID` is the fallback shape: `score * ratio**power`,
# tried only if no linear weight clears Carthay without a regression
# elsewhere -- see the module docstring and the report this script prints.


def linear_effective(score: float, words: int, max_words: int, weight: float) -> float:
    if max_words <= 0:
        return score
    ratio = words / max_words
    return score * (weight + (1.0 - weight) * ratio)


def power_effective(score: float, words: int, max_words: int, power: float) -> float:
    if max_words <= 0:
        return score
    ratio = words / max_words
    return score * (ratio**power)


LINEAR_WEIGHT_GRID: tuple[float, ...] = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0)
POWER_GRID: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0)


class Rule:
    """One candidate scoring rule: a name and a pure (score, words, max_words) -> float."""

    def __init__(self, label: str, fn) -> None:
        self.label = label
        self.fn = fn

    def __call__(self, score: float, words: int, max_words: int) -> float:
        return self.fn(score, words, max_words)


def rule_family() -> list[Rule]:
    rules = [
        Rule(f"linear(weight={w})", lambda s, wd, mw, w=w: linear_effective(s, wd, mw, w))
        for w in LINEAR_WEIGHT_GRID
    ]
    rules += [
        Rule(f"power({p})", lambda s, wd, mw, p=p: power_effective(s, wd, mw, p))
        for p in POWER_GRID
    ]
    return rules


# The rule this sweep replaced -- kept at the literal old value (0.5) rather
# than reading `tetrak_ocr.auto_local.LENGTH_WEIGHT`, which is now the winner
# this script chose. Comparing against a moving target would make "current
# rule" mean something different every time this script runs after the next
# re-fit.
CURRENT_RULE = Rule(
    "linear(weight=0.5)  [pre-fix]", lambda s, wd, mw: linear_effective(s, wd, mw, 0.5)
)


# ---------------------------------------------------------------------------
# Regret.
# ---------------------------------------------------------------------------


def _by_fixture(rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row["fixture"]), []).append(row)
    return grouped


def choice_and_regret(
    fixture_rows: list[dict[str, object]], rule: Rule
) -> tuple[str, float, float]:
    """Return (chosen_backend, chosen_char_sim, regret) for one fixture under one rule.

    Ties break the same way `auto_local.ocr_image()` breaks them: the first
    maximum in candidate order (`_build_candidates()`'s order, which is the
    iteration order these rows were produced in).
    """
    max_words = max(int(row["word_count"]) for row in fixture_rows) or 1
    best_effective = float("-inf")
    chosen = fixture_rows[0]
    for row in fixture_rows:
        effective = rule(float(row["combined_score"]), int(row["word_count"]), max_words)
        if effective > best_effective:
            best_effective = effective
            chosen = row
    best_char_sim = max(float(row["char_sim"]) for row in fixture_rows)
    chosen_char_sim = float(chosen["char_sim"])
    return str(chosen["backend"]), chosen_char_sim, best_char_sim - chosen_char_sim


def mean_regret(rows: list[dict[str, object]], fixtures: list[str], rule: Rule) -> float:
    by_fixture = _by_fixture(rows)
    regrets = []
    for fixture in fixtures:
        fixture_rows = by_fixture.get(fixture, [])
        if len(fixture_rows) < 2:
            continue  # nothing to route between; uninformative for fitting
        _, _, regret = choice_and_regret(fixture_rows, rule)
        regrets.append(regret)
    return sum(regrets) / len(regrets) if regrets else 0.0


def evaluate_family(
    rows: list[dict[str, object]], fit_fixtures: list[str]
) -> tuple[Rule, list[Rule]]:
    """Return (winner, family) ranked by mean regret over `fit_fixtures`.

    Ties (regret equal to several decimal places) break towards the rule
    closest to the shipped one, on the same "least surprising" principle
    `sweep.py` uses for contrast ties.
    """
    family = rule_family()
    scored = sorted(
        family,
        key=lambda rule: (
            round(mean_regret(rows, fit_fixtures, rule), 6),
            abs(_distance_from_shipped(rule)),
        ),
    )
    return scored[0], family


def _distance_from_shipped(rule: Rule) -> float:
    """A rough distance from the pre-fix linear(weight=0.5), for tie-breaking.

    Deliberately the historical 0.5, not auto_local.LENGTH_WEIGHT: the
    tie-break prefers the least-changed rule relative to where the sweep
    started, and moving this anchor with each re-fit would make ties drift.
    """
    if rule.label.startswith("linear(weight="):
        weight = float(rule.label.split("=")[1].rstrip(")"))
        return weight - 0.5
    return 10.0  # any power-law rule is "further" than any linear one


# ---------------------------------------------------------------------------
# Reporting.
# ---------------------------------------------------------------------------


def _partitions(rows: list[dict[str, object]]) -> tuple[list[str], list[str], list[str]]:
    """Return (fit, held_out, excluded) fixture stems present in `rows`."""
    present = {str(row["fixture"]) for row in rows}
    fit, held_out = splits.split("original-corpus")
    excluded = sorted(present - set(fit) - set(held_out))
    return sorted(set(fit) & present), sorted(set(held_out) & present), excluded


def regret_table(
    rows: list[dict[str, object]], fixtures: list[str], rule: Rule
) -> list[dict[str, object]]:
    by_fixture = _by_fixture(rows)
    table = []
    for fixture in fixtures:
        fixture_rows = by_fixture.get(fixture, [])
        if not fixture_rows:
            continue
        if len(fixture_rows) < 2:
            chosen = fixture_rows[0]
            table.append(
                {
                    "fixture": fixture,
                    "chosen": chosen["backend"],
                    "chosen_char_sim": chosen["char_sim"],
                    "best_char_sim": chosen["char_sim"],
                    "regret": 0.0,
                    "note": "single candidate",
                }
            )
            continue
        chosen, chosen_sim, regret = choice_and_regret(fixture_rows, rule)
        best_sim = max(float(r["char_sim"]) for r in fixture_rows)
        table.append(
            {
                "fixture": fixture,
                "chosen": chosen,
                "chosen_char_sim": chosen_sim,
                "best_char_sim": best_sim,
                "regret": round(regret, 4),
                "note": "",
            }
        )
    return table


def _print_table(title: str, table: list[dict[str, object]]) -> None:
    print(f"\n{title}")
    print(f"{'fixture':<38} {'chosen':<14} {'chosen':>8} {'best':>8} {'regret':>8}")
    for row in table:
        print(
            f"{row['fixture']:<38} {row['chosen']:<14} "
            f"{row['chosen_char_sim']:>8.4f} {row['best_char_sim']:>8.4f} "
            f"{row['regret']:>8.4f}"
        )
    if table:
        mean = sum(float(r["regret"]) for r in table) / len(table)
        print(f"{'mean regret':<38} {'':<14} {'':>8} {'':>8} {mean:>8.4f}")


def write_report(
    rows: list[dict[str, object]],
    fit: list[str],
    held_out: list[str],
    excluded: list[str],
    current: Rule,
    winner: Rule,
) -> None:
    lines = [
        "# Router length-weight sweep",
        "",
        "Generated by `python -m evaluation.ocr.calibration.router_sweep --save`. Do not edit.",
        "",
        "Every cached local-backend transcript scored under the shipped rule and the",
        "winning rule from the family, reported as regret against the best local",
        'candidate per fixture. See the error taxonomy (product analytics) ("The',
        "router's own error rate\") for the problem and",
        "brief 007 (the calibration toolkit) for why regret, not mean score,",
        "is the objective.",
        "",
        f"**Fit set** (original-corpus, 6 fixtures): {', '.join(fit)}",
        "",
        f"**Held out**, scored but never fit to: {', '.join(held_out)}",
        "",
        f"**Excluded** from fitting by `splits.toml` (reported separately): {', '.join(excluded)}",
        "",
        f"**Current rule:** `{current.label}`",
        "",
        f"**Winning rule:** `{winner.label}`",
        "",
    ]

    for title, fixtures in (
        ("## Fit set", fit),
        ("## Held out", held_out),
        ("## Excluded", excluded),
    ):
        lines.append(title)
        lines.append("")
        for label, rule in (("Current", current), ("Winner", winner)):
            table = regret_table(rows, fixtures, rule)
            if not table:
                continue
            lines.append(f"### {label} rule (`{rule.label}`)")
            lines.append("")
            lines.append("| Fixture | Chosen | chosen char_sim | best char_sim | regret |")
            lines.append("|---|---|---:|---:|---:|")
            for row in table:
                lines.append(
                    f"| `{row['fixture']}` | {row['chosen']} | {row['chosen_char_sim']:.4f} "
                    f"| {row['best_char_sim']:.4f} | {row['regret']:.4f} |"
                )
            if table:
                mean = sum(float(r["regret"]) for r in table) / len(table)
                lines.append(f"| **mean regret** | | | | **{mean:.4f}** |")
            lines.append("")

    ROUTER_SWEEP_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {ROUTER_SWEEP_MD.name}")


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--measure", action="store_true", help="run OCR to fill gaps in router_cache/"
    )
    parser.add_argument("--save", action="store_true", help="write router_sweep.csv and .md")
    args = parser.parse_args(argv)

    pairs = published_pairs()
    if not pairs:
        print(f"No fixtures with ground truth in {FIXTURES_DIR}", file=sys.stderr)
        return 1

    if args.measure:
        measure(pairs)

    rows = score_cache(pairs)
    if not rows:
        print("No cached transcripts found -- run with --measure first", file=sys.stderr)
        return 1

    fit, held_out, excluded = _partitions(rows)
    winner, family = evaluate_family(rows, fit)

    print(f"{len(rows)} scored (fixture, backend) pairs over {len(pairs)} fixtures")
    print(f"Fit set ({len(fit)}): {', '.join(fit)}")
    print(f"Held out ({len(held_out)}): {', '.join(held_out)}")
    print(f"Excluded ({len(excluded)}): {', '.join(excluded)}")

    print(f"\n{'rule':<24} {'mean regret (fit)':>18}")
    for rule in sorted(family, key=lambda r: mean_regret(rows, fit, r)):
        marker = "  <- winner" if rule.label == winner.label else ""
        print(f"{rule.label:<24} {mean_regret(rows, fit, rule):>18.4f}{marker}")

    _print_table("Fit set, current rule", regret_table(rows, fit, CURRENT_RULE))
    _print_table("Fit set, winning rule", regret_table(rows, fit, winner))
    _print_table("Held out, current rule", regret_table(rows, held_out, CURRENT_RULE))
    _print_table("Held out, winning rule", regret_table(rows, held_out, winner))
    _print_table("Excluded, current rule", regret_table(rows, excluded, CURRENT_RULE))
    _print_table("Excluded, winning rule", regret_table(rows, excluded, winner))

    if args.save:
        write_csv(rows)
        print(f"\nWrote {ROUTER_SWEEP_CSV.name}")
        write_report(rows, fit, held_out, excluded, CURRENT_RULE, winner)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
