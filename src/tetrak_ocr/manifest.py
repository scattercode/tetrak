"""The batch's CSV manifest: one row per file, for a spreadsheet or an import.

Not the triage manifest, the per-file report `batch` writes beside a
triaged scan; this is one table for the whole workspace.

**Beta.** The columns may change before this is declared stable; the header
row is what to rely on, never a column's position.

Where the telemetry log is for watching a run and measuring it, the manifest
is for the people who receive its output. A small archive keeps its
catalogue in a spreadsheet; a collections system imports a CSV (Omeka S's CSV
Import, among others). Either way the question is the same: for each scan,
what was read, by which engine, did it pass the quality gate, and where are
the files now. A triaged or failed file gets a row too, so the manifest is
also the list of what still needs a person.

The file is appended to, one row per file as it finishes, so it grows with
the workspace across runs, as `workspace/processed/` does. The header is
written when the file is new. A file whose header is not this version's is
refused before any scan is touched, rather than given rows that do not line
up with its columns.

UTF-8 without a byte-order mark, which is what import tools expect. Excel
reads a UTF-8 file without a BOM as the local code page when it is
double-clicked; import it through *Data > From Text/CSV* instead to keep
non-Latin transcripts intact.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

COLUMNS = (
    "file",
    "status",
    "backend",
    "engine",
    "quality",
    "quality_gate",
    "transcript",
    "outputs",
    "location",
    "note",
    "run",
    "finished_at",
    "tetrak_version",
)
"""The manifest's columns, in order.

- ``file``: the scan's file name, as it was in ``scans/``.
- ``status``: ``processed``, ``triage`` or ``error``.
- ``backend``: the backend the run asked for.
- ``engine``: the engine whose transcript was kept or rejected. The same as
  ``backend``, except under ``auto-local``, where it is the one that won.
- ``quality``: the transcript's quality score, from 0 to 1, when it was
  scored; empty when it was not.
- ``quality_gate``: ``passed``, ``failed``, ``skipped`` (a transcript not in
  the Latin script, which the English-only score cannot judge) or ``off``.
- ``transcript``: the full transcript of a processed file. Empty for a file
  sent to triage, so that importing the manifest never imports a reading the
  gate rejected; the triage report beside the scan has the excerpts.
- ``outputs``: the files written for it, relative to the workspace and
  separated by ``;``.
- ``location``: where the scan is now, relative to the workspace.
- ``note``: why a file went to triage, or what went wrong; for a processed
  file read with ``--orient``, what was done to turn it upright.
- ``run``: the telemetry run id, to find the run's events in the log; empty
  when telemetry is off.
- ``finished_at``: when the file finished, in UTC, ISO 8601.
- ``tetrak_version``: the Tetrak release that read it.
"""

DEFAULT_NAME = "manifest.csv"


class ManifestError(Exception):
    """The manifest cannot be appended to as it stands."""


def _version() -> str:
    try:
        return metadata.version("tetrak")
    except metadata.PackageNotFoundError:  # pragma: no cover - a bare checkout
        return "unknown"


class Manifest:
    """Appends rows to a manifest CSV, writing its header when it is new."""

    def __init__(self, path: Path, run: str | None = None):
        self.path = Path(path)
        self.run = run or ""
        self.version = _version()

    def check(self) -> None:
        """Refuse a file that already has a different header.

        Called before the batch starts, so a mismatch is found before any
        scan is moved.
        """
        if not self.path.exists() or self.path.stat().st_size == 0:
            return
        with self.path.open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle), [])
        if tuple(header) != COLUMNS:
            raise ManifestError(
                f"{self.path} has different columns from this version of Tetrak's "
                "manifest. Move it aside or name another file with --manifest PATH."
            )

    def write(self, **fields: object) -> None:
        """Append one row. Unknown fields are a programming error."""
        unknown = set(fields) - set(COLUMNS)
        if unknown:
            raise ValueError(f"not manifest columns: {', '.join(sorted(unknown))}")
        row = {
            "run": self.run,
            "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "tetrak_version": self.version,
            **fields,
        }
        quality = row.get("quality")
        if isinstance(quality, float):
            row["quality"] = f"{quality:.4f}"
        outputs = row.get("outputs")
        if isinstance(outputs, (list, tuple)):
            row["outputs"] = ";".join(str(p) for p in outputs)

        new = not self.path.exists() or self.path.stat().st_size == 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS, restval="")
            if new:
                writer.writeheader()
            writer.writerow(row)
