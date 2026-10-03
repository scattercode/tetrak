"""Tests for the corpus manifest.

Unmarked, so they run in the fast loop: this is TOML parsing and set algebra,
with no OCR anywhere near it.

These exist to make a documented rule mechanical. `CLAUDE.md` says the held-out
fixtures must not be folded into a re-fit without saying so, and until now that
was advice. A new scan now fails CI until it is classified, and promoting a
held-out fixture costs a visible diff in `splits.toml`.
"""

from pathlib import Path

import pytest

# evaluation/ is not an installed package. conftest puts the repository root on
# sys.path, which is what makes this import work -- the same route
# test_harness_save.py takes to reach the harness.
from evaluation.ocr.calibration import splits


def test_the_manifest_accounts_for_the_corpus() -> None:
    """Every split classifies every fixture on disk. This is the guard."""
    splits.validate()


def test_every_split_names_something_to_fit() -> None:
    """A split with an empty fit set would silently fit to nothing."""
    for name in splits.split_names():
        fit, _ = splits.split(name)
        assert fit, f"[splits.{name}] has no fit fixtures"


def test_the_pdf_is_excluded_from_fitting() -> None:
    """The bands never run on the PDF path, so no split may learn from it."""
    excluded = splits.excluded()
    assert "king-of-kings-souvenir-1927" in excluded

    for name in splits.split_names():
        fit, held_out = splits.split(name)
        assert not set(fit) & excluded
        assert not set(held_out) & excluded


def test_the_original_split_holds_back_the_two_later_tiffs() -> None:
    """The baseline split must match what the shipped bands actually saw.

    Both TIFFs arrived on 17 August 2026, after the bands were fitted. If they
    ever appear in this split's fit set, the "honest baseline" stops being one.

    Membership, not equality. This asserted `set(held_out) == {the two TIFFs}`
    until the 28 September widening, which was the same assertion while the
    corpus could not grow and an over-specified one afterwards: every fixture
    added since is held out from this split by definition, so an exact match
    fails on corpus growth while saying nothing about the property that
    matters. What matters is that the fit stays the six.
    """
    fit, held_out = splits.split("original-corpus")
    assert {"hollywood-music-box-playbill-1926", "kinema-theater-ad-1920"} <= set(held_out)
    assert len(fit) == 6, "the shipped bands were fitted to six rasters, not seven"
    assert not {"hollywood-music-box-playbill-1926", "kinema-theater-ad-1920"} & set(fit)


def test_publication_is_opt_in() -> None:
    """A fixture is calibration-only until the manifest names it.

    The corpus is growing to widen calibration and the research pages must not
    grow with it, so the site reads this list rather than the directory.
    """
    on_disk = splits.corpus_stems()
    assert splits.published() <= on_disk

    # Held until the fourteen fixtures added on 22 August 2026 (excluded from
    # every split -- see splits.toml), which is the first time published()
    # and on_disk have actually diverged. This is that deletion, not a
    # loosening: what is checked below (every published stem exists, and
    # every originally-published stem is still published) is what stayed
    # true when it happened.
    originally_published = {
        "carthay-circle-postcard-back",
        "carthay-circle-premiere",
        "graumans-chinese-theatre",
        "hollywood-music-box-playbill-1926",
        "inside-facts-1930-cover",
        "inside-facts-1930-page-six",
        "kar-mi-troupe-poster",
        "kinema-theater-ad-1920",
        "king-of-kings-souvenir-1927",
    }
    assert originally_published <= splits.published()


def test_validate_rejects_an_unclassified_fixture() -> None:
    """The guard has to actually fail, not merely exist."""
    manifest = splits.load()
    with pytest.raises(splits.ManifestError, match="does not classify"):
        splits.validate(manifest, images_dir=_corpus_plus_one())


def _corpus_plus_one(tmp: Path | None = None) -> Path:
    """A corpus directory with one extra, unclassified scan in it."""
    import tempfile

    staging = Path(tmp or tempfile.mkdtemp())
    for stem in splits.corpus_stems():
        (staging / f"{stem}.png").touch()
    (staging / "a-newly-sourced-scan.png").touch()
    return staging


@pytest.mark.slow
def test_the_shipped_bands_are_what_the_committed_sweep_produces() -> None:
    """`tuning.py` is generated. This is the re-derivation.

    It fails on a hand-edit of the band values, on a sweep that has moved
    underneath them, and on a change to the fitter that would produce
    different bands. All three should cost a visible diff rather than leaving
    the module quietly disagreeing with the evidence it cites.

    Marked `slow` on 2026-09-29, reluctantly. It ran in two seconds at the
    4x3 budget and takes over three minutes at 5x4, because the psm
    enumeration grows steeply with the band count and the fit set. It runs no
    OCR, so the mark is a lie about *why* it is slow, but `pytest -m "not
    slow"` is the loop everyone actually runs and a three-minute fast loop
    stops being one.

    The guard is not lost: `.github/workflows/ci.yml` runs
    `fit.py --check`, which is this assertion by another route, as its own
    step. If that step is ever removed, unmark this.
    """
    from evaluation.ocr.calibration import fit

    result = fit.fit_bands()
    committed_contrast, committed_psm = fit.committed_bands()

    assert committed_contrast == result.contrast_bands, (
        "CONTRAST_BANDS is not what a fresh fit produces -- run "
        "`python -m evaluation.ocr.calibration.fit --write`"
    )
    assert committed_psm == result.psm_bands, (
        "PSM_BANDS is not what a fresh fit produces -- run "
        "`python -m evaluation.ocr.calibration.fit --write`"
    )


def test_the_fitter_respects_the_thresholds_ci_actually_enforces() -> None:
    """The fitter's copy of the CI gate must match the gate.

    The fit optimises character similarity, so nothing in the objective stops
    it trading word recall away -- and it tried to: the unconstrained optimum
    gives carthay-circle-premiere contrast 3.5, worth +0.18 character
    similarity and a word recall of 0.7857 against a gate of 0.80. The gate is
    a constraint in `fit.py` for that reason, and a second copy of a threshold
    is a thing that drifts, so this pins the two together.
    """
    from evaluation.ocr.calibration import fit
    from tests.ocr import test_thresholds

    assert fit.CI_CHARACTER_THRESHOLD == test_thresholds.CHARACTER_SIMILARITY_THRESHOLD
    assert fit.CI_WORD_RECALL_THRESHOLD == test_thresholds.WORD_RECALL_THRESHOLD

    # Which fixtures the gate actually binds on: every swept raster the
    # threshold test does not mark xfail. Derived, so that marking a fixture
    # xfail -- or taking one off the list after a re-fit repairs it -- fails
    # here until the fitter is told too.
    swept = {Path(str(row["fixture"])).stem for row in fit.sweep.read()}
    assert {Path(name).stem for name in fit.CI_GATED} == (
        swept - test_thresholds.KNOWN_TESSERACT_LIMITATIONS
    )


def test_the_dynamic_program_agrees_with_brute_force() -> None:
    """The fitter claims a global optimum. This checks the claim.

    `fit()` enumerates the psm assignments and solves the contrast banding by
    dynamic program for each, which is what makes an exact search cheap. The
    saving is only sound if the DP really returns the best banding, so this
    brute-forces the same problem by enumerating *both* families and comparing
    the objective.

    A synthetic grid, not the corpus: random-looking scores with no structure
    are harder for a DP bug to survive than real ones, where a greedy answer
    is often right by luck. Deterministic, because a fitter that fails once a
    fortnight is worse than one that fails always.
    """
    import random

    from evaluation.ocr.calibration import fit as fitter

    contrasts = [1.0, 2.0, 3.0]
    psms = [3, 6]
    names = [f"f{i}.png" for i in range(5)]
    rng = random.Random(20260927)

    rows: list[dict[str, object]] = []
    for name in names:
        for contrast in contrasts:
            for psm in psms:
                rows.append(
                    {
                        "fixture": name,
                        "contrast": contrast,
                        "psm": psm,
                        # Rounded to 4dp like the real sweep, so exact ties are
                        # as reachable here as they are there.
                        "char_sim": round(rng.random(), 4),
                        "word_recall": 1.0,
                        "seconds": 0.1,
                    }
                )
    # The baseline cell must exist: Grid reads it for the never-worse-than-plain
    # floor. 2.0/3 is in the grid above.
    features = {
        name: {"stddev": float(i * 10 + 5), "dark_pct": float((len(names) - i) * 7)}
        for i, name in enumerate(names)
    }

    budget = fitter.Budget(contrast=3, psm=2)
    grid = fitter.Grid(rows, names)
    got = fitter.fit(grid, features, budget)

    by_stddev = sorted(names, key=lambda n: features[n]["stddev"])
    by_dark = sorted(names, key=lambda n: features[n]["dark_pct"])
    best: fitter.Cost | None = None
    for psm_map in fitter._step_functions(by_dark, list(range(1, len(names))), psms, budget.psm):
        for contrast_map in fitter._step_functions(
            by_stddev, list(range(1, len(names))), contrasts, budget.contrast
        ):
            total = fitter.ZERO
            for name in names:
                total = total + grid.cost(name, contrast_map[name], psm_map[name])
            if best is None or total < best:
                best = total

    assert best is not None
    assert got.cost == best, f"dynamic program found {got.cost}, brute force {best}"


def test_the_fitted_bands_place_every_fixture_where_the_fit_intended() -> None:
    """The bands must reproduce the assignment they were derived from.

    `fit()` chooses a (contrast, psm) pair per fixture and `_bands()` turns
    that into thresholds. Those are two representations of one answer, and the
    edge placement is where they could come apart -- a bound landing on the
    wrong side of a fixture would silently give it a different configuration
    from the one the objective scored.
    """
    from evaluation.ocr.calibration import fit as fitter

    # A small budget deliberately: this checks that `_bands()` and `select()`
    # agree about where an edge falls, which is a property of the machinery
    # and not of the shipped numbers. Fitting at the shipped 5x4 would make a
    # mechanism test take three minutes to say the same thing.
    budget = fitter.Budget(contrast=3, psm=3)
    result = fitter.fit_bands(budget=budget)
    features = fitter.read_features()

    for fixture, intended in result.assignment.items():
        assert fitter.apply_bands(result, fixture, features) == intended, (
            f"{fixture} was fitted at {intended} but the bands give it "
            f"{fitter.apply_bands(result, fixture, features)}"
        )


def test_write_refuses_when_no_banding_meets_the_constraints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An infeasible fit must not overwrite the shipped bands.

    The search minimises violations lexicographically rather than refusing to
    answer, so it always returns *something* -- which is right for a
    diagnostic run and dangerous for `--write`. Without this guard a widened
    sweep or a new fixture could quietly replace a valid band set with one
    known to break brief 007's floors, and `--check` would then agree with it
    ever after, because the module and the sweep would match.
    """
    from evaluation.ocr.calibration import fit as fitter

    shipped = tmp_path / "tuning.py"
    original = fitter.TUNING_PY.read_text(encoding="utf-8")
    shipped.write_text(original, encoding="utf-8")
    monkeypatch.setattr(fitter, "TUNING_PY", shipped)
    monkeypatch.setattr(fitter, "FIT_MD", tmp_path / "fit.md")

    # kar-mi-troupe-poster tops out at 0.0559 across the entire 42-cell sweep:
    # a chromolithograph nothing reads. No banding can put it above 0.9.
    monkeypatch.setitem(fitter.FIXTURE_FLOORS, "kar-mi-troupe-poster.jpg", 0.9)
    # Shrink the search for the same reason as above -- the refusal is what is
    # under test, not the shipped band shape. `main()` reads these globals when
    # it builds its argument defaults, so patching them here is enough.
    monkeypatch.setattr(fitter, "MAX_CONTRAST_BANDS", 3)
    monkeypatch.setattr(fitter, "MAX_PSM_BANDS", 3)

    # Stub the leave-one-out pass. `--write` builds the full report -- twelve
    # refits -- before it reaches the refusal, and none of that is what this
    # test is about. Without the stub a test of one `if` costs seventy
    # seconds of the fast loop.
    monkeypatch.setattr(
        fitter,
        "leave_one_out",
        lambda rows, fixtures, features, budget=None: (0.0, dict.fromkeys(fixtures, 0.0)),
    )

    assert fitter.main(["--write"]) == 1
    assert "Refusing to write" in capsys.readouterr().err
    assert shipped.read_text(encoding="utf-8") == original, "the shipped bands were overwritten"
    assert not (tmp_path / "fit.md").exists()
