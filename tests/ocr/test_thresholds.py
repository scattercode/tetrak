"""Accuracy tests: compare OCR output against expected reference files.

For each fixture image that has a matching file in evaluation/ocr/corpus/expected/,
this test runs Tesseract OCR with automatic per-image configuration and
asserts that the similarity scores meet the configured thresholds.

Auto-configuration (--auto mode) uses analyse_image() to choose the contrast
enhancement factor and Tesseract PSM based on image characteristics, so no
manual tuning is needed per image.

To add expectations for an image:
    1. Run the batch processor or ocr_tesseract.py on the image to see what
       Tesseract currently produces.
    2. Create evaluation/ocr/corpus/expected/<image-stem>.md containing the text
       you consider correct for that image.
    3. Re-run pytest — this test will now include that image.

Thresholds are calibrated against a measured benchmark run rather than chosen
by hand — see the comment above CHARACTER_SIMILARITY_THRESHOLD for the current
values and the floors they sit under.
"""

from pathlib import Path

import pytest

# The corpus lives under evaluation/ocr/, not tests/ -- it is a benchmark
# corpus shared with the evaluation harness, not a unit-test fixture.
#
# Taken from conftest rather than derived here. This module used to walk up
# from __file__ with its own parent count, which is a second definition of
# where the repository root is, and it pointed at the wrong directory the
# moment the file moved a level deeper. conftest resolves it once.
# Parametrisation happens at import time, so these are module-level constants
# rather than fixtures.
from conftest import CORPUS_EXPECTED as EXPECTED_DIR
from conftest import CORPUS_IMAGES as FIXTURES_DIR

from tetrak_ocr.accuracy import character_similarity, word_recall
from tetrak_ocr.backends.tesseract import SUPPORTED_EXTENSIONS, ocr_image

# Minimum acceptable scores, calibrated against a measured benchmark run on
# this fixture set (see evaluation/ocr/benchmark.md).
#
# These were raised after the analyse_image() PSM bands were re-fitted.  The
# old bands sent dense pages to PSM 11 (sparse), which scrambled reading order
# and pushed character similarity down to 0.07-0.38 while word recall stayed
# high — so the character threshold had to sit at 0.05 and carried no signal.
# With the bands fixed, the four passing fixtures now measure:
#
#   carthay-circle-premiere      0.49 char / 0.86 word
#   king-of-kings-souvenir-1927  0.45 char / 0.95 word
#   inside-facts-1930-page-six   0.37 char / 0.89 word
#   inside-facts-1930-cover      0.35 char / 0.91 word
#
# Both thresholds sit just under those floors with a little headroom.  Character
# similarity is now a real gate rather than a collapse detector.
CHARACTER_SIMILARITY_THRESHOLD = 0.30
WORD_RECALL_THRESHOLD = 0.80

# Images where Tesseract falls short of at least one threshold whatever the
# configuration -- not both: graumans-chinese-theatre and
# carthay-circle-postcard-back have among the best character similarity in the
# set and fail only on word recall, which the note further down explains.
# Kept in the suite as aspirational benchmarks and marked xfail
# by `parametrised()` so they stay visible without blocking CI.
#
# Scores below are auto-configured Tesseract, char / word, from
# evaluation/ocr/benchmark.csv after the 2026-09-27 band re-fit. Do not trust
# them to be current -- the benchmark is the source, this is orientation.
#
#   kar-mi-troupe-poster          0.02 / 0.01  chromolithograph display type on
#                                              curved and arched baselines.
#                                              The whole 42-cell sweep tops out
#                                              at 0.06: genuinely unreadable.
#   graumans-chinese-theatre      0.86 / 0.54  reads its caption well; the words
#                                              it misses are the half-legible
#                                              marquee lettering, which Claude
#                                              does recover
#   carthay-circle-postcard-back  0.91 / 0.71  rotated text and stamp read
#                                              correctly; the shortfall is the
#                                              faint "TAC" monogram
#   hollywood-music-box-playbill  0.24 / 0.48  a full sheet of footnote-sized
#                                              cast lists and synopses. Not
#                                              enough resolution on the small
#                                              type; the sweep's ceiling is
#                                              0.34.
#   kinema-theater-ad-1920        0.23 / 0.40  repaired, but not to a passing
#                                              score. The bands used to send it
#                                              to PSM 6 -- a large illustration
#                                              makes the frame 42.9% dark, which
#                                              the dark_pct band read as
#                                              "image-dominated, no page
#                                              structure" -- and it collapsed to
#                                              0.04 against plain Tesseract's
#                                              0.23. The re-fit moved the PSM-6
#                                              edge past it and it now matches
#                                              plain exactly. Its sweep ceiling
#                                              is 0.2341, so the 0.30 character
#                                              gate is out of reach for
#                                              Tesseract at any setting.
#
# Three of the five fail only on *word recall* -- their character similarity is
# among the best in the set. They are held back by text Tesseract cannot see at
# all rather than by text it garbles, which is the opposite of the problem the
# re-fits solved. Splitting the two thresholds per fixture would let them pass
# on their merits; brief 007 rules it out of scope rather than out of order.
#
# carthay-circle-premiere is not on this list: it went 0.14/0.00 -> 0.49/0.86
# in the August re-fit and 0.49 -> 0.51 in this one, and passes outright. It is
# also the fixture that constrains the fit hardest. Contrast 3.5 would score it
# 0.67 on character similarity, the largest single gain available anywhere in
# the sweep, at a word recall of 0.7857 -- which this file would fail. The
# fitter treats WORD_RECALL_THRESHOLD as a hard constraint for that reason.
# Whether 0.80 is the right number to be defending is a real question, and a
# separate one from re-fitting the bands.
# Per-fixture floors, for a gated fixture whose score moves across Tesseract
# releases by more than the global floors' headroom. The global thresholds
# stay what the band fit defends (evaluation/ocr/calibration/fit.py keeps its
# own copy, checked against these by test_calibration); these only stop CI
# failing on engine-version noise, and still sit far above the collapse the
# fixture exists to catch.
#
# carthay-circle-premiere, auto-configured (contrast 2.0, PSM 6 on every
# version -- the configuration does not change, the engine's reading does):
#
#   Tesseract 5.3.4 (Ubuntu 24.04, CI)   0.272 char / 0.857 word
#   Tesseract 5.5.1 (alex-p PPA)         0.535 char / 0.786 word
#   Tesseract 5.5.2 (Homebrew)           0.514 char / 0.857 word
#
# Every version reads the caption; 5.3.4 adds noise from the photograph, and
# 5.5.1 drops one of the transcript's fourteen words. Under the bands before
# August it scored 0.14 / 0.00, which these floors would still fail.
FIXTURE_FLOORS: dict[str, tuple[float, float]] = {
    "carthay-circle-premiere": (0.25, 0.75),
}

KNOWN_TESSERACT_LIMITATIONS = {
    "kar-mi-troupe-poster",
    "carthay-circle-postcard-back",
    "graumans-chinese-theatre",
    "hollywood-music-box-playbill-1926",
    "kinema-theater-ad-1920",
    # The eight rasters transcribed on 28 September 2026 to widen calibration
    # (see evaluation/ocr/corpus/splits.toml). Listed here on arrival rather
    # than on evidence, which is the conservative direction and deliberate:
    #
    #   A fixture *absent* from this set is one CI enforces both thresholds
    #   on, and `evaluation/ocr/calibration/fit.py` turns that into a hard
    #   constraint on the band fit. Admitting eight unmeasured fixtures as
    #   gates could make the fit infeasible -- and the fixture that broke it
    #   would be one nobody had looked at yet.
    #
    # They are all sparse display material -- four Tichnor linen postcards and
    # four lithographed theatre posters -- and word recall of 0.80 on a
    # chromolithograph is not a realistic bar. Take one off this list when the
    # measurement says it clears both thresholds, which `xfail(strict=False)`
    # will report as XPASS rather than leaving anyone to notice.
    "bancroft-magician-poster",
    "chinese-theatre-triptych-postcard",
    "greek-theatre-night",
    "hollywood-boulevard-east",
    "hollywood-boulevard-west",
    "over-the-fence-poster",
    "parlor-match-poster",
    "thurston-magician-poster",
}


def available_pairs() -> list[tuple[Path, Path]]:
    """Return (image_path, expected_path) for each fixture with an expected file."""
    return sorted(
        (img, EXPECTED_DIR / f"{img.stem}.md")
        for img in FIXTURES_DIR.iterdir()
        if img.is_file()
        and img.suffix.lower() in SUPPORTED_EXTENSIONS
        and (EXPECTED_DIR / f"{img.stem}.md").exists()
    )


_pairs = available_pairs()


def parametrised() -> list[object]:
    """Return the parametrize arguments, marked where Tesseract falls short.

    The marks are **declarative**, applied to the parameter rather than raised
    inside the test. This module used to call `pytest.xfail()` in the body,
    which raises the moment it is reached: the OCR never ran, so the case could
    not report XPASS, and a fixture repaired by a re-fit would go on reporting
    `xfailed` for ever with nobody the wiser. Brief 007 records that as the
    reason the calibration work was unverifiable before it started -- a band
    fit could have fixed kinema-theater-ad-1920 and this suite would have said
    nothing.

    `strict=False`, deliberately. An XPASS here is news, not a failure: the
    calibration toolkit is expected to repair some of these, and a suite that
    goes red on an improvement is one people learn to ignore. When a fixture
    passes reliably, take it off KNOWN_TESSERACT_LIMITATIONS -- that is a
    visible diff, which is the point.
    """
    return [
        pytest.param(
            image,
            expected,
            id=image.stem,
            marks=(
                [
                    pytest.mark.xfail(
                        strict=False,
                        reason=(
                            f"{image.name} is a known Tesseract limitation. The OCR still "
                            "runs, so a re-fit that repairs it reports XPASS rather than "
                            "passing silently."
                        ),
                    )
                ]
                if image.stem in KNOWN_TESSERACT_LIMITATIONS
                else []
            ),
        )
        for image, expected in _pairs
    ]


# Reads the corpus and runs Tesseract for real, so it is excluded from the
# fast loop (`pytest -m "not slow"`).
@pytest.mark.slow
@pytest.mark.skipif(
    not _pairs,
    reason=(
        "No expected files in evaluation/ocr/corpus/expected/ — "
        "add a <name>.md file alongside each fixture image to enable accuracy tests."
    ),
)
@pytest.mark.parametrize(
    "image_path,expected_path",
    parametrised() if _pairs else [pytest.param(Path("."), Path("."), id="skip")],
)
def test_ocr_accuracy(image_path: Path, expected_path: Path) -> None:
    """OCR output for each fixture should meet the similarity thresholds.

    Uses auto=True so that contrast and PSM are chosen per image based on
    image characteristics rather than a fixed global default.

    Images in KNOWN_TESSERACT_LIMITATIONS are marked xfail by `parametrised()`:
    they are included so regressions are visible and repairs show up as XPASS,
    but they do not block the suite.
    """
    actual = ocr_image(image_path, auto=True)
    expected = expected_path.read_text(encoding="utf-8")

    sim = character_similarity(actual, expected)
    recall = word_recall(actual, expected)
    char_floor, word_floor = FIXTURE_FLOORS.get(
        image_path.stem, (CHARACTER_SIMILARITY_THRESHOLD, WORD_RECALL_THRESHOLD)
    )

    # Print scores so they are visible in pytest -v output.
    print(f"\n  character similarity : {sim:.3f}  (threshold: {char_floor})")
    print(f"  word recall          : {recall:.3f}  (threshold: {word_floor})")

    assert sim >= char_floor, (
        f"Character similarity {sim:.3f} is below threshold {char_floor} for {image_path.name}"
    )
    assert recall >= word_floor, (
        f"Word recall {recall:.3f} is below threshold {word_floor} for {image_path.name}"
    )
