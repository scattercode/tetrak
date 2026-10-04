"""Unit tests for backend resolution.

The registry replaced three separate if/elif import chains (in batch, in the
evaluation harness, and inline). Its whole job is to be the single place that
knows which backends exist and what to say when one is not installed, so both
halves of that are worth pinning.
"""

from __future__ import annotations

import sys
import types

import pytest

from tetrak_ocr.errors import MissingBackendError, UnknownBackendError
from tetrak_ocr.registry import (
    BACKENDS,
    available,
    get_backend,
    is_available,
    supported_extensions,
)


class TestBackendList:
    def test_the_documented_backends_are_all_registered(self) -> None:
        """The set the README, CLI and harness all advertise."""
        assert set(BACKENDS) == {
            "tesseract",
            "tesseract-auto",
            "claude",
            "easyocr",
            "easyocr-hy",
            "paddle",
            "paddle-vl",
            "marker",
            "vision",
            "auto-local",
        }

    def test_core_backends_need_no_extras(self) -> None:
        """Tesseract ships in the core install, so a bare
        `pip install tetrak` must leave the tool usable."""
        assert is_available("tesseract")
        assert is_available("tesseract-auto")

    def test_auto_local_is_not_a_core_backend(self) -> None:
        """It scores every transcript, and scoring needs the `qa` extra.

        This test previously asserted the opposite. That claim was wrong:
        `tetrak-ocr backends` reported auto-local as runnable on a machine
        where it failed on the first file with "No module named
        'spellchecker'".
        """
        from tetrak_ocr.registry import _BACKENDS

        assert _BACKENDS["auto-local"][1] == "qa"

    def test_available_is_a_subset_of_all_backends(self) -> None:
        assert set(available()) <= set(BACKENDS)


class TestResolution:
    def test_returns_a_callable(self) -> None:
        assert callable(get_backend("tesseract"))

    def test_unknown_name_lists_the_valid_ones(self) -> None:
        """The error has to be self-service — it is what a typo produces."""
        with pytest.raises(UnknownBackendError) as exc:
            get_backend("tesseractt")
        message = str(exc.value)
        assert "tesseractt" in message
        assert "tesseract" in message

    def test_tesseract_auto_defaults_to_auto_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`tesseract-auto` is the same backend with auto-configuration on.

        Two registry entries share one module, so this checks the wrapper
        actually passes auto=True rather than silently being a duplicate.
        """
        from tetrak_ocr.backends import tesseract

        seen: dict[str, object] = {}

        def fake_ocr(path, **kwargs):
            seen.update(kwargs)
            return "text"

        monkeypatch.setattr(tesseract, "ocr_image", fake_ocr)

        get_backend("tesseract-auto")("image.png")
        assert seen.get("auto") is True

    def test_plain_tesseract_does_not_force_auto(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tetrak_ocr.backends import tesseract

        seen: dict[str, object] = {}

        def fake_ocr(path, **kwargs):
            seen.update(kwargs)
            return "text"

        monkeypatch.setattr(tesseract, "ocr_image", fake_ocr)

        get_backend("tesseract")("image.png")
        assert seen.get("auto") is not True


class TestMissingExtras:
    """The behaviour this module exists for.

    Before the registry, a backend whose dependency was absent called
    sys.exit(1) at import time — fine for a script, fatal for a caller that
    wanted to fall back to another backend.
    """

    def test_missing_extra_raises_rather_than_exiting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = types.ModuleType("tetrak_ocr.backends.paddle")
        stub._IMPORT_OK = False
        monkeypatch.setitem(sys.modules, "tetrak_ocr.backends.paddle", stub)

        with pytest.raises(MissingBackendError):
            get_backend("paddle")

    def test_the_error_names_the_extra_to_install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub = types.ModuleType("tetrak_ocr.backends.paddle")
        stub._IMPORT_OK = False
        monkeypatch.setitem(sys.modules, "tetrak_ocr.backends.paddle", stub)

        with pytest.raises(MissingBackendError) as exc:
            get_backend("paddle")

        message = str(exc.value)
        assert "tetrak[paddle]" in message, "must give the exact install command"
        assert "pip install" in message

    def test_is_available_reports_false_without_raising(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub = types.ModuleType("tetrak_ocr.backends.marker")
        stub._IMPORT_OK = False
        monkeypatch.setitem(sys.modules, "tetrak_ocr.backends.marker", stub)

        assert is_available("marker") is False
        assert "marker" not in available()

    def test_unknown_backend_is_not_available(self) -> None:
        assert is_available("does-not-exist") is False


class TestSupportedExtensions:
    def test_tesseract_handles_pdfs(self) -> None:
        """Tesseract is the PDF path, which is why auto-local routes PDFs to it."""
        assert ".pdf" in supported_extensions("tesseract")

    def test_extensions_are_lowercase_with_a_leading_dot(self) -> None:
        """Callers match on `path.suffix.lower()`, so the set must agree."""
        for ext in supported_extensions("tesseract"):
            assert ext.startswith(".")
            assert ext == ext.lower()


class TestAutoLocal:
    """`auto-local` is the one remaining strategy name.

    `auto-local-fast` used to sit beside it, dispatching a second mode through
    the same module. The benchmark retired it: in every installed
    configuration it was at best equal to naming `tesseract-auto` directly.
    """

    def test_it_is_registered(self) -> None:
        assert "auto-local" in BACKENDS

    def test_fast_mode_is_gone(self) -> None:
        """A removed backend must not linger in the advertised list.

        `BACKENDS` is what the CLI builds `--backend` choices from, so a stale
        entry here would offer a name that no longer resolves.
        """
        assert "auto-local-fast" not in BACKENDS

    def test_it_declares_the_qa_extra(self) -> None:
        """Scoring needs `qa`. Declaring it "core" made `backends` report a
        backend as runnable that failed on the first file."""
        from tetrak_ocr.registry import _BACKENDS

        _module, extra, _packages = _BACKENDS["auto-local"]
        assert extra == "qa"

    def test_it_resolves_to_the_module_function_directly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No wrapper left behind once the mode parameter went away.

        `_IMPORT_OK` is forced on because this asserts the name-to-callable
        wiring, which is independent of whether the `qa` extra happens to be
        installed. Without it the test passes only on a machine that has qa --
        which is how it first slipped through locally and failed in CI.
        """
        from tetrak_ocr import auto_local

        monkeypatch.setattr(auto_local, "_IMPORT_OK", True)
        assert get_backend("auto-local") is auto_local.ocr_image
