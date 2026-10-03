"""Tests for the `tetrak-ocr` console entry point.

These exist because the CLI shipped in 1.0.0 with `tetrak-ocr batch` raising
TypeError on every invocation: `cli._cmd_batch` called `batch.main(argv=...)`
while `batch.main` names its parameter `args`. Nothing caught it, because every
other test drives `batch.main` directly and never crosses the CLI boundary --
which is exactly the seam the bug lived in.

So these tests assert the wiring rather than the OCR: that each subcommand
reaches the right callable, that flags survive the hop, and that exit codes
propagate. The backends themselves are mocked; their behaviour is covered
elsewhere.
"""

from __future__ import annotations

import pytest

from tetrak_ocr import batch, cli


class TestBatchSubcommand:
    """`tetrak-ocr batch` -- the command that was broken."""

    def test_invokes_batch_main_without_raising(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The regression itself: this raised TypeError for every user of 1.0.0."""
        seen: dict = {}

        def fake_main(args=None):
            seen["args"] = args
            return 0

        monkeypatch.setattr(batch, "main", fake_main)

        assert cli.main(["batch"]) == 0
        assert seen["args"] == ["--backend", "tesseract"]

    def test_forwards_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict = {}
        monkeypatch.setattr(batch, "main", lambda args=None: (seen.update(args=args), 0)[1])

        cli.main(["batch", "--backend", "auto-local"])

        assert seen["args"] == ["--backend", "auto-local"]

    def test_forwards_tuning_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--contrast/--psm/--auto were accepted by batch.main but never sent."""
        seen: dict = {}
        monkeypatch.setattr(batch, "main", lambda args=None: (seen.update(args=args), 0)[1])

        cli.main(["batch", "--contrast", "3.0", "--psm", "6", "--auto"])

        assert seen["args"] == [
            "--backend",
            "tesseract",
            "--contrast",
            "3.0",
            "--psm",
            "6",
            "--auto",
        ]

    def test_forwards_the_paddle_vl_opt_in(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict = {}
        monkeypatch.setattr(batch, "main", lambda args=None: (seen.update(args=args), 0)[1])

        cli.main(["batch", "--backend", "auto-local", "--with-paddle-vl"])

        assert "--with-paddle-vl" in seen["args"]

    def test_forwards_dry_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict = {}
        monkeypatch.setattr(batch, "main", lambda args=None: (seen.update(args=args), 0)[1])

        cli.main(["batch", "--dry-run"])

        assert "--dry-run" in seen["args"]

    def test_propagates_failure_exit_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A partial batch failure has to reach the shell, not report success."""
        monkeypatch.setattr(batch, "main", lambda args=None: 1)

        assert cli.main(["batch"]) == 1

    def test_forwarded_flags_are_accepted_by_batchs_own_parser(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """Guards the two argument lists against drifting apart.

        `_cmd_batch` builds a command line for a parser it does not own, so a
        flag removed from `batch.main` would leave the CLI sending something
        argparse rejects with exit(2). Parsing the real thing is the only way to
        catch that; asserting on the string the CLI builds would just restate
        the code under test.
        """
        monkeypatch.setattr(batch, "SCANS_DIR", tmp_path / "scans")
        (tmp_path / "scans").mkdir()

        # --dry-run stops before any OCR, so this exercises argument parsing
        # and nothing more.
        assert (
            batch.main(
                args=[
                    "--backend",
                    "tesseract",
                    "--contrast",
                    "3.0",
                    "--psm",
                    "6",
                    "--auto",
                    "--with-paddle-vl",
                    "--dry-run",
                ]
            )
            == 0
        )

    def test_missing_scans_directory_returns_nonzero_through_the_cli(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """The failure has to come back as a value, not as SystemExit.

        `cli.main` is annotated `-> int` and is called directly by these tests
        and by anyone embedding the tool. A `sys.exit` inside `batch.main` used
        to sail straight through it, so the shell saw the right code but a
        programmatic caller got an exception instead of a return.
        """
        monkeypatch.setattr(batch, "SCANS_DIR", tmp_path / "absent")

        assert cli.main(["batch"]) == 1


class TestOcrSubcommand:
    def test_prints_transcript(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path
    ) -> None:
        monkeypatch.setattr(batch, "build_ocr_fn", lambda *a, **k: lambda path: "hello")
        img = tmp_path / "scan.png"
        img.touch()

        assert cli.main(["ocr", str(img)]) == 0
        assert "hello" in capsys.readouterr().out

    def test_writes_output_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.setattr(batch, "build_ocr_fn", lambda *a, **k: lambda path: "transcript")
        img = tmp_path / "scan.png"
        img.touch()
        out = tmp_path / "out.md"

        assert cli.main(["ocr", str(img), "--output", str(out)]) == 0
        assert out.read_text() == "transcript"

    def test_passes_tuning_flags_to_the_backend(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """These were documented against `ocr` but rejected as unknown arguments."""
        seen: dict = {}

        def fake_build(backend, contrast=None, psm=None, auto=False, with_paddle_vl=False):
            seen.update(
                backend=backend,
                contrast=contrast,
                psm=psm,
                auto=auto,
                with_paddle_vl=with_paddle_vl,
            )
            return lambda path: ""

        monkeypatch.setattr(batch, "build_ocr_fn", fake_build)
        img = tmp_path / "scan.png"
        img.touch()

        cli.main(["ocr", str(img), "--contrast", "3.5", "--psm", "11", "--auto"])

        assert seen == {
            "backend": "tesseract",
            "contrast": 3.5,
            "psm": 11,
            "auto": True,
            "with_paddle_vl": False,
        }

    def test_defaults_leave_tuning_unset(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """Unset must stay None so the backend applies its own defaults."""
        seen: dict = {}

        def fake_build(backend, contrast=None, psm=None, auto=False, with_paddle_vl=False):
            seen.update(contrast=contrast, psm=psm, auto=auto, with_paddle_vl=with_paddle_vl)
            return lambda path: ""

        monkeypatch.setattr(batch, "build_ocr_fn", fake_build)
        img = tmp_path / "scan.png"
        img.touch()

        cli.main(["ocr", str(img)])

        assert seen == {"contrast": None, "psm": None, "auto": False, "with_paddle_vl": False}

    def test_passes_the_paddle_vl_opt_in(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """The flag has to survive the hop, like the tuning flags before it.

        auto-local's pool is built inside the backend, so a flag that parsed
        here and never arrived would silently do nothing -- the failure mode
        this whole test module exists for.
        """
        seen: dict = {}

        def fake_build(backend, contrast=None, psm=None, auto=False, with_paddle_vl=False):
            seen.update(backend=backend, with_paddle_vl=with_paddle_vl)
            return lambda path: ""

        monkeypatch.setattr(batch, "build_ocr_fn", fake_build)
        img = tmp_path / "scan.png"
        img.touch()

        cli.main(["ocr", str(img), "--backend", "auto-local", "--with-paddle-vl"])

        assert seen == {"backend": "auto-local", "with_paddle_vl": True}


class TestBackendsSubcommand:
    def test_lists_every_registered_backend(self, capsys: pytest.CaptureFixture) -> None:
        from tetrak_ocr.registry import BACKENDS

        assert cli.main(["backends"]) == 0
        out = capsys.readouterr().out
        for name in BACKENDS:
            assert name in out


class TestArgumentHandling:
    def test_unknown_flag_is_rejected(self, capsys: pytest.CaptureFixture, tmp_path) -> None:
        img = tmp_path / "scan.png"
        img.touch()

        assert cli.main(["ocr", str(img), "--nonsense"]) == 2
        assert "unrecognized arguments" in capsys.readouterr().err

    def test_evaluate_forwards_unknown_flags_to_the_harness(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`evaluate` is the one subcommand whose extra flags belong elsewhere."""
        import sys
        import types

        seen: dict = {}
        fake = types.ModuleType("harness")
        fake.main = lambda argv=None: (seen.update(argv=argv), 0)[1]
        package = types.ModuleType("evaluation")
        pipeline = types.ModuleType("evaluation.ocr")
        pipeline.harness = fake
        package.ocr = pipeline
        # Every level has to be stubbed. Miss one and the import falls through
        # to the real harness, which benchmarks the whole corpus with every
        # installed backend -- so the test hangs for minutes rather than
        # failing, which is how the evaluation/ocr/ move was caught.
        monkeypatch.setitem(sys.modules, "evaluation", package)
        monkeypatch.setitem(sys.modules, "evaluation.ocr", pipeline)
        monkeypatch.setitem(sys.modules, "evaluation.ocr.harness", fake)

        assert cli.main(["evaluate", "--all", "--save"]) == 0
        assert seen["argv"] == ["--all", "--save"]

    def test_missing_backend_reports_the_extra_rather_than_a_traceback(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path
    ) -> None:
        from tetrak_ocr.errors import MissingBackendError

        def boom(*a, **k):
            raise MissingBackendError("paddle", "paddle", "the 'paddleocr' package")

        monkeypatch.setattr(batch, "build_ocr_fn", boom)
        img = tmp_path / "scan.png"
        img.touch()

        assert cli.main(["ocr", str(img), "--backend", "paddle"]) == 1
        assert "tetrak-ocr[paddle]" in capsys.readouterr().err


class TestQualityGateFlag:
    """`--quality-gate` replaced the `auto-local-fast` backend.

    Fast mode was the only way to get one cheap engine *plus* triage,
    which is the single thing lost by removing it. The gate is a batch flag
    now, so any backend can have it — and the gate judges the transcript, which
    is what it was always actually about.
    """

    def test_batch_forwards_the_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict = {}
        monkeypatch.setattr(batch, "main", lambda args=None: (seen.update(args=args), 0)[1])

        cli.main(["batch", "--backend", "tesseract-auto", "--quality-gate"])

        assert seen["args"] == ["--backend", "tesseract-auto", "--quality-gate"]

    def test_the_retired_backend_is_no_longer_accepted(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """argparse rejects it, rather than the name resolving to something.

        A choices= list built from BACKENDS is the only thing enforcing this,
        so it is worth asserting that removing the registry entry really did
        withdraw the name from the CLI.
        """
        img = tmp_path / "scan.png"
        img.touch()

        with pytest.raises(SystemExit):
            cli.main(["ocr", str(img), "--backend", "auto-local-fast"])
