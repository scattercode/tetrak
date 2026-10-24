"""Tests for the PaddleOCR backend.

Accuracy belongs in the benchmark. What these pin is the contract around the
result handling: the text is the same join of `rec_texts` it has always been,
and the polygons that sat beside it in the result dict -- read by nothing
until now -- arrive as spans in the package's convention, attached only where
they line up with the texts.

PaddleOCR is stubbed: CI installs no heavy backends, and the pipeline is
never constructed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from tetrak_ocr.backends import paddle
from tetrak_ocr.layout import Transcript, spans_of


def page(texts, polys=None, scores=None) -> dict:
    """One result page, shaped like PaddleOCR 3's OCRResult: a dict with these keys."""
    result = {"rec_texts": list(texts)}
    if polys is not None:
        result["rec_polys"] = polys
    if scores is not None:
        result["rec_scores"] = scores
    return result


def poly(left: float, top: float, right: float, bottom: float) -> list[list[float]]:
    return [[left, top], [right, top], [right, bottom], [left, bottom]]


class TestTranscript:
    def test_the_text_is_the_join_of_rec_texts(self) -> None:
        """What the backend wrote before, byte for byte, pages included."""
        results = [page(["one", "two"]), page(["three"])]
        assert paddle._transcript(results) == "one\ntwo\nthree"

    def test_the_spans_carry_the_polygons_and_scores(self) -> None:
        results = [
            page(
                ["a", "b"],
                polys=[poly(0, 0, 10, 10), poly(0, 20, 10, 30)],
                scores=[0.5, 1.0],
            )
        ]

        spans = spans_of(paddle._transcript(results))

        assert [(s.text, s.bbox, s.confidence) for s in spans] == [
            ("a", (0.0, 0.0, 10.0, 10.0), 50.0),
            ("b", (0.0, 20.0, 10.0, 30.0), 100.0),
        ]

    def test_polygons_that_do_not_line_up_give_text_without_boxes(self) -> None:
        """A wrong box is a silent error; no box is an honest one."""
        results = [page(["a", "b"], polys=[poly(0, 0, 10, 10)])]

        transcript = paddle._transcript(results)

        assert transcript == "a\nb"
        assert [s.bbox for s in spans_of(transcript)] == [None, None]

    def test_scores_that_do_not_line_up_are_dropped_but_the_boxes_kept(self) -> None:
        results = [page(["a"], polys=[poly(0, 0, 10, 10)], scores=[])]

        spans = spans_of(paddle._transcript(results))

        assert spans[0].bbox == (0.0, 0.0, 10.0, 10.0)
        assert spans[0].confidence is None

    def test_pages_not_shaped_like_a_result_are_skipped(self) -> None:
        """What the backend did before: anything without `rec_texts` is ignored."""
        results = [{"something": "else"}, "not a dict", page(["kept"])]
        assert paddle._transcript(results) == "kept"

    def test_empty_results_give_an_empty_transcript(self) -> None:
        assert paddle._transcript(None) == ""
        assert paddle._transcript([]) == ""
        assert spans_of(paddle._transcript([])) == []


class TestOcrImage:
    def test_the_result_reaches_the_caller_as_a_transcript(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        class Engine:
            def predict(self, target):
                return [page(["hello"], polys=[poly(1, 2, 3, 4)], scores=[0.9])]

        monkeypatch.setattr(paddle, "_ocr_instance", Engine())
        image = tmp_path / "scan.png"
        Image.new("RGB", (10, 10), "white").save(image)

        transcript = paddle.ocr_image(image)

        assert isinstance(transcript, Transcript)
        assert transcript == "hello"
        assert spans_of(transcript)[0].bbox == (1.0, 2.0, 3.0, 4.0)
