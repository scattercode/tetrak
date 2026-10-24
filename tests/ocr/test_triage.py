"""Tests for the triage queue: the record batch writes and the page that lists it.

What is pinned: that a held file keeps every candidate's transcript whole
rather than a 500-character excerpt, that the record carries what a view
needs without parsing Markdown, that the queue reads older directories
without losing anything, and that the server binds to the loopback address
and nothing else. Fast: no engine, and the server gets a free port.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from tetrak_ocr import triage

LONG = "word " * 300  # 1,500 characters: three times the old excerpt


def held(tmp_path: Path, stem: str = "faint", scores=None, transcripts=None) -> Path:
    """Hold one file with two candidates, the way batch does, and return the directory."""
    image = tmp_path / "scans" / f"{stem}.png"
    image.parent.mkdir(exist_ok=True)
    image.touch()
    triage.hold(
        tmp_path / "triage",
        image,
        scores if scores is not None else {"vision": 0.0724, "easyocr": 0.0},
        transcripts if transcripts is not None else {"vision": LONG, "easyocr": ""},
        reason="Best transcript (vision, score=0.0724) is below threshold 0.1000",
        backend="auto-local",
    )
    return tmp_path / "triage"


class TestHold:
    def test_every_transcript_is_kept_whole(self, tmp_path: Path) -> None:
        """The manifest's excerpt stops at 500 characters; this does not."""
        directory = held(tmp_path)

        assert (directory / "faint.vision.txt").read_text(encoding="utf-8") == LONG
        assert (directory / "faint.easyocr.txt").read_text(encoding="utf-8") == ""

    def test_the_record_says_what_a_view_needs(self, tmp_path: Path) -> None:
        directory = held(tmp_path)

        record = json.loads((directory / "faint.json").read_text(encoding="utf-8"))

        assert record["file"] == "faint.png"
        assert record["reason"].startswith("Best transcript (vision")
        assert record["backend"] == "auto-local"
        assert record["best"] == {"engine": "vision", "score": 0.0724}
        assert record["candidates"] == [
            {"backend": "vision", "score": 0.0724, "transcript": "faint.vision.txt"},
            {"backend": "easyocr", "score": 0.0, "transcript": "faint.easyocr.txt"},
        ]
        assert record["held_at"]
        assert record["tetrak_version"]

    def test_the_paths_written_are_returned_record_first(self, tmp_path: Path) -> None:
        image = tmp_path / "page.png"
        image.touch()

        written = triage.hold(tmp_path / "t", image, {"a": 0.01}, {"a": "x"}, reason="poor")

        assert [p.name for p in written] == ["page.json", "page.a.txt"]
        assert all(p.exists() for p in written)


class TestQueue:
    def test_lists_held_items_by_name(self, tmp_path: Path) -> None:
        directory = held(tmp_path, "zebra")
        held(tmp_path, "apple", scores={"paddle": 0.05}, transcripts={"paddle": "x"})

        items = triage.queue(directory)

        assert [item.stem for item in items] == ["apple", "zebra"]
        assert items[1].best_engine == "vision"
        assert items[1].best_score == 0.0724
        assert [c.backend for c in items[1].candidates] == ["vision", "easyocr"]

    def test_an_older_manifest_without_a_record_is_still_listed(self, tmp_path: Path) -> None:
        """A directory written before records existed must not look empty."""
        directory = tmp_path / "triage"
        directory.mkdir()
        (directory / "old.md").write_text("# old\n", encoding="utf-8")
        (directory / "old.jpg").touch()

        (item,) = triage.queue(directory)

        assert (item.file, item.best_score, item.record) == ("old.jpg", None, None)
        assert "old.md" in item.reason

    def test_a_missing_directory_is_an_empty_queue(self, tmp_path: Path) -> None:
        assert triage.queue(tmp_path / "nowhere") == []

    def test_scans_and_transcripts_are_not_items(self, tmp_path: Path) -> None:
        directory = held(tmp_path)
        (directory / "faint.png").touch()

        assert len(triage.queue(directory)) == 1


class TestRendering:
    def test_an_empty_queue_is_a_plain_message(self, tmp_path: Path) -> None:
        page = triage.render([], tmp_path)
        assert "The triage queue is empty." in page
        assert "<table" not in page

    def test_each_row_shows_the_file_its_best_score_and_the_reason(self, tmp_path: Path) -> None:
        directory = held(tmp_path)

        page = triage.render(triage.queue(directory), directory)

        assert "<code>faint.png</code>" in page
        assert "0.0724" in page
        assert "is below threshold 0.1000" in page

    def test_names_and_reasons_are_escaped(self, tmp_path: Path) -> None:
        directory = held(tmp_path, "a<b", scores={"x": 0.0}, transcripts={"x": ""})

        page = triage.render(triage.queue(directory), directory)

        assert "a&lt;b.png" in page and "<b.png" not in page

    def test_the_terminal_listing_carries_the_same_columns(self, tmp_path: Path) -> None:
        directory = held(tmp_path)

        text = triage.describe(triage.queue(directory), directory)

        assert "faint.png" in text and "0.0724" in text and "vision" in text
        assert "empty" in triage.describe([], directory)


class TestServer:
    @pytest.fixture
    def server(self, tmp_path: Path):
        directory = held(tmp_path)
        server = triage.make_server(directory, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            server.server_close()

    def test_binds_to_the_loopback_address_only(self, server) -> None:
        """Brief 001: nothing remote, so nothing to authenticate. There is no
        flag to bind elsewhere, and this pins that the default is loopback."""
        assert server.server_address[0] == "127.0.0.1"
        assert triage.HOST == "127.0.0.1"

    def test_serves_the_queue_page(self, server) -> None:
        host, port = server.server_address[:2]

        with urlopen(f"http://{host}:{port}/") as response:
            page = response.read().decode("utf-8")
            content_type = response.headers["Content-Type"]

        assert content_type.startswith("text/html")
        assert "<code>faint.png</code>" in page
        assert "0.0724" in page

    def test_serves_nothing_else(self, server) -> None:
        host, port = server.server_address[:2]

        with pytest.raises(HTTPError) as excinfo:
            urlopen(f"http://{host}:{port}/faint.png")
        assert excinfo.value.code == 404

    def test_an_empty_queue_is_a_page_not_an_error(self, tmp_path: Path) -> None:
        server = triage.make_server(tmp_path / "empty", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[:2]
            with urlopen(f"http://{host}:{port}/") as response:
                assert response.status == 200
                assert "The triage queue is empty." in response.read().decode("utf-8")
        finally:
            server.shutdown()
            server.server_close()
