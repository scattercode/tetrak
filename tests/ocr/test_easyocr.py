"""Tests for the stock EasyOCR backend.

Accuracy belongs in the benchmark. What these pin is the contract around the
one change this backend has had: it asks `readtext` for the detailed result
instead of the bare texts, so the boxes reach the caller as spans. The text
must be byte for byte what `detail=0` gave -- the benchmark column must not
move -- and the geometry beside it must arrive in the package's convention.

`easyocr` is stubbed: CI installs no heavy backends, and these need geometry
and string handling, not weights.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from tetrak_ocr.backends import easyocr
from tetrak_ocr.layout import Transcript, spans_of


def region(text: str, left: float, top: float, right: float, bottom: float, conf: float = 0.9):
    """One `readtext(detail=1)` result: a four-point polygon, the text, a confidence."""
    return ([[left, top], [right, top], [right, bottom], [left, bottom]], text, conf)


class TestTranscript:
    def test_the_text_is_what_detail_zero_returned(self) -> None:
        """`readtext(detail=0)` is `[item[1] for item in result]`. Joining those
        is the output this backend has always produced, and still does."""
        results = [region("first", 0, 0, 10, 10), region("second", 0, 20, 10, 30)]
        detail_zero = [text for _, text, _ in results]

        assert easyocr._transcript(results) == "\n".join(detail_zero)

    def test_the_spans_carry_the_boxes_in_detector_order(self) -> None:
        """The engine's order, not a reading order: ordering is a separate,
        measured pass that the writer applies."""
        results = [region("lower", 0, 20, 10, 30), region("upper", 0, 0, 10, 10)]

        spans = spans_of(easyocr._transcript(results))

        assert [s.text for s in spans] == ["lower", "upper"]
        assert spans[0].bbox == (0.0, 20.0, 10.0, 30.0)

    def test_a_polygon_becomes_its_axis_aligned_extent(self) -> None:
        skewed = ([[10, 0], [30, 4], [28, 14], [8, 10]], "slant", 0.9)
        assert spans_of(easyocr._transcript([skewed]))[0].bbox == (8.0, 0.0, 30.0, 14.0)

    def test_confidence_is_rescaled_to_the_documented_range(self) -> None:
        """EasyOCR reports 0-1; TextSpan documents 0-100."""
        spans = spans_of(easyocr._transcript([region("a", 0, 0, 10, 10, conf=0.25)]))
        assert spans[0].confidence == 25.0

    def test_no_regions_is_an_empty_transcript_with_no_spans(self) -> None:
        transcript = easyocr._transcript([])
        assert transcript == ""
        assert spans_of(transcript) == []


class TestOcrImage:
    """The reader is asked for the detailed result, and it reaches the caller."""

    def test_the_result_reaches_the_caller_as_a_transcript(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        seen: dict = {}

        class Reader:
            def readtext(self, image, **kwargs):
                seen.update(kwargs)
                return [region("hello", 0, 0, 50, 10), region("world", 0, 20, 50, 30)]

        monkeypatch.setattr(easyocr, "_reader", Reader())
        page = tmp_path / "page.png"
        Image.new("RGB", (60, 40), "white").save(page)

        transcript = easyocr.ocr_image(page)

        assert seen["detail"] == 1, "detail=0 is the texts alone; the boxes need detail=1"
        assert isinstance(transcript, Transcript)
        assert transcript == "hello\nworld"
        assert [s.bbox for s in spans_of(transcript)] == [
            (0.0, 0.0, 50.0, 10.0),
            (0.0, 20.0, 50.0, 30.0),
        ]
