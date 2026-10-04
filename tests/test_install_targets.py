"""Tests for the SBOM install-target enumeration.

The list is derived from pyproject.toml so that adding an extra publishes its
SBOM without anyone editing a workflow. These pin the derivation, because a
target silently dropping off the list means a published package ships with no
bill of materials and nothing fails.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "install_targets.py"
sys.path.insert(0, str(TOOL.parent))

from install_targets import targets  # noqa: E402


def write_pyproject(tmp_path: Path, extras: dict[str, list[str]]) -> Path:
    lines = [
        "[project]",
        'name = "thing"',
        'version = "1.0.0"',
        "",
        "[project.optional-dependencies]",
    ]
    for name, reqs in extras.items():
        rendered = ", ".join(f'"{r}"' for r in reqs)
        lines.append(f"{name} = [{rendered}]")
    p = tmp_path / "pyproject.toml"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


class TestDerivation:
    def test_core_is_always_a_target(self, tmp_path: Path) -> None:
        """`pip install tetrak` with no extras is what most people do."""
        found = targets(write_pyproject(tmp_path, {}))
        assert [t["target"] for t in found] == ["core"]
        assert found[0]["spec"] == "."

    def test_a_new_extra_appears_without_editing_anything(self, tmp_path: Path) -> None:
        """The reason this is derived rather than written down."""
        found = targets(write_pyproject(tmp_path, {"newthing": ["somepkg>=1.0"]}))

        assert "newthing" in [t["target"] for t in found]
        assert next(t for t in found if t["target"] == "newthing")["spec"] == ".[newthing]"

    @pytest.mark.parametrize("excluded", ["dev", "docs", "apidocs", "ocr"])
    def test_toolchain_and_aggregate_extras_are_skipped(
        self, tmp_path: Path, excluded: str
    ) -> None:
        """Nobody consumes dev or docs, and `ocr` only re-exports `all`."""
        found = targets(write_pyproject(tmp_path, {excluded: ["somepkg>=1.0"]}))
        assert [t["target"] for t in found] == ["core"]

    def test_all_is_kept(self, tmp_path: Path) -> None:
        """The maximal closure is exactly what a cautious consumer wants."""
        found = targets(write_pyproject(tmp_path, {"all": ["thing[a,b]"]}))
        assert "all" in [t["target"] for t in found]


class TestPlatformRouting:
    def test_a_darwin_only_extra_runs_on_macos(self, tmp_path: Path) -> None:
        """Resolved on Linux it installs nothing, so its SBOM would be a
        mislabelled copy of core -- worse than publishing none."""
        found = targets(
            write_pyproject(tmp_path, {"vision": ["ocrmac>=1.0; sys_platform == 'darwin'"]})
        )

        assert next(t for t in found if t["target"] == "vision")["runner"] == "macos-latest"

    def test_an_ordinary_extra_runs_on_linux(self, tmp_path: Path) -> None:
        found = targets(write_pyproject(tmp_path, {"easyocr": ["easyocr>=1.7"]}))

        assert next(t for t in found if t["target"] == "easyocr")["runner"] == "ubuntu-latest"

    def test_a_partly_darwin_extra_stays_on_linux(self, tmp_path: Path) -> None:
        """Only route to macOS when *nothing* would install elsewhere."""
        found = targets(
            write_pyproject(
                tmp_path, {"mixed": ["ocrmac>=1.0; sys_platform == 'darwin'", "pillow>=10"]}
            )
        )

        assert next(t for t in found if t["target"] == "mixed")["runner"] == "ubuntu-latest"


class TestAgainstTheRealProject:
    def test_every_shipped_extra_gets_an_sbom(self) -> None:
        """A consumer-facing extra with no SBOM is the failure this prevents."""
        found = {t["target"] for t in targets(TOOL.parent.parent / "pyproject.toml")}

        assert {"core", "all", "claude", "easyocr", "marker", "paddle", "qa", "vision"} <= found
        assert "dev" not in found and "docs" not in found and "apidocs" not in found

    def test_the_matrix_is_valid_json_for_actions(self) -> None:
        out = subprocess.run(
            [sys.executable, str(TOOL), "--github"], capture_output=True, text=True, check=True
        ).stdout
        matrix = json.loads(out)

        assert "include" in matrix
        assert all({"target", "spec", "runner"} <= set(e) for e in matrix["include"])
