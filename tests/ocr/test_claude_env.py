"""The Claude backend's .env loading.

This exists because the loader broke silently during the package restructure.
It used `Path(__file__).parent.parent / ".env"`, which was the repository root
while the module lived in scripts/. Moving it to src/tetrak_ocr/backends/ put
it two levels deeper, so it pointed at src/tetrak_ocr/.env -- a path that has
never existed.

Nothing failed at import. The backend simply failed on every call with "Could
not resolve authentication method", which only surfaced when a full benchmark
run tried to use it and lost the entire Claude column.
"""

from __future__ import annotations

import importlib
import os

import pytest


@pytest.fixture
def clean_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """No key in the environment, so anything found came from the .env."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_a_dotenv_in_the_working_directory_is_loaded(
    clean_key, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Importing the backend from a directory with a .env picks up the key."""
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-test-value\n")
    monkeypatch.chdir(tmp_path)

    from tetrak_ocr.backends import claude

    importlib.reload(claude)

    assert os.environ.get("ANTHROPIC_API_KEY") == "sk-ant-test-value"


def test_a_dotenv_further_up_the_tree_is_found(
    clean_key, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Running from a subdirectory still finds the project's .env.

    This is the case that matters in practice: `tetrak-ocr batch` is run from
    wherever the scans are, which is rarely the directory holding the .env.
    """
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-from-parent\n")
    nested = tmp_path / "scans" / "batch-01"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    from tetrak_ocr.backends import claude

    importlib.reload(claude)

    assert os.environ.get("ANTHROPIC_API_KEY") == "sk-ant-from-parent"


def test_importing_without_a_dotenv_does_not_raise(
    clean_key, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """A missing .env is normal -- the key may be set in the environment."""
    monkeypatch.chdir(tmp_path)

    from tetrak_ocr.backends import claude

    importlib.reload(claude)  # must not raise
