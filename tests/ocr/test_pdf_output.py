"""Tests for the searchable PDF writer.

Fast: these build images in memory and never run OCR. What they do need is
`pdftotext`, because the only honest check on a text layer is to read it back
out the way an indexer would. Poppler is already a requirement of `pdf2image`,
so it is not a new dependency -- but the tests skip rather than fail where it
is absent.

`-raw` is deliberate. Plain `pdftotext` reflows and de-hyphenates, which turned
an exact match into 0.9853 and made the test look like a bug in the writer.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import reportlab
from PIL import Image

from tetrak_ocr.accuracy import normalise
from tetrak_ocr.errors import MultiPagePdfError
from tetrak_ocr.pdf_output import PdfFontError, select_font, write_searchable_pdf

pytestmark = pytest.mark.skipif(
    shutil.which("pdftotext") is None,
    reason="pdftotext (poppler) is needed to read the text layer back",
)

# Ships with reportlab, and covers Latin only -- so it is a font guaranteed to
# be present and guaranteed to fail on Armenian, which is what the refusal test
# needs to be deterministic rather than dependent on the host's fonts.
VERA = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"


def scan(width: int = 800, height: int = 1000) -> Image.Image:
    """A stand-in for a scanned page."""
    return Image.new("RGB", (width, height), "white")


def extract(pdf: Path) -> str:
    return subprocess.run(
        ["pdftotext", "-raw", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout


def test_the_text_layer_is_the_transcript(tmp_path: Path) -> None:
    """The whole point: what goes in comes back out.

    This is what an indexer does to a PDF, so it is the check that decides
    whether the feature works at all.
    """
    transcript = "GRAUMAN'S CHINESE THEATRE\nHollywood Boulevard\nPremiere tonight"
    out = write_searchable_pdf([(scan(), transcript)], tmp_path / "one.pdf")
    assert normalise(extract(out)) == normalise(transcript)


def test_printers_punctuation_survives(tmp_path: Path) -> None:
    """Em dashes and curly quotes are what OCR of printed matter produces.

    They are absent from Latin-1 and present in WinAnsi, which reportlab
    actually uses for its built-in fonts. Testing against the wrong one
    rejected every transcript containing a dash.
    """
    transcript = "It's a “test” — really…"
    out = write_searchable_pdf([(scan(), transcript)], tmp_path / "punct.pdf")
    assert normalise(extract(out)) == normalise(transcript)


def test_every_page_carries_its_own_text(tmp_path: Path) -> None:
    pages = [(scan(), "page one text"), (scan(), "page two text")]
    got = extract(write_searchable_pdf(pages, tmp_path / "two.pdf"))
    assert "page one text" in normalise(got)
    assert "page two text" in normalise(got)


def test_the_access_copy_is_smaller_than_the_original(tmp_path: Path) -> None:
    """A 600dpi archival TIFF must not become a PDF nobody can serve.

    Handed a PIL image, reportlab embeds it losslessly; a 1400x895 postcard
    came out at 1650KB before the access copy was actually JPEG-encoded.
    """
    # Noise, so that JPEG has something to compress and the comparison is real.
    detailed = Image.effect_noise((2000, 2000), 40).convert("RGB")
    access = write_searchable_pdf([(detailed, "text")], tmp_path / "access.pdf")
    full = write_searchable_pdf([(detailed, "text")], tmp_path / "full.pdf", full_size=True)
    assert access.stat().st_size < full.stat().st_size


def test_a_unicode_font_is_not_rejected_over_line_breaks() -> None:
    """Line separators are consumed by the layout and never reach the font.

    No TrueType face has a glyph for U+000A, so testing the raw transcript
    made every candidate font look incapable the moment the text had more than
    one line -- which is every transcript. The Unicode fallback could never
    succeed, `--pdf-font` could never succeed, and the error then named the
    *builtin* font's missing characters, pointing at the wrong problem.
    """
    from tetrak_ocr.pdf_output import _UNICODE_FONT_CANDIDATES, select_font

    if not any(Path(c).exists() for c in _UNICODE_FONT_CANDIDATES):
        pytest.skip("no system Unicode font on this machine")

    # Cyrillic, not CJK. Which scripts the fallback covers is a property of
    # whichever font the machine happens to have: macOS offers Arial Unicode,
    # which covers CJK, while a Linux runner offers DejaVu, which does not.
    # Cyrillic is covered by both, so the test exercises the line-break bug
    # rather than the host's font coverage.
    text = "GRAUMAN'S CHINESE THEATRE\nHollywood \u2014 Boulevard\n\u0435\u043e\u0440\u0445\u0447\nLast line"

    try:
        chosen = select_font(text)
    except Exception as exc:  # noqa: BLE001 - reported as a skip, not a failure
        pytest.skip(f"no available font covers Cyrillic here: {exc}")

    assert chosen != "Helvetica", "should fall back to a Unicode font"

    # The regression itself: the same text on one line must choose the same
    # font. If line breaks are being tested for glyph coverage, these differ.
    assert select_font(text.replace("\n", " ")) == chosen


def test_line_breaks_alone_never_force_a_fallback() -> None:
    """Plain multi-line text must still use the builtin font.

    The counterpart to the test above: the fix must not make everything
    embed a Unicode font, which would grow every PDF for nothing.
    """
    from tetrak_ocr.pdf_output import select_font

    assert select_font("First line\nSecond line\n\nFourth") == "Helvetica"


def test_a_transcript_the_font_cannot_encode_is_refused(tmp_path: Path) -> None:
    """Never black boxes.

    reportlab does not raise on a character the font lacks -- it substitutes a
    filled square, so an Armenian transcript becomes a row of boxes that
    extracts as nothing. A file that looks like a result and is not one is the
    failure this package refuses everywhere else.
    """
    with pytest.raises(PdfFontError):
        write_searchable_pdf(
            [(scan(), "Հայաստան")],
            tmp_path / "armenian.pdf",
            font_path=VERA,
        )


def test_a_named_font_is_used_when_it_covers_the_text() -> None:
    assert select_font("plain latin text", font_path=VERA) == "Vera"


def test_ordinary_text_embeds_no_font_at_all() -> None:
    """The built-in font keeps the file small; only reach past it when needed."""
    assert select_font("ordinary transcript") == "Helvetica"


def test_an_empty_document_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one page"):
        write_searchable_pdf([], tmp_path / "empty.pdf")


def test_a_page_with_no_text_still_produces_a_page(tmp_path: Path) -> None:
    """A blank leaf is part of the document, not an error."""
    out = write_searchable_pdf([(scan(), "")], tmp_path / "blank.pdf")
    assert out.exists() and out.stat().st_size > 0


def test_multi_page_input_is_refused_rather_than_guessed(tmp_path: Path) -> None:
    """One transcript cannot be divided across pages honestly.

    A reader searching a 21-page programme would be sent to the wrong leaf
    while the file looked entirely correct.
    """
    from tetrak_ocr.pdf_output import searchable_pdf_for

    source = tmp_path / "two-frames.tif"
    scan(200, 300).save(source, save_all=True, append_images=[scan(200, 300)])

    with pytest.raises(MultiPagePdfError, match="one transcript per page"):
        searchable_pdf_for(source, "some text", tmp_path / "out.pdf")


@pytest.mark.slow
def test_a_real_scan_round_trips_through_the_pipeline(tmp_path: Path) -> None:
    """End to end on corpus material: OCR a scan, write the PDF, read it back.

    The fast tests above build their own images, so they prove the writer works
    on text it was handed. This proves the thing a user gets: that the layer in
    the file an institution would ingest says exactly what the transcript said.
    """
    from conftest import CORPUS_IMAGES

    from tetrak_ocr.backends.tesseract import ocr_image
    from tetrak_ocr.pdf_output import searchable_pdf_for

    source = CORPUS_IMAGES / "carthay-circle-postcard-back.png"
    transcript = ocr_image(source, auto=True)

    out = searchable_pdf_for(source, transcript, tmp_path / "postcard.pdf")

    assert normalise(extract(out)) == normalise(transcript)
    # An access copy, not a re-wrapped original.
    assert out.stat().st_size < source.stat().st_size
