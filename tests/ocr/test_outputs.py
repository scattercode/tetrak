"""Tests for output format selection and writing.

The pipeline used to write Markdown and, if asked, a PDF beside it. It now
writes any set of formats from one OCR pass, so the things worth pinning down
are: the default has not moved, a set is honoured in full, and the legacy
`--pdf` flag still means what it used to.
"""

from pathlib import Path

import pytest

from tetrak_ocr import outputs
from tetrak_ocr.errors import UnknownFormatError


class TestParsing:
    """Turning `--format` values into a canonical list."""

    def test_default_is_markdown(self) -> None:
        """Asking for nothing writes what the pipeline has always written."""
        assert outputs.parse(None) == ["markdown"]
        assert outputs.parse([]) == ["markdown"]

    def test_repeated_flags(self) -> None:
        assert outputs.parse(["markdown", "pdf"]) == ["markdown", "pdf"]

    def test_comma_separated(self) -> None:
        assert outputs.parse(["markdown,pdf"]) == ["markdown", "pdf"]

    def test_the_two_spellings_agree(self) -> None:
        """Whichever way someone types it, they get the same set."""
        assert outputs.parse(["text,pdf"]) == outputs.parse(["text", "pdf"])

    def test_order_follows_first_mention(self) -> None:
        assert outputs.parse(["pdf,markdown"]) == ["pdf", "markdown"]

    def test_duplicates_collapse(self) -> None:
        """Asking twice must not write the file twice."""
        assert outputs.parse(["markdown", "markdown,pdf"]) == ["markdown", "pdf"]

    @pytest.mark.parametrize(
        ("alias", "expected"),
        [("md", "markdown"), ("txt", "text"), ("plaintext", "text"), ("PDF", "pdf")],
    )
    def test_aliases_and_case(self, alias: str, expected: str) -> None:
        assert outputs.parse([alias]) == [expected]

    def test_unknown_format_names_the_alternatives(self) -> None:
        """The useful error tells you what you could have typed."""
        with pytest.raises(UnknownFormatError) as excinfo:
            outputs.parse(["pdff"])

        message = str(excinfo.value)
        assert "pdff" in message
        assert "markdown" in message

    def test_whitespace_and_empty_parts_are_tolerated(self) -> None:
        assert outputs.parse([" markdown , pdf "]) == ["markdown", "pdf"]
        assert outputs.parse(["markdown,"]) == ["markdown"]


class TestWriting:
    """What each writer puts on disk."""

    def test_markdown_is_titled(self, tmp_path: Path) -> None:
        source = tmp_path / "postcard.jpg"
        source.touch()

        written = outputs.write("markdown", source, "some words", tmp_path)

        assert written.name == "postcard.md"
        assert written.read_text(encoding="utf-8") == "# postcard\n\nsome words\n"

    def test_text_is_bare(self, tmp_path: Path) -> None:
        """Plain text carries no heading — an indexer wanted the transcript."""
        source = tmp_path / "postcard.jpg"
        source.touch()

        written = outputs.write("text", source, "some words", tmp_path)

        assert written.name == "postcard.txt"
        assert written.read_text(encoding="utf-8") == "some words\n"

    def test_outputs_share_the_source_stem(self, tmp_path: Path) -> None:
        """Every format for one document sits together under one name."""
        source = tmp_path / "playbill-1926.tif"
        source.touch()

        names = {outputs.write(fmt, source, "text", tmp_path).name for fmt in ("markdown", "text")}
        assert names == {"playbill-1926.md", "playbill-1926.txt"}

    def test_extension_lookup(self) -> None:
        assert outputs.extension("markdown") == ".md"
        assert outputs.extension("txt") == ".txt"
        assert outputs.extension("pdf") == ".pdf"
