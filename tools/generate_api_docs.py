#!/usr/bin/env python3
"""Generate the Python API reference from the package's own docstrings.

Replaces mkdocstrings, which had no Hugo equivalent. Walks the public surface
of each documented module and emits Markdown into content/reference/, so
docstrings stay the single source of truth and the page cannot drift from the
code.

Deliberately not a general-purpose autodoc tool. It documents what a caller of
this package actually reaches for -- module docstrings, public functions and
classes, their signatures and their docstrings -- and stops there. Rendering
every private helper would produce a page nobody reads and would bury the six
things that matter.

Prerequisites:
    The package importable -- `pip install -e .` -- and nothing else. It reads
    signatures with `inspect`, so it needs the modules to import, which is why
    every backend records a missing dependency in `_IMPORT_OK` rather than
    raising.

Run:
    python tools/generate_api_docs.py

    Also runs automatically before Hugo via `npm run build`, the way velostevie
    runs extract-gps.
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# The Hugo site lives in site/; the package it documents is at the root.
SITE_ROOT = REPO_ROOT / "site"
OUTPUT = SITE_ROOT / "content" / "reference" / "api.md"

# Module -> the heading it appears under. Ordered as a reader meets them:
# resolve a backend, run it, score the result, route on the score, batch it,
# handle the errors.
MODULES: list[tuple[str, str]] = [
    ("tetrak_ocr.registry", "Registry"),
    ("tetrak_ocr.accuracy", "Accuracy metrics"),
    ("tetrak_ocr.qa_score", "Quality scoring"),
    ("tetrak_ocr.imaging", "Image and frame handling"),
    ("tetrak_ocr.auto_local", "Auto-local routing"),
    ("tetrak_ocr.outputs", "Output formats"),
    ("tetrak_ocr.telemetry", "Telemetry"),
    ("tetrak_ocr.batch", "Batch pipeline"),
    ("tetrak_ocr.errors", "Errors"),
]

PREAMBLE = """---
title: "Python API"
kicker: "Reference"
---

{{% generated %}}

Resolve a backend by name rather than importing one directly — the registry
reports a missing optional dependency as an actionable error instead of
`ModuleNotFoundError`.

```python
from pathlib import Path
from tetrak_ocr.registry import get_backend

ocr = get_backend("tesseract-auto")
text = ocr(Path("scan.jpg"))
```
"""


def is_public(name: str, obj: object, module_name: str) -> bool:
    """Public, and defined here rather than imported from somewhere else.

    Without the module check every `from x import y` would be re-documented at
    each import site, which is how autodoc output becomes noise.
    """
    if name.startswith("_"):
        return False
    if not (inspect.isfunction(obj) or inspect.isclass(obj)):
        return False
    return getattr(obj, "__module__", None) == module_name


def signature_of(obj: object) -> str:
    try:
        return str(inspect.signature(obj))
    except (ValueError, TypeError):
        # Builtins and C extensions have no introspectable signature. Better an
        # empty pair of brackets than a crash mid-build.
        return "(…)"


def render_member(name: str, obj: object, kind: str) -> list[str]:
    lines = [f"### `{name}{signature_of(obj)}`", ""]
    doc = inspect.getdoc(obj)
    if doc:
        lines += [doc, ""]
    else:
        lines += [f"*No docstring. This {kind} is public and undocumented.*", ""]
    return lines


def render_module(module_name: str, heading: str) -> list[str]:
    module = importlib.import_module(module_name)
    lines = [f"## {heading}", "", f"`{module_name}`", ""]

    # The module docstring carries the reasoning -- why fan-out is sequential,
    # why the quality gate is where it is. That is the part worth publishing.
    doc = inspect.getdoc(module)
    if doc:
        lines += [doc, ""]

    members = [
        (name, obj) for name, obj in vars(module).items() if is_public(name, obj, module_name)
    ]
    # Source order rather than alphabetical: the author's ordering usually
    # tracks how the pieces are meant to be met.
    members.sort(
        key=lambda item: getattr(item[1], "__code__", None) and item[1].__code__.co_firstlineno or 0
    )

    for name, obj in members:
        lines += render_member(name, obj, "class" if inspect.isclass(obj) else "function")

    return lines


def main() -> int:
    out: list[str] = [PREAMBLE]
    missing: list[str] = []

    for module_name, heading in MODULES:
        try:
            out.append("\n".join(render_module(module_name, heading)))
        except ImportError as exc:
            # A module whose optional extra is absent is skipped with a note
            # rather than silently omitted -- a reference page with a hole in
            # it and no explanation is worse than one that says why.
            missing.append(f"{module_name} ({exc})")
            out.append(
                f"## {heading}\n\n*Not documented: `{module_name}` could not be imported.*\n"
            )

    # Every module failing means the package is not importable at all -- a
    # setup problem, not a missing optional extra. Writing a page of "Not
    # documented" placeholders and exiting 0 is how a hollow reference gets
    # published while the build stays green; it happened once already.
    if len(missing) == len(MODULES):
        print(
            "generate_api_docs: could not import tetrak_ocr at all.\n"
            "  Install the package first:  pip install -e .\n"
            "  Refusing to write a reference page with no content in it.",
            file=sys.stderr,
        )
        return 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(out), encoding="utf-8")

    print(f"Wrote {OUTPUT.relative_to(REPO_ROOT)} from {len(MODULES) - len(missing)} modules")
    for m in missing:
        print(f"  ! skipped {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
