"""Write a searchable PDF: the scan, with the transcript invisible over it.

This is the output that makes a transcript useful without asking a vendor for
anything. Preservica Starter has no OCR but full-text-indexes text-embedded
PDFs; Omeka Classic's PDF plugin needs the text layer to already exist;
CONTENTdm and AtoM index it. It is also the accessibility feature, because the
same layer an indexer reads is what a screen reader reads.

Why the text is not positioned per word
---------------------------------------
The obvious construction puts each word's text invisibly over that word, and
that is what Tesseract's own PDF renderer does. It was measured and rejected
for this release. Against the corpus ground truth, character similarity of a
word-positioned layer versus the plain transcript:

    inside-facts-1930-page-six    0.0921 positioned    0.3657 transcript
    inside-facts-1930-cover       0.0407 positioned    0.3522 transcript
    carthay-circle-postcard-back  0.8066 positioned    0.9136 transcript

Word *recall* is identical in every case -- the words are all present either
way -- so this is purely reading order, and it is not a defect in our
implementation: Tesseract's native renderer scores 0.1137 on the first of
those, no better than ours. Any word-positioned layer inherits it, OCRmyPDF
included.

Content-stream order is what a screen reader announces, so for the two things
this feature exists for -- indexing and accessibility -- the better-ordered
transcript wins. Per-word boxes become load-bearing at ALTO/hOCR, where
coordinates are the point rather than a side effect. See
brief 008 (searchable PDF).

The consequence worth knowing: the text layer is byte-identical to the sidecar,
and selecting text in a viewer will not align with the words on the page.
"""

from __future__ import annotations

from collections.abc import Iterable
from io import BytesIO
from pathlib import Path

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .errors import MultiPagePdfError
from .imaging import page_count, streamed_pages

# PDF text render mode 3: fill none, stroke none. The glyphs are laid down and
# selectable and extractable, and nothing is painted. This one number is what
# makes a searchable PDF searchable.
_INVISIBLE = 3

# Archival scans frequently carry no DPI metadata at all. 300 is the floor most
# digitisation guidelines specify, so a page sized by it comes out close to the
# physical original rather than absurdly large.
_ASSUMED_DPI = 300

# The access derivative. NDNP and the Internet Archive both ship the PDF as an
# access copy beside a preservation master, and a 600dpi archival TIFF makes a
# PDF no small institution can serve from its website.
_ACCESS_LONG_EDGE = 2400
_ACCESS_JPEG_QUALITY = 80

# Tried in order when the transcript needs more than the built-in font can
# encode. Nothing is bundled: shipping a Unicode font would add megabytes to
# every install for a case most collections never hit.
_UNICODE_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
)

_BUILTIN_FONT = "Helvetica"


class PdfFontError(Exception):
    """No available font can encode the transcript.

    Raised rather than writing the PDF anyway. reportlab does not fail on a
    character the font lacks -- it substitutes a black box, so an Armenian
    transcript silently becomes a row of squares that extracts as nothing. A
    file that looks like a result and is not one is the failure this package
    guards against everywhere else.
    """


def _drawable(text: str) -> str:
    """The characters that will actually be drawn into the page.

    ``_draw_invisible_text`` lays the transcript down a line at a time via
    ``splitlines()``, so line separators are consumed by the layout and never
    reach the font. Testing them for glyph coverage rejects fonts that are
    perfectly capable: no TrueType face has a glyph for U+000A, so the Unicode
    fallback failed on every multi-line transcript -- which is all of them --
    and reported the *builtin* font's missing characters while doing it.
    """
    return "".join(text.splitlines())


def _encodable(text: str, font: str) -> bool:
    """True when every character in *text* survives being written in *font*."""
    if font == _BUILTIN_FONT:
        # WinAnsi, not Latin-1. reportlab encodes the built-in Type 1 fonts as
        # WinAnsiEncoding, which is CP1252 -- and the difference is exactly the
        # punctuation OCR of printed matter produces constantly: em dashes and
        # curly quotes are absent from Latin-1 and present in CP1252. Testing
        # against the wrong one rejected every transcript with a dash in it.
        try:
            text.encode("cp1252")
        except UnicodeEncodeError:
            return False
        return True

    face = pdfmetrics.getFont(font).face
    return all(face.charToGlyph.get(ord(char)) for char in set(_drawable(text)))


def select_font(text: str, font_path: str | Path | None = None) -> str:
    """Return a registered font name that can encode *text*.

    Prefers the built-in font, which embeds nothing and keeps the file small.
    Falls back to a system Unicode font only when the transcript needs one.

    Args:
        text:      Everything that will be written into the PDF.
        font_path: An explicit TrueType font to use instead of searching.

    Raises:
        PdfFontError: When nothing available can encode the text.
    """
    if font_path:
        name = Path(font_path).stem
        pdfmetrics.registerFont(TTFont(name, str(font_path)))
        if not _encodable(text, name):
            missing = _missing_characters(text, name)
            raise PdfFontError(f"{font_path} cannot encode: {missing}")
        return name

    if _encodable(text, _BUILTIN_FONT):
        return _BUILTIN_FONT

    # The last font actually tried, so the error names what *it* could not
    # encode. Reporting the builtin's misses instead pointed at characters a
    # Unicode font handles perfectly well, sending anyone reading it after the
    # wrong problem.
    widest = _BUILTIN_FONT
    for candidate in _UNICODE_FONT_CANDIDATES:
        if not Path(candidate).exists():
            continue
        name = Path(candidate).stem.replace(" ", "")
        try:
            pdfmetrics.registerFont(TTFont(name, candidate))
        except Exception:  # noqa: BLE001 - an unreadable font is just a miss
            continue
        if _encodable(text, name):
            return name
        widest = name

    raise PdfFontError(
        "The transcript contains characters no available font can encode "
        f"({_missing_characters(text, widest)}). Install a Unicode font "
        "or pass one with --pdf-font. Writing the PDF anyway would substitute "
        "black boxes, which extract as nothing."
    )


def _missing_characters(text: str, font: str, limit: int = 12) -> str:
    """A short, readable list of what could not be encoded."""
    bad = sorted({char for char in _drawable(text) if not _encodable(char, font)})
    shown = "".join(bad[:limit])
    return f"{shown!r}{'...' if len(bad) > limit else ''}"


def _access_copy(image: Image.Image) -> BytesIO:
    """Downsample and JPEG-encode an image for embedding as an access copy.

    Returned as encoded JPEG bytes rather than a PIL image, because that is
    what controls the file size. Handed a PIL image, reportlab embeds it
    losslessly: a 1400x895 postcard came out as a 1650KB PDF, which is not an
    access copy of anything. Handed a JPEG stream it stores it as-is, and the
    same page becomes a file an institution can actually serve.
    """
    copy = image.convert("RGB")
    long_edge = max(copy.size)
    if long_edge > _ACCESS_LONG_EDGE:
        scale = _ACCESS_LONG_EDGE / long_edge
        copy = copy.resize(
            (max(1, round(copy.width * scale)), max(1, round(copy.height * scale))),
            Image.LANCZOS,
        )
    buffer = BytesIO()
    copy.save(buffer, format="JPEG", quality=_ACCESS_JPEG_QUALITY, optimize=True)
    buffer.seek(0)
    return buffer


def _page_size(image: Image.Image) -> tuple[float, float]:
    """Page size in points, from the image's own DPI where it records one."""
    dpi = image.info.get("dpi")
    x_dpi = float(dpi[0]) if dpi and dpi[0] else _ASSUMED_DPI
    y_dpi = float(dpi[1]) if dpi and len(dpi) > 1 and dpi[1] else x_dpi
    return image.width / x_dpi * 72.0, image.height / y_dpi * 72.0


def searchable_pdf_for(
    path: Path,
    transcript: str,
    destination: Path,
    *,
    page_transcripts: list[str] | None = None,
    **kwargs,
) -> Path:
    """Write the searchable PDF for one transcribed document.

    The single entry point the CLI and the batch processor share, so the guard
    below cannot be applied in one and forgotten in the other.

    A multi-page document needs *page_transcripts* -- one string per page, in
    page order. Given those, each page's text is laid onto the page it came
    from and the document is written whole. Without them there is only a
    document-level *transcript*, which cannot honestly be divided across pages,
    and this refuses rather than putting every page's text on page one.

    Args:
        path:             The transcribed document.
        transcript:       Document-level text, used for a single-page document.
        destination:      Where to write.
        page_transcripts: Per-page text, required for a multi-page document.

    Raises:
        MultiPagePdfError: Multi-page, and no per-page transcripts were given.
        ValueError:        Per-page transcripts given, but not one per page.
    """
    # Counted rather than rendered: page_count reads the PDF trailer, where
    # materialising the pages to call len() on them costs 881 MB on a 21-page
    # document. See imaging.streamed_pages.
    total = page_count(path)

    if page_transcripts is not None:
        if len(page_transcripts) != total:
            raise ValueError(
                f"{path.name} has {total} pages but {len(page_transcripts)} "
                f"transcript(s) were given. Text would land on the wrong page."
            )
        # The font is resolved here, from transcripts the caller already holds,
        # so the writer never has to read the text off the images -- which is
        # what lets the pages stream one at a time.
        font = select_font("".join(page_transcripts), kwargs.get("font_path"))
        with streamed_pages(path) as images:
            # strict=: the count check above already covers this, but a silent
            # truncation here would put text on the wrong page, which is the
            # exact failure this function exists to prevent.
            paired = zip(images, page_transcripts, strict=True)
            return write_searchable_pdf(paired, destination, font=font, **kwargs)

    if total > 1:
        raise MultiPagePdfError(path, total)

    with streamed_pages(path) as images:
        first = next(iter(images), None)
        if first is None:
            raise ValueError("A PDF needs at least one page")
        return write_searchable_pdf([(first, transcript)], destination, **kwargs)


def write_searchable_pdf(
    pages: Iterable[tuple[Image.Image, str]],
    destination: Path,
    *,
    full_size: bool = False,
    font_path: str | Path | None = None,
    font: str | None = None,
) -> Path:
    """Write *pages* as a searchable PDF at *destination*.

    Args:
        pages:       (image, transcript) per page, in page order. Any iterable
                     -- pass an iterator together with *font* to stream a long
                     document instead of holding every page image at once.
        destination: Where to write. Parent directories must exist.
        full_size:   Embed the source image untouched instead of an access
                     derivative. Larger, and faithful to the original.
        font_path:   An explicit TrueType font for the text layer.
        font:        A font already resolved by the caller. Choosing one here
                     requires reading every transcript first, which would
                     defeat streaming; a caller holding the transcripts already
                     can resolve it without touching the images.

    Returns:
        The path written.

    Raises:
        ValueError:   If *pages* is empty.
        PdfFontError: If the transcript cannot be encoded -- see `select_font`.
    """
    if font is None:
        # No pre-resolved font, so the text has to be read up front and the
        # pages materialised. One font for the whole document: a font picked
        # per page could differ between pages of one file, and a reader
        # extracting the whole thing would see it change under them.
        pages = list(pages)
        if not pages:
            raise ValueError("A PDF needs at least one page")
        font = select_font("".join(text for _, text in pages), font_path)

    writer = canvas.Canvas(str(destination))
    writer.setTitle(destination.stem)

    drawn = 0
    for image, text in pages:
        embedded = image.convert("RGB") if full_size else _access_copy(image)
        # ImageReader accepts a PIL image or a file-like of encoded bytes; the
        # JPEG path relies on the second so the stream is stored, not re-coded.
        width, height = _page_size(image)
        writer.setPageSize((width, height))
        writer.drawImage(ImageReader(embedded), 0, 0, width=width, height=height)
        _draw_invisible_text(writer, text, width, height, font)
        writer.showPage()
        drawn += 1

        # The access copy is ours, so release it before the next page. The
        # source image belongs to whoever passed it in and is not closed here:
        # a caller that goes on using its own image should not find it shut.
        # Streamed pages are released by their producer -- see
        # imaging.streamed_pages.
        if embedded is not image:
            embedded.close()

    if not drawn:
        raise ValueError("A PDF needs at least one page")

    writer.save()
    return destination


def _draw_invisible_text(
    writer: canvas.Canvas, text: str, width: float, height: float, font: str
) -> None:
    """Lay the transcript down the page in invisible glyphs.

    Line spacing is derived from the page and the line count so that every line
    lands inside the page box. Text drawn past the bottom edge is still in the
    file, but extractors differ on whether they report it and some viewers clip
    it -- and a transcript that is only sometimes found is the kind of quiet
    half-failure this pipeline exists to avoid.
    """
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return

    leading = min(12.0, max(1.0, height / (len(lines) + 1)))
    size = max(1.0, leading * 0.8)

    cursor = writer.beginText()
    cursor.setTextRenderMode(_INVISIBLE)
    cursor.setFont(font, size)
    cursor.setLeading(leading)
    cursor.setTextOrigin(2.0, height - leading)
    for line in lines:
        cursor.textLine(line)
    writer.drawText(cursor)
