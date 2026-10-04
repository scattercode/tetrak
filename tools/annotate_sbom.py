#!/usr/bin/env python3
"""Record which install target and platform an SBOM actually describes.

The eight SBOMs published with a release are not comparable unless you know
what each one resolved against. `[vision]` is macOS-only and so resolves on a
macOS runner, where it produced *seventeen* packages against core's twenty-seven
on Linux -- not because the extra removes anything, but because the two
documents describe different operating systems. Nothing in the files said so:
all eight named their subject `.sbomvenv`.

CycloneDX has no field for this. The specification's file-naming convention
covers the extension (`.cdx.json`, already used) and `metadata.component` names
the subject, but neither the spec overview nor the property-taxonomy registry
defines anything for the operating system or architecture a BOM was resolved
for. That is not an oversight so much as a container-shaped assumption: image
SBOMs get one document per digest, and the platform is implicit in the digest.
A Python package with platform-conditional extras does not have that.

So the platform goes in `metadata.properties` under our own namespace, which is
the extension point the specification does sanction. `syft --source-name` and
`--source-version` handle the subject's identity; this adds the context those
flags cannot.

Run:
    python3 tools/annotate_sbom.py sbom-vision.cdx.json --target 'tetrak[vision]'
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

# Unregistered, and deliberately so: the taxonomy registry asks that a
# namespace's documentation be publicly available, and this file is it. The
# prefix keeps our additions from colliding with syft's own `syft:` properties.
NAMESPACE = "tetrak"


def properties(target: str, python_version: str | None = None) -> list[dict]:
    """The context a reader needs to compare one of these documents with another."""
    return [
        {"name": f"{NAMESPACE}:install-target", "value": target},
        {"name": f"{NAMESPACE}:platform:os", "value": platform.system().lower()},
        {"name": f"{NAMESPACE}:platform:arch", "value": platform.machine().lower()},
        # The interpreter matters as much as the OS: a different minor version
        # resolves different wheels, and for some packages a different set of
        # dependencies entirely.
        {
            "name": f"{NAMESPACE}:python:version",
            "value": python_version or platform.python_version(),
        },
    ]


def annotate(document: dict, target: str, python_version: str | None = None) -> dict:
    """Add the properties, replacing any this tool set on a previous run."""
    metadata = document.setdefault("metadata", {})
    existing = [
        p
        for p in metadata.get("properties", [])
        if not str(p.get("name", "")).startswith(f"{NAMESPACE}:")
    ]
    metadata["properties"] = existing + properties(target, python_version)
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sbom", type=Path, help="the CycloneDX JSON document to annotate")
    parser.add_argument("--target", required=True, help="e.g. tetrak[vision]")
    parser.add_argument("--python-version", help="defaults to the running interpreter")
    args = parser.parse_args(argv)

    document = json.loads(args.sbom.read_text(encoding="utf-8"))
    annotate(document, args.target, args.python_version)
    args.sbom.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    for p in document["metadata"]["properties"]:
        if str(p["name"]).startswith(f"{NAMESPACE}:"):
            print(f"  {p['name']:<28} {p['value']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
