"""Tests for the Apple Vision backend.

Vision is macOS-only and its recognition is a system service, so these check
the contract around it rather than its accuracy: that the module refuses what
it cannot read, that reading order is reconstructed correctly from Apple's
bottom-left origin, and that an unavailable backend fails with a reason.

Accuracy belongs in the benchmark, not here -- `evaluate --all` measures it
against the corpus, and pinning a score in a unit test would make an OS
upgrade look like a code regression.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tetrak_ocr.backends import vision

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="Vision is macOS-only")


class TestAvailability:
    def test_reports_unavailable_off_macos(self) -> None:
        """The registry's _IMPORT_OK contract: importable everywhere, honest
        about whether it can actually run."""
        assert vision._IS_MACOS is (sys.platform == "darwin")

    def test_unavailable_backend_explains_why(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A direct caller gets a reason rather than a NameError."""
        monkeypatch.setattr(vision, "_IMPORT_OK", False)
        with pytest.raises(RuntimeError, match="unavailable"):
            vision.ocr_image(Path("anything.png"))


class TestInputHandling:
    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            vision.ocr_image(Path("does-not-exist.png"))

    def test_pdf_is_refused_by_extension(self, tmp_path: Path) -> None:
        """Vision takes images, not documents. Refusing by extension is
        better than handing Pillow a PDF and failing obscurely."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        with pytest.raises(ValueError, match="Unsupported file type"):
            vision.ocr_image(pdf)


class TestReadingOrder:
    """Apple's bounding boxes put the origin at the BOTTOM left, the opposite
    of every image convention elsewhere in this package. Sorting naively
    returns the document upside down, which is silent and looks like poor OCR
    rather than a bug -- hence these.
    """

    def test_topmost_region_comes_first(self) -> None:
        # y=0.9 is near the top of the page in Apple's coordinates.
        annotations = [
            ("bottom", 0.99, (0.1, 0.1, 0.2, 0.05)),
            ("top", 0.99, (0.1, 0.9, 0.2, 0.05)),
        ]
        assert vision._to_reading_order(annotations).splitlines() == ["top", "bottom"]

    def test_regions_on_one_line_read_left_to_right(self) -> None:
        annotations = [
            ("second", 0.99, (0.5, 0.5, 0.2, 0.05)),
            ("first", 0.99, (0.1, 0.5, 0.2, 0.05)),
        ]
        assert vision._to_reading_order(annotations) == "first second"

    def test_near_but_not_equal_y_stays_on_one_line(self) -> None:
        """Two boxes on the same visual line rarely share an exact y, so the
        tolerance exists. Without it a line fragments into one row per word."""
        annotations = [
            ("a", 0.99, (0.1, 0.500, 0.1, 0.05)),
            ("b", 0.99, (0.3, 0.505, 0.1, 0.05)),
        ]
        assert vision._to_reading_order(annotations) == "a b"

    def test_clearly_separate_lines_do_not_merge(self) -> None:
        annotations = [
            ("upper", 0.99, (0.1, 0.80, 0.1, 0.05)),
            ("lower", 0.99, (0.1, 0.20, 0.1, 0.05)),
        ]
        assert vision._to_reading_order(annotations).splitlines() == ["upper", "lower"]

    def test_empty_input_gives_empty_output(self) -> None:
        assert vision._to_reading_order([]) == ""

    def test_regions_without_a_box_are_kept(self) -> None:
        """Defensive: ocrmac has changed its tuple shape between releases, and
        dropping text because the geometry moved would be a silent loss."""
        assert vision._to_reading_order([("text",)]) == "text"


class TestLanguages:
    def test_reports_the_languages_this_mac_supports(self) -> None:
        """Regression: this asked ocrmac for a helper it does not have, so it
        returned [] on every call while appearing to consult the OS."""
        langs = vision.supported_languages()
        assert langs, "Vision should report at least one language on macOS"
        assert any(code.startswith("en") for code in langs)

    def test_armenian_is_not_available(self) -> None:
        """Recorded because it is a live question for this project, not as a
        complaint about Vision. If a future macOS adds it, this fails and the
        docstring needs revisiting."""
        assert not [c for c in vision.supported_languages() if c.startswith("hy")]
