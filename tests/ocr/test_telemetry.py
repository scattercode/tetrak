"""Tests for the run log.

The log exists to explain a slow batch, which means it has to survive one: the
things worth pinning down are that it records what it promises, that it is
readable while the run is still going, and above all that it never takes a run
down with it.
"""

import json
from pathlib import Path

import pytest

from tetrak_ocr import telemetry


@pytest.fixture(autouse=True)
def _detach_sink():
    """Never leave a global sink attached between tests."""
    telemetry.finish_run()
    yield
    telemetry.finish_run()


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class TestSink:
    def test_records_are_ignored_when_no_run_is_active(self, tmp_path: Path) -> None:
        """The library must be usable without a run wrapped around it."""
        telemetry.record("backend_finish", backend="tesseract")
        assert not telemetry.active()
        assert list(tmp_path.iterdir()) == []

    def test_run_start_and_finish_bracket_the_events(self, tmp_path: Path) -> None:
        log = tmp_path / "telemetry.jsonl"
        telemetry.start_run(log, backend="auto-local", files=1)
        telemetry.record("file_start", file="scan.jpg")
        telemetry.finish_run(files=1)

        events = [r["event"] for r in read(log)]
        assert events == ["run_start", "file_start", "run_finish"]

    def test_every_record_carries_the_run_id(self, tmp_path: Path) -> None:
        """Appending to one log across runs is the point; the id separates them."""
        log = tmp_path / "telemetry.jsonl"
        telemetry.start_run(log)
        telemetry.record("file_start", file="a.jpg")
        telemetry.finish_run()
        first = {r["run"] for r in read(log)}

        telemetry.start_run(log)
        telemetry.record("file_start", file="b.jpg")
        telemetry.finish_run()
        both = {r["run"] for r in read(log)}

        assert len(first) == 1
        assert len(both) == 2, "a second run must not reuse the first run's id"

    def test_it_appends_rather_than_truncating(self, tmp_path: Path) -> None:
        log = tmp_path / "telemetry.jsonl"
        log.write_text('{"event": "pre-existing"}\n', encoding="utf-8")

        telemetry.start_run(log)
        telemetry.finish_run()

        assert read(log)[0]["event"] == "pre-existing"

    def test_the_log_is_readable_mid_run(self, tmp_path: Path) -> None:
        """Each line is flushed as it is written, so `tail -f` works."""
        log = tmp_path / "telemetry.jsonl"
        telemetry.start_run(log)
        telemetry.record("file_start", file="scan.jpg")

        assert [r["event"] for r in read(log)] == ["run_start", "file_start"]

    def test_the_directory_is_created(self, tmp_path: Path) -> None:
        log = tmp_path / "nested" / "deeper" / "telemetry.jsonl"
        telemetry.start_run(log)
        telemetry.finish_run()

        assert log.exists()

    def test_none_valued_fields_are_dropped(self, tmp_path: Path) -> None:
        """Absent is absent; a null adds nothing but noise to every line."""
        log = tmp_path / "telemetry.jsonl"
        telemetry.start_run(log)
        telemetry.record("backend_finish", backend="marker", score=None)
        telemetry.finish_run()

        record = read(log)[1]
        assert "score" not in record
        assert record["backend"] == "marker"


class TestMemory:
    """Every record carries memory, so the log plots as a profile of the run."""

    def test_records_carry_resident_memory(self, tmp_path: Path) -> None:
        log = tmp_path / "telemetry.jsonl"
        telemetry.start_run(log)
        telemetry.record("file_start", file="scan.jpg")
        telemetry.finish_run()

        for r in read(log):
            assert r["peak_rss_mb"] > 0, "peak memory is stdlib-only and always present"

    def test_peak_memory_is_a_plausible_size(self, tmp_path: Path) -> None:
        """ru_maxrss is bytes on macOS and kibibytes on Linux.

        Getting that wrong is a factor of 1024, which reads as either a
        rounding error or an implausible number rather than as obviously wrong.
        """
        log = tmp_path / "telemetry.jsonl"
        telemetry.start_run(log)
        telemetry.finish_run()

        peak = read(log)[0]["peak_rss_mb"]
        assert 5 < peak < 100_000, f"{peak} MB is not a plausible process size"


class TestItNeverBreaksTheRun:
    def test_a_write_failure_is_survivable(self, tmp_path: Path, capsys) -> None:
        """Half an hour of OCR must not be lost to a logging problem."""
        blocked = tmp_path / "file-in-the-way"
        blocked.write_text("not a directory", encoding="utf-8")

        telemetry.start_run(blocked / "telemetry.jsonl")
        telemetry.record("file_start", file="scan.jpg")  # must not raise

        assert "telemetry disabled" in capsys.readouterr().err

    def test_unserialisable_values_do_not_raise(self, tmp_path: Path) -> None:
        log = tmp_path / "telemetry.jsonl"
        telemetry.start_run(log)
        telemetry.record("file_start", path=Path("scan.jpg"), odd=object())
        telemetry.finish_run()

        assert len(read(log)) == 3

    def test_the_env_var_disables_it(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv(telemetry.DISABLE_ENV_VAR, "1")
        log = tmp_path / "telemetry.jsonl"

        assert telemetry.start_run(log) is None
        telemetry.record("file_start", file="scan.jpg")
        assert not log.exists()


class TestTimed:
    def test_it_records_a_duration(self, tmp_path: Path) -> None:
        log = tmp_path / "telemetry.jsonl"
        telemetry.start_run(log)
        with telemetry.timed("backend_finish", backend="tesseract"):
            pass
        telemetry.finish_run()

        record = read(log)[1]
        assert record["ok"] is True
        assert record["seconds"] >= 0

    def test_a_failure_is_still_timed(self, tmp_path: Path) -> None:
        """A backend that raised after twenty minutes is the interesting case."""
        log = tmp_path / "telemetry.jsonl"
        telemetry.start_run(log)
        with pytest.raises(ValueError), telemetry.timed("backend_finish", backend="marker"):
            raise ValueError("boom")
        telemetry.finish_run()

        record = read(log)[1]
        assert record["ok"] is False
        assert record["error"] == "ValueError"


class TestDescribeFile:
    def test_it_reports_size_and_type(self, tmp_path: Path) -> None:
        scan = tmp_path / "postcard.jpg"
        scan.write_bytes(b"x" * 1234)

        info = telemetry.describe_file(scan)

        assert info["file"] == "postcard.jpg"
        assert info["suffix"] == ".jpg"
        assert info["bytes"] == 1234

    def test_a_missing_file_does_not_raise(self, tmp_path: Path) -> None:
        info = telemetry.describe_file(tmp_path / "gone.jpg")
        assert info["file"] == "gone.jpg"
        assert "bytes" not in info
