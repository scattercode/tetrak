"""Files refused before any decoder reads past the header.

Pillow picks its reader from a file's contents, not its name, so the only
gate that counts is the list of readers it may use. These build every file in
memory with Pillow itself; the PDF cases need poppler's ``pdfinfo`` and skip
without it.
"""

import shutil
from pathlib import Path

import pytest
from PIL import Image

from tetrak_ocr import imaging
from tetrak_ocr.errors import InputRefusedError
from tetrak_ocr.imaging import check_pdf, iter_frames, open_image, streamed_pages
from tetrak_ocr.pdf_output import _page_size

needs_poppler = pytest.mark.skipif(
    shutil.which("pdfinfo") is None, reason="pdfinfo (poppler) reads the PDF's structure"
)


def page(width: int = 200, height: int = 300) -> Image.Image:
    return Image.new("RGB", (width, height), "white")


class TestFormats:
    def test_a_supported_scan_opens(self, tmp_path: Path) -> None:
        path = tmp_path / "postcard.png"
        page().save(path)

        with open_image(path) as image:
            assert image.format == "PNG"

    def test_a_file_whose_name_lies_is_refused(self, tmp_path: Path) -> None:
        """A GIF called .png: Pillow would read it as a GIF if allowed to."""
        path = tmp_path / "postcard.png"
        page().save(path, format="GIF")

        with pytest.raises(InputRefusedError, match="not one of the formats"):
            open_image(path)

    def test_a_postscript_file_never_reaches_the_eps_reader(self, tmp_path: Path) -> None:
        """The October 2026 flaw's path: an EPS header behind a raster name."""
        path = tmp_path / "scan.jpg"
        path.write_bytes(b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\n")

        with pytest.raises(InputRefusedError, match="not one of the formats"):
            open_image(path)


class TestPixels:
    def test_an_image_over_the_limit_is_refused(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(imaging, "MAX_PIXELS", 200 * 300 - 1)
        path = tmp_path / "poster.png"
        page().save(path)

        with pytest.raises(InputRefusedError, match="the limit is 59,999"):
            open_image(path)

    def test_a_later_tiff_frame_over_the_limit_is_refused(self, tmp_path, monkeypatch) -> None:
        """Each frame has its own size; checking frame 0 alone is not enough."""
        monkeypatch.setattr(imaging, "MAX_PIXELS", 200 * 300)
        path = tmp_path / "register.tif"
        page().save(path, save_all=True, append_images=[page(400, 600)])

        frames = iter_frames(path)
        next(frames).close()
        with pytest.raises(InputRefusedError, match="400 x 600"):
            next(frames)


@needs_poppler
class TestPdf:
    def test_a_sane_pdf_is_counted(self, tmp_path: Path) -> None:
        path = tmp_path / "programme.pdf"
        page().save(path, save_all=True, append_images=[page()], resolution=300)

        assert check_pdf(path) == 2

    def test_a_pdf_over_the_page_limit_is_refused(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(imaging, "MAX_PDF_PAGES", 1)
        path = tmp_path / "programme.pdf"
        page().save(path, save_all=True, append_images=[page()], resolution=300)

        with pytest.raises(InputRefusedError, match="2 pages; the limit is 1"):
            check_pdf(path)

    def test_a_page_too_large_to_render_is_refused_before_rendering(self, tmp_path: Path) -> None:
        """200 x 300 pixels at 1 dpi is a page 200 x 300 inches."""
        path = tmp_path / "poster.pdf"
        page().save(path, resolution=1)

        with pytest.raises(InputRefusedError, match="Page 1 is 14400 x 21600 pts"):
            with streamed_pages(path):
                pass

    def test_a_file_poppler_cannot_read_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.pdf"
        path.write_bytes(b"not a pdf at all")

        with pytest.raises(InputRefusedError, match="could not read it as a PDF"):
            check_pdf(path)


class TestPageSize:
    def test_pillows_one_dpi_for_no_resolution_is_not_believed(self) -> None:
        image = page()
        image.info["dpi"] = (1, 1)

        assert _page_size(image) == (48.0, 72.0)

    def test_a_real_resolution_is_kept(self) -> None:
        image = page(600, 900)
        image.info["dpi"] = (600, 600)

        assert _page_size(image) == (72.0, 108.0)
