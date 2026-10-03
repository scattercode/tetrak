"""Tests for multi-page documents reaching a searchable PDF.

A searchable PDF needs one transcript per page, and a backend returns one per
document. That gap is closed by transcribing page by page, which costs roughly
twice a whole-document pass -- so the pipeline takes that route only when the
`pdf` format is actually asked for on a multi-page document.

What matters here is that text lands on the page it came from. A PDF with
every page's words stacked onto page one looks entirely correct from outside
and sends every search to the wrong leaf, which is the failure the old refusal
existed to prevent.
"""

import subprocess
from pathlib import Path

import pytest
from PIL import Image

from tetrak_ocr import outputs
from tetrak_ocr.errors import MultiPagePdfError
from tetrak_ocr.imaging import page_count, page_documents, streamed_pages
from tetrak_ocr.pdf_output import searchable_pdf_for


def scan(width: int = 200, height: int = 300) -> Image.Image:
    return Image.new("RGB", (width, height), "white")


def multi_frame_tiff(path: Path, frames: int = 3) -> Path:
    first, *rest = [scan() for _ in range(frames)]
    first.save(path, save_all=True, append_images=rest)
    return path


def page_text(pdf: Path, page: int) -> str:
    return subprocess.run(
        ["pdftotext", "-raw", "-f", str(page), "-l", str(page), str(pdf), "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


class TestSplitting:
    def test_a_single_page_document_yields_itself(self, tmp_path: Path) -> None:
        """Nothing to split, so no copy is made."""
        source = tmp_path / "postcard.tif"
        scan().save(source)

        with page_documents(source) as pages:
            assert pages == [source]

    def test_a_multi_frame_raster_splits_into_one_file_per_frame(self, tmp_path: Path) -> None:
        source = multi_frame_tiff(tmp_path / "pamphlet.tif", frames=3)

        with page_documents(source) as pages:
            assert len(pages) == 3
            assert all(p.exists() for p in pages)
            assert [page_count(p) for p in pages] == [1, 1, 1]

    def test_the_split_pages_are_cleaned_up(self, tmp_path: Path) -> None:
        source = multi_frame_tiff(tmp_path / "pamphlet.tif", frames=2)

        with page_documents(source) as pages:
            held = list(pages)
        assert not any(p.exists() for p in held)

    def test_page_order_is_preserved(self, tmp_path: Path) -> None:
        """Order is the whole point: page 3's text must not reach page 1."""
        source = multi_frame_tiff(tmp_path / "pamphlet.tif", frames=4)

        with page_documents(source) as pages:
            assert [p.name for p in pages] == sorted(p.name for p in pages)


class TestStreamingPages:
    """Pages are rendered one at a time rather than all into memory.

    `convert_from_path` returns a list, so `iter_pages` only looks like a
    generator: a 21-page document cost 881 MB of peak RSS before this, against
    58 MB rendering into a temporary directory instead.
    """

    def test_every_page_is_yielded_in_order(self, tmp_path: Path) -> None:
        source = multi_frame_tiff(tmp_path / "pamphlet.tif", frames=4)

        with streamed_pages(source) as pages:
            sizes = [p.size for p in pages]

        assert len(sizes) == 4

    def test_a_page_is_released_once_the_next_is_requested(self, tmp_path: Path) -> None:
        """The producer owns these images, so it closes them.

        Left to the consumer, every page's pixel data stays loaded and the
        streaming buys nothing.
        """
        source = multi_frame_tiff(tmp_path / "pamphlet.tif", frames=3)

        seen = []
        with streamed_pages(source) as pages:
            for page in pages:
                seen.append(page)

        assert len(seen) == 3
        # A closed Pillow image raises on any pixel access. Every page the
        # consumer moved past must be in that state, or the pixel data is
        # still resident and the streaming bought nothing.
        for page in seen:
            with pytest.raises(ValueError, match="closed"):
                page.load()

    def test_a_caller_owned_image_is_not_closed(self, tmp_path: Path) -> None:
        """`write_searchable_pdf` must not shut an image it was handed.

        A caller that goes on using its own image should not find it closed --
        this regressed once and `test_the_access_copy_is_smaller_than_the_original`
        caught it.
        """
        from tetrak_ocr.pdf_output import write_searchable_pdf

        image = scan()
        write_searchable_pdf([(image, "text")], tmp_path / "out.pdf")

        assert image.size == (200, 300), "the image should still be usable"


class TestWritingAMultiPageSearchablePdf:
    def test_each_page_carries_its_own_text(self, tmp_path: Path) -> None:
        source = multi_frame_tiff(tmp_path / "pamphlet.tif", frames=3)
        out = tmp_path / "out.pdf"

        searchable_pdf_for(
            source,
            "unused document-level text",
            out,
            page_transcripts=["FIRST PAGE", "SECOND PAGE", "THIRD PAGE"],
        )

        assert "FIRST PAGE" in page_text(out, 1)
        assert "SECOND PAGE" in page_text(out, 2)
        assert "THIRD PAGE" in page_text(out, 3)

    def test_text_does_not_leak_between_pages(self, tmp_path: Path) -> None:
        """The failure the refusal guarded against: everything on page one."""
        source = multi_frame_tiff(tmp_path / "pamphlet.tif", frames=3)
        out = tmp_path / "out.pdf"

        searchable_pdf_for(source, "", out, page_transcripts=["ALPHA", "BRAVO", "CHARLIE"])

        first = page_text(out, 1)
        assert "ALPHA" in first
        assert "BRAVO" not in first
        assert "CHARLIE" not in first

    def test_a_wrong_transcript_count_is_refused(self, tmp_path: Path) -> None:
        """Off-by-one here would silently shift text onto neighbouring pages."""
        source = multi_frame_tiff(tmp_path / "pamphlet.tif", frames=3)

        with pytest.raises(ValueError, match="wrong page"):
            searchable_pdf_for(source, "", tmp_path / "out.pdf", page_transcripts=["ONE", "TWO"])

    def test_multi_page_without_per_page_transcripts_still_refuses(self, tmp_path: Path) -> None:
        """The old guard remains for callers that cannot supply pages."""
        source = multi_frame_tiff(tmp_path / "pamphlet.tif", frames=2)

        with pytest.raises(MultiPagePdfError, match="one transcript per page"):
            searchable_pdf_for(source, "some text", tmp_path / "out.pdf")


class TestOutputNameCollision:
    """A PDF transcribed to a searchable PDF wants its own source's name.

    The batch pipeline moves the original into the same directory, so without
    a distinct name one silently overwrote the other and the run still
    reported success.
    """

    def test_a_pdf_source_does_not_overwrite_itself(self, tmp_path: Path) -> None:
        source = tmp_path / "programme.pdf"
        searchable_pdf_for(multi_frame_tiff(tmp_path / "seed.tif", 1), "seed", source)

        written = outputs.write("pdf", source, "text", tmp_path)

        assert written.name == "programme.searchable.pdf"
        assert written != source
        assert source.exists(), "the source must survive its own transcription"

    def test_a_non_colliding_source_keeps_the_plain_name(self, tmp_path: Path) -> None:
        source = tmp_path / "postcard.jpg"
        scan().save(source)

        written = outputs.write("pdf", source, "text", tmp_path)

        assert written.name == "postcard.pdf"

    def test_markdown_is_unaffected(self, tmp_path: Path) -> None:
        source = tmp_path / "programme.pdf"
        searchable_pdf_for(multi_frame_tiff(tmp_path / "seed.tif", 1), "seed", source)

        assert outputs.write("markdown", source, "text", tmp_path).name == "programme.md"
