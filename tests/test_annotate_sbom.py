"""Tests for the SBOM platform annotation.

Eight documents are published per release and they are not comparable without
knowing what each resolved against: `[vision]` is macOS-only, so its SBOM had
seventeen packages against core's twenty-seven on Linux. Nothing in the files
recorded that, and a reader would reasonably conclude the extra *removes* ten
packages.
"""

import json
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "annotate_sbom.py"
sys.path.insert(0, str(TOOL.parent))

from annotate_sbom import NAMESPACE, annotate, properties  # noqa: E402


def bom(**metadata) -> dict:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "metadata": metadata,
        "components": [{"type": "library", "name": "pillow", "version": "12.3.0"}],
    }


def ours(document: dict) -> dict[str, str]:
    return {
        p["name"]: p["value"]
        for p in document["metadata"]["properties"]
        if p["name"].startswith(f"{NAMESPACE}:")
    }


class TestWhatIsRecorded:
    def test_the_install_target_is_recorded(self) -> None:
        """Without it, every document names its subject the same thing."""
        d = annotate(bom(), "tetrak[vision]")
        assert ours(d)[f"{NAMESPACE}:install-target"] == "tetrak[vision]"

    def test_the_platform_is_recorded(self) -> None:
        """The reason vision's SBOM is smaller than core's, not a defect."""
        recorded = ours(annotate(bom(), "tetrak"))
        assert recorded[f"{NAMESPACE}:platform:os"]
        assert recorded[f"{NAMESPACE}:platform:arch"]

    def test_the_python_version_is_recorded(self) -> None:
        """A different minor version resolves different wheels."""
        d = annotate(bom(), "tetrak", python_version="3.12.1")
        assert ours(d)[f"{NAMESPACE}:python:version"] == "3.12.1"

    def test_every_property_is_namespaced(self) -> None:
        """An unregistered namespace is the sanctioned extension point; an
        unprefixed key would risk colliding with syft's own properties."""
        assert all(p["name"].startswith(f"{NAMESPACE}:") for p in properties("t"))


class TestItDoesNotDamageTheDocument:
    def test_components_are_untouched(self) -> None:
        d = annotate(bom(), "tetrak")
        assert d["components"] == [{"type": "library", "name": "pillow", "version": "12.3.0"}]

    def test_foreign_properties_survive(self) -> None:
        """syft writes its own properties; ours must sit beside them."""
        d = annotate(bom(properties=[{"name": "syft:package:type", "value": "python"}]), "t")

        names = [p["name"] for p in d["metadata"]["properties"]]
        assert "syft:package:type" in names

    def test_running_twice_does_not_duplicate(self) -> None:
        """Re-annotating replaces our keys rather than appending them again."""
        d = annotate(annotate(bom(), "tetrak[qa]"), "tetrak[qa]")

        assert len(ours(d)) == len(properties("tetrak[qa]"))

    def test_re_annotating_updates_the_value(self) -> None:
        d = annotate(annotate(bom(), "tetrak[qa]"), "tetrak[all]")
        assert ours(d)[f"{NAMESPACE}:install-target"] == "tetrak[all]"

    def test_a_document_without_metadata_is_handled(self) -> None:
        d = annotate({"bomFormat": "CycloneDX", "components": []}, "tetrak")
        assert ours(d)[f"{NAMESPACE}:install-target"] == "tetrak"


class TestTheDocumentStaysValidJson:
    def test_it_round_trips_through_the_cli(self, tmp_path: Path) -> None:
        import subprocess

        p = tmp_path / "sbom.cdx.json"
        p.write_text(json.dumps(bom()), encoding="utf-8")

        subprocess.run(
            [sys.executable, str(TOOL), str(p), "--target", "tetrak[marker]"],
            check=True,
            capture_output=True,
        )

        reloaded = json.loads(p.read_text(encoding="utf-8"))
        assert reloaded["specVersion"] == "1.7"
        assert ours(reloaded)[f"{NAMESPACE}:install-target"] == "tetrak[marker]"


@pytest.mark.parametrize("target", ["tetrak", "tetrak[all]", "tetrak[vision]"])
def test_each_published_target_annotates(target: str) -> None:
    assert ours(annotate(bom(), target))[f"{NAMESPACE}:install-target"] == target
