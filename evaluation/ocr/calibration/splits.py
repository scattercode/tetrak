"""Read the corpus manifest at `evaluation/ocr/corpus/splits.toml`.

One parser, because the manifest has three consumers that must agree about it:
the coverage test, the band fitter, and whatever publishes the site's subset.
Three copies of `tomllib.load` would be three chances to disagree about what
"held out" means.

Stems throughout, never filenames -- the corpus mixes .png, .jpg, .tif and
.pdf and no caller should have to care which.
"""

import tomllib
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent.parent / "corpus"
IMAGES_DIR = CORPUS_DIR / "images"
MANIFEST = CORPUS_DIR / "splits.toml"


class ManifestError(Exception):
    """The manifest disagrees with the corpus on disk."""


def load(path: Path = MANIFEST) -> dict:
    """Return the parsed manifest."""
    with path.open("rb") as handle:
        return tomllib.load(handle)


def corpus_stems(images_dir: Path = IMAGES_DIR) -> set[str]:
    """Return every fixture stem present on disk."""
    return {
        path.stem
        for path in images_dir.iterdir()
        if path.is_file() and not path.name.startswith(".")
    }


def excluded(manifest: dict | None = None) -> set[str]:
    """Return stems no band fit may use, for any split."""
    manifest = manifest if manifest is not None else load()
    return set(manifest.get("excluded", {}).get("stems", []))


def split_names(manifest: dict | None = None) -> list[str]:
    """Return the names of the defined splits."""
    manifest = manifest if manifest is not None else load()
    return sorted(manifest.get("splits", {}))


def split(name: str, manifest: dict | None = None) -> tuple[list[str], list[str]]:
    """Return `(fit, held_out)` stems for one named split.

    Raises:
        ManifestError: If the split is not defined.
    """
    manifest = manifest if manifest is not None else load()
    splits = manifest.get("splits", {})
    if name not in splits:
        raise ManifestError(f"no split named {name!r}; defined splits are {sorted(splits)}")
    return list(splits[name].get("fit", [])), list(splits[name].get("held_out", []))


def published(manifest: dict | None = None) -> set[str]:
    """Return the stems the documentation site may show.

    Publication is opt-in: a fixture absent from the list is calibration-only,
    so the corpus can grow without the research pages growing with it.
    """
    manifest = manifest if manifest is not None else load()
    return set(manifest.get("published", {}).get("stems", []))


def validate(manifest: dict | None = None, images_dir: Path = IMAGES_DIR) -> None:
    """Check the manifest accounts for the corpus exactly.

    Every split must partition the corpus into fit, held out and excluded, with
    nothing missing, nothing invented and nothing counted twice. `published`
    must name fixtures that exist.

    Raises:
        ManifestError: With every problem found, not just the first -- a new
            scan usually breaks several splits at once, and fixing them one
            error per run is miserable.
    """
    manifest = manifest if manifest is not None else load()
    on_disk = corpus_stems(images_dir)
    excluded_stems = excluded(manifest)
    problems: list[str] = []

    unknown_excluded = excluded_stems - on_disk
    if unknown_excluded:
        problems.append(f"[excluded] names fixtures not in the corpus: {sorted(unknown_excluded)}")

    for name in split_names(manifest):
        fit, held_out = split(name, manifest)

        overlap = set(fit) & set(held_out)
        if overlap:
            problems.append(
                f"[splits.{name}] has fixtures in both fit and held_out: {sorted(overlap)}"
            )

        fit_excluded = (set(fit) | set(held_out)) & excluded_stems
        if fit_excluded:
            problems.append(f"[splits.{name}] uses excluded fixtures: {sorted(fit_excluded)}")

        covered = set(fit) | set(held_out) | excluded_stems
        missing = on_disk - covered
        if missing:
            problems.append(
                f"[splits.{name}] does not classify {sorted(missing)} -- "
                "add each to fit, held_out or [excluded]"
            )

        invented = covered - on_disk
        if invented:
            problems.append(f"[splits.{name}] names fixtures not in the corpus: {sorted(invented)}")

    unknown_published = published(manifest) - on_disk
    if unknown_published:
        problems.append(
            f"[published] names fixtures not in the corpus: {sorted(unknown_published)}"
        )

    if problems:
        raise ManifestError(
            f"{MANIFEST.name} does not match the corpus:\n  " + "\n  ".join(problems)
        )
