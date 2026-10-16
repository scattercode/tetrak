"""The batch manifest: one CSV row per file (beta).

The OCR is stubbed throughout, as in `test_batch.py`'s quality-gate tests:
what is under test is what the row says about each outcome, not whether an
engine reads the page.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tetrak_ocr import auto_local, batch, cli, qa_score
from tetrak_ocr.batch import main as run_batch
from tetrak_ocr.manifest import COLUMNS, Manifest, ManifestError
from tetrak_ocr.qa_score import LowQualityError


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture
def manifest_path(working_dirs) -> Path:
    """Where `--manifest` writes by default: beside scans/, in the workspace."""
    return working_dirs["scans"].parent / "manifest.csv"


@pytest.fixture
def reads(monkeypatch):
    """Make every file read as *text*, or raise *error*."""

    def _reads(text: str = "A clean transcript", error: Exception | None = None):
        def ocr(path):
            if error is not None:
                raise error
            return text

        monkeypatch.setattr(batch, "build_ocr_fn", lambda *a, **k: ocr)

    return _reads


def _gate(monkeypatch, score: float) -> None:
    monkeypatch.setattr(qa_score, "combined_score", lambda _text: score)
    monkeypatch.setattr(qa_score, "is_available", lambda: True)


class TestOffByDefault:
    def test_no_manifest_unless_asked_for(self, working_dirs, manifest_path, reads):
        (working_dirs["scans"] / "page.png").touch()
        reads()

        assert run_batch(["--no-telemetry"]) == 0

        assert not manifest_path.exists()


class TestRows:
    def test_a_processed_file(self, working_dirs, manifest_path, reads):
        (working_dirs["scans"] / "page.png").touch()
        reads("Matinees Wednesday, Saturday\nand Sunday")

        assert run_batch(["--manifest", "--no-telemetry"]) == 0

        (row,) = _rows(manifest_path)
        assert row["file"] == "page.png"
        assert row["status"] == "processed"
        assert row["backend"] == row["engine"] == "tesseract"
        assert row["quality"] == ""
        assert row["quality_gate"] == "off"
        assert row["transcript"] == "Matinees Wednesday, Saturday\nand Sunday"
        assert row["location"] == "processed/page.png"
        assert row["tetrak_version"]
        assert row["finished_at"].endswith("+00:00")

    def test_the_outputs_are_listed(self, working_dirs, manifest_path, reads):
        (working_dirs["scans"] / "page.png").touch()
        reads()

        run_batch(["--manifest", "--no-telemetry", "--format", "markdown,text"])

        (row,) = _rows(manifest_path)
        assert row["outputs"] == "processed/page.md;processed/page.txt"

    def test_a_scored_file_that_passes(self, working_dirs, manifest_path, reads, monkeypatch):
        (working_dirs["scans"] / "page.png").touch()
        reads()
        _gate(monkeypatch, 0.4321)

        run_batch(["--manifest", "--no-telemetry", "--quality-gate"])

        (row,) = _rows(manifest_path)
        assert (row["status"], row["quality"], row["quality_gate"]) == (
            "processed",
            "0.4321",
            "passed",
        )

    def test_a_triaged_file_has_no_transcript(
        self, working_dirs, manifest_path, reads, monkeypatch
    ):
        """Importing the manifest must never import a reading the gate rejected."""
        (working_dirs["scans"] / "faint.png").touch()
        reads("unreadable smudge")
        _gate(monkeypatch, 0.01)

        assert run_batch(["--manifest", "--no-telemetry", "--quality-gate"]) == 0

        (row,) = _rows(manifest_path)
        assert row["status"] == "triage"
        assert row["quality"] == "0.0100"
        assert row["quality_gate"] == "failed"
        assert row["transcript"] == ""
        assert row["location"] == "triage/faint.png"
        assert row["outputs"] == "triage/faint.md"
        assert "below threshold" in row["note"]

    def test_a_transcript_the_gate_cannot_judge(
        self, working_dirs, manifest_path, reads, monkeypatch
    ):
        (working_dirs["scans"] / "page.png").touch()
        reads("Հայկական Սովետական Հանրագիտարան")
        _gate(monkeypatch, 0.0)

        run_batch(["--manifest", "--no-telemetry", "--quality-gate"])

        (row,) = _rows(manifest_path)
        assert (row["status"], row["quality_gate"]) == ("processed", "skipped")
        assert row["transcript"] == "Հայկական Սովետական Հանրագիտարան"

    def test_a_failed_file(self, working_dirs, manifest_path, reads):
        (working_dirs["scans"] / "broken.png").touch()
        reads(error=RuntimeError("engine fell over"))

        assert run_batch(["--manifest", "--no-telemetry"]) == 1

        (row,) = _rows(manifest_path)
        assert row["status"] == "error"
        assert row["location"] == "scans/broken.png"
        assert row["note"] == "RuntimeError: engine fell over"


class TestAutoLocal:
    """auto-local's choice of engine, which its transcript alone cannot carry."""

    def test_the_winning_engine_is_named(self, working_dirs, manifest_path, monkeypatch):
        (working_dirs["scans"] / "page.png").touch()

        def ocr(path):
            auto_local.last_choice = {"engine": "vision", "quality": 0.2187}
            return "Grauman's Chinese"

        monkeypatch.setattr(batch, "build_ocr_fn", lambda *a, **k: ocr)

        run_batch(["--backend", "auto-local", "--manifest", "--no-telemetry"])

        (row,) = _rows(manifest_path)
        assert (row["backend"], row["engine"]) == ("auto-local", "vision")
        assert (row["quality"], row["quality_gate"]) == ("0.2187", "passed")

    def test_a_file_no_engine_could_read(self, working_dirs, manifest_path, monkeypatch):
        (working_dirs["scans"] / "ruined.jpg").touch()

        def ocr(path):
            auto_local.last_choice = {"engine": "vision", "quality": 0.0724}
            raise LowQualityError(
                "Best transcript (vision, score=0.0724) is below threshold 0.1000",
                scores={"vision": 0.0724, "easyocr": 0.0},
                transcripts={"vision": "ISIDE FACTS", "easyocr": ""},
            )

        monkeypatch.setattr(batch, "build_ocr_fn", lambda *a, **k: ocr)

        run_batch(["--backend", "auto-local", "--manifest", "--no-telemetry"])

        (row,) = _rows(manifest_path)
        assert (row["status"], row["engine"], row["quality"]) == ("triage", "vision", "0.0724")
        assert row["quality_gate"] == "failed"
        assert row["transcript"] == ""


class TestTheFile:
    def test_it_is_appended_to_across_runs(self, working_dirs, manifest_path, reads):
        reads()
        for name in ("one.png", "two.png"):
            (working_dirs["scans"] / name).touch()
            run_batch(["--manifest", "--no-telemetry"])

        assert [row["file"] for row in _rows(manifest_path)] == ["one.png", "two.png"]
        assert manifest_path.read_text(encoding="utf-8").count("file,status,") == 1

    def test_the_header_is_the_columns(self, working_dirs, manifest_path, reads):
        (working_dirs["scans"] / "page.png").touch()
        reads()

        run_batch(["--manifest", "--no-telemetry"])

        with manifest_path.open(newline="", encoding="utf-8") as handle:
            assert tuple(next(csv.reader(handle))) == COLUMNS

    def test_a_path_can_be_named(self, working_dirs, tmp_path, reads):
        (working_dirs["scans"] / "page.png").touch()
        reads()
        elsewhere = tmp_path / "reports" / "june.csv"

        run_batch(["--manifest", str(elsewhere), "--no-telemetry"])

        assert [row["file"] for row in _rows(elsewhere)] == ["page.png"]

    def test_a_different_header_is_refused_before_anything_moves(
        self, working_dirs, manifest_path, reads
    ):
        (working_dirs["scans"] / "page.png").touch()
        reads()
        manifest_path.write_text("filename,text\nold.png,hello\n", encoding="utf-8")

        assert run_batch(["--manifest", "--no-telemetry"]) == 1

        assert (working_dirs["scans"] / "page.png").exists()
        assert manifest_path.read_text(encoding="utf-8") == "filename,text\nold.png,hello\n"

    def test_the_run_is_the_telemetry_run(self, working_dirs, manifest_path, reads, tmp_path):
        (working_dirs["scans"] / "page.png").touch()
        reads()
        log = tmp_path / "telemetry.jsonl"

        run_batch(["--manifest", "--telemetry", str(log)])

        (row,) = _rows(manifest_path)
        assert row["run"] and row["run"] in log.read_text(encoding="utf-8")

    def test_an_unknown_column_is_a_bug(self, tmp_path):
        with pytest.raises(ValueError, match="not manifest columns"):
            Manifest(tmp_path / "m.csv").write(file="a.png", colour="red")

    def test_check_passes_a_new_or_empty_file(self, tmp_path):
        Manifest(tmp_path / "absent.csv").check()
        (tmp_path / "empty.csv").touch()
        Manifest(tmp_path / "empty.csv").check()

    def test_check_refuses_another_header(self, tmp_path):
        (tmp_path / "m.csv").write_text("a,b\n", encoding="utf-8")
        with pytest.raises(ManifestError):
            Manifest(tmp_path / "m.csv").check()


class TestTheCommandLine:
    def test_batch_forwards_the_flag(self, working_dirs, manifest_path, reads):
        (working_dirs["scans"] / "page.png").touch()
        reads()

        assert cli.main(["batch", "--manifest", "--no-telemetry"]) == 0

        assert [row["file"] for row in _rows(manifest_path)] == ["page.png"]

    def test_batch_forwards_a_path(self, working_dirs, tmp_path, reads):
        (working_dirs["scans"] / "page.png").touch()
        reads()

        assert cli.main(["batch", "--manifest", str(tmp_path / "m.csv"), "--no-telemetry"]) == 0

        assert (tmp_path / "m.csv").exists()
