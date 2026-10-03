"""Tests for the Tesseract auto-configuration bands.

These are unmarked, so they run in the fast loop (`pytest -m "not slow"`).
`tuning` imports nothing but the standard library, which is the point: the
bands can be checked with no OCR stack installed at all.

The band *values* are a fit and will change when the calibration toolkit
re-fits them. What is pinned here is the band *machinery* -- the boundary
semantics, the terminator, and the types the backend depends on -- plus a
guard that the shipped bands still describe the corpus they claim to.
"""

import math

import pytest

from tetrak_ocr.backends.tuning import (
    CONTRAST_BANDS,
    FIT_PROVENANCE,
    PSM_BANDS,
    Band,
    describe,
    select,
)


@pytest.mark.parametrize("bands", [CONTRAST_BANDS, PSM_BANDS])
def test_bands_are_ordered_and_terminated(bands: tuple[Band, ...]) -> None:
    """Bounds ascend and the family ends at infinity, so every input lands."""
    uppers = [band.upper for band in bands]
    assert uppers == sorted(uppers), f"bands out of order: {uppers}"
    assert math.isinf(uppers[-1]), "the last band must be terminated by math.inf"
    assert not any(math.isinf(u) for u in uppers[:-1]), "only the last band may be infinite"


def test_select_treats_bounds_as_exclusive() -> None:
    """A value *equal* to a bound falls into the next band, not that one.

    This is the off-by-one the `if stddev < 30` chain encoded implicitly and
    nothing tested. Getting it backwards would move every fixture sitting on a
    boundary into the neighbouring band, and the scores would move with them.

    Against a synthetic family, not the shipped one. This used to assert
    `select(CONTRAST_BANDS, 30.0) == 3.0`, which reads as a test of `select()`
    and is really a test of where the fit put an edge -- so it failed on the
    first honest re-fit, having found no bug. The semantics are the thing that
    must not move; the edges are output.
    """
    family = (Band(10.0, "low"), Band(20.0, "mid"), Band(math.inf, "high"))

    assert select(family, 9.999) == "low"
    assert select(family, 10.0) == "mid", "a value equal to a bound belongs to the next band"
    assert select(family, 19.999) == "mid"
    assert select(family, 20.0) == "high"
    assert select(family, 1e9) == "high"


def test_select_agrees_with_the_shipped_bands_at_their_own_edges() -> None:
    """The same rule, exercised on whatever the current fit produced.

    Derived from the bands rather than written out, so it keeps testing the
    boundary behaviour after a re-fit moves every edge.
    """
    for bands in (CONTRAST_BANDS, PSM_BANDS):
        for lower, upper in zip(bands[:-1], bands[1:], strict=True):
            assert select(bands, lower.upper - 1e-9) == lower.value
            assert select(bands, lower.upper) == upper.value


def test_select_rejects_an_unterminated_family() -> None:
    """A family that does not end at infinity is malformed, not silently None."""
    with pytest.raises(ValueError, match="math.inf"):
        select((Band(10.0, 1.0),), 99.0)


def test_psm_stays_an_int() -> None:
    """PSM is interpolated into `--psm {psm}`; 12.0 is not a segmentation mode."""
    for band in PSM_BANDS:
        assert isinstance(band.value, int), f"{band} must carry an int"


def test_suggest_matches_the_bands_it_is_built_from() -> None:
    """suggest() is the two selects, in that order, coerced to (float, int).

    Checked against the bands rather than against a remembered pair. The
    remembered pair was `(3.0, 3)` for inside-facts-1930-page-six, which the
    2026-09-27 re-fit changed to `(1.0, 3)` -- the assertion caught the re-fit,
    not a fault in `suggest()`. What matters here is that `suggest()` does not
    quietly transpose the two families or the two features.
    """
    from tetrak_ocr.backends.tuning import suggest

    for stddev, dark_pct in ((32.4, 22.5), (85.2, 42.9), (0.0, 0.0), (1e6, 100.0)):
        contrast, psm = suggest(stddev=stddev, dark_pct=dark_pct)
        assert contrast == select(CONTRAST_BANDS, stddev)
        assert psm == select(PSM_BANDS, dark_pct)
        assert isinstance(contrast, float)
        assert isinstance(psm, int)


def test_describe_covers_every_band_with_no_gaps() -> None:
    """The published table must tile each feature's range from zero upwards."""
    rows = describe()
    assert len(rows) == len(CONTRAST_BANDS) + len(PSM_BANDS)

    for feature in ("stddev", "dark_pct"):
        spans = [(r["lower"], r["upper"]) for r in rows if r["feature"] == feature]
        assert spans[0][0] == 0.0, f"{feature} table must start at zero"
        assert math.isinf(spans[-1][1]), f"{feature} table must run to infinity"
        for (_, upper), (lower, _) in zip(spans[:-1], spans[1:], strict=True):
            assert upper == lower, f"gap or overlap in the {feature} table at {upper}"


def test_provenance_names_the_corpus_it_was_fitted_to() -> None:
    """A band set without its corpus is not reproducible.

    Weak on purpose: this asserts the record exists and is populated, not what
    it says. The fitter rewrites it wholesale, and a test pinning its prose
    would fail on every re-fit for no benefit.
    """
    assert FIT_PROVENANCE.keys() >= {"split", "fitted", "method"}
    assert all(FIT_PROVENANCE.values()), "no provenance field may be blank"
