"""Unit tests for ocr_image.py.

These tests generate a simple image programmatically using Pillow so they
run without needing any external fixture files — useful for CI and for
verifying that Tesseract is correctly installed on a new machine.

The generated images intentionally use large, clear text so that Tesseract
can reliably extract it regardless of font availability.
"""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tetrak_ocr.backends.tesseract import SUPPORTED_EXTENSIONS, ocr_image


def make_text_image(tmp_path: Path, text: str, filename: str = "test.png") -> Path:
    """Create a simple white PNG image containing the given text."""
    img = Image.new("RGB", (600, 100), color="white")
    draw = ImageDraw.Draw(img)
    # Use the default PIL bitmap font — always available, no file dependency.
    draw.text((10, 10), text, fill="black")
    path = tmp_path / filename
    img.save(path)
    return path


class TestOcrImage:
    def test_returns_string(self, tmp_path):
        """OCR on a valid image should return a string."""
        path = make_text_image(tmp_path, "Hello")
        result = ocr_image(path)
        assert isinstance(result, str)

    def test_detects_text(self, tmp_path):
        """OCR on an image with clear text should return a non-empty result."""
        path = make_text_image(tmp_path, "ABCDEF")
        result = ocr_image(path)
        # We don't assert exact accuracy — Tesseract may vary — but the result
        # should contain at least some characters.
        assert len(result.strip()) > 0

    def test_file_not_found(self):
        """Passing a non-existent path should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ocr_image(Path("/tmp/does-not-exist-xyz.png"))

    def test_unsupported_extension(self, tmp_path):
        """Passing an unsupported file type should raise ValueError."""
        path = tmp_path / "test.bmp"
        path.write_bytes(b"fake")
        with pytest.raises(ValueError, match="Unsupported file type"):
            ocr_image(path)

    def test_supported_extensions_set(self):
        """Verify the expected extensions are all present."""
        assert ".jpg" in SUPPORTED_EXTENSIONS
        assert ".jpeg" in SUPPORTED_EXTENSIONS
        assert ".png" in SUPPORTED_EXTENSIONS
        assert ".tif" in SUPPORTED_EXTENSIONS
        assert ".tiff" in SUPPORTED_EXTENSIONS
        assert ".pdf" in SUPPORTED_EXTENSIONS

    @pytest.mark.parametrize("ext", [".jpg", ".png", ".tiff"])
    def test_raster_formats(self, tmp_path, ext):
        """OCR should work on common raster image formats."""
        path = make_text_image(tmp_path, "TEST", filename=f"test{ext}")
        result = ocr_image(path)
        assert isinstance(result, str)


class TestLanguagePassThrough:
    """The `lang` kwarg must reach pytesseract untouched.

    Mocked rather than run: the Armenian traineddata this exists for
    (brief 011, the Armenian recogniser) is not installed in CI,
    and what these tests pin is the plumbing, not Tesseract's Armenian.
    """

    @staticmethod
    def _capture_calls(monkeypatch):
        from tetrak_ocr.backends import tesseract

        calls = []

        def fake_image_to_string(image, config="", lang=None):
            calls.append({"config": config, "lang": lang})
            return "text"

        monkeypatch.setattr(tesseract.pytesseract, "image_to_string", fake_image_to_string)
        return calls

    def test_lang_reaches_pytesseract(self, tmp_path, monkeypatch):
        calls = self._capture_calls(monkeypatch)
        path = make_text_image(tmp_path, "whatever")

        ocr_image(path, lang="hye")

        assert calls and calls[0]["lang"] == "hye"

    def test_default_is_none_not_a_hardcoded_english(self, tmp_path, monkeypatch):
        """None delegates the default to Tesseract itself, so the behaviour
        of every existing caller is exactly what it was before `lang`."""
        calls = self._capture_calls(monkeypatch)
        path = make_text_image(tmp_path, "whatever")

        ocr_image(path)

        assert calls and calls[0]["lang"] is None

    def test_lang_reaches_every_tiff_frame(self, tmp_path, monkeypatch):
        """The multi-page TIFF path builds its calls separately from the
        single-image path, so it needs its own pin."""
        from PIL import Image

        from tetrak_ocr.backends import tesseract

        calls = self._capture_calls(monkeypatch)
        monkeypatch.setattr(tesseract, "frame_count", lambda path: 2)
        monkeypatch.setattr(
            tesseract,
            "iter_frames",
            lambda path: iter(
                [Image.new("RGB", (60, 20), "white"), Image.new("RGB", (60, 20), "white")]
            ),
        )
        path = make_text_image(tmp_path, "whatever", filename="doc.tiff")

        tesseract.ocr_image(path, lang="hye")

        assert len(calls) == 2
        assert all(call["lang"] == "hye" for call in calls)

    def test_lang_reaches_every_pdf_page(self, tmp_path, monkeypatch):
        from tetrak_ocr.backends import tesseract

        calls = self._capture_calls(monkeypatch)

        def fake_convert_from_path(path):
            from PIL import Image

            return [Image.new("RGB", (60, 20), "white"), Image.new("RGB", (60, 20), "white")]

        import pdf2image

        monkeypatch.setattr(pdf2image, "convert_from_path", fake_convert_from_path)
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-fake")

        tesseract.ocr_image(pdf, lang="hye+eng")

        assert len(calls) == 2
        assert all(call["lang"] == "hye+eng" for call in calls)
