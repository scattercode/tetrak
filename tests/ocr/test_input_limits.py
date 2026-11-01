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

        with pytest.raises(InputRefusedError, match="says PNG, is GIF"):
            open_image(path)

    def test_a_postscript_file_never_reaches_the_eps_reader(self, tmp_path: Path) -> None:
        """The October 2026 flaw's path: an EPS header behind a raster name."""
        path = tmp_path / "scan.jpg"
        path.write_bytes(b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\n")

        with pytest.raises(InputRefusedError, match="says JPEG, is PostScript"):
            open_image(path)


class TestPixels:
    def test_an_image_over_the_limit_is_refused(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(imaging, "MAX_PIXELS", 200 * 300 - 1)
        path = tmp_path / "poster.png"
        page().save(path)

        with pytest.raises(InputRefusedError, match="the limit is 59,999"):
            open_image(path)

    def test_a_later_tiff_frame_over_the_limit_is_refused(self, tmp_path, monkeypatch) -> None:
        """Each frame has its own size; checking frame 0 alone is not enough.

        The whole chain is walked before Pillow opens the file, so the file
        is refused at once, before even the first frame is handed out.
        """
        monkeypatch.setattr(imaging, "MAX_PIXELS", 200 * 300)
        path = tmp_path / "register.tif"
        page().save(path, save_all=True, append_images=[page(400, 600)])

        with pytest.raises(InputRefusedError, match="240,000 pixels; the limit is 60,000"):
            next(iter_frames(path))


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

        with pytest.raises(InputRefusedError, match="2,400,000,000 pixels"):
            with streamed_pages(path):
                pass

    def test_a_file_poppler_cannot_read_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.pdf"
        path.write_bytes(b"not a pdf at all")

        with pytest.raises(InputRefusedError, match="unknown format"):
            check_pdf(path)

    def test_a_pdf_that_carries_javascript_is_refused(self, tmp_path: Path) -> None:
        """sillybos 3 refuses the features a scanned book never has; the reason reaches triage."""
        path = tmp_path / "scripted.pdf"
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R /OpenAction 4 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>",
            b"<< /Type /Action /S /JavaScript /JS (app.alert('hello');) >>",
        ]
        out = bytearray(b"%PDF-1.4\n")
        offsets = []
        for number, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
        for position in offsets:
            out += f"{position:010d} 00000 n \n".encode()
        out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        path.write_bytes(bytes(out))

        with pytest.raises(InputRefusedError, match="a PDF with JavaScript"):
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
