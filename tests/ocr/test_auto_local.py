"""Unit tests for the auto-local routing and fan-out.

This is the most consequential logic in the package — it decides which local
backends run and which transcript wins — and it had no coverage at all. The
decision table it implements is documented as a Mermaid chart in the docs;
these tests are that chart, executable.

Every backend is mocked. The point is the routing and the selection rule, not
whether Tesseract can read a poster.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tetrak_ocr import auto_local, qa_score
from tetrak_ocr.qa_score import LowQualityError


@pytest.fixture(autouse=True)
def isolate_engines(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from a machine with no optional engine installed.

    Autouse because the alternative is each test remembering to null every
    engine it does not care about. Miss one and the test silently inherits
    whatever happens to be installed on the machine running it -- so it passes
    here and fails in CI, or worse, passes everywhere until someone installs an
    extra. Tests opt in to an engine by setting it after this runs.
    """
    monkeypatch.setattr(auto_local, "_marker_ocr", None)
    monkeypatch.setattr(auto_local, "_vision_ocr", None)
    monkeypatch.setattr(auto_local, "_paddle_ocr", None)
    monkeypatch.setattr(auto_local, "_easyocr_ocr", None)


@pytest.fixture
def no_optional_backends() -> None:
    """Named marker for tests whose subject is the bare-machine case.

    The isolation above already guarantees it; this keeps those tests reading
    as a deliberate scenario rather than an accident of the default.
    """


class TestCandidateSelection:
    """Which backends are eligible, per the routing chart."""

    def test_tesseract_is_always_a_candidate(self, no_optional_backends) -> None:
        """The floor: with nothing optional installed there is still a path."""
        names = [name for name, _ in auto_local._build_candidates(Path("scan.jpg"))]
        assert names == ["tesseract-auto"]

    def test_paddle_is_offered_for_images(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_ocr", lambda p: "paddle text")

        names = [name for name, _ in auto_local._build_candidates(Path("scan.jpg"))]
        assert names == ["paddle", "tesseract-auto"]

    def test_paddle_is_skipped_for_pdfs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Paddle has no native PDF support, so PDFs route past it."""
        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_ocr", lambda p: "paddle text")

        names = [name for name, _ in auto_local._build_candidates(Path("scan.pdf"))]
        assert names == ["tesseract-auto"]

    def test_marker_leads_when_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Marker is listed first: it produces the most structured output and
        wins ties by virtue of ordering."""
        monkeypatch.setattr(auto_local, "_marker_ocr", lambda p: "marker text")
        monkeypatch.setattr(auto_local, "_paddle_ocr", lambda p: "paddle text")

        names = [name for name, _ in auto_local._build_candidates(Path("scan.jpg"))]
        assert names[0] == "marker"

    def test_marker_handles_pdfs_unlike_paddle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(auto_local, "_marker_ocr", lambda p: "marker text")
        monkeypatch.setattr(auto_local, "_paddle_ocr", lambda p: "paddle text")

        names = [name for name, _ in auto_local._build_candidates(Path("scan.pdf"))]
        assert names == ["marker", "tesseract-auto"]

    def test_easyocr_is_offered_for_images(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """EasyOCR was documented as a candidate but never actually wired in.

        The original CLAUDE.md described auto-local as using "paddle (or
        easyocr) for images"; the code only ever added paddle, in every
        revision. Installing the easyocr extra bought you nothing.
        """
        monkeypatch.setattr(auto_local, "_easyocr_ocr", lambda p: "easyocr text")

        names = [name for name, _ in auto_local._build_candidates(Path("scan.jpg"))]
        assert names == ["easyocr", "tesseract-auto"]

    def test_easyocr_is_skipped_for_pdfs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same constraint as Paddle: no native PDF support."""
        monkeypatch.setattr(auto_local, "_easyocr_ocr", lambda p: "easyocr text")

        names = [name for name, _ in auto_local._build_candidates(Path("scan.pdf"))]
        assert names == ["tesseract-auto"]

    def test_vision_is_offered_for_images(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """macOS's on-device engine joins the fan-out when it is installed."""
        monkeypatch.setattr(auto_local, "_vision_ocr", lambda p: "vision text")

        names = [name for name, _ in auto_local._build_candidates(Path("scan.jpg"))]
        assert "vision" in names

    def test_vision_is_skipped_for_pdfs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Vision reads images only, so a PDF must not route to it."""
        monkeypatch.setattr(auto_local, "_vision_ocr", lambda p: "vision text")

        names = [name for name, _ in auto_local._build_candidates(Path("scan.pdf"))]
        assert "vision" not in names

    def test_vision_outranks_the_other_non_marker_engines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Order is the tiebreaker, and Vision measures best of the four.

        Marker still leads where it is available: it is the only candidate
        modelling reading order, which is a structural reason rather than a
        scored one.
        """
        monkeypatch.setattr(auto_local, "_marker_ocr", lambda p: "marker text")
        monkeypatch.setattr(auto_local, "_vision_ocr", lambda p: "vision text")
        monkeypatch.setattr(auto_local, "_easyocr_ocr", lambda p: "easyocr text")
        monkeypatch.setattr(auto_local, "_paddle_ocr", lambda p: "paddle text")

        names = [name for name, _ in auto_local._build_candidates(Path("scan.jpg"))]
        assert names == ["marker", "vision", "easyocr", "paddle", "tesseract-auto"]

    def test_easyocr_outranks_paddle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Order is a routing decision, not cosmetic: fast mode takes the first
        entry, and fan-out uses it to break ties.

        EasyOCR leads on the evaluation corpus, ahead on every image where
        either engine reads anything at all.  The scores are in
        content/evaluation/results.md rather than repeated here, so this assertion
        does not go stale in a way nothing checks.
        """
        monkeypatch.setattr(auto_local, "_easyocr_ocr", lambda p: "easyocr text")
        monkeypatch.setattr(auto_local, "_paddle_ocr", lambda p: "paddle text")

        names = [name for name, _ in auto_local._build_candidates(Path("scan.jpg"))]
        assert names == ["easyocr", "paddle", "tesseract-auto"]

    def test_every_installed_engine_joins_the_pool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fan-out scores what it runs, so a viable engine costs only time.

        There is no reason to withhold one from the pool: a bad transcript
        loses on score, and the quality gate catches the case where they all do.
        """
        monkeypatch.setattr(auto_local, "_marker_ocr", lambda p: "marker text")
        monkeypatch.setattr(auto_local, "_easyocr_ocr", lambda p: "easyocr text")
        monkeypatch.setattr(auto_local, "_paddle_ocr", lambda p: "paddle text")

        names = [name for name, _ in auto_local._build_candidates(Path("scan.jpg"))]
        assert names == ["marker", "easyocr", "paddle", "tesseract-auto"]

    def test_extension_matching_is_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`.PDF` from a scanner must route the same as `.pdf`."""
        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_ocr", lambda p: "paddle text")

        names = [name for name, _ in auto_local._build_candidates(Path("SCAN.PDF"))]
        assert names == ["tesseract-auto"]


class TestEffectiveScore:
    """`_effective_score()`: the pure function behind ranking, no backend needed.

    See `LENGTH_WEIGHT`'s provenance comment in auto_local.py and
    `evaluation/ocr/calibration/router_sweep.py` for how 0.8 was chosen.
    """

    def test_the_max_word_candidate_always_gets_full_credit(self) -> None:
        """Ratio 1.0 means `LENGTH_WEIGHT + (1 - LENGTH_WEIGHT) * 1 == 1`,
        for any weight -- the longest transcript is never penalised."""
        assert auto_local._effective_score(0.42, 100, 100) == pytest.approx(0.42)

    def test_a_zero_word_candidate_gets_exactly_the_floor(self) -> None:
        assert auto_local._effective_score(0.42, 0, 100) == pytest.approx(
            0.42 * auto_local.LENGTH_WEIGHT
        )

    def test_a_non_positive_max_words_returns_the_score_unchanged(self) -> None:
        """Guards the `or 1` at the call site's counterpart: if every
        candidate is somehow empty, there is nothing to compare word counts
        against, so the raw score passes through rather than dividing by
        zero."""
        assert auto_local._effective_score(0.3, 0, 0) == 0.3

    def test_ranking_is_monotonic_in_word_count_for_equal_raw_scores(self) -> None:
        lower = auto_local._effective_score(0.5, 10, 100)
        higher = auto_local._effective_score(0.5, 50, 100)
        assert higher > lower

    class TestTheCarthayCase:
        """Hand-built score/word-count table reproducing the failure mode
        the error taxonomy (product analytics) ("The router's own error rate")
        found on `carthay-circle-premiere.jpg`: a transcript inflated by
        noise into being the longest candidate, beating a shorter one with a
        clearly higher raw quality score.

        Numbers below are illustrative round figures chosen to demonstrate
        the mechanism, not copied from the real fixture -- see
        `evaluation/ocr/calibration/router_sweep.csv` for the measured case
        (marker/vision/EasyOCR all near 11 words there, tesseract-auto at 77).
        """

        # The noisy, artificially long transcript -- lower raw quality.
        LONG_SCORE, LONG_WORDS = 0.11, 80
        # The shorter, cleaner transcript -- higher raw quality, far fewer words.
        SHORT_SCORE, SHORT_WORDS = 0.15, 10
        MAX_WORDS = LONG_WORDS  # the long transcript sets the ceiling

        def test_the_old_weight_let_word_count_alone_overturn_the_quality_gap(
            self,
        ) -> None:
            """LENGTH_WEIGHT was 0.5 before this fix -- recomputed inline
            rather than imported, since the whole point is what the *old*
            value did, and importing today's LENGTH_WEIGHT here would silently
            stop testing that if it ever changed again."""
            old_weight = 0.5
            long_effective = self.LONG_SCORE * (
                old_weight + (1 - old_weight) * self.LONG_WORDS / self.MAX_WORDS
            )
            short_effective = self.SHORT_SCORE * (
                old_weight + (1 - old_weight) * self.SHORT_WORDS / self.MAX_WORDS
            )
            assert long_effective > short_effective

        def test_the_shipped_weight_lets_the_higher_quality_transcript_win(self) -> None:
            long_effective = auto_local._effective_score(
                self.LONG_SCORE, self.LONG_WORDS, self.MAX_WORDS
            )
            short_effective = auto_local._effective_score(
                self.SHORT_SCORE, self.SHORT_WORDS, self.MAX_WORDS
            )
            assert short_effective > long_effective


class TestWinnerSelection:
    """Fan-out runs every candidate; the best-scoring transcript is returned."""

    def test_highest_scoring_transcript_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_ocr", lambda p: "the good transcript")
        monkeypatch.setattr(auto_local, "_tesseract_ocr", lambda p, **kw: "the bad transcript")
        monkeypatch.setattr(
            auto_local,
            "combined_score",
            lambda text: 0.9 if "good" in text else 0.2,
        )

        assert auto_local.ocr_image(Path("scan.jpg")) == "the good transcript"

    def test_a_higher_quality_shorter_transcript_beats_a_longer_noisier_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end version of `TestEffectiveScore.TestTheCarthayCase`: a
        backend that recovers many words of noise must not automatically beat
        one with far fewer words and a clearly higher raw quality score —
        the failure `LENGTH_WEIGHT` was raised from 0.5 to fix."""
        long_noisy = " ".join(["noise"] * 80)
        short_clean = " ".join(["clean"] * 10)

        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_ocr", lambda p: long_noisy)
        monkeypatch.setattr(auto_local, "_tesseract_ocr", lambda p, **kw: short_clean)
        monkeypatch.setattr(
            auto_local,
            "combined_score",
            lambda text: 0.11 if "noise" in text else 0.15,
        )

        assert auto_local.ocr_image(Path("scan.jpg")) == short_clean

    def test_a_failing_backend_does_not_sink_the_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """One backend raising must not lose the others' results — the whole
        point of running several is resilience."""

        def exploding(path):
            raise RuntimeError("model failed to load")

        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_ocr", exploding)
        monkeypatch.setattr(auto_local, "_tesseract_ocr", lambda p, **kw: "survivor text")
        monkeypatch.setattr(auto_local, "combined_score", lambda text: 0.8)

        assert auto_local.ocr_image(Path("scan.jpg")) == "survivor text"

    def test_all_backends_failing_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def exploding(path, **kwargs):
            raise RuntimeError("nope")

        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_ocr", None)
        monkeypatch.setattr(auto_local, "_tesseract_ocr", exploding)

        with pytest.raises(RuntimeError):
            auto_local.ocr_image(Path("scan.jpg"))

    def test_uniformly_poor_output_goes_to_the_triage_queue(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Below the quality floor, auto-local refuses rather than returning
        rubbish — batch routes the file to triage/ for human triage."""
        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_ocr", None)
        monkeypatch.setattr(auto_local, "_tesseract_ocr", lambda p, **kw: "!!! ###")
        monkeypatch.setattr(auto_local, "combined_score", lambda text: 0.0)

        with pytest.raises(LowQualityError) as exc:
            auto_local.ocr_image(Path("scan.jpg"))

        # The exception carries what the triage manifest needs.
        assert exc.value.scores
        assert exc.value.transcripts

    def test_accepts_a_string_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Documented as `Path | str`, and batch passes a Path — but callers do
        pass strings."""
        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_ocr", None)
        monkeypatch.setattr(auto_local, "_tesseract_ocr", lambda p, **kw: "text")
        monkeypatch.setattr(auto_local, "combined_score", lambda text: 0.8)

        assert auto_local.ocr_image("scan.jpg") == "text"


class TestModes:
    """fan-out versus fast: the distinction is how many engines actually run.

    These matter because the two modes are otherwise indistinguishable from
    their output on a machine where only one backend is installed — which is
    the common case, and was the case when this was written.
    """

    @staticmethod
    def _counting_backends(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
        """Install two mock backends that record how often they are called."""
        calls = {"paddle": 0, "tesseract": 0}

        def paddle(_path):
            calls["paddle"] += 1
            return "paddle transcript with several plain words"

        def tesseract(_path, **_kwargs):
            calls["tesseract"] += 1
            return "tesseract transcript with several plain words"

        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_ocr", paddle)
        monkeypatch.setattr(auto_local, "_tesseract_ocr", tesseract)
        monkeypatch.setattr(auto_local, "combined_score", lambda text: 0.5)
        return calls

    def test_fanout_runs_every_eligible_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = self._counting_backends(monkeypatch)

        auto_local.ocr_image(Path("scan.jpg"))

        assert calls == {"paddle": 1, "tesseract": 1}


class TestAvailabilityGate:
    """`_IMPORT_OK` must cover everything scoring actually reaches for.

    This gate is what stops `tetrak-ocr backends` advertising a backend that
    dies on the first file. It got this wrong once already: torch was added to
    the `qa` extra but not to the gate, leaving exactly the failure the gate
    exists to prevent on any machine with transformers but no torch.
    """

    def test_the_gate_covers_every_scoring_dependency(self) -> None:
        assert set(qa_score.REQUIREMENTS) == {"spellchecker", "transformers", "torch"}

    def test_torch_is_checked_because_transformers_does_not_imply_it(self) -> None:
        """transformers has no torch dependency, so its presence proves nothing
        about whether qa_score's perplexity path can run."""
        assert "torch" in qa_score.REQUIREMENTS

    def test_auto_local_reads_the_shared_list_rather_than_its_own(self) -> None:
        """One list, two callers.

        auto_local gates the backend on it and `batch --quality-gate` gates the
        CLI flag on it. Keeping a private copy in either place is how the two
        drift apart, which is the same defect that let the two-element totals
        accumulator survive in the harness.
        """
        assert auto_local._IMPORT_OK is qa_score.is_available()


@pytest.mark.slow
class TestRouterSweepReproducesTheShippedWeight:
    """`LENGTH_WEIGHT` must still be an optimal choice against the committed
    sweep data -- the regression test for the fit itself.

    Marked `slow` per project convention for anything touching the corpus or
    its cached transcripts, but it needs neither: `router_sweep.csv` is
    already-scored, committed data derived from `router_cache/`, so this
    reads two small CSV/TOML files and does arithmetic. No OCR engine and no
    `qa` extra required, which is what keeps it running in CI's `corpus` job
    (`.[dev]` only) rather than skipping there.
    """

    def test_the_shipped_weight_matches_the_sweep_s_own_optimum(self) -> None:
        from evaluation.ocr.calibration import router_sweep, splits

        rows = router_sweep.read(router_sweep.ROUTER_SWEEP_CSV)
        fit, _held_out = splits.split("original-corpus")

        winner, _family = router_sweep.evaluate_family(rows, fit)
        shipped = router_sweep.Rule(
            "shipped auto_local.LENGTH_WEIGHT",
            lambda score, words, max_words: auto_local._effective_score(score, words, max_words),
        )

        shipped_regret = router_sweep.mean_regret(rows, fit, shipped)
        winner_regret = router_sweep.mean_regret(rows, fit, winner)
        assert shipped_regret == pytest.approx(winner_regret), (
            f"auto_local.LENGTH_WEIGHT={auto_local.LENGTH_WEIGHT} scores "
            f"{shipped_regret:.4f} mean regret on the committed sweep, but "
            f"the family's best is {winner_regret:.4f} ({winner.label}) -- "
            "re-run router_sweep.py --save and update LENGTH_WEIGHT to match."
        )


class TestPaddleVlOptIn:
    """PaddleOCR-VL is in the pool only when asked for.

    It measures as the strongest local backend on the corpus and wins the
    fixtures the rest of the pool reads worst, so it earns a place. It also
    takes minutes per page where the others take seconds, and fan-out runs
    every candidate on every file -- so admitting it by default would make
    the recommended backend far slower for everyone, including on the
    fixtures where it loses.
    """

    def test_absent_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_vl_ocr", lambda p: "vl text")

        names = [name for name, _ in auto_local._build_candidates(Path("scan.jpg"))]
        assert "paddle-vl" not in names

    def test_present_when_asked_for(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_vl_ocr", lambda p: "vl text")

        names = [
            name for name, _ in auto_local._build_candidates(Path("scan.jpg"), with_paddle_vl=True)
        ]
        assert names[0] == "paddle-vl"

    def test_offered_for_pdfs_too(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unlike vision, EasyOCR and Paddle, it reads documents -- so the
        PDF branch must not exclude it the way it excludes those three."""
        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_vl_ocr", lambda p: "vl text")

        names = [
            name for name, _ in auto_local._build_candidates(Path("scan.pdf"), with_paddle_vl=True)
        ]
        assert names == ["paddle-vl", "tesseract-auto"]

    def test_asking_for_it_uninstalled_is_not_an_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The flag is a request, not a requirement. Failing here would make
        `--with-paddle-vl` unusable in a mixed fleet where only some machines
        carry the extra."""
        monkeypatch.setattr(auto_local, "_marker_ocr", None)
        monkeypatch.setattr(auto_local, "_paddle_vl_ocr", None)

        names = [
            name for name, _ in auto_local._build_candidates(Path("scan.jpg"), with_paddle_vl=True)
        ]
        assert "paddle-vl" not in names
        assert names  # and the rest of the pool still runs
