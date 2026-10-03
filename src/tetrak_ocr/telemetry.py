"""Append-only run log: what was processed, by which backend, and how long it took.

A long batch is otherwise silent about its own cost. `auto-local` prints its
score table only once every backend has finished, so a file that takes forty
minutes looks identical to one that has hung -- and when it does finish, the
table says which backend won but not which one spent the time.

This module records that as it happens. Every event is one JSON object on one
line, flushed immediately, so `tail -f` on the log is a live progress view and
the finished file is a dataset:

    {"ts": "...", "run": "20260822T115103Z-7f3a", "event": "backend_finish",
     "file": "camera-1919.pdf", "backend": "marker", "seconds": 2246.8, ...}

JSON Lines rather than CSV because the fields differ per event and will grow;
rather than a database because appending a line is atomic enough for a
sequential pipeline and needs nothing installed to read it back.

The sink is process-global. That is deliberate: backends expose a fixed
``ocr_image(path) -> str`` signature with nowhere to thread a logger through,
and the fan-out is documented as sequential, so there is no concurrent writer
to coordinate. When no run has been started every call is a cheap no-op, which
is what keeps the library usable as a library.
"""

from __future__ import annotations

import json
import os
import resource
import secrets
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

# Where the log lands when nobody says otherwise: beside the directories whose
# work it describes, so a workspace carries its own history.
DEFAULT_LOG_PATH = Path("workspace") / "telemetry.jsonl"

# Set to any value to turn telemetry off for a run without touching flags --
# the escape hatch for a read-only or otherwise awkward filesystem.
DISABLE_ENV_VAR = "TETRAK_NO_TELEMETRY"

_log: TelemetryLog | None = None


# ru_maxrss is bytes on macOS and kibibytes on Linux. Getting this wrong is a
# factor of 1024, which would read as either a rounding error or an implausible
# number depending on which way it fell -- neither obviously wrong in a log.
_RSS_TO_BYTES = 1 if sys.platform == "darwin" else 1024

try:  # psutil arrives with the heavy backends but is not a declared dependency
    import psutil

    _process = psutil.Process()
except Exception:  # noqa: BLE001 - absent, or refusing to introspect
    _process = None


def _memory() -> dict:
    """Current and peak resident memory, in MB.

    Recorded on every event so the log plots as a memory profile of the run
    rather than a summary at the end. Both reads are measured in microseconds
    (0.4us for the peak, 2.2us via psutil), so this costs nothing next to OCR.

    ``peak_rss_mb`` is a high-water mark and never falls -- it answers "how
    close did this run come to the ceiling". ``rss_mb`` is what is resident
    now, and is the one to plot over time; it needs psutil, which ships with
    the heavy backends but is not guaranteed, so it is omitted rather than
    faked when absent.
    """
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * _RSS_TO_BYTES
    info = {"peak_rss_mb": round(peak / 1048576, 1)}
    if _process is not None:
        try:
            info["rss_mb"] = round(_process.memory_info().rss / 1048576, 1)
        except Exception:  # noqa: BLE001 - a dead or unreadable process
            pass
    return info


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class TelemetryLog:
    """One run's worth of events, appended to a JSON Lines file."""

    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self._failed = False

    def emit(self, event: str, **fields) -> None:
        """Append one event. Never raises: telemetry must not fail a run.

        A batch that has spent half an hour on OCR should not lose the result
        because the log directory went away, so the first write failure
        disables the log for the rest of the run and says so once.
        """
        if self._failed:
            return
        record = {"ts": _now(), "run": self.run_id, "event": event}
        record.update(_memory())
        record.update({k: v for k, v in fields.items() if v is not None})
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
                # Flushed per line so `tail -f` is live during a long run,
                # which is most of the point of writing this at all.
                fh.flush()
        except OSError as exc:
            self._failed = True
            print(f"warning: telemetry disabled ({exc})", file=sys.stderr)


def start_run(path: Path | str | None = None, **fields) -> TelemetryLog | None:
    """Begin recording, returning the log (or None when disabled)."""
    if os.environ.get(DISABLE_ENV_VAR):
        return None
    global _log
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(2)}"
    _log = TelemetryLog(Path(path) if path else DEFAULT_LOG_PATH, run_id)
    _log.emit("run_start", **fields)
    return _log


def finish_run(**fields) -> None:
    """Close out the current run and detach the sink."""
    global _log
    if _log is not None:
        _log.emit("run_finish", **fields)
    _log = None


def record(event: str, **fields) -> None:
    """Emit an event if a run is active, otherwise do nothing."""
    if _log is not None:
        _log.emit(event, **fields)


def active() -> bool:
    return _log is not None


def log_path() -> Path | None:
    return _log.path if _log is not None else None


def describe_file(path: Path) -> dict:
    """The file facts worth having on every record about it.

    Page count matters more than byte size here and is the thing people are
    surprised by: a 3 MB PDF that is ten pages is ten documents of work, and
    reading a per-file duration without it invites the wrong conclusion. It is
    read cheaply and never allowed to fail -- a page count is not worth an
    exception in the middle of a batch.
    """
    info: dict = {"file": path.name, "path": str(path), "suffix": path.suffix.lower()}
    try:
        info["bytes"] = path.stat().st_size
    except OSError:
        pass
    try:
        from .imaging import page_count

        info["pages"] = page_count(path)
    except Exception:
        pass
    return info


@contextmanager
def timed(event: str, **fields):
    """Time a block and emit *event* with its duration, success or not.

    Emits on the failure path too, because a backend that raised after twenty
    minutes is exactly the thing worth having in the log.
    """
    started = time.perf_counter()
    try:
        yield
    except BaseException as exc:
        record(
            event,
            seconds=round(time.perf_counter() - started, 3),
            ok=False,
            error=type(exc).__name__,
            **fields,
        )
        raise
    else:
        record(event, seconds=round(time.perf_counter() - started, 3), ok=True, **fields)
