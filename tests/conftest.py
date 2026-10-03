"""Shared test fixtures.

The evaluation corpus lives outside `tests/` — it is a benchmark corpus, not a
unit-test fixture, and the evaluation harness is its primary consumer. Tests
that genuinely need a real scanned image borrow from it through
:func:`corpus_images`; everything else generates its own images with Pillow so
the fast test loop needs no data files at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# The evaluation harness is not part of the installed package -- it sits beside
# the corpus it reads, so evaluation data and evaluation code stay together.
# That means importing it needs the repository root on sys.path, which is
# exactly what `cli._cmd_evaluate` does at runtime for the same reason.
#
# Locally this happens to be satisfied already, which is why a test importing
# `evaluation.harness` passed here and failed in CI's lean install with
# ModuleNotFoundError. Doing it explicitly makes the requirement visible rather
# than incidental.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
CORPUS_DIR = REPO_ROOT / "evaluation" / "ocr" / "corpus"
CORPUS_IMAGES = CORPUS_DIR / "images"
CORPUS_EXPECTED = CORPUS_DIR / "expected"


@pytest.fixture(scope="session")
def corpus_images() -> list[Path]:
    """Every image in the evaluation corpus, or an empty list if absent."""
    if not CORPUS_IMAGES.is_dir():
        return []
    return sorted(p for p in CORPUS_IMAGES.iterdir() if p.is_file() and not p.name.startswith("."))


@pytest.fixture
def working_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Point the batch pipeline at throwaway scans/processed/triage dirs.

    The batch module resolves these relative to the current directory, so the
    tests monkeypatch the module attributes rather than chdir-ing, which would
    leak into any test running in parallel.
    """
    from tetrak_ocr import batch

    dirs = {name: tmp_path / name for name in ("scans", "processed", "triage")}
    for path in dirs.values():
        path.mkdir()

    monkeypatch.setattr(batch, "SCANS_DIR", dirs["scans"])
    monkeypatch.setattr(batch, "PROCESSED_DIR", dirs["processed"])
    monkeypatch.setattr(batch, "TRIAGE_DIR", dirs["triage"])
    return dirs
