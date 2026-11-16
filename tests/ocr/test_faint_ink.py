"""The faint-page rule: which pages are stretched before detection, and
that every other page reaches the reader exactly as it always has.

The rule was measured on real scans (brief 023); what these pin is its
shape. The pages here are drawn, not scanned: paper at one grey level, a
block of "ink" at another, sized so the ink is the share of the page a
block of text is.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tetrak_ocr.backends import armenian
from tetrak_ocr.imaging import FAINT_INK_LEVEL, detector_input, lift_faint_ink


def page(paper: int, ink: int | None, *, ink_box=(200, 300, 800, 900)) -> Image.Image:
    """A 1000 x 1400 page: *paper* everywhere, *ink* in one block."""
    image = Image.new("L", (1000, 1400), paper)
    if ink is not None:
        ImageDraw.Draw(image).rectangle(ink_box, fill=ink)
    return image


class TestWhichPagesAreFaint:
    def test_black_on_white_is_left_alone(self) -> None:
        assert lift_faint_ink(page(255, 0)) is None

    def test_a_grey_photograph_is_stretched(self) -> None:
        """Paper near 160, ink near 95: the page the rule was written for."""
        lifted = lift_faint_ink(page(160, 95))
        assert lifted is not None
        assert lifted.mode == "L"
        low, high = lifted.getextrema()
        assert low <= 5
        assert high >= 250

    def test_black_ink_on_toned_paper_is_left_alone(self) -> None:
        """Toned paper is not faint ink; stretching one such register cost
        it word recall, so the rule looks at the ink and not the paper."""
        assert lift_faint_ink(page(162, 8)) is None

    def test_a_sparse_page_of_black_ink_is_left_alone(self) -> None:
        """A title page: a few words, properly black. The darkest
        thousandth still finds them."""
        sparse = page(250, 0, ink_box=(450, 650, 520, 690))
        assert lift_faint_ink(sparse) is None

    def test_a_blank_grey_leaf_is_left_alone(self) -> None:
        """Nothing to lift: stretching it would only amplify the paper."""
        assert lift_faint_ink(page(170, None)) is None
        assert lift_faint_ink(page(170, 160)) is None

    def test_a_dark_edge_does_not_pass_for_ink(self) -> None:
        """A binding or a scanner bed at the margin is outside the region
        the page is judged on, so the faint text is still found faint."""
        image = page(160, 95)
        ImageDraw.Draw(image).rectangle((0, 0, 1000, 60), fill=0)
        assert lift_faint_ink(image) is not None

    def test_the_threshold_is_where_it_was_measured(self) -> None:
        assert lift_faint_ink(page(230, FAINT_INK_LEVEL)) is None
        assert lift_faint_ink(page(230, FAINT_INK_LEVEL + 1)) is not None

    def test_a_colour_page_is_judged_in_grey(self) -> None:
        colour = Image.merge("RGB", [page(160, 95)] * 3)
        assert lift_faint_ink(colour) is not None


class TestWhatTheReaderIsHanded:
    def test_an_ordinary_page_is_handed_over_as_its_path(self, tmp_path: Path) -> None:
        """Not re-encoded, not even opened by the reader differently: the
        same string the backends have always passed."""
        scan = tmp_path / "page.png"
        page(255, 0).save(scan)
        assert detector_input(scan) == str(scan)

    def test_a_faint_page_is_handed_over_stretched(self, tmp_path: Path) -> None:
        scan = tmp_path / "faint.jpg"
        page(160, 95).save(scan, quality=95)
        handed = detector_input(scan)
        assert isinstance(handed, bytes)
        low, high = Image.open(io.BytesIO(handed)).convert("L").getextrema()
        assert low <= 5
        assert high >= 250

    def test_a_tiff_is_still_converted(self, tmp_path: Path) -> None:
        scan = tmp_path / "page.tif"
        page(255, 0).save(scan)
        handed = detector_input(scan)
        assert isinstance(handed, bytes)
        assert Image.open(io.BytesIO(handed)).format == "PNG"


class TestTheArmenianBackendUsesIt:
    @pytest.fixture
    def reader(self, monkeypatch: pytest.MonkeyPatch):
        class Reader:
            seen: list = []

            def readtext(self, image, **kwargs):
                self.seen.append(image)
                return []

        instance = Reader()
        monkeypatch.setattr(armenian, "_reader", instance)
        monkeypatch.setattr(armenian, "_get_reader", lambda: instance)
        return instance

    def test_a_faint_page_reaches_the_detector_stretched(self, reader, tmp_path: Path) -> None:
        scan = tmp_path / "faint.png"
        page(160, 95).save(scan)
        armenian.ocr_image(scan)
        assert isinstance(reader.seen[-1], bytes)

    def test_an_ordinary_page_reaches_it_unchanged(self, reader, tmp_path: Path) -> None:
        scan = tmp_path / "page.png"
        page(255, 0).save(scan)
        armenian.ocr_image(scan)
        assert reader.seen[-1] == str(scan)
