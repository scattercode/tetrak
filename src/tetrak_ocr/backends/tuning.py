"""Auto-configuration bands for the Tesseract backend.

`analyse_image()` picks a contrast factor and a page segmentation mode per image
from two cheap pixel statistics. This module holds the thresholds that mapping
uses, as data rather than as a chain of `if`/`elif`, so that they can be fitted,
published and tested without importing the backend.

**Standard library only, deliberately.** Nothing here imports Pillow,
pytesseract or `tesseract.py`. That is what lets the fast test suite, the band
fitter under `evaluation/ocr/calibration/` and the API documentation generator
all import it with no OCR stack installed.

The bands are a *fit*, not a set of opinions, and `FIT_PROVENANCE` records which
corpus produced them and how well it generalised.

**The three blocks below are generated.** They come from
`python -m evaluation.ocr.calibration.fit --write`, which chooses the edges by
minimising mean regret over the committed configuration sweep. Editing the
numbers by hand makes the module disagree with the sweep it claims to come
from, and `fit.py --check` will say so. Re-fit instead — see
brief 007 (the calibration toolkit).

Reading the bands
-----------------
Each band is an upper bound and the value to use below it. Bounds are
**exclusive**, matching the `<` comparisons these replaced, and the last band in
each family is terminated by `math.inf` so every input lands somewhere. Given
`Band(30.0, 3.5)` followed by `Band(55.0, 3.0)`:

    stddev 29.9  ->  contrast 3.5      (below the first bound, 30)
    stddev 30.0  ->  contrast 3.0      (30 is not < 30)

Those two bounds are an illustration. The fitted ones are below, and they move.
"""

import math
from typing import NamedTuple


class Band(NamedTuple):
    """One threshold in a band family: use `value` while below `upper`."""

    upper: float
    # PSM values must stay `int`. They are interpolated into Tesseract's
    # command line as `--psm {psm}`, and 12.0 is not a page segmentation mode.
    value: float | int


# Contrast enhancement factor, chosen from the greyscale standard deviation.
#
# The premise was that a low stddev means a tonally flat image -- ink and
# background at similar brightness -- which wants *more* contrast to separate
# them. The measurement does not support it. The flattest fixture in the
# corpus, inside-facts-1930-page-six at 32.4, reads best at contrast 1.0:
# no enhancement at all, and 0.09 better than the 3.0 the hand-fitted bands
# gave it. The values below are not monotonic in stddev and there is no
# reason to expect them to be.
#
# Why that is plausible rather than a fluke: page six is dense small type on
# aged newsprint, where boosting contrast thickens the strokes until adjacent
# characters merge. Flatness and fragility travel together in this corpus.
# Two fixtures is not enough to call that a rule, so it is recorded as an
# observation and the fit is left to the sweep.
# --- BEGIN GENERATED: CONTRAST_BANDS ---
CONTRAST_BANDS: tuple[Band, ...] = (
    # inside-facts-1930-page-six
    Band(34.0, 2.0),
    # carthay-circle-postcard-back
    Band(40.0, 2.5),
    # chinese-theatre-triptych-postcard
    Band(46.0, 2.0),
    # bancroft-magician-poster, graumans-chinese-theatre,
    # hollywood-music-box-playbill-1926, inside-facts-1930-cover,
    # parlor-match-poster
    Band(67.0, 3.0),
    # carthay-circle-premiere, greek-theatre-night, kar-mi-troupe-poster,
    # kinema-theater-ad-1920
    Band(math.inf, 2.0),
)
# --- END GENERATED: CONTRAST_BANDS ---

# Page segmentation mode, chosen from `dark_pct`: the share of the frame below
# luminance 128.
#
# Read `dark_pct` as "how much of the frame is not paper", NOT as text density
# -- it cannot tell ink from imagery. A night-scene postcard reads 56% dark
# because of the photograph, not because it is covered in text. That is the
# useful signal anyway: a frame dominated by a dark image has little page
# structure for layout analysis to work with, however the darkness got there.
#
# PSM 3  -- fully automatic page segmentation; finds and orders columns
# PSM 6  -- assumes one uniform block; right when there is no real layout
# PSM 12 -- sparse text with orientation detection; the OSD is what reads the
#           90-degree rotated imprint on a postcard reverse
# --- BEGIN GENERATED: PSM_BANDS ---
PSM_BANDS: tuple[Band, ...] = (
    # carthay-circle-postcard-back
    Band(10.0, 12),
    # chinese-theatre-triptych-postcard, graumans-chinese-theatre,
    # hollywood-music-box-playbill-1926, inside-facts-1930-cover,
    # inside-facts-1930-page-six, kinema-theater-ad-1920, parlor-match-poster
    Band(49.0, 3),
    # bancroft-magician-poster, carthay-circle-premiere, kar-mi-troupe-poster
    Band(69.2, 6),
    # greek-theatre-night
    Band(math.inf, 3),
)
# --- END GENERATED: PSM_BANDS ---

# Where these numbers came from. Kept beside them because a band set without its
# corpus is not reproducible: which fixtures the fit saw, what it optimised, and
# -- the field to read first -- how far leave-one-out regret sits above
# in-sample, which is how much of the fit is memory rather than signal.
# --- BEGIN GENERATED: FIT_PROVENANCE ---
FIT_PROVENANCE: dict[str, str] = {
    "split": "wide-corpus, from evaluation/ocr/corpus/splits.toml",
    "fitted": (
        "bancroft-magician-poster, carthay-circle-postcard-back, "
        "carthay-circle-premiere, chinese-theatre-triptych-postcard, "
        "graumans-chinese-theatre, greek-theatre-night, "
        "hollywood-music-box-playbill-1926, inside-facts-1930-cover, "
        "inside-facts-1930-page-six, kar-mi-troupe-poster, "
        "kinema-theater-ad-1920, parlor-match-poster"
    ),
    "not_fitted": (
        "hollywood-boulevard-east, hollywood-boulevard-west, "
        "over-the-fence-poster, thurston-magician-poster"
    ),
    "method": (
        "fitted by evaluation/ocr/calibration/fit.py from the committed sweep, "
        "minimising mean regret in character similarity over 12 rasters, at most "
        "5 contrast and 4 psm bands. Do not edit these values by hand"
    ),
    "in_sample_mean_regret": "0.0760",
    "leave_one_out_mean_regret": "0.2650",
    "generalisation_gap": "+0.1890 -- leave-one-out minus in-sample; the overfitting measure",
    "mean_char_sim": "0.5796",
    "known_defects": (
        "none on the fitted corpus -- but every fixture is in the fit set, so "
        "read generalisation_gap before trusting these bands on new material"
    ),
}
# --- END GENERATED: FIT_PROVENANCE ---


def select(bands: tuple[Band, ...], value: float) -> float | int:
    """Return the value of the first band whose upper bound `value` is below.

    Bounds are exclusive, so a value equal to a bound falls into the *next*
    band: with the contrast bands, 29.9 gives 3.5 and 30.0 gives 3.0.

    Args:
        bands: A band family, ordered by ascending bound and terminated by
            `math.inf`.
        value: The measured feature.

    Returns:
        The band's configured value.

    Raises:
        ValueError: If no band matched, which means the family is not
            terminated by `math.inf` and is therefore malformed.
    """
    for band in bands:
        if value < band.upper:
            return band.value
    raise ValueError(f"no band matched {value!r}: the last band must be terminated by math.inf")


def suggest(stddev: float, dark_pct: float) -> tuple[float, int]:
    """Return the (contrast, psm) pair for a pair of measured image statistics.

    Args:
        stddev:   Standard deviation of the greyscale image.
        dark_pct: Percentage of pixels below luminance 128.

    Returns:
        A (contrast, psm) tuple. `psm` is an int, because it is interpolated
        into Tesseract's command line.
    """
    return float(select(CONTRAST_BANDS, stddev)), int(select(PSM_BANDS, dark_pct))


def describe() -> list[dict[str, object]]:
    """Return the bands as rows, for documentation and diagnostics.

    `tools/generate_tuning_data.py` reads this into `site/data/tuning.toml`
    before Hugo runs, so the values published at
    https://tetrak.dev/reference/routing/ come from the module rather than
    from a copy someone typed. That matters more than it used to: the edges
    are fitted now, and they move.
    """
    rows: list[dict[str, object]] = []
    for feature, setting, bands in (
        ("stddev", "contrast", CONTRAST_BANDS),
        ("dark_pct", "psm", PSM_BANDS),
    ):
        lower = 0.0
        for band in bands:
            rows.append(
                {
                    "feature": feature,
                    "setting": setting,
                    "lower": lower,
                    "upper": band.upper,
                    "range": (
                        f"{feature} >= {lower:g}"
                        if math.isinf(band.upper)
                        else f"{lower:g} <= {feature} < {band.upper:g}"
                    ),
                    "value": band.value,
                }
            )
            lower = band.upper
    return rows
