#!/usr/bin/env python3
"""Fit the auto-configuration bands to the committed sweep.

The bands in `tetrak_ocr.backends.tuning` were hand-fitted in August 2026 and
scored *worse* than plain Tesseract on two of the eight rasters. This chooses
them by measurement instead: it reads the sweep, searches the band edges
exhaustively, and regenerates the shipped module between its `GENERATED`
markers. It has run once, on 27 September 2026; `tuning.py`'s `FIT_PROVENANCE`
records what that produced.

Usage:
    python -m evaluation.ocr.calibration.fit                 # fit, print, write nothing
    python -m evaluation.ocr.calibration.fit --write         # regenerate tuning.py and fit.md
    python -m evaluation.ocr.calibration.fit --check         # committed bands vs committed sweep
    python -m evaluation.ocr.calibration.fit --split original-corpus

No OCR *runs* and nothing leaves the machine: it reads `sweep.csv`,
`features.csv` and `splits.toml`, all committed, and a re-fit is seconds.
That is the whole reason the sweep is a separate step.

It does still *import* the OCR stack, though, because `sweep.read()` is the
single definition of the sweep CSV's schema and `sweep` reaches the harness
to get it -- so importing this module pulls Pillow, numpy and pytesseract.
Do not "fix" that by copying the reader here; two parsers for one file is a
worse problem than an unused import. Only `tuning.py` itself is promised to
be dependency-free.

Regret, not mean score
----------------------
`regret(fixture, cell) = best_char_sim(fixture) - char_sim(fixture, cell)`.

The corpus spans a 350x range in transcript length, so a mean score hands the
objective to the longest documents. Regret makes each fixture contribute only
what the selector could have done better, which is the quantity a selector is
actually responsible for. Length weighting was rejected in brief 007: it would
give roughly 68% of the objective to the two *Inside Facts* pages.

Character similarity is the metric. On kinema-theater-ad-1920 word recall moved
only 0.397 -> 0.385 while character similarity collapsed 0.231 -> 0.043,
because word recall is set membership and blind to reading-order scrambling.
Fitting on it would not have seen the bug at all.

Why the search is exact
-----------------------
A band family is a step function over one feature, so a candidate fit is just
an assignment of a value to each fixture that is constant on contiguous runs of
the feature ordering. The two families read *different* features, so their
orderings differ and the objective does not separate across them -- a fixture's
regret depends on the (contrast, psm) pair, not on either alone.

That is handled by enumerating the smaller family exhaustively and solving the
larger one exactly for each enumeration: for a fixed psm-per-fixture
assignment, every fixture's cost becomes a function of contrast alone, and the
best contrast banding follows from a partition dynamic program. A few thousand
psm assignments times a dynamic program over eight fixtures is a second or two,
and the result is a global optimum rather than a hill-climb.

What stops it overfitting is the band budget, not the search. Given eight bands
per family the optimum *is* the per-fixture oracle, which generalises to
nothing. `MAX_CONTRAST_BANDS` and `MAX_PSM_BANDS` keep the shipped shape, and
the reported leave-one-out gap is how much even that shape has memorised.
"""

import argparse
import csv
import json
import math
import re
import sys
from itertools import combinations, product
from pathlib import Path
from typing import NamedTuple

from evaluation.ocr.calibration import splits, sweep

CALIBRATION_DIR = Path(__file__).resolve().parent
FIT_MD = CALIBRATION_DIR / "fit.md"
# Named here rather than imported from `features`, which would pull Pillow in
# to learn a filename. `sweep` already drags the OCR stack in (see above), so
# this saves nothing today -- it stops the fitter acquiring a *second* reason
# to be heavy, which is the one that would be awkward to unpick later.
FEATURES_CSV = CALIBRATION_DIR / "features.csv"
TUNING_PY = CALIBRATION_DIR.parent.parent.parent / "src" / "tetrak_ocr" / "backends" / "tuning.py"

# The shipped band shape, and the only regulariser this fit has. Four contrast
# bands and three PSM bands is what `tuning.py` carries today; holding the
# budget fixed is what makes the re-fit a comparison rather than a different
# model. Given eight bands per family the optimum is the per-fixture oracle,
# which generalises to nothing, so the budget is doing real work and
# `--max-contrast-bands` / `--max-psm-bands` exist to measure how much.
#
# 5x4 since 2026-09-29, raised from the 4x3 the hand-fit shipped. The corpus
# doubled on 28 September -- eight rasters transcribed and human-checked, see
# corpus/SOURCES.md -- and 4x3 cannot serve the result: it spends its three
# psm bands on the mid-range and drops PSM 12 entirely, which puts
# carthay-circle-postcard-back at 0.5950 against a floor of 0.9136. The fit is
# infeasible, and --write refuses it.
#
# Measured over the twelve fit fixtures:
#
#   4x3  mean 0.4404  in-sample 0.0993  LOO 0.2646  psm[3,6,3]      floor unmet
#   4x4  mean 0.4659  in-sample 0.0738  LOO   --    psm[12,3,6,3]   floor unmet by 0.0128
#   5x4  mean 0.4618  in-sample 0.0779  LOO 0.2647  psm[12,3,6,3]   all floors met
#
# The fifth *contrast* band is what clears the last floor, and it is worth
# understanding why before anyone trims it back: the postcard reverse reads
# best at contrast 2.5, and four bands cannot isolate that value from its
# neighbours on this corpus. The band exists to reach one fixture's optimum.
#
# Normally that would be the definition of memorisation and a reason to refuse
# it. It is not, here, and the leave-one-out figures are why: 0.2646 at 4x3
# against 0.2647 at 5x4. Two extra bands bought 0.021 of *in-sample* fit and
# nothing at all out of sample. The generalisation gap widens (+0.165 ->
# +0.187) only because the in-sample half improved; the half that predicts
# behaviour on unseen material did not move. Per-fixture the LOO values do
# differ and happen to cancel -- greek-theatre-night improves, page-six
# worsens -- so the equality is real rather than an artefact.
#
# The larger finding, which no band budget addresses: leave-one-out sits at
# ~0.265 whatever the shape, and it got *worse* when the corpus grew (0.2006
# over eight fixtures, 0.2647 over twelve). More data made generalisation
# harder because the material is now genuinely varied -- linen postcards,
# newsprint, a playbill and lithographed posters do not share one mapping from
# two pixel statistics to a configuration. Neither the band count nor the
# corpus size is the binding constraint any more. The two-feature model is.
# `features.py` already measures `interior_gutters` against that day.
MAX_CONTRAST_BANDS = 5
MAX_PSM_BANDS = 4


class Budget(NamedTuple):
    """How many bands each family may use."""

    contrast: int = MAX_CONTRAST_BANDS
    psm: int = MAX_PSM_BANDS

    def __str__(self) -> str:
        return f"{self.contrast} contrast / {self.psm} psm bands"


# Tesseract's own defaults, and therefore "plain" -- the `tesseract` column of
# the benchmark. The sweep's (2.0, 3) cell reproduces that column exactly on
# every fixture, so the no-regression rule below is measured against the same
# data as the objective rather than against a second, older measurement.
BASELINE_CELL = (2.0, 3)

# Floors the fit must clear, from brief 007's "How we would know it worked".
# These are *additional* to the rule that no fixture may score below plain;
# the effective floor is whichever is higher.
#
#   inside-facts-1930-cover  the binding CI constraint -- tests/ocr/
#                            test_thresholds.py gates at 0.30
#   carthay-circle-premiere  the biggest auto win; do not spend it
#   carthay-circle-postcard  the PSM-12 band's only justification
FIXTURE_FLOORS: dict[str, float] = {
    "inside-facts-1930-cover.jpg": 0.30,
    "carthay-circle-premiere.jpg": 0.4930,
    "carthay-circle-postcard-back.png": 0.9136,
}

# kinema-theater-ad-1920 is the fixture the current bands get backwards, and
# the brief asks for more than a score: the page has a programme column beside
# the headline, so a fit that reached the score through PSM 6 would have got
# the right answer for the wrong reason and would not survive the next page
# laid out like it.
REQUIRED_PSM: dict[str, int] = {"kinema-theater-ad-1920.tif": 3}

# The CI gate, from tests/ocr/test_thresholds.py. A fixture that test does not
# mark xfail must clear *both* thresholds, so both are constraints here --
# otherwise the fit is free to trade one metric for the other and turn the
# suite red. It nearly did: the unconstrained optimum gives
# carthay-circle-premiere contrast 3.5, worth +0.1818 character similarity and
# -0.0714 word recall, which lands at 0.7857 against a gate of 0.80.
#
# Character similarity stays the *objective*. Word recall is set membership and
# blind to reading-order scrambling -- on kinema-theater-ad-1920 it moved 0.397
# -> 0.385 while character similarity collapsed 0.231 -> 0.043 -- so fitting on
# it would not have seen the bug this work exists to repair. It is a floor to
# respect, not a thing to maximise.
#
# `tests/ocr/test_calibration.py` asserts these three constants still match the
# test module, so the two cannot drift apart silently.
CI_CHARACTER_THRESHOLD = 0.30
CI_WORD_RECALL_THRESHOLD = 0.80
CI_GATED: frozenset[str] = frozenset(
    {
        "carthay-circle-premiere.jpg",
        "inside-facts-1930-cover.jpg",
        "inside-facts-1930-page-six.jpg",
    }
)

# Corpus-level target, over the fit set. Not a search constraint: minimising
# total regret maximises the mean, so if the optimum misses this, nothing
# meets it. Checked and reported on the result.
TARGET_MEAN_CHAR_SIM = 0.45

# `line-length` from [tool.ruff] in pyproject.toml. Duplicated rather than
# parsed: the generator needs it to emit source the formatter will leave alone,
# and reading the TOML to find out would make a band fitter depend on the
# project's lint configuration.
RUFF_LINE_LENGTH = 100

GENERATED_BEGIN = "# --- BEGIN GENERATED: {name} ---"
GENERATED_END = "# --- END GENERATED: {name} ---"


class Band(NamedTuple):
    """One threshold: use `value` while the feature is below `upper`."""

    upper: float
    value: float | int


class Cost(NamedTuple):
    """The objective, compared lexicographically.

    `violations` leads so that an infeasible corner of the search space can
    never beat a feasible one, and so that an entirely infeasible problem
    still returns its least-bad answer with something to point at, rather
    than an exception and no diagnosis.

    The two tie-breaks below regret matter more than they look. PSM 1 and
    PSM 3 score *identically* on every cell the sweep measured, so without
    `psm_rank` the winner would be decided by dictionary iteration order --
    and PSM 1 would sometimes win, which reads as a finding and is not one.
    `contrast_distance` breaks the remaining ties towards Tesseract's default,
    on the principle that where the measurement cannot tell two settings
    apart, the shipped bands should intervene less.
    """

    violations: int
    regret: float
    psm_rank: int
    contrast_distance: float

    def __add__(self, other: "Cost") -> "Cost":  # type: ignore[override]
        return Cost(
            self.violations + other.violations,
            self.regret + other.regret,
            self.psm_rank + other.psm_rank,
            self.contrast_distance + other.contrast_distance,
        )

    def __sub__(self, other: "Cost") -> "Cost":
        return Cost(
            self.violations - other.violations,
            self.regret - other.regret,
            self.psm_rank - other.psm_rank,
            self.contrast_distance - other.contrast_distance,
        )


ZERO = Cost(0, 0.0, 0, 0.0)


class Grid:
    """The sweep, indexed for fitting, with the constraints already applied.

    Constructed once per fit. Holds only the fixtures being fitted, so the
    leave-one-out passes build a smaller Grid rather than filtering inside the
    search.
    """

    def __init__(self, rows: list[dict[str, object]], fixtures: list[str]) -> None:
        self.fixtures = sorted(fixtures)
        self.score: dict[tuple[str, float, int], float] = {}
        self.recall: dict[tuple[str, float, int], float] = {}
        wanted = set(self.fixtures)
        for row in rows:
            name = str(row["fixture"])
            if name in wanted:
                cell = (name, float(row["contrast"]), int(row["psm"]))
                self.score[cell] = float(row["char_sim"])
                self.recall[cell] = float(row["word_recall"])

        measured = {name for name, _, _ in self.score}
        missing = set(self.fixtures) - measured
        if missing:
            raise SystemExit(
                f"sweep.csv has no cells for {sorted(missing)} -- re-run "
                "`python -m evaluation.ocr.calibration.sweep --save`"
            )

        self.contrast_values = sorted({c for _, c, _ in self.score})
        self.psm_values = sorted({p for _, _, p in self.score})
        self.best = {
            name: max(v for (f, _, _), v in self.score.items() if f == name)
            for name in self.fixtures
        }
        self.plain = {name: self.score[(name, *BASELINE_CELL)] for name in self.fixtures}
        self.floor = {
            name: max(self.plain[name], FIXTURE_FLOORS.get(name, 0.0)) for name in self.fixtures
        }

    def cost(self, fixture: str, contrast: float, psm: int) -> Cost:
        """The objective contribution of putting one fixture in one cell."""
        score = self.score[(fixture, contrast, psm)]
        violations = 0
        if score < self.floor[fixture] - 1e-9:
            violations += 1
        if fixture in REQUIRED_PSM and psm != REQUIRED_PSM[fixture]:
            violations += 1
        if fixture in CI_GATED:
            if score < CI_CHARACTER_THRESHOLD - 1e-9:
                violations += 1
            if self.recall[(fixture, contrast, psm)] < CI_WORD_RECALL_THRESHOLD - 1e-9:
                violations += 1
        rank = (
            sweep.PSM_PREFERENCE.index(psm)
            if psm in sweep.PSM_PREFERENCE
            else len(sweep.PSM_PREFERENCE)
        )
        return Cost(
            violations,
            self.best[fixture] - score,
            rank,
            abs(contrast - sweep.DEFAULT_CONTRAST),
        )


class Result(NamedTuple):
    """A fitted band set and everything needed to judge it."""

    contrast_bands: tuple[Band, ...]
    psm_bands: tuple[Band, ...]
    cost: Cost
    assignment: dict[str, tuple[float, int]]


def _orderings(
    grid: Grid, feature_values: dict[str, dict[str, float]]
) -> tuple[list[str], list[str]]:
    """Return the fixtures ordered by stddev and by dark_pct.

    Two orderings of the same fixtures, which is exactly why the two band
    families do not separate.
    """
    by_stddev = sorted(grid.fixtures, key=lambda f: feature_values[f]["stddev"])
    by_dark = sorted(grid.fixtures, key=lambda f: feature_values[f]["dark_pct"])
    return by_stddev, by_dark


def _cuttable(order: list[str], values: dict[str, float]) -> list[int]:
    """Return the gap indices a band edge may fall in.

    A gap between two fixtures with the *same* feature value cannot be cut: no
    threshold separates them, and generating one anyway would silently put both
    on the same side of an edge the fit believed it had placed between them.
    """
    return [i for i in range(1, len(order)) if values[order[i]] > values[order[i - 1]] + 1e-12]


def _step_functions(
    order: list[str], cuttable: list[int], values: list[int], max_runs: int
) -> list[dict[str, int]]:
    """Enumerate every step function over `order` with at most `max_runs` runs.

    Adjacent runs are required to differ, so a fit using fewer runs than the
    budget is enumerated once rather than once per way of padding it.
    """
    out: list[dict[str, int]] = []
    for runs in range(1, max_runs + 1):
        for cuts in combinations(cuttable, runs - 1):
            groups = []
            bounds = (0, *cuts, len(order))
            for start, stop in zip(bounds[:-1], bounds[1:], strict=True):
                groups.append(order[start:stop])
            for assigned in product(values, repeat=runs):
                if any(a == b for a, b in zip(assigned[:-1], assigned[1:], strict=True)):
                    continue
                mapping: dict[str, int] = {}
                for group, value in zip(groups, assigned, strict=True):
                    for fixture in group:
                        mapping[fixture] = value
                out.append(mapping)
    return out


def _best_partition(
    order: list[str],
    cuttable: set[int],
    per_value_cost: list[list[Cost]],
    values: list[float],
    max_runs: int,
) -> tuple[Cost, dict[str, float]]:
    """Solve the one-dimensional banding exactly, by dynamic program.

    `per_value_cost[k][v]` is what fixture `order[k]` costs under value
    `values[v]`, with the other family's choice already fixed. Because that
    cost is additive over fixtures, the best banding of a prefix depends only
    on where the last band starts, which is what makes this a partition DP
    rather than another enumeration.
    """
    n = len(order)
    # prefix[k][v] = cost of order[:k] all taking values[v]
    prefix = [[ZERO] * len(values) for _ in range(n + 1)]
    for k in range(n):
        for v in range(len(values)):
            prefix[k + 1][v] = prefix[k][v] + per_value_cost[k][v]

    # table[j][b] = (cost, start of the last band, value index of the last band)
    table: list[list[tuple[Cost, int, int] | None]] = [
        [None] * (max_runs + 1) for _ in range(n + 1)
    ]
    table[0][0] = (ZERO, 0, 0)
    for j in range(1, n + 1):
        for b in range(1, max_runs + 1):
            best: tuple[Cost, int, int] | None = None
            for i in range(j):
                if i != 0 and i not in cuttable:
                    continue
                prev = table[i][b - 1]
                if prev is None:
                    continue
                for v in range(len(values)):
                    total = prev[0] + (prefix[j][v] - prefix[i][v])
                    if best is None or total < best[0]:
                        best = (total, i, v)
            table[j][b] = best

    winner = min(
        (entry for entry in (table[n][b] for b in range(1, max_runs + 1)) if entry is not None),
        key=lambda entry: entry[0],
        default=None,
    )
    if winner is None:  # pragma: no cover -- unreachable while max_runs >= 1
        raise SystemExit("no banding was reachable; the band budget cannot be zero")

    # Walk the choices back out. Only the final band's (start, value) is
    # stored, so recover the rest by re-solving each prefix at one fewer band.
    assignment: dict[str, float] = {}
    j, b = n, None
    for candidate in range(1, max_runs + 1):
        entry = table[n][candidate]
        if entry is not None and entry[0] == winner[0]:
            b = candidate
            break
    assert b is not None
    while j > 0:
        entry = table[j][b]
        assert entry is not None
        _, start, value_index = entry
        for fixture in order[start:j]:
            assignment[fixture] = values[value_index]
        j, b = start, b - 1
    return winner[0], assignment


def _edges(order: list[str], values: dict[str, float], assigned: dict[str, object]) -> list[float]:
    """Return one threshold per run boundary, placed between the two fixtures.

    The midpoint is the max-margin choice, but a threshold is also read by
    people, so this prefers the roundest number that still separates the pair:
    the coarsest rounding of the midpoint that stays above the lower fixture
    and at or below the upper one. Bounds are exclusive, so landing *on* the
    upper fixture's value is correct -- that fixture belongs to the next band.
    """
    edges: list[float] = []
    for i in range(1, len(order)):
        if assigned[order[i]] == assigned[order[i - 1]]:
            continue
        low, high = values[order[i - 1]], values[order[i]]
        midpoint = (low + high) / 2
        for places in range(0, 5):
            candidate = round(midpoint, places)
            if low < candidate <= high:
                edges.append(candidate)
                break
        else:  # pragma: no cover -- 4dp always separates distinct sweep features
            edges.append(midpoint)
    return edges


def _bands(
    order: list[str], values: dict[str, float], assigned: dict[str, object]
) -> tuple[Band, ...]:
    """Turn a per-fixture assignment into an ordered, inf-terminated family."""
    edges = _edges(order, values, assigned)
    runs: list[object] = []
    for fixture in order:
        if not runs or runs[-1] != assigned[fixture]:
            runs.append(assigned[fixture])
    bounds = [*edges, math.inf]
    return tuple(Band(bound, value) for bound, value in zip(bounds, runs, strict=True))  # type: ignore[arg-type]


def fit(
    grid: Grid,
    feature_values: dict[str, dict[str, float]],
    budget: Budget = Budget(),
) -> Result:
    """Return the band set minimising total regret under the hard constraints."""
    by_stddev, by_dark = _orderings(grid, feature_values)
    stddev = {f: feature_values[f]["stddev"] for f in grid.fixtures}
    dark = {f: feature_values[f]["dark_pct"] for f in grid.fixtures}

    contrast_cuts = set(_cuttable(by_stddev, stddev))
    psm_assignments = _step_functions(
        by_dark, _cuttable(by_dark, dark), grid.psm_values, budget.psm
    )

    # Every (fixture, contrast, psm) cost, computed once rather than rebuilt
    # per psm assignment. Worth 4% and no more, measured: 3m19s to 3m10s at
    # the shipped 5x4 budget.
    #
    # Recorded because the 4% is the useful part of the result. `Grid.cost()`
    # looked like the hot spot and is not; the cost is `_best_partition`,
    # which runs ~5,000 tuple operations per psm assignment across ~174,000
    # assignments. Anyone trying to make this fit fast enough to sit in the
    # fast test loop needs to attack that -- vectorise the dynamic program,
    # or shrink the psm enumeration (psm 1 is provably dominated by psm 3,
    # scoring identically on every measured cell and losing the tie-break, so
    # dropping it from the value set is sound and worth ~2x on its own).
    # Hoisting the costs is not the answer, and now nobody has to find that
    # out twice.
    costs = {
        (fixture, psm): [grid.cost(fixture, contrast, psm) for contrast in grid.contrast_values]
        for fixture in by_stddev
        for psm in grid.psm_values
    }

    best: tuple[Cost, dict[str, int], dict[str, float]] | None = None
    for psm_by_fixture in psm_assignments:
        per_value_cost = [costs[(fixture, psm_by_fixture[fixture])] for fixture in by_stddev]
        cost, contrast_by_fixture = _best_partition(
            by_stddev, contrast_cuts, per_value_cost, grid.contrast_values, budget.contrast
        )
        if best is None or cost < best[0]:
            best = (cost, psm_by_fixture, contrast_by_fixture)

    assert best is not None
    cost, psm_by_fixture, contrast_by_fixture = best
    return Result(
        contrast_bands=_bands(by_stddev, stddev, contrast_by_fixture),
        psm_bands=_bands(by_dark, dark, psm_by_fixture),
        cost=cost,
        assignment={f: (contrast_by_fixture[f], psm_by_fixture[f]) for f in grid.fixtures},
    )


def select(bands: tuple[Band, ...], value: float) -> float | int:
    """Local copy of `tuning.select`, so the fitter can score a candidate.

    Deliberately not imported: `--check` compares a fresh fit against the
    committed module, and importing the thing under test to evaluate the
    thing under test would make a broken `select()` agree with itself.
    """
    for band in bands:
        if value < band.upper:
            return band.value
    raise ValueError(f"no band matched {value!r}: the last band must end at math.inf")


def apply_bands(
    result: Result, fixture: str, feature_values: dict[str, dict[str, float]]
) -> tuple[float, int]:
    """Return the (contrast, psm) a band set gives one fixture."""
    return (
        float(select(result.contrast_bands, feature_values[fixture]["stddev"])),
        int(select(result.psm_bands, feature_values[fixture]["dark_pct"])),
    )


def leave_one_out(
    rows: list[dict[str, object]],
    fixtures: list[str],
    feature_values: dict[str, dict[str, float]],
    budget: Budget = Budget(),
) -> tuple[float, dict[str, float]]:
    """Refit without each fixture in turn and score it with the bands that result.

    This replaces the held-out split, which brief 007 spent to repair
    kinema-theater-ad-1920. It is the weaker measure -- eight fits differing by
    one fixture are not eight independent experiments -- but it is the honest
    one available, and its gap from in-sample regret is what says whether the
    band shape has memorised the corpus.
    """
    per_fixture: dict[str, float] = {}
    for held in fixtures:
        remainder = [f for f in fixtures if f != held]
        partial = fit(Grid(rows, remainder), feature_values, budget)
        contrast, psm = apply_bands(partial, held, feature_values)
        full = Grid(rows, fixtures)
        per_fixture[held] = full.best[held] - full.score[(held, contrast, psm)]
    return sum(per_fixture.values()) / len(per_fixture), per_fixture


def read_features(path: Path = FEATURES_CSV) -> dict[str, dict[str, float]]:
    """Read the committed per-fixture pixel statistics."""
    with path.open(encoding="utf-8") as handle:
        return {
            row["fixture"]: {"stddev": float(row["stddev"]), "dark_pct": float(row["dark_pct"])}
            for row in csv.DictReader(handle)
        }


def fit_fixtures(split_name: str, rows: list[dict[str, object]]) -> tuple[list[str], list[str]]:
    """Return the swept fixture *filenames* for a split's fit and held-out stems."""
    swept = sorted({str(row["fixture"]) for row in rows})
    by_stem = {Path(name).stem: name for name in swept}
    fit_stems, held_stems = splits.split(split_name)
    missing = [stem for stem in fit_stems if stem not in by_stem]
    if missing:
        raise SystemExit(f"[splits.{split_name}] fits to {missing}, which the sweep does not cover")
    return (
        [by_stem[stem] for stem in fit_stems],
        [by_stem[stem] for stem in held_stems if stem in by_stem],
    )


def committed_bands() -> tuple[tuple[Band, ...], tuple[Band, ...]]:
    """Read the band values out of the shipped module, for `--check`."""
    from tetrak_ocr.backends import tuning

    return (
        tuple(Band(b.upper, b.value) for b in tuning.CONTRAST_BANDS),
        tuple(Band(b.upper, b.value) for b in tuning.PSM_BANDS),
    )


def _literal(text: str) -> str:
    """Render a string as a double-quoted Python literal.

    `repr()` would do, but it prefers single quotes and `ruff format` would
    rewrite every one of them on the next run -- so the generator would produce
    a file that the formatter immediately reports as unformatted.
    """
    return json.dumps(text, ensure_ascii=False)


def _band_members(bands: tuple[Band, ...], measured: dict[str, float]) -> list[list[str]]:
    """Return the fixtures falling in each band, by feature range.

    By *range*, not by value. Keying the annotation on the band's value was
    wrong whenever two bands shared one -- the 2026-09-29 fit puts contrast
    2.0 in two separate stddev ranges, and both comments then claimed every
    fixture set to 2.0, including ones forty points of stddev away. The
    comment exists to show what each edge was chosen from, so it has to be
    computed the way `select()` reads the bands.
    """
    out: list[list[str]] = []
    lower = 0.0
    for band in bands:
        out.append(sorted(f for f, value in measured.items() if lower <= value < band.upper))
        lower = band.upper
    return out


def _render_band_family(name: str, bands: tuple[Band, ...], members: list[list[str]]) -> str:
    """Render one band family as source, each band annotated with its fixtures.

    The annotation is the evidence, not decoration: a band whose comment says
    "moderately flat" cannot be checked, and goes stale the moment an edge
    moves. A band that names the fitted fixtures inside it is regenerated with
    the fit and says what the number was chosen from.
    """
    lines = [f"{name}: tuple[Band, ...] = ("]
    for band, inside in zip(bands, members, strict=True):
        bound = "math.inf" if math.isinf(band.upper) else repr(float(band.upper))
        note = ", ".join(Path(f).stem for f in inside) if inside else "no fitted fixture"
        # Above the band rather than trailing it: four fixture names do not fit
        # on one line, and a comment is the one thing `ruff format` will not
        # wrap for us.
        # rstrip: _wrap keeps the trailing space that concatenated string
        # literals need, and a comment needs the opposite.
        lines.extend(f"    # {chunk.rstrip()}" for chunk in _wrap(note, 74))
        lines.append(f"    Band({bound}, {band.value!r}),")
    lines.append(")")
    return "\n".join(lines)


def _render_provenance(provenance: dict[str, str]) -> str:
    lines = ["FIT_PROVENANCE: dict[str, str] = {"]
    for key, value in provenance.items():
        # Split at ruff's line length rather than at a threshold of our own.
        # `--write` is followed by `ruff format` in CI, and a generator that
        # disagrees with the formatter produces a file that is reformatted the
        # moment anyone checks it -- which makes every re-fit a two-commit job.
        inline = f"    {_literal(key)}: {_literal(value)},"
        if len(inline) <= RUFF_LINE_LENGTH:
            lines.append(inline)
        else:
            lines.append(f"    {_literal(key)}: (")
            lines.extend(f"        {_literal(chunk)}" for chunk in _wrap(value, 72))
            lines.append("    ),")
    lines.append("}")
    return "\n".join(lines)


def _wrap(text: str, width: int) -> list[str]:
    """Split a string into chunks at spaces, for concatenated source literals.

    Every chunk but the last keeps its trailing space, because adjacent string
    literals in the source are concatenated with nothing between them. The last
    one loses it -- a provenance field should not end in whitespace.
    """
    chunks: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current}{word} "
        if len(candidate) > width and current:
            chunks.append(current)
            current = f"{word} "
        else:
            current = candidate
    if current:
        chunks.append(current.rstrip())
    return chunks


def replace_generated(source: str, name: str, body: str) -> str:
    """Swap the text between one pair of generated markers.

    Marker-delimited rather than a whole-file rewrite, because the prose around
    each family explains what the *feature* means -- what `dark_pct` measures,
    why PSM 12 exists at all -- and none of that is an output of the fit. A
    generator that owned the file would delete it on every run.
    """
    begin = GENERATED_BEGIN.format(name=name)
    end = GENERATED_END.format(name=name)
    pattern = re.compile(rf"^{re.escape(begin)}\n.*?^{re.escape(end)}$", re.MULTILINE | re.DOTALL)
    if not pattern.search(source):
        raise SystemExit(f"{TUNING_PY.name} has no generated block for {name}")
    return pattern.sub(f"{begin}\n{body}\n{end}", source)


class Report(NamedTuple):
    """Everything the fit produced, assembled once for both outputs."""

    split: str
    result: Result
    grid: Grid
    features: dict[str, dict[str, float]]
    held_out: list[str]
    loo_mean: float
    loo_per_fixture: dict[str, float]
    current: dict[str, tuple[float, int]]
    budget: Budget

    @property
    def in_sample_mean_regret(self) -> float:
        return self.result.cost.regret / len(self.grid.fixtures)

    @property
    def gap(self) -> float:
        """Leave-one-out regret minus in-sample. The overfitting measure."""
        return self.loo_mean - self.in_sample_mean_regret

    def fitted_score(self, fixture: str) -> float:
        return self.grid.score[(fixture, *self.result.assignment[fixture])]

    def fitted_recall(self, fixture: str) -> float:
        return self.grid.recall[(fixture, *self.result.assignment[fixture])]

    def current_score(self, fixture: str) -> float:
        return self.grid.score[(fixture, *self.current[fixture])]

    @property
    def mean_char_sim(self) -> float:
        return sum(self.fitted_score(f) for f in self.grid.fixtures) / len(self.grid.fixtures)

    @property
    def regressions(self) -> list[str]:
        """Fixtures the fitted bands leave below plain Tesseract."""
        return [f for f in self.grid.fixtures if self.fitted_score(f) < self.grid.plain[f] - 1e-9]

    @property
    def unmet(self) -> list[str]:
        """Fixtures whose floor or required PSM the fit could not reach."""
        return [
            f
            for f in self.grid.fixtures
            if self.grid.cost(f, *self.result.assignment[f]).violations
        ]


def fit_bands(split_name: str = "wide-corpus", budget: Budget = Budget()) -> Result:
    """Fit one split and return just the bands, skipping leave-one-out.

    Separate from `build_report` because the leave-one-out pass refits once per
    fixture and dominates the runtime. `--check` and the test that guards
    against a hand-edited `tuning.py` only need the bands, and both want to be
    cheap enough to run in the fast loop.
    """
    rows = sweep.read()
    features = read_features()
    fit_names, _ = fit_fixtures(split_name, rows)
    _require_features(fit_names, features)
    return fit(Grid(rows, fit_names), features, budget)


def _require_features(fit_names: list[str], features: dict[str, dict[str, float]]) -> None:
    unmeasured = [f for f in fit_names if f not in features]
    if unmeasured:
        raise SystemExit(
            f"features.csv has no statistics for {unmeasured} -- re-run "
            "`python -m evaluation.ocr.calibration.features --write`"
        )


def build_report(split_name: str, budget: Budget = Budget()) -> Report:
    """Run the fit and the leave-one-out pass for one split."""
    rows = sweep.read()
    features = read_features()
    fit_names, held_names = fit_fixtures(split_name, rows)
    _require_features(fit_names, features)

    grid = Grid(rows, fit_names)
    result = fit(grid, features, budget)
    loo_mean, loo_per_fixture = leave_one_out(rows, fit_names, features, budget)

    contrast_bands, psm_bands = committed_bands()
    shipped = Result(contrast_bands, psm_bands, ZERO, {})
    current = {f: apply_bands(shipped, f, features) for f in fit_names}

    return Report(
        split=split_name,
        result=result,
        grid=grid,
        features=features,
        held_out=held_names,
        loo_mean=loo_mean,
        loo_per_fixture=loo_per_fixture,
        current=current,
        budget=budget,
    )


def provenance(report: Report) -> dict[str, str]:
    """The record that ships beside the bands.

    A band set without its corpus is not reproducible, and the fields here are
    chosen so that someone reading `tuning.py` alone can tell what the numbers
    saw, what they were optimised for, and where they still fall short.
    """
    stems = [Path(f).stem for f in report.grid.fixtures]
    held = [Path(f).stem for f in report.held_out]
    regressions = [Path(f).stem for f in report.regressions]
    unmet = [Path(f).stem for f in report.unmet]
    defects = []
    if regressions:
        defects.append(f"scores below plain tesseract on {', '.join(regressions)}")
    if unmet:
        defects.append(f"misses the brief 007 floor on {', '.join(unmet)}")
    return {
        "split": f"{report.split}, from evaluation/ocr/corpus/splits.toml",
        "fitted": ", ".join(stems),
        "not_fitted": (
            ", ".join(held)
            if held
            else (
                "nothing is held out: this split spends the held-out data to "
                "repair kinema-theater-ad-1920, so generalisation is measured "
                "by leave-one-out instead (brief 007, open question 2). PDFs "
                "are excluded structurally -- the bands never run on the PDF path"
            )
        ),
        "method": (
            "fitted by evaluation/ocr/calibration/fit.py from the committed "
            f"sweep, minimising mean regret in character similarity over "
            f"{len(stems)} rasters, at most {report.budget.contrast} contrast "
            f"and {report.budget.psm} psm bands. Do not edit these values by hand"
        ),
        "in_sample_mean_regret": f"{report.in_sample_mean_regret:.4f}",
        "leave_one_out_mean_regret": f"{report.loo_mean:.4f}",
        "generalisation_gap": (
            f"{report.gap:+.4f} -- leave-one-out minus in-sample; the overfitting measure"
        ),
        "mean_char_sim": f"{report.mean_char_sim:.4f}",
        # The corpus-level caveat belongs here, not only in the gap field: a
        # reader scanning for "what is wrong with these numbers" reads this
        # key, and "none" would be a fair answer to the wrong question.
        "known_defects": (
            "; ".join(defects)
            if defects
            else (
                "none on the fitted corpus -- but every fixture is in the fit "
                "set, so read generalisation_gap before trusting these bands "
                "on new material"
            )
        ),
    }


def render_module(report: Report, source: str) -> str:
    """Return `tuning.py` with its three generated blocks refreshed."""
    stddev = {f: report.features[f]["stddev"] for f in report.grid.fixtures}
    dark = {f: report.features[f]["dark_pct"] for f in report.grid.fixtures}

    source = replace_generated(
        source,
        "CONTRAST_BANDS",
        _render_band_family(
            "CONTRAST_BANDS",
            report.result.contrast_bands,
            _band_members(report.result.contrast_bands, stddev),
        ),
    )
    source = replace_generated(
        source,
        "PSM_BANDS",
        _render_band_family(
            "PSM_BANDS", report.result.psm_bands, _band_members(report.result.psm_bands, dark)
        ),
    )
    return replace_generated(source, "FIT_PROVENANCE", _render_provenance(provenance(report)))


def table(report: Report, *, show_now: bool = True) -> list[str]:
    """The fit as Markdown rows, shared by stdout and fit.md.

    `show_now` is what the *committed* bands give each fixture, which is the
    before-and-after when the fitter runs without `--write`. It is dropped
    from `fit.md`, because that file is written after the module has been
    regenerated: the column would equal `fitted` by construction and read as
    a comparison when it is an identity.
    """
    now = "now | " if show_now else ""
    now_rule = "---:|" if show_now else ""
    lines = [
        f"| Fixture | stddev | dark_pct | plain | {now}fitted cell | fitted | word | "
        "regret | LOO regret |",
        f"|---|---:|---:|---:|{now_rule}:--|---:|---:|---:|---:|",
    ]
    for fixture in report.grid.fixtures:
        contrast, psm = report.result.assignment[fixture]
        fitted = report.fitted_score(fixture)
        stats = report.features[fixture]
        lines.append(
            f"| `{Path(fixture).stem}` | {stats['stddev']:.1f} | {stats['dark_pct']:.1f} | "
            f"{report.grid.plain[fixture]:.4f} | "
            + (f"{report.current_score(fixture):.4f} | " if show_now else "")
            + f"c{contrast:g} psm{psm} | {fitted:.4f} | "
            f"{report.fitted_recall(fixture):.4f} | "
            f"{report.grid.best[fixture] - fitted:.4f} | "
            f"{report.loo_per_fixture[fixture]:.4f} |"
        )
    return lines


def summary(report: Report, *, show_now: bool = True) -> list[str]:
    """The numbers that decide whether the fit is acceptable."""
    plain_mean = sum(report.grid.plain.values()) / len(report.grid.fixtures)
    now_mean = sum(report.current_score(f) for f in report.grid.fixtures) / len(
        report.grid.fixtures
    )
    oracle = sum(report.grid.best.values()) / len(report.grid.fixtures)
    now = f"now {now_mean:.4f}   " if show_now else ""
    target = "met" if report.mean_char_sim >= TARGET_MEAN_CHAR_SIM else "MISSED"
    regressions = (
        "none" if not report.regressions else ", ".join(Path(f).stem for f in report.regressions)
    )
    unmet = "none" if not report.unmet else ", ".join(Path(f).stem for f in report.unmet)
    return [
        f"mean char_sim        plain {plain_mean:.4f}   {now}"
        f"fitted {report.mean_char_sim:.4f}   oracle {oracle:.4f}",
        f"target >= {TARGET_MEAN_CHAR_SIM}        {target}",
        f"worse than plain     {regressions}",
        f"floors not met       {unmet}",
        f"mean regret          in-sample {report.in_sample_mean_regret:.4f}   "
        f"leave-one-out {report.loo_mean:.4f}   gap {report.gap:+.4f}",
    ]


def write_markdown(report: Report) -> None:
    """Write the evidence file beside the sweep it was fitted from."""
    lines = [
        "# Band fit",
        "",
        "Generated by `python -m evaluation.ocr.calibration.fit --write`. Do not edit.",
        "",
        f"Split `{report.split}`, fitted from `sweep.csv` by minimising mean regret in",
        "character similarity. `plain` is Tesseract's own defaults -- the sweep's",
        "(2.0, 3) cell, which reproduces the benchmark's `tesseract` column exactly.",
        "`oracle` is the ceiling a perfect per-fixture selector would reach.",
        "",
        *table(report, show_now=False),
        "",
        "## Result",
        "",
        "```text",
        *summary(report, show_now=False),
        "```",
        "",
        "## Bands",
        "",
        "| Feature | Range | Setting |",
        "|---|---|---:|",
    ]
    for feature, setting, bands in (
        ("stddev", "contrast", report.result.contrast_bands),
        ("dark_pct", "psm", report.result.psm_bands),
    ):
        lower = 0.0
        for band in bands:
            span = (
                f"{feature} >= {lower:g}"
                if math.isinf(band.upper)
                else f"{lower:g} <= {feature} < {band.upper:g}"
            )
            lines.append(f"| `{feature}` | {span} | {setting} {band.value} |")
            lower = band.upper
    lines.append("")
    FIT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def check(result: Result, split_name: str) -> int:
    """Compare the committed bands against a fresh fit from the committed sweep.

    The point of a generated artefact is that it can be re-derived, and this is
    the re-derivation. It fails on a hand-edit of `tuning.py`, on a sweep that
    has moved underneath it, and on a change to the fitter that would produce
    different bands -- all three of which should cost a visible diff.
    """
    committed_contrast, committed_psm = committed_bands()
    problems = []
    if committed_contrast != result.contrast_bands:
        problems.append(
            f"CONTRAST_BANDS\n    committed {list(committed_contrast)}\n"
            f"    fitted    {list(result.contrast_bands)}"
        )
    if committed_psm != result.psm_bands:
        problems.append(
            f"PSM_BANDS\n    committed {list(committed_psm)}\n"
            f"    fitted    {list(result.psm_bands)}"
        )
    if problems:
        print(
            "tuning.py does not match a fresh fit from the committed sweep:\n  "
            + "\n  ".join(problems)
            + "\n\nRe-run `python -m evaluation.ocr.calibration.fit --write`.",
            file=sys.stderr,
        )
        return 1
    print(f"tuning.py matches a fresh fit on split {split_name!r}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split",
        default="wide-corpus",
        help=(
            "which split to fit (default: wide-corpus, the 2026-09-28 corpus with four "
            "rasters held back). all-rasters and original-corpus are frozen historical "
            "records -- see evaluation/ocr/corpus/splits.toml"
        ),
    )
    parser.add_argument(
        "--write", action="store_true", help="regenerate tuning.py and write fit.md"
    )
    parser.add_argument(
        "--max-contrast-bands",
        type=int,
        default=MAX_CONTRAST_BANDS,
        help=(
            "band budget for contrast (default: %(default)s, the shipped shape). "
            "Lower it to trade in-sample regret for a smaller leave-one-out gap"
        ),
    )
    parser.add_argument(
        "--max-psm-bands",
        type=int,
        default=MAX_PSM_BANDS,
        help="band budget for psm (default: %(default)s, the shipped shape)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if the committed bands are not what a fresh fit produces",
    )
    args = parser.parse_args(argv)
    if args.write and args.check:
        parser.error("--write and --check do opposite things; pick one")

    if args.max_contrast_bands < 1 or args.max_psm_bands < 1:
        # Without this, a budget of 0 enumerates no assignments and the search
        # trips its own `assert best is not None` -- an internal error for what
        # is a plain bad argument.
        parser.error(
            "band budgets must be at least 1; a family needs somewhere to put every fixture"
        )

    budget = Budget(args.max_contrast_bands, args.max_psm_bands)
    # Against the module globals, not `Budget()`. A NamedTuple binds its
    # defaults at class-definition time, so `Budget()` is a snapshot of these
    # taken at import and stops tracking them the moment anything changes
    # them -- which is what the tests do to keep a mechanism test from running
    # the full three-minute search.
    shipped = Budget(MAX_CONTRAST_BANDS, MAX_PSM_BANDS)
    if args.write and budget != shipped:
        parser.error(
            "--write regenerates the shipped module, so it only accepts the "
            f"shipped band budget ({shipped}); drop the budget flags, or "
            "change MAX_CONTRAST_BANDS / MAX_PSM_BANDS and say why in the commit"
        )

    if args.check:
        return check(fit_bands(args.split, budget), args.split)

    report = build_report(args.split, budget)

    print(f"Split {args.split!r}: {len(report.grid.fixtures)} fixtures, {budget}\n")
    for line in table(report):
        print(line)
    print()
    for line in summary(report):
        print(line)
    print()
    for feature, setting, bands in (
        ("stddev", "contrast", report.result.contrast_bands),
        ("dark_pct", "psm", report.result.psm_bands),
    ):
        rendered = ", ".join(
            f"<{'inf' if math.isinf(b.upper) else f'{b.upper:g}'} -> {b.value}" for b in bands
        )
        print(f"{setting:<9} from {feature:<9} {rendered}")

    if args.write:
        # The search minimises violations lexicographically rather than
        # refusing to answer, so an infeasible problem still returns its
        # least-bad banding. That is right for a diagnostic run -- it shows
        # which constraint is unreachable and by how much -- and wrong for
        # --write, which would otherwise replace a valid shipped band set
        # with one known to break the floors. Print the diagnosis, write
        # nothing, and fail.
        if report.unmet:
            print(
                "\nRefusing to write: no banding satisfies the hard constraints.\n"
                "  unmet: " + ", ".join(Path(f).stem for f in report.unmet) + "\n"
                "Each fixture above misses its floor in brief 007, falls below plain\n"
                "tesseract, or misses the PSM the fit requires of it. Re-run without\n"
                "--write to see the table, then widen the sweep grid, revisit the\n"
                "constraints, or raise the band budget -- but do not ship this.",
                file=sys.stderr,
            )
            return 1

        source = TUNING_PY.read_text(encoding="utf-8")
        TUNING_PY.write_text(render_module(report, source), encoding="utf-8")
        write_markdown(report)
        print(f"\nWrote {TUNING_PY.name} and {FIT_MD.name}")

        if report.mean_char_sim < TARGET_MEAN_CHAR_SIM:
            # A warning, not a refusal: the corpus mean is a stated goal that
            # moves as fixtures are added, not a per-fixture guarantee, and a
            # wider corpus could legitimately fail it while every constraint
            # holds.
            print(
                f"\nWarning: mean char_sim {report.mean_char_sim:.4f} is below the "
                f"{TARGET_MEAN_CHAR_SIM} target in brief 007.",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
