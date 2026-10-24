"""Output formats for a finished transcript.

One transcript can be written several ways at once — Markdown for a human,
plain text for a downstream tool, a searchable PDF for a catalogue — so the
pipeline asks for a *set* of formats rather than a single one.

Every writer exposes the same callable::

    write(source, transcript, destination, **options) -> None

``source`` is the file that was transcribed, which the text formats ignore and
the PDF writer needs (it embeds the scan). ``options`` carries format-specific
settings; a writer must tolerate options meant for a different format, because
the caller passes one dict to all of them. The pipeline and the ``ocr``
subcommand pass the same set to every writer::

    page_transcripts  one string per page of a multi-page document, or None
    spans             the backend's positioned spans for the document --
                      ``layout.TextSpan``, pixels, top-left origin, in the
                      engine's own order -- or None when the backend has none
                      (see ``layout.Transcript`` and ``layout.spans_of``)
    page_spans        one such list, or None, per page, when the document was
                      read page by page; ``spans`` is then None
    pdf_full_size     the searchable PDF's own settings
    pdf_font

The text writers ignore the spans. They exist for the positioned formats --
ALTO, hOCR -- where the coordinates are the output.

Adding a format means adding one entry to ``_FORMATS`` and nothing else: the
CLI takes its choices, its help text and its validation from this table, the
same way backends are resolved through ``registry.py``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from .errors import UnknownFormatError

# The format written when nobody asks for anything, matching what the batch
# pipeline has always produced.
DEFAULT_FORMAT = "markdown"


def _write_markdown(source: Path, transcript: str, destination: Path, **options) -> None:
    """Transcript as Markdown, titled with the document's stem."""
    destination.write_text(f"# {source.stem}\n\n{transcript.strip()}\n", encoding="utf-8")


def _write_text(source: Path, transcript: str, destination: Path, **options) -> None:
    """Transcript as plain text: no title, no markup, just the words.

    The format to reach for when something else is going to parse the file —
    a Markdown heading is noise to an indexer that wanted the transcript.
    """
    destination.write_text(f"{transcript.strip()}\n", encoding="utf-8")


def _write_pdf(source: Path, transcript: str, destination: Path, **options) -> None:
    """The scan with the transcript embedded as an invisible text layer.

    A multi-page document needs ``page_transcripts`` in *options* -- one string
    per page. The caller produces those by transcribing page by page; without
    them a multi-page document is refused rather than having every page's text
    stacked onto page one.

    Imported lazily: the PDF path pulls in Pillow's PDF machinery and a font,
    which nobody writing Markdown should pay for.

    The ``spans`` option is deliberately not used. A word-positioned text
    layer was measured and rejected for this format -- see the
    :mod:`tetrak_ocr.pdf_output` module docstring.
    """
    from .pdf_output import searchable_pdf_for

    searchable_pdf_for(
        source,
        transcript,
        destination,
        page_transcripts=options.get("page_transcripts"),
        full_size=options.get("pdf_full_size", False),
        font_path=options.get("pdf_font"),
    )


# name -> (extension, writer, one-line description for `--help`)
_FORMATS: dict[str, tuple[str, Callable[..., None], str]] = {
    "markdown": (".md", _write_markdown, "transcript as Markdown, titled (default)"),
    "text": (".txt", _write_text, "transcript as plain text, no markup"),
    "pdf": (".pdf", _write_pdf, "the scan with an invisible text layer, for catalogue indexing"),
}

FORMATS: tuple[str, ...] = tuple(_FORMATS)

# Names people reasonably type for the same thing. Kept separate from _FORMATS
# so that `--help` and the docs list one canonical name per format rather than
# every spelling of it.
_ALIASES: dict[str, str] = {
    "md": "markdown",
    "txt": "text",
    "plaintext": "text",
    "plain": "text",
}


def canonical(name: str) -> str:
    """Resolve a format name or alias, raising for anything unrecognised."""
    key = name.strip().lower()
    key = _ALIASES.get(key, key)
    if key not in _FORMATS:
        raise UnknownFormatError(name, list(FORMATS))
    return key


def parse(values: Iterable[str] | None) -> list[str]:
    """Turn CLI ``--format`` values into an ordered list of canonical names.

    Accepts both spellings people try — repeated flags and one comma-separated
    value — because guessing wrong about which a tool supports is a papercut::

        --format markdown --format pdf
        --format markdown,pdf

    Order follows first mention, and duplicates collapse, so asking for
    ``markdown,markdown,pdf`` is not an error and does not write twice.
    Returns the default when nothing was asked for.
    """
    if not values:
        return [DEFAULT_FORMAT]

    chosen: list[str] = []
    for value in values:
        for part in str(value).split(","):
            if not part.strip():
                continue
            name = canonical(part)
            if name not in chosen:
                chosen.append(name)
    return chosen or [DEFAULT_FORMAT]


def extension(name: str) -> str:
    """The file extension a format writes, including the leading dot."""
    return _FORMATS[canonical(name)][0]


def describe() -> str:
    """Format list for `--help`, one per line."""
    return "\n".join(f"  {name:<10} {desc}" for name, (_, _, desc) in _FORMATS.items())


def write(name: str, source: Path, transcript: str, destination_dir: Path, **options) -> Path:
    """Write *transcript* in format *name*, returning the path written.

    The destination filename is the source's stem plus the format's extension,
    which is what keeps a document's outputs sitting together under one name.

    **Except when that would collide with the source itself.** A PDF
    transcribed to a searchable PDF wants the same name as the original, and
    the batch pipeline moves the original into the same directory -- so one
    silently overwrote the other, with the run reporting success either way.
    Such an output is written as `<stem>.searchable<ext>` instead. Only a
    source whose own extension is also an output format can hit this, which
    today means PDF alone.
    """
    ext = extension(name)
    stem = source.stem
    if ext == source.suffix.lower():
        stem = f"{stem}.searchable"
    return write_to(name, source, transcript, destination_dir / f"{stem}{ext}", **options)


def write_to(name: str, source: Path, transcript: str, destination: Path, **options) -> Path:
    """Write *transcript* in format *name* to exactly *destination*.

    For a caller that has named the file -- `ocr --output` with one format.
    No stem rule and no collision guard apply: the name was chosen, and a
    chosen name is honoured whatever its extension says.
    """
    _, writer, _ = _FORMATS[canonical(name)]
    writer(source, transcript, destination, **options)
    return destination
