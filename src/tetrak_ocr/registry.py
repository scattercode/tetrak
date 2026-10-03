"""Resolve a backend by name.

Every backend exposes the same callable — ``ocr_image(path) -> str`` — so the
rest of the package can treat them interchangeably. This module is where a
name becomes one of those callables, and where a missing optional dependency
turns into an error that says which extra to install.

Importing a backend module is always safe: each one records whether its heavy
dependency imported successfully in ``_IMPORT_OK`` rather than failing at
import time. That matters because :func:`available` needs to inspect every
backend, including the ones this machine cannot run.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path

from .errors import MissingBackendError, UnknownBackendError

# name -> (module path, extra to install, human-readable requirement)
#
# Some entries share a module and differ only in how they are invoked:
#
#   tesseract / tesseract-auto  — the same backend with per-image contrast and
#                                 page-segmentation detection turned on
#
# They are separate names rather than flags so the evaluation harness scores
# them as distinct backends -- which is the only way the difference between
# them becomes a measurement instead of a claim.
#
# `auto-local-fast` was a third such name, running only the top-ranked eligible
# backend. `evaluate --all` measured it and it lost: in every configuration it
# was at best equal to naming `tesseract-auto` directly, so it was removed
# rather than documented around.
_BACKENDS: dict[str, tuple[str, str | None, str]] = {
    "tesseract": ("tetrak_ocr.backends.tesseract", None, "pytesseract (core)"),
    "tesseract-auto": ("tetrak_ocr.backends.tesseract", None, "pytesseract (core)"),
    "claude": ("tetrak_ocr.backends.claude", "claude", "the 'anthropic' package"),
    "easyocr": ("tetrak_ocr.backends.easyocr", "easyocr", "the 'easyocr' package"),
    # Stock EasyOCR with the project's own Armenian recogniser swapped in.
    # Its own name, like tesseract-auto: the harness then scores it against
    # stock easyocr rather than the difference being asserted.
    "easyocr-hy": (
        "tetrak_ocr.backends.armenian",
        "armenian",
        "the 'tetrak-easyocr-armenian' package",
    ),
    "paddle": (
        "tetrak_ocr.backends.paddle",
        "paddle",
        "the 'paddleocr' and 'paddlepaddle' packages",
    ),
    # Same package as `paddle`, different model and different class: a
    # document vision-language model rather than a detector plus classifier.
    # Its own name for the same reason tesseract-auto has one.
    "paddle-vl": (
        "tetrak_ocr.backends.paddle_vl",
        "paddle-vl",
        "the 'paddleocr', 'paddlex[ocr]' and 'paddlepaddle' packages",
    ),
    "marker": ("tetrak_ocr.backends.marker", "marker", "the 'marker-pdf' package"),
    # macOS only. Vision ships with the OS, so this backend needs no model
    # download and no network -- but it does not exist on Linux or Windows,
    # and `ocrmac` is declared with a sys_platform marker to match.
    "vision": ("tetrak_ocr.backends.vision", "vision", "the 'ocrmac' package (macOS only)"),
    # auto-local scores its transcripts, which needs the `qa` extra. It was
    # previously declared as "core" and so reported as available on a machine
    # that could not actually run it.
    "auto-local": (
        "tetrak_ocr.auto_local",
        "qa",
        "the 'pyspellchecker', 'transformers' and 'torch' packages",
    ),
}

BACKENDS: tuple[str, ...] = tuple(_BACKENDS)


def _load(name: str):
    """Import a backend module, raising a helpful error for unknown names."""
    try:
        module_path, extra, packages = _BACKENDS[name]
    except KeyError:
        raise UnknownBackendError(name, list(_BACKENDS)) from None

    module = importlib.import_module(module_path)

    # A backend whose optional dependency is absent still imports; it just
    # cannot run. Turn that into the actionable error here rather than letting
    # a NameError surface from deep inside the call.
    if extra is not None and not getattr(module, "_IMPORT_OK", True):
        raise MissingBackendError(name, extra, packages)

    return module


def get_backend(name: str) -> Callable[..., str]:
    """Return the ``ocr_image`` callable for *name*.

    Raises :class:`UnknownBackendError` for a name that does not exist, and
    :class:`MissingBackendError` when the backend exists but its extra is not
    installed.
    """
    module = _load(name)
    if name == "tesseract-auto":
        # Same function, auto-configuration switched on.
        def _auto(path: Path, **kwargs) -> str:
            kwargs.setdefault("auto", True)
            return module.ocr_image(path, **kwargs)

        return _auto

    return module.ocr_image


def is_available(name: str) -> bool:
    """True when *name* can actually run on this machine."""
    try:
        _load(name)
    except (MissingBackendError, UnknownBackendError):
        return False
    return True


def available() -> list[str]:
    """Every backend whose dependencies are installed here.

    Used by the CLI and the evaluation harness to skip backends the current
    environment cannot run, instead of failing the whole run.
    """
    return [name for name in _BACKENDS if is_available(name)]


def supported_extensions(name: str) -> set[str]:
    """File extensions *name* accepts, from the backend's own declaration."""
    module = _load(name)
    return set(getattr(module, "SUPPORTED_EXTENSIONS", set()))
