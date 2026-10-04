#!/usr/bin/env python3
"""Enumerate the install targets an SBOM should be published for.

A consumer installs one of several different things -- `tetrak-ocr`,
`tetrak[easyocr]`, `tetrak[all]` -- and each pulls a different
dependency closure. An SBOM for one of them says nothing useful about the
others: core declares five dependencies, `[all]` resolves to nearly two
hundred.

Publishing an SBOM per *combination* is not feasible. Six composable extras
means 64 combinations before counting core, and each install pulls
multi-gigabyte wheels. This emits the practical covering set instead: core,
each extra on its own, and the maximal `[all]`. A consumer of two extras reads
the two documents; see the caveat in the workflow about why that is an
approximation rather than a guarantee.

The list is derived from pyproject.toml rather than written down, so adding an
extra produces its SBOM without anyone editing the workflow. That is the whole
point -- a hand-maintained list is one release away from being wrong.

Run:
    python3 tools/install_targets.py            # human-readable
    python3 tools/install_targets.py --github   # matrix JSON for Actions

Standard library only: this runs on a CI runner before any install.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path

# Extras that exist for developing or documenting the project rather than for
# using it. Nobody consumes these, so an SBOM for them would describe a
# toolchain rather than a delivered artefact.
_NOT_CONSUMER_FACING = {"dev", "docs", "apidocs"}

# Aggregates that only re-export other extras. `all` is kept because the
# maximal closure is exactly what a cautious consumer wants to see; `ocr` is
# dropped because it is `all` minus nothing anyone installs separately.
_REDUNDANT_AGGREGATES = {"ocr"}

# A requirement carrying this marker only materialises on macOS. Building its
# SBOM on Linux would silently produce a copy of core and label it something
# else, which is worse than not publishing it.
_DARWIN_MARKER = re.compile(r";\s*sys_platform\s*==\s*['\"]darwin['\"]")


def targets(pyproject: Path) -> list[dict]:
    """Every install target worth an SBOM, with the runner each needs."""
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data["project"]
    extras = project.get("optional-dependencies", {})

    found = [
        {
            "target": "core",
            "extras": "",
            "spec": ".",
            "runner": "ubuntu-latest",
            "note": "what `pip install tetrak` pulls",
        }
    ]

    for name in sorted(extras):
        if name in _NOT_CONSUMER_FACING or name in _REDUNDANT_AGGREGATES:
            continue
        requirements = [str(r) for r in extras[name]]
        darwin_only = requirements and all(_DARWIN_MARKER.search(r) for r in requirements)
        found.append(
            {
                "target": name,
                "extras": f"[{name}]",
                "spec": f".[{name}]",
                # macOS-only extras must be resolved on macOS or the SBOM is a
                # mislabelled copy of core.
                "runner": "macos-latest" if darwin_only else "ubuntu-latest",
                "note": f"`pip install 'tetrak[{name}]'`",
            }
        )

    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--github", action="store_true", help="emit matrix JSON")
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "pyproject.toml",
    )
    args = parser.parse_args(argv)

    found = targets(args.pyproject)

    if args.github:
        matrix = json.dumps({"include": found})
        if path := os.environ.get("GITHUB_OUTPUT"):
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"matrix={matrix}\n")
        print(matrix)
        return 0

    print(f"{len(found)} install target(s):", file=sys.stderr)
    for t in found:
        print(f"  {t['target']:<10} {t['spec']:<14} {t['runner']:<14} {t['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
