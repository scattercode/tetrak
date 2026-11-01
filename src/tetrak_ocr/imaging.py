"""Frame handling for multi-page raster images.

TIFF is the one raster format in SUPPORTED_EXTENSIONS that can hold more than
one page, and archival TIFF frequently does — a scanned pamphlet or register
often arrives as a single file with one frame per leaf.

Pillow opens such a file at frame 0 and says nothing about the rest. Every
backend here loads images through Pillow, directly or indirectly, so
"TIFF support" meant reading page one and silently discarding the others. That
is the same failure the Claude backend already guards against with its
max_tokens check: a truncated transcript is worse than a failed one, because it
looks like a result and quietly corrupts everything downstream of it.

So the rule in this package is that a multi-frame image is either read in full
or refused by name. Tesseract reads it in full, page by page, exactly as it
already does for PDFs. The backends that cannot yet do so raise
:class:`MultiPageNotSupportedError`, which names the file, the page count and a
backend that will read it — rather than returning page one as though that were
the document.

It is also where every file is opened, so it is where files are refused.
The deciding is done by sillybos (``pip install sillybos``), which grew out
of this module: it names a file's real format from its first bytes, reads
the JPEG, PNG or TIFF header with code of its own, asks ``pdfinfo`` about a
PDF, and refuses anything outside a policy with a reason in a sentence.
:func:`open_image` runs that check and then lets Pillow use only the JPEG,
PNG and TIFF readers, so a PostScript or FlashPix file renamed ``.png``
never reaches the readers whose flaws ran commands in October 2026;
:func:`check_pdf` does the same for a PDF's page count and page sizes
before a page is rendered. The limits are this module's constants, set
from the corpus; sillybos's defaults are the same numbers.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

import sillybos
from PIL import Image
from sillybos.pillow import pillow_formats

from .errors import InputRefusedError, MultiPageNotSupportedError

MAX_PIXELS = 89_478_485
"""The most pixels in one image or rendered page: Pillow's own warning
threshold, and 2.3 times the largest scan Tetrak has read (38.7 million,
an Armenian page at 600 dpi). Enforced here, not left to Pillow's global,
so that a program which raises the global cannot raise it for us."""

MAX_PDF_PAGES = 500
"""The most pages in one PDF: three times the longest book read so far
(166 pages). Rendering streams page by page, so this bounds the time and the
temporary disk a run takes rather than its memory."""

PDF_RENDER_DPI = 200
"""The resolution poppler renders at: pdf2image's default, used everywhere."""


RASTER_FORMATS = frozenset({"jpeg", "png", "tiff"})
"""What :func:`open_image` accepts: the formats Pillow is allowed to read. A
PDF is never handed to Pillow; poppler renders it."""


def _policy(formats: frozenset[str]) -> sillybos.Policy:
    """Tetrak's limits as a sillybos policy, built per call so a test can tune the constants."""
    return sillybos.Policy(
        formats=formats,
        max_pixels=MAX_PIXELS,
        max_pages=MAX_PDF_PAGES,
        render_dpi=PDF_RENDER_DPI,
    )


def _require(path: Path, formats: frozenset[str]) -> sillybos.Verdict:
    """Check *path* against Tetrak's limits; refuse with sillybos's reasons in one sentence."""
    verdict = sillybos.check(path, _policy(formats))
    if not verdict.ok:
        raise InputRefusedError(path, "; ".join(verdict.reasons) + ".")
    return verdict


def open_image(path: Path) -> Image.Image:
    """Open a raster scan with only Tetrak's readers, refusing an oversized one.

    sillybos decides first, from the file's own bytes and header: the format
    it really is, its size, and every frame's pixels for a TIFF. Only then is
    Pillow asked to open it, with ``formats`` naming the JPEG, PNG and TIFF
    readers, so no other reader can be chosen whatever the file claims to
    be. Only the header has been read when this returns; the pixels are
    decoded later, on first use.

    Raises:
        InputRefusedError: If the file is not JPEG, PNG or TIFF, lies about
            which it is, or has a frame with more pixels than
            :data:`MAX_PIXELS`.
    """
    path = Path(path)
    policy = _policy(RASTER_FORMATS)
    _require(path, RASTER_FORMATS)
    return Image.open(path, formats=pillow_formats(policy))


def check_pdf(path: Path) -> int:
    """Refuse a PDF too long, or with a page too large, to render; else count its pages.

    sillybos reads poppler's ``pdfinfo``, which parses the document's
    structure without rendering anything, in a separate process with a time
    limit. A page's size is in points (1/72 inch), so its pixels at
    :data:`PDF_RENDER_DPI` are known before poppler allocates them.

    Raises:
        InputRefusedError: If the file is not a PDF or poppler cannot read
            it, it has more pages than :data:`MAX_PDF_PAGES`, a page would
            render to more pixels than :data:`MAX_PIXELS`, or it is
            encrypted.
    """
    verdict = _require(Path(path), frozenset({"pdf"}))
    assert verdict.facts is not None  # a passing verdict always carries its facts
    return verdict.facts.pages


def pdf_renderer():
    """Return ``pdf2image.convert_from_path``, or explain why it is missing.

    Every PDF path in the package goes through here so the advice is given
    once and is correct. pdf2image is a **core** dependency, not an extra, so
    an ImportError means an incomplete install -- the three call sites used to
    say ``pip install -r requirements.txt``, naming a file this project has not
    had since it became a package, so the one instruction offered could not
    work.
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise ImportError(
            "pdf2image is needed to read PDFs and could not be imported. It is a "
            "core dependency, so this install is incomplete: reinstall with "
            "`pip install -e .` from a checkout, or `pip install tetrak`.\n"
            "Rendering also needs poppler on the system -- `brew install poppler` "
            "on macOS, `apt install poppler-utils` on Debian."
        ) from None
    return convert_from_path


def frame_count(path: Path) -> int:
    """Number of *pages* in a raster image; 1 for ordinary single-page files.

    Pages, not IFDs. Not every extra frame in a TIFF is another leaf of the
    document -- see :func:`_is_page`.

    Non-raster inputs (PDFs) and anything Pillow cannot open report 1: this is
    a question about TIFF paging, and callers handle those cases by other
    routes. It never raises, so it is safe to call as a guard.
    """
    try:
        with open_image(path) as image:
            frames = int(getattr(image, "n_frames", 1))
            if frames == 1:
                return 1
            pages = 0
            for index in range(frames):
                image.seek(index)
                if _is_page(image):
                    pages += 1
            return max(pages, 1)
    except Exception:
        return 1


def page_count(path: Path) -> int:
    """Pages in a document of any supported kind, without rendering it.

    :func:`frame_count` answers this for rasters but reports 1 for a PDF,
    because paging a PDF is somebody else's route. This closes that gap for
    callers who want the number rather than the pages -- telemetry, mainly,
    where "how long did it take" is meaningless next to a page count.

    PDFs go through poppler's ``pdfinfo``, which reads the trailer rather than
    rasterising; :func:`iter_pages` would render every page to count them.
    Never raises: a page count is not worth an exception mid-batch.
    """
    if path.suffix.lower() == ".pdf":
        try:
            from pdf2image import pdfinfo_from_path

            return int(pdfinfo_from_path(str(path))["Pages"])
        except Exception:
            return 1
    return frame_count(path)


def _is_page(image: Image.Image) -> bool:
    """True when the current frame is a page rather than a derived rendition.

    TIFF's NewSubfileType tag (254) has bit 0 set on a *reduced-resolution
    version of another image in this file* -- the levels of a pyramidal scan,
    or an embedded thumbnail. Those are renditions of a page already present,
    not further leaves of the document.

    Treating them as pages transcribes the same leaf twice and concatenates the
    results. That is not hypothetical: appending a half-size level to the
    Carthay Circle postcard took its transcript from 32 words to 52, because at
    half resolution the type is still legible. Dense small type usually falls
    below legibility and contributes nothing, which is luck rather than a
    safeguard.

    Bit 2 (transparency mask) is excluded for the same reason. Bit 1 marks a
    single page of a multi-page document, which is exactly what we do want.
    """
    subfile_type = image.tag_v2.get(254, 0) if hasattr(image, "tag_v2") else 0
    reduced_resolution = bool(subfile_type & 1)
    transparency_mask = bool(subfile_type & 4)
    return not (reduced_resolution or transparency_mask)


def iter_frames(path: Path) -> Iterator[Image.Image]:
    """Yield every *page* of *path* as an independent image.

    Reduced-resolution renditions and transparency masks are skipped; see
    :func:`_is_page`.

    **The frame's mode is preserved, not normalised.** A bilevel TIFF yields
    mode "1", a palette one yields "P". That is deliberate: converting to RGB
    first was measured and changes no OCR output, so it would be a conversion
    that costs memory and buys nothing. `preprocess` greyscales whatever it is
    given. See TestFrameModeIsNotAProblem for the measurement.

    Each frame is copied before being yielded. Pillow's frames are views onto
    one open file that `seek` mutates in place, so a caller that collected them
    without copying would end up holding several references to the last frame.
    """
    with open_image(path) as image:
        for index in range(int(getattr(image, "n_frames", 1))):
            image.seek(index)
            if _is_page(image):
                # Every frame's size was checked by open_image, before Pillow
                # opened the file: sillybos walks the whole frame chain.
                yield image.copy()


def _release_after_use(images: Iterable[Image.Image]) -> Iterator[Image.Image]:
    """Close each page once the consumer asks for the next one.

    The producer owns the images it hands out, so it releases them. Left to the
    consumer, every page's pixel data stays resident and the streaming buys
    nothing -- which is the whole reason this exists.
    """
    for image in images:
        try:
            yield image
        finally:
            image.close()


@contextmanager
def streamed_pages(path: Path) -> Iterator[Iterator[Image.Image]]:
    """Yield page images one at a time, without holding the document in memory.

    :func:`iter_pages` looks like a generator but is not a streaming one for
    PDFs: ``convert_from_path`` renders every page into a list before the first
    is yielded, so a 21-page document costs **881 MB** of peak RSS whether the
    caller wants one page or all of them.

    Rendering into a temporary directory instead hands back images backed by
    files, which Pillow loads on demand. Same single poppler invocation, same
    wall time (13.8s against 13.7s measured), **58 MB** peak instead of 881.
    Rendering a page at a time with ``first_page``/``last_page`` also bounds
    memory but costs an invocation per page (90 MB, 14.9s), so it loses on both
    counts.

    The images are only valid inside the block -- their backing files are
    deleted on exit. Close each one when done with it, or the loaded pixel data
    accumulates and the saving is undone.

    Multi-frame rasters need none of this: :func:`iter_frames` already yields
    one frame at a time.
    """
    if path.suffix.lower() != ".pdf":
        # iter_frames already yields one frame at a time, but the copies it
        # hands out are still the consumer's to hold. Releasing them here too
        # keeps the contract the same whatever the input is.
        yield _release_after_use(iter_frames(path))
        return

    convert_from_path = pdf_renderer()
    check_pdf(path)

    with tempfile.TemporaryDirectory(prefix="tetrak-render-") as tmp:
        # fmt="ppm" is what pdf2image writes natively, so nothing is re-encoded
        # on the way to disk.
        yield _release_after_use(
            convert_from_path(path, output_folder=tmp, fmt="ppm", dpi=PDF_RENDER_DPI)
        )


@contextmanager
def page_documents(path: Path) -> Iterator[list[Path]]:
    """Split *path* into one single-page document per page, in a temp directory.

    Yields the page paths in order; they are deleted on exit, so a caller that
    needs the transcripts must read them inside the block.

    **PDFs are split as PDFs, never rendered to images.** Marker reads a PDF's
    existing text layer through pdftext instead of OCR-ing it, and rendering a
    page to PNG throws that layer away: measured at 1.8x slower *and* losing
    text outright, with one page dropping from 167 characters to zero. See
    design research note 001 (Marker throughput and multi-page PDFs).

    Multi-frame rasters have no text layer to preserve, so their frames are
    written as single-frame TIFFs -- lossless, and preserving the frame mode
    that :func:`iter_frames` deliberately does not normalise.

    A single-page document yields itself unchanged rather than a copy: there is
    nothing to split, and the copy would only be a slower way to say so.
    """
    if page_count(path) <= 1:
        yield [path]
        return

    with tempfile.TemporaryDirectory(prefix="tetrak-pages-") as tmp:
        directory = Path(tmp)
        if path.suffix.lower() == ".pdf":
            import pypdfium2 as pdfium

            # Every PdfDocument holds a handle into the pdfium library and must
            # be closed explicitly. Left to the garbage collector they are
            # finalised at interpreter shutdown, after pdfium has torn itself
            # down, and each one prints "Cannot close object, library is
            # destroyed. This may cause a memory leak!". A 21-page document
            # opens 22 of them.
            check_pdf(path)
            pages = []
            source = pdfium.PdfDocument(path)
            try:
                for index in range(len(source)):
                    page_path = directory / f"{path.stem}-p{index + 1:04d}.pdf"
                    single = pdfium.PdfDocument.new()
                    try:
                        single.import_pages(source, [index])
                        single.save(page_path)
                    finally:
                        single.close()
                    pages.append(page_path)
            finally:
                source.close()
        else:
            pages = []
            for index, frame in enumerate(iter_frames(path)):
                page_path = directory / f"{path.stem}-p{index + 1:04d}.tif"
                frame.save(page_path)
                pages.append(page_path)
        yield pages


def reject_multi_page(path: Path, backend: str, *, use_instead: str = "tesseract") -> None:
    """Raise if *path* holds more than one frame.

    For backends that read only frame 0. Called before any work is done, so the
    caller learns the file cannot be read properly rather than receiving a
    plausible-looking transcript of its first page.
    """
    pages = frame_count(path)
    if pages > 1:
        raise MultiPageNotSupportedError(path, backend, pages, use_instead)


def iter_pages(path: Path) -> Iterator[Image.Image]:
    """Yield every page of a document, whether it is a PDF or a raster.

    :func:`iter_frames` handles multi-frame rasters and PDFs are handled by
    ``pdf2image`` -- two routes to the same idea, which the Tesseract backend
    has always kept apart because it only ever needed the text.

    Producing a searchable PDF needs both halves to agree: the OCR pass reads
    the pages to find where the words are, and the writer reads them again to
    draw them. If those two disagreed about what page three is, the text layer
    would land on the wrong image. Going through one iterator is what stops
    that being possible.
    """
    if path.suffix.lower() == ".pdf":
        yield from pdf_renderer()(path)
        return

    yield from iter_frames(path)
