"""Integration tests for the batch pipeline.

The pipeline moves files workspace/scans/ → workspace/processed/, writing a
Markdown transcript alongside each image, and diverts anything that fails
quality scoring to workspace/triage/.

These run against throwaway directories (the `working_dirs` fixture) rather
than the repository's real workspace/ folders. The previous version
cleared those real directories before and after every test, which worked but
would have destroyed a developer's in-progress scans if a run coincided.

Tests needing a real scanned image borrow one from the evaluation corpus and
are marked `slow`, because they invoke Tesseract for real.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import tetrak_ocr.backends.tesseract as tesseract_backend
from tetrak_ocr.backends.tesseract import DEFAULT_CONTRAST, DEFAULT_PSM, SUPPORTED_EXTENSIONS
from tetrak_ocr.batch import build_ocr_fn
from tetrak_ocr.batch import main as run_batch


def _write_legible_image(path: Path, text: str = "HELLO ARCHIVE") -> None:
    """A plain black-on-white image Tesseract reads reliably.

    Generated rather than loaded so the fast test loop needs no data files.
    """
    img = Image.new("RGB", (900, 220), "white")
    ImageDraw.Draw(img).text((40, 80), text, fill="black")
    img.save(path)


class TestEmptyInput:
    def test_empty_scans_completes_without_error(self, working_dirs):
        """An empty scans/ directory is a no-op, not an error."""
        assert run_batch(args=[]) == 0

    def test_missing_scans_dir_is_reported(self, working_dirs, capsys):
        """A missing scans/ directory returns non-zero with a clear message.

        Returned rather than raised: `main` reports every failure it decides on
        through its return value, so `cli.main` can hand back an exit code
        instead of letting SystemExit escape a documented `-> int`.
        """
        shutil.rmtree(working_dirs["scans"])
        assert run_batch(args=[]) == 1
        assert "scans" in capsys.readouterr().err.lower()


@pytest.mark.slow
class TestProcessing:
    """End-to-end runs. Marked slow: these call Tesseract for real."""

    def test_image_is_moved_and_transcribed(self, working_dirs):
        _write_legible_image(working_dirs["scans"] / "sample.png")

        run_batch(args=[])

        produced = {p.name for p in working_dirs["processed"].iterdir()}
        assert "sample.png" in produced, "the original image should move to processed/"
        assert "sample.md" in produced, "a transcript should be written alongside it"

    def test_scans_dir_is_emptied(self, working_dirs):
        _write_legible_image(working_dirs["scans"] / "sample.png")

        run_batch(args=[])

        remaining = [p for p in working_dirs["scans"].iterdir() if p.name != ".gitkeep"]
        assert remaining == [], f"scans/ should be empty, found {[p.name for p in remaining]}"

    def test_transcript_starts_with_a_title(self, working_dirs):
        """Each transcript opens with an H1 naming the source file."""
        _write_legible_image(working_dirs["scans"] / "sample.png")

        run_batch(args=[])

        content = (working_dirs["processed"] / "sample.md").read_text(encoding="utf-8")
        assert content.startswith("# sample")

    def test_every_corpus_image_is_processed(self, working_dirs, corpus_images):
        """Every corpus format round-trips without a file going missing.

        Every raster, but only the smallest PDF. The corpus holds several
        multi-page PDFs added as candidate fixtures, and OCRing every page of
        every one took over 300 of this test's 325 seconds locally, and about
        19 minutes on CI's runner -- most of the Corpus workflow's 30-minute
        budget. One PDF exercises the same path through the pipeline.
        """
        usable = [p for p in corpus_images if p.suffix.lower() in SUPPORTED_EXTENSIONS]
        pdfs = sorted(
            (p for p in usable if p.suffix.lower() == ".pdf"), key=lambda p: p.stat().st_size
        )
        usable = [p for p in usable if p.suffix.lower() != ".pdf"] + pdfs[:1]
        if not usable:
            pytest.skip("evaluation corpus is empty")

        for image in usable:
            shutil.copy(image, working_dirs["scans"] / image.name)

        run_batch(args=[])

        produced = {p.name for p in working_dirs["processed"].iterdir()}
        for image in usable:
            assert image.name in produced, f"{image.name} did not reach processed/"
            assert f"{image.stem}.md" in produced, f"no transcript for {image.name}"


class TestQualityGate:
    """`--quality-gate` extends triage to any single backend.

    Before this, the gate lived inside `auto-local`: it scored every backend it
    ran in order to pick a winner, and raised if the winner was poor. That made
    fan-out the only route to the triage queue, and fan-out is the most
    expensive thing the pipeline does. The gate judges a transcript, not an
    engine, so there was never a reason to couple the two.

    These tests stub the scorer. Whether `combined_score` ranks real
    transcripts sensibly is `test_thresholds.py`'s job; what matters here is
    that the threshold is applied, that it is applied to *any* backend, and
    that it stays off unless asked for.
    """

    @staticmethod
    def _batch_with_score(monkeypatch, score: float, text: str = "some transcript"):
        """Run the pipeline over one file with a fixed quality score."""
        from tetrak_ocr import batch, qa_score

        monkeypatch.setattr(batch, "build_ocr_fn", lambda *a, **k: lambda path: text)
        monkeypatch.setattr(qa_score, "combined_score", lambda _text: score)
        monkeypatch.setattr(qa_score, "is_available", lambda: True)
        return batch

    def test_a_poor_transcript_is_triaged(self, working_dirs, monkeypatch):
        (working_dirs["scans"] / "faint.png").touch()
        self._batch_with_score(monkeypatch, score=0.01)

        assert run_batch(["--backend", "tesseract", "--quality-gate"]) == 0

        assert (working_dirs["triage"] / "faint.png").exists()
        assert not (working_dirs["processed"] / "faint.png").exists()

    def test_the_manifest_names_the_backend_that_produced_it(self, working_dirs, monkeypatch):
        """The manifest is for a human deciding what to do with the file.

        With one backend there is no score table to compare, so the least it
        can do is say which engine produced the transcript being rejected.
        """
        (working_dirs["scans"] / "faint.png").touch()
        self._batch_with_score(monkeypatch, score=0.01, text="unreadable smudge")

        run_batch(["--backend", "tesseract-auto", "--quality-gate"])

        manifest = (working_dirs["triage"] / "faint.md").read_text()
        assert "tesseract-auto" in manifest
        assert "unreadable smudge" in manifest

    def test_a_good_transcript_passes_through(self, working_dirs, monkeypatch):
        (working_dirs["scans"] / "clean.png").touch()
        self._batch_with_score(monkeypatch, score=0.9)

        assert run_batch(["--backend", "tesseract", "--quality-gate"]) == 0

        assert (working_dirs["processed"] / "clean.png").exists()
        assert not (working_dirs["triage"] / "clean.png").exists()

    def test_the_gate_is_off_unless_asked_for(self, working_dirs, monkeypatch):
        """Turning it on by default would start diverting output for anyone
        already running `--backend tesseract`, which is why it is opt-in."""
        (working_dirs["scans"] / "faint.png").touch()
        self._batch_with_score(monkeypatch, score=0.01)

        assert run_batch(["--backend", "tesseract"]) == 0

        assert (working_dirs["processed"] / "faint.png").exists()
        assert not (working_dirs["triage"] / "faint.png").exists()

    def test_it_refuses_up_front_without_the_qa_extra(self, working_dirs, monkeypatch):
        """Fail before touching any file.

        Discovering the missing extra on the first transcript would leave the
        batch half-done, with some files moved and the rest still in scans/.
        """
        (working_dirs["scans"] / "one.png").touch()
        from tetrak_ocr import qa_score

        monkeypatch.setattr(qa_score, "is_available", lambda: False)

        assert run_batch(["--backend", "tesseract", "--quality-gate"]) == 1

        assert (working_dirs["scans"] / "one.png").exists()
        assert not any(working_dirs["processed"].iterdir())


class TestTuningFlagsReachTheBackend:
    """What `build_ocr_fn` actually hands the Tesseract backend.

    Every other test in this file monkeypatches `build_ocr_fn` away, which is
    how two flag-wiring faults survived: `--auto` did nothing at all on the
    `tesseract` backend, and `--contrast`/`--psm` were dropped entirely by
    `tesseract-auto`. Both are invisible from the outside -- the run succeeds
    and the transcript is merely produced with settings nobody asked for.

    `None` is the assertion that matters throughout: it is what leaves a
    parameter for `analyse_image()` to fill, so a default substituted in its
    place is auto-configuration silently switched off.
    """

    @pytest.fixture
    def seen(self, monkeypatch):
        """The keyword arguments the backend was called with."""
        captured: dict = {}

        def fake_ocr_image(path, contrast=None, psm=None, auto=False, lang=None):
            captured.update(contrast=contrast, psm=psm, auto=auto)
            return ""

        monkeypatch.setattr(tesseract_backend, "ocr_image", fake_ocr_image)
        return captured

    def test_plain_tesseract_applies_its_defaults(self, seen):
        build_ocr_fn("tesseract")(Path("scan.png"))
        assert seen == {"contrast": DEFAULT_CONTRAST, "psm": DEFAULT_PSM, "auto": False}

    def test_explicit_values_are_passed_through(self, seen):
        build_ocr_fn("tesseract", contrast=3.5, psm=11)(Path("scan.png"))
        assert seen == {"contrast": 3.5, "psm": 11, "auto": False}

    def test_auto_leaves_both_for_the_image_analysis(self, seen):
        """`--auto` was inert: both values arrived filled, so the backend's
        `auto and (contrast is None or psm is None)` branch never ran."""
        build_ocr_fn("tesseract", auto=True)(Path("scan.png"))
        assert seen == {"contrast": None, "psm": None, "auto": True}

    def test_auto_still_honours_a_value_given_alongside_it(self, seen):
        """Auto fills what was not specified, rather than overriding it."""
        build_ocr_fn("tesseract", contrast=3.0, auto=True)(Path("scan.png"))
        assert seen == {"contrast": 3.0, "psm": None, "auto": True}

    def test_tesseract_auto_is_auto_without_being_asked(self, seen):
        build_ocr_fn("tesseract-auto")(Path("scan.png"))
        assert seen == {"contrast": None, "psm": None, "auto": True}

    @pytest.mark.parametrize(
        ("flag", "value", "other"),
        [("contrast", 3.0, "psm"), ("psm", 6, "contrast")],
    )
    def test_tesseract_auto_honours_the_tuning_flags(self, seen, flag, value, other):
        """These were silently dropped: the name passed the `startswith`
        warning guard but failed the `== "tesseract"` wiring check, so it fell
        through both branches."""
        build_ocr_fn("tesseract-auto", **{flag: value})(Path("scan.png"))
        assert seen[flag] == value
        assert seen[other] is None
        assert seen["auto"] is True

    def test_a_backend_that_ignores_them_says_so(self, capsys, monkeypatch):
        """The warning is the contract for every non-Tesseract backend.

        Patched on `batch`, not on `registry`: batch imports the name at module
        level, so replacing it in the registry leaves the already-bound
        reference untouched. CI installs no heavy extras by design, so the real
        lookup raises MissingBackendError rather than warning -- which is how
        the first version of this test passed here and failed there.
        """
        from tetrak_ocr import batch

        monkeypatch.setattr(batch, "get_backend", lambda name: lambda path: "")
        build_ocr_fn("easyocr", contrast=3.0)
        assert "--contrast" in capsys.readouterr().err


class TestTheGateOnlyJudgesWhatItCanRead:
    """The quality metrics are English-only, and the pipeline is not.

    `dictionary_coverage` counts `[a-zA-Z]` tokens against an English wordlist,
    so an Armenian transcript scores 0.0 however well it was read. Before the
    `easyocr-hy` backend everything the pipeline read was English and this
    could not arise; now `batch --backend easyocr-hy --quality-gate` would
    otherwise triage every file in the run and report each as poor quality.
    """

    ARMENIAN = "Հայկական Սովետական Հանրագիտարան հատոր երկու"

    def test_armenian_is_not_scoreable(self):
        from tetrak_ocr.qa_score import scores_english_text

        assert not scores_english_text(self.ARMENIAN)

    def test_english_is_scoreable(self):
        from tetrak_ocr.qa_score import scores_english_text

        assert scores_english_text("The quick brown fox jumps over the lazy dog")

    def test_armenian_with_latin_names_and_numerals_is_still_not_scoreable(self):
        """Armenian print mixes in Latin, which must not tip the balance."""
        from tetrak_ocr.qa_score import scores_english_text

        assert not scores_english_text(f"{self.ARMENIAN} (Yerevan, 1974) 363")

    def test_an_empty_transcript_stays_scoreable(self):
        """Empty output is genuinely poor, and scoring says so correctly --
        only another *script* is what this guard exists for."""
        from tetrak_ocr.qa_score import scores_english_text

        assert scores_english_text("")
        assert scores_english_text("363) 1974 —")

    def test_a_non_latin_transcript_is_not_triaged(self, working_dirs, monkeypatch, capsys):
        """The end of it: the file is processed, and the skip is reported."""
        from tetrak_ocr import batch, qa_score

        (working_dirs["scans"] / "page.png").touch()
        monkeypatch.setattr(batch, "build_ocr_fn", lambda *a, **k: lambda path: self.ARMENIAN)
        monkeypatch.setattr(qa_score, "is_available", lambda: True)
        # Would fail every threshold if it were ever consulted.
        monkeypatch.setattr(qa_score, "combined_score", lambda _text: 0.0)

        # `tesseract`, though `easyocr-hy` is what makes this reachable in
        # practice: the gate is what is under test and the backend is
        # incidental, but naming easyocr-hy resolves it for real through the
        # registry, and CI installs no extras.
        assert run_batch(["--backend", "tesseract", "--quality-gate"]) == 0

        assert (working_dirs["processed"] / "page.png").exists()
        assert not (working_dirs["triage"] / "page.png").exists()
        assert "quality gate skipped" in capsys.readouterr().err
