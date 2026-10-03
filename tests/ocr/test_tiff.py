"""TIFF handling, including the multi-page case.

Every backend has always declared `.tif`/`.tiff` in SUPPORTED_EXTENSIONS, and
`test_ocr_tesseract.py` checked that a Pillow-generated TIFF could be read. That
combination is what made the gap easy to miss: the declaration was honest for
single-page files and quietly wrong for multi-page ones, which is what archival
TIFF often is.

Pillow opens a multi-frame file at frame 0 and reports nothing about the rest,
so a scanned pamphlet returned its cover as though it were the document. It
would have passed quality scoring and entered an archive looking like a
complete transcript.

Tesseract now reads every frame, exactly as it already did for PDF pages. The
backends that cannot raise MultiPageNotSupportedError instead. These tests use
Pillow-generated multi-frame TIFFs rather than corpus fixtures, so they stay in
the fast suite and need no OCR engine beyond Tesseract.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from tetrak_ocr.errors import MultiPageNotSupportedError
from tetrak_ocr.imaging import frame_count, iter_frames, reject_multi_page

# Nonsense words, chosen so a match cannot come from anywhere but the page it
# was drawn on -- real words risk one page's output being read as another's.
PAGE_WORDS = ["ALPHAZULU", "BRAVOYANKEE", "DELTAXRAY"]


def _write_tiff(path: Path, words: list[str]) -> Path:
    """Write a TIFF with one frame per entry in *words*.

    LZW-compressed to match the corpus fixtures, which came out of a museum
    scanning pipeline that way. Compression is a plausible place for frame
    handling to go wrong, so testing the uncompressed default would be testing
    the easier case.
    """
    frames = []
    for word in words:
        image = Image.new("RGB", (900, 300), "white")
        ImageDraw.Draw(image).text((40, 120), word, fill="black")
        frames.append(image)
    frames[0].save(path, save_all=True, append_images=frames[1:], compression="tiff_lzw")
    return path


@pytest.fixture
def single_page(tmp_path: Path) -> Path:
    return _write_tiff(tmp_path / "one.tif", PAGE_WORDS[:1])


@pytest.fixture
def multi_page(tmp_path: Path) -> Path:
    return _write_tiff(tmp_path / "three.tif", PAGE_WORDS)


class TestFrameCounting:
    def test_a_single_page_tiff_reports_one_frame(self, single_page):
        assert frame_count(single_page) == 1

    def test_a_multi_page_tiff_reports_every_frame(self, multi_page):
        assert frame_count(multi_page) == 3

    def test_a_non_image_reports_one(self, tmp_path):
        """PDFs and unreadable files answer 1 rather than raising.

        frame_count guards other code paths, so it has to be safe to call on
        anything the pipeline accepts -- a PDF reaches it on the way to a
        backend that handles PDF paging by another route entirely.
        """
        not_an_image = tmp_path / "notes.pdf"
        not_an_image.write_bytes(b"%PDF-1.4 not really a pdf")
        assert frame_count(not_an_image) == 1

    def test_iter_frames_yields_independent_images(self, multi_page):
        """Frames must be copied, not views onto one seeking file handle.

        Pillow mutates a single image object as it seeks. Collecting the frames
        without copying leaves every entry pointing at the last one, which
        would silently OCR page three three times.
        """
        frames = list(iter_frames(multi_page))

        assert len(frames) == 3
        assert len({id(f) for f in frames}) == 3
        assert len({f.tobytes() for f in frames}) == 3


class TestTesseractReadsEveryPage:
    def test_all_pages_are_transcribed(self, multi_page):
        from tetrak_ocr.backends.tesseract import ocr_image

        text = ocr_image(multi_page).upper()

        missing = [w for w in PAGE_WORDS if w not in text.replace(" ", "")]
        assert not missing, f"pages dropped from the transcript: {missing}"

    def test_pages_are_separated_like_pdf_pages(self, multi_page):
        """A blank line between pages, matching `_ocr_pdf`.

        The two paths produce the same kind of thing -- one document arriving
        as a sequence of page images -- so they should not format it
        differently.
        """
        from tetrak_ocr.backends.tesseract import ocr_image

        assert "\n\n" in ocr_image(multi_page).strip()

    def test_single_page_behaviour_is_unchanged(self, single_page):
        from tetrak_ocr.backends.tesseract import ocr_image

        text = ocr_image(single_page).upper().replace(" ", "")
        assert PAGE_WORDS[0] in text


class TestBackendsThatReadOnlyTheFirstFrame:
    """These refuse rather than returning page one as the document.

    Each backend is called directly rather than through the registry. Importing
    a backend is always safe -- the heavy dependency is recorded in `_IMPORT_OK`
    rather than raising at import -- and the guard runs before anything touches
    that dependency. So these assert real behaviour on a machine with none of
    the optional extras installed, which is what CI runs.
    """

    @pytest.mark.parametrize("backend", ["claude", "easyocr", "paddle", "marker"])
    def test_a_multi_page_tiff_is_refused(self, backend, multi_page):
        import importlib

        module = importlib.import_module(f"tetrak_ocr.backends.{backend}")

        with pytest.raises(MultiPageNotSupportedError) as excinfo:
            module.ocr_image(multi_page)

        message = str(excinfo.value)
        assert "3 pages" in message
        assert backend in message
        # The error has to say what to do instead, not merely what failed.
        assert "tesseract" in message

    def test_the_guard_names_the_file_and_the_page_count(self, multi_page):
        with pytest.raises(MultiPageNotSupportedError) as excinfo:
            reject_multi_page(multi_page, "easyocr")

        assert excinfo.value.pages == 3
        assert excinfo.value.path.name == "three.tif"

    def test_single_page_files_pass_the_guard(self, single_page):
        assert reject_multi_page(single_page, "easyocr") is None


class TestEveryBackendDeclaresTiff:
    """The declaration was right all along; this stops it regressing."""

    @pytest.mark.parametrize("backend", ["tesseract", "claude", "easyocr", "paddle", "marker"])
    def test_tif_and_tiff_are_both_declared(self, backend):
        import importlib

        module = importlib.import_module(f"tetrak_ocr.backends.{backend}")

        assert ".tif" in module.SUPPORTED_EXTENSIONS
        assert ".tiff" in module.SUPPORTED_EXTENSIONS


@pytest.mark.slow
class TestTheCorpusTiffFixtures:
    """The real archival files, which are single-page LZW RGB.

    Marked slow because it runs Tesseract against full-resolution scans. The
    point is not the score -- the benchmark measures that -- but that a genuine
    museum TIFF goes through the pipeline and comes back with recognisable
    content in it.
    """

    @pytest.mark.parametrize(
        "stem",
        ["hollywood-music-box-playbill-1926", "kinema-theater-ad-1920"],
    )
    def test_a_corpus_tiff_transcribes(self, stem):
        """Overlap with the committed ground truth, not a magic phrase.

        The first version of this asserted "KINEMA" appeared in the Kinema
        transcript. It does not: that masthead is hand-lettered display type
        and Tesseract misses it completely while reading 95 words of the
        programme column beside it -- the same failure the Kar-Mi poster shows.

        Asserting on a specific string therefore tests which words this engine
        happens to win on, which is the benchmark's job and moves whenever the
        engine is retuned. Overlap answers the question actually being asked:
        did a real archival TIFF go through the pipeline and come back with the
        document in it?
        """
        from conftest import CORPUS_EXPECTED, CORPUS_IMAGES

        from tetrak_ocr.backends.tesseract import ocr_image

        fixture = CORPUS_IMAGES / f"{stem}.tif"
        reference = CORPUS_EXPECTED / f"{stem}.md"
        if not fixture.exists() or not reference.exists():
            pytest.skip(f"corpus fixture or ground truth not present for {stem}")

        got = {w.strip(".,;:\"'").lower() for w in ocr_image(fixture).split()}
        want = {w.strip(".,;:\"'").lower() for w in reference.read_text().split()}
        shared = got & want

        assert len(got) > 50, "a near-empty transcript means the read failed"
        assert len(shared) >= 20, (
            f"only {len(shared)} words shared with the reference — "
            "the file was read but the content does not match the document"
        )


class TestNotEveryFrameIsAPage:
    """A TIFF's extra frames are not always further leaves of the document.

    NewSubfileType bit 0 marks a *reduced-resolution version of another image
    in this file* — a pyramid level or an embedded thumbnail. Scanning
    pipelines and libvips emit these routinely.

    Treating them as pages transcribes the same leaf twice. Measured on the
    Carthay Circle postcard: appending a half-size level took the transcript
    from 32 words to 52, because at half resolution that type is still
    legible. Dense small type usually degrades below legibility and
    contributes nothing, which is luck rather than a safeguard — so the tag is
    checked rather than relied upon not to matter.
    """

    @staticmethod
    def _pyramid(path: Path) -> Path:
        """A page plus a reduced-resolution level, flagged as TIFF requires."""
        from PIL import TiffImagePlugin

        full = Image.new("RGB", (1200, 400), "white")
        ImageDraw.Draw(full).text((60, 160), PAGE_WORDS[0], fill="black")
        half = full.resize((600, 200))

        info = TiffImagePlugin.ImageFileDirectory_v2()
        info[254] = 1  # reduced-resolution version
        full.save(
            path,
            save_all=True,
            append_images=[half],
            compression="tiff_lzw",
            tiffinfo=info,
        )
        return path

    def test_a_pyramid_level_is_not_counted_as_a_page(self, tmp_path):
        assert frame_count(self._pyramid(tmp_path / "pyr.tif")) == 1

    def test_a_pyramid_level_is_not_transcribed_twice(self, tmp_path):
        from tetrak_ocr.backends.tesseract import ocr_image

        text = ocr_image(self._pyramid(tmp_path / "pyr.tif")).upper().replace(" ", "")
        assert text.count(PAGE_WORDS[0]) == 1, "the reduced level was read as a second page"

    def test_a_pyramid_is_not_refused_as_multi_page(self, tmp_path):
        """One page plus a rendition is one page.

        The frame-0 backends must still accept it — refusing would withdraw a
        file they can read perfectly well.
        """
        assert reject_multi_page(self._pyramid(tmp_path / "pyr.tif"), "easyocr") is None

    def test_genuine_pages_are_still_read(self, multi_page):
        """The guard must not swallow real leaves along with the renditions."""
        assert frame_count(multi_page) == 3


class TestFrameModeIsNotAProblem:
    """Pinning down a review finding that did not hold, so it is not re-raised.

    A review flagged that `iter_frames` yields frames in whatever mode the TIFF
    encoded them — bilevel "1", palette "P", "CMYK" — and proposed converting
    each to RGB, on the reasoning that the single-page path is protected
    because `Image.open` "promotes the mode on access".

    It does not. `Image.open` reports mode "1" for a bilevel TIFF whether the
    file has one frame or ten, so both paths see identical modes and the
    multi-page path introduces nothing. Converting to RGB first was measured
    and changes no OCR output at all: a bilevel playbill reads 163 words either
    way, a palette copy 352 either way.

    What *is* true is that the encoding matters a great deal — see
    TestBilevelCostsAccuracy. That is a property of the source file, not of how
    frames are iterated, and no mode conversion recovers it.
    """

    MODES = ["1", "L", "P", "CMYK", "RGB"]

    @staticmethod
    def _render(mode: str) -> Image.Image:
        image = Image.new("RGB", (900, 300), "white")
        ImageDraw.Draw(image).text((40, 120), PAGE_WORDS[0], fill="black")
        return image if mode == "RGB" else image.convert(mode)

    @pytest.mark.parametrize("mode", MODES)
    def test_open_does_not_promote_mode(self, tmp_path, mode):
        """The premise of the finding, checked directly."""
        path = tmp_path / f"single-{mode}.tif"
        self._render(mode).save(path)

        with Image.open(path) as image:
            assert image.mode == mode

    @pytest.mark.parametrize("mode", MODES)
    def test_every_mode_survives_the_multi_page_path(self, tmp_path, mode):
        from tetrak_ocr.backends.tesseract import ocr_image

        path = tmp_path / f"multi-{mode}.tif"
        page = self._render(mode)
        page.save(path, save_all=True, append_images=[page], compression="tiff_lzw")

        text = ocr_image(path).upper().replace(" ", "")
        assert text.count(PAGE_WORDS[0]) == 2, f"mode {mode} lost a page"

    def test_copy_preserves_a_palette(self, tmp_path):
        """The specific mechanism the finding worried about."""
        palette = self._render("P")

        assert palette.copy().mode == "P"
        assert palette.copy().getpalette() == palette.getpalette()


@pytest.mark.slow
class TestBilevelCostsAccuracy:
    """Encoding matters more than paging does, and nothing in code recovers it.

    CCITT G4 bilevel is the archival norm for text documents — it is tiny and
    lossless for pure black-on-white. It is also where OCR accuracy goes: the
    Hollywood playbill reads 297 words from its RGB original and 163 from a
    bilevel copy, a 45% loss, because thresholding to one bit destroys the
    antialiasing Tesseract uses to resolve small type.

    Converting back to RGB does not help — the information is already gone.
    This is recorded so the number is known rather than discovered later, and
    so nobody proposes a mode conversion as the remedy.
    """

    def test_bilevel_loses_words_the_original_had(self, tmp_path):
        from conftest import CORPUS_IMAGES

        from tetrak_ocr.backends.tesseract import ocr_image

        fixture = CORPUS_IMAGES / "hollywood-music-box-playbill-1926.tif"
        if not fixture.exists():
            pytest.skip("corpus fixture not present")

        with Image.open(fixture) as source:
            rgb = source.convert("RGB")

        rgb_path, bilevel_path = tmp_path / "rgb.tif", tmp_path / "bilevel.tif"
        rgb.save(rgb_path, compression="tiff_lzw")
        rgb.convert("1").save(bilevel_path, compression="tiff_lzw")

        rgb_words = len(ocr_image(rgb_path).split())
        bilevel_words = len(ocr_image(bilevel_path).split())

        assert bilevel_words < rgb_words, (
            "expected bilevel to lose accuracy; if this fails the finding has "
            "changed and the docs claiming a ~45% loss need re-deriving"
        )
