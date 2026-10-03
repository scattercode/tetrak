"""Tests for the Armenian backend.

The recogniser itself is a trained model with published numbers; its
accuracy belongs in the benchmark, not here. What these check is the
contract around it: that it refuses what it cannot read, that the
homoglyph fold is applied to every region, and that a two-column page is
serialised column by column rather than across the gutter.

The last of those is the reason this backend exists in the shape it does.
Joining detected regions in detector order costs nothing in word recall
and roughly halves character similarity, so a test that only checked the
text came back would pass while the backend was useless for the metric it
was built to move.

`tetrak_hy` is stubbed throughout: CI installs no heavy backends, and
these need geometry and string handling, not weights.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from PIL import Image

from tetrak_ocr.backends import armenian


@pytest.fixture
def stub_tetrak_hy(monkeypatch: pytest.MonkeyPatch):
    """A stand-in for the library, with a real-enough fold.

    The fold is the genuine rule in miniature -- Latin `h` becomes `հ`
    inside a token that already has an Armenian letter -- so a test can
    tell whether the backend applied it without depending on the
    installed package.
    """
    module = types.ModuleType("tetrak_hy")

    def fold_script(text: str) -> str:
        return " ".join(
            token.replace("h", "հ") if any("԰" <= c <= "֏" for c in token) else token
            for token in text.split()
        )

    module.fold_script = fold_script
    module.reader = lambda **kwargs: None
    monkeypatch.setattr(armenian, "tetrak_hy", module, raising=False)
    monkeypatch.setitem(sys.modules, "tetrak_hy", module)
    return module


def region(text: str, left: float, top: float, right: float, bottom: float, conf: float = 0.9):
    """One EasyOCR result: a four-point polygon, the text, a confidence."""
    return ([[left, top], [right, top], [right, bottom], [left, bottom]], text, conf)


class TestInputHandling:
    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            armenian.ocr_image(Path("does-not-exist.png"))

    def test_pdf_is_refused_by_extension(self, tmp_path: Path) -> None:
        """This backend takes images. PDFs are converted upstream."""
        pdf = tmp_path / "scan.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        with pytest.raises(ValueError, match="Unsupported file type"):
            armenian.ocr_image(pdf)

    def test_pdf_is_not_in_the_supported_set(self) -> None:
        assert ".pdf" not in armenian.SUPPORTED_EXTENSIONS
        assert ".jpg" in armenian.SUPPORTED_EXTENSIONS


class TestSpans:
    def test_the_fold_is_applied_to_every_region(self, stub_tetrak_hy) -> None:
        """The recogniser emits Latin twins inside Armenian words; the fold
        is what puts them back, and it belongs at the point text enters
        the pipeline rather than at each caller."""
        spans = armenian._spans([region("hայ", 0, 0, 10, 10)])
        assert [s.text for s in spans] == ["հայ"]

    def test_a_polygon_becomes_its_axis_aligned_extent(self, stub_tetrak_hy) -> None:
        spans = armenian._spans([region("ա", 5, 7, 25, 27)])
        assert spans[0].bbox == (5.0, 7.0, 25.0, 27.0)

    def test_confidence_is_rescaled_to_the_documented_range(self, stub_tetrak_hy) -> None:
        """EasyOCR reports 0-1; TextSpan documents 0-100."""
        spans = armenian._spans([region("ա", 0, 0, 10, 10, conf=0.5)])
        assert spans[0].confidence == 50.0

    def test_no_regions_gives_no_spans(self, stub_tetrak_hy) -> None:
        assert armenian._spans([]) == []


class TestReadingOrder:
    """The reason the backend serialises through tetrak_ocr.layout."""

    def two_column_regions(self):
        regions = []
        for row in range(6):
            top = 200 + row * 30
            regions.append(region(f"L{row}", 100, top, 260, top + 10))
            regions.append(region(f"R{row}", 500, top, 660, top + 10))
        return regions

    def test_a_two_column_page_is_read_column_by_column(self, stub_tetrak_hy) -> None:
        from tetrak_ocr.layout import to_text

        text = to_text(armenian._spans(self.two_column_regions()))
        assert text.split("\n") == [f"L{r}" for r in range(6)] + [f"R{r}" for r in range(6)]

    def test_detector_order_would_have_interleaved_them(self, stub_tetrak_hy) -> None:
        """What the naive join produces, for contrast: this is the output
        that scores 0.12 character similarity where the ordered text scores
        far higher, and it is why joining `readtext(detail=0)` was not
        good enough."""
        naive = "\n".join(text for _, text, _ in self.two_column_regions())
        assert naive.split("\n")[:4] == ["L0", "R0", "L1", "R1"]


class TestReaderSelection:
    """The word list is used when the library has one, and greedy decoding
    otherwise. Both fallbacks matter: an older library rejects `lexicon=`
    outright, and a newer one with no released list refuses to load it.
    """

    class _Reader:
        def __init__(self) -> None:
            self.decoders: list[str] = []

        def readtext(self, image, **kwargs):
            self.decoders.append(kwargs["decoder"])
            return [region("ա", 0, 0, 10, 10)]

    @pytest.fixture
    def library(self, stub_tetrak_hy, monkeypatch: pytest.MonkeyPatch):
        """The stub, with a fresh reader singleton and a record of each call."""
        monkeypatch.setattr(armenian, "_reader", None)
        monkeypatch.setattr(armenian, "_decoder", "greedy")
        stub_tetrak_hy.WeightsNotAvailableError = type(
            "WeightsNotAvailableError", (RuntimeError,), {}
        )
        stub_tetrak_hy.calls = []
        return stub_tetrak_hy

    def read(self, tmp_path: Path) -> None:
        page = tmp_path / "page.png"
        Image.new("RGB", (20, 20), "white").save(page)
        armenian.ocr_image(page)

    def test_a_released_word_list_selects_beam_search(self, library, tmp_path: Path) -> None:
        reader = self._Reader()

        def make(**kwargs):
            library.calls.append(kwargs)
            return reader

        library.reader = make
        self.read(tmp_path)
        assert library.calls == [{"verbose": False, "lexicon": True}]
        assert reader.decoders == ["beamsearch"]

    def test_an_older_library_without_lexicon_reads_greedily(self, library, tmp_path: Path) -> None:
        reader = self._Reader()

        def make(verbose):  # the pre-0.8 signature: no `lexicon`
            library.calls.append({"verbose": verbose})
            return reader

        library.reader = make
        self.read(tmp_path)
        assert library.calls == [{"verbose": False}]
        assert reader.decoders == ["greedy"]

    def test_no_released_word_list_reads_greedily(self, library, tmp_path: Path) -> None:
        reader = self._Reader()

        def make(**kwargs):
            library.calls.append(kwargs)
            if kwargs.get("lexicon"):
                raise library.WeightsNotAvailableError("no word list released")
            return reader

        library.reader = make
        self.read(tmp_path)
        assert library.calls == [{"verbose": False, "lexicon": True}, {"verbose": False}]
        assert reader.decoders == ["greedy"]

    def test_the_reader_is_built_once(self, library, tmp_path: Path) -> None:
        reader = self._Reader()

        def make(**kwargs):
            library.calls.append(kwargs)
            return reader

        library.reader = make
        self.read(tmp_path)
        self.read(tmp_path)
        assert len(library.calls) == 1
        assert reader.decoders == ["beamsearch", "beamsearch"]
