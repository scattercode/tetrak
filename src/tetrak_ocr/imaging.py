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
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from PIL import Image

from .errors import MultiPageNotSupportedError


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
        with Image.open(path) as image:
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
    with Image.open(path) as image:
        for index in range(int(getattr(image, "n_frames", 1))):
            image.seek(index)
            if _is_page(image):
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

    with tempfile.TemporaryDirectory(prefix="tetrak-render-") as tmp:
        # fmt="ppm" is what pdf2image writes natively, so nothing is re-encoded
        # on the way to disk.
        yield _release_after_use(convert_from_path(path, output_folder=tmp, fmt="ppm"))


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
