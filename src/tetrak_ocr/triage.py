"""The triage queue: what was held, why, and a local page that lists it.

``batch`` diverts a file whose best transcript falls below the quality floor
into ``workspace/triage/``, with a Markdown manifest a person can read. That
manifest carried a 500-character excerpt of each candidate transcript and
the rest was discarded, so a decision about a page was often made on a
fragment, and a view of the queue could not show what had never been saved
(brief 001, the triage dashboard).

A held item is now three kinds of file, side by side::

    <stem>.md                 the manifest, exactly as before
    <stem>.json               the record: every candidate's score, the
                              reason the file was held, and where each
                              full transcript is
    <stem>.<backend>.txt      each candidate's transcript, whole

The record is what a view loads; the manifest stays for anyone who reads
the directory directly. Nothing here edits a transcript or moves a file:
triage is passive by design, and this module reads what ``batch`` wrote.

``tetrak-ocr triage`` prints the queue; ``tetrak-ocr triage --serve`` serves
it as a page. The server binds to the loopback address and nothing else,
takes no option to bind elsewhere, answers GET for one page and refuses
everything else. It reads a local directory for the person sitting at the
machine, so there is nothing to authenticate and nothing remote.
"""

from __future__ import annotations

import html
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import metadata
from pathlib import Path

# The loopback address, and only that. Not a setting: a flag to bind
# elsewhere would be the first step towards the remote, unauthenticated
# service the brief rules out.
HOST = "127.0.0.1"
DEFAULT_PORT = 8321

RECORD_SUFFIX = ".json"
MANIFEST_SUFFIX = ".md"
TRANSCRIPT_SUFFIX = ".txt"


@dataclass(frozen=True)
class Candidate:
    """One backend's attempt at a held file."""

    backend: str
    score: float | None
    transcript: str  # file name, relative to the triage directory


@dataclass(frozen=True)
class Item:
    """One held file, as the queue lists it."""

    stem: str
    file: str
    reason: str
    held_at: str
    backend: str | None
    best_engine: str | None
    best_score: float | None
    candidates: tuple[Candidate, ...]
    record: Path | None
    manifest: Path | None


def _version() -> str:
    try:
        return metadata.version("tetrak")
    except metadata.PackageNotFoundError:  # pragma: no cover - a checkout without install
        return "unknown"


def transcript_name(stem: str, backend: str) -> str:
    """Where a candidate's full transcript goes, beside the manifest."""
    return f"{stem}.{backend}{TRANSCRIPT_SUFFIX}"


def hold(
    triage_dir: Path,
    image: Path,
    scores: dict[str, float],
    transcripts: dict[str, str],
    reason: str,
    backend: str | None = None,
) -> list[Path]:
    """Write the record and every full transcript for a file being held.

    Called by ``batch`` beside the Markdown manifest it already writes; this
    adds the machine-readable half. *transcripts* are written whole, exactly
    as the backends returned them. Returns the paths written, the record
    first.
    """
    triage_dir.mkdir(parents=True, exist_ok=True)
    stem = image.stem
    written: list[Path] = []
    candidates = []
    for name, text in transcripts.items():
        path = triage_dir / transcript_name(stem, name)
        path.write_text(text, encoding="utf-8")
        written.append(path)
        candidates.append({"backend": name, "score": scores.get(name), "transcript": path.name})

    best = max(scores, key=lambda name: scores[name]) if scores else None
    record = {
        "file": image.name,
        "stem": stem,
        "reason": reason,
        "held_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "backend": backend,
        "best": None if best is None else {"engine": best, "score": scores[best]},
        "candidates": candidates,
        "tetrak_version": _version(),
    }
    record_path = triage_dir / f"{stem}{RECORD_SUFFIX}"
    record_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return [record_path, *written]


def _from_record(path: Path) -> Item:
    data = json.loads(path.read_text(encoding="utf-8"))
    best = data.get("best") or {}
    manifest = path.with_suffix(MANIFEST_SUFFIX)
    return Item(
        stem=data.get("stem", path.stem),
        file=data.get("file", path.stem),
        reason=data.get("reason", ""),
        held_at=data.get("held_at", ""),
        backend=data.get("backend"),
        best_engine=best.get("engine"),
        best_score=best.get("score"),
        candidates=tuple(
            Candidate(c.get("backend", "?"), c.get("score"), c.get("transcript", ""))
            for c in data.get("candidates", [])
        ),
        record=path,
        manifest=manifest if manifest.exists() else None,
    )


def _from_manifest_only(path: Path) -> Item:
    """A file held by a release that wrote the manifest and nothing else."""
    stem = path.stem
    held = next((p.name for p in path.parent.iterdir() if p.stem == stem and p != path), stem)
    return Item(
        stem=stem,
        file=held,
        reason=f"held before records were written; see {path.name}",
        held_at="",
        backend=None,
        best_engine=None,
        best_score=None,
        candidates=(),
        record=None,
        manifest=path,
    )


def queue(triage_dir: Path) -> list[Item]:
    """Every held item in *triage_dir*, by name.

    An item is a record, or -- for a directory written by an older release
    -- a manifest with no record beside it, listed so nothing already in
    the queue disappears from the view. A missing directory is an empty
    queue, not an error.
    """
    if not triage_dir.is_dir():
        return []
    records = {p.stem: p for p in triage_dir.glob(f"*{RECORD_SUFFIX}")}
    items = [_from_record(path) for path in records.values()]
    items += [
        _from_manifest_only(path)
        for path in triage_dir.glob(f"*{MANIFEST_SUFFIX}")
        if path.stem not in records
    ]
    return sorted(items, key=lambda item: item.stem)


def _score(item: Item) -> str:
    return "–" if item.best_score is None else f"{item.best_score:.4f}"


def describe(items: list[Item], triage_dir: Path) -> str:
    """The queue as a table for the terminal."""
    if not items:
        return f"The triage queue is empty ({triage_dir})."
    width = max(len(item.file) for item in items)
    lines = [
        f"{len(items)} item(s) in {triage_dir}",
        "",
        f"{'File':<{width}}  {'Best':>7}  {'Engine':<14}  Reason held",
        f"{'-' * width}  {'-' * 7}  {'-' * 14}  {'-' * 11}",
    ]
    for item in items:
        lines.append(
            f"{item.file:<{width}}  {_score(item):>7}  {(item.best_engine or '–'):<14}  {item.reason}"
        )
    return "\n".join(lines)


_STYLE = """
body { font: 16px/1.5 system-ui, sans-serif; margin: 2rem auto; max-width: 64rem; padding: 0 1rem; color: #1a1a1a; background: #fff; }
h1 { font-size: 1.5rem; margin: 0 0 0.25rem; }
p.meta { color: #555; margin: 0 0 1.5rem; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; vertical-align: top; padding: 0.5rem 0.75rem; border-bottom: 1px solid #ddd; }
th { font-weight: 600; }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
code { font-size: 0.95em; }
"""


def render(items: list[Item], triage_dir: Path) -> str:
    """The queue as one HTML page: every item, its best score and why it was held."""
    esc = html.escape
    head = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Triage queue · Tetrak OCR</title>\n"
        f"<style>{_STYLE}</style>\n</head>\n<body>\n<h1>Triage queue</h1>\n"
    )
    if not items:
        return (
            head
            + f'<p class="meta"><code>{esc(str(triage_dir))}</code></p>\n'
            + "<p>The triage queue is empty.</p>\n</body>\n</html>\n"
        )
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td><code>{esc(item.file)}</code></td>"
            f'<td class="num">{esc(_score(item))}</td>'
            f"<td>{esc(item.best_engine or '–')}</td>"
            f"<td>{esc(item.reason)}</td>"
            f"<td>{esc(item.held_at or '–')}</td>"
            f'<td class="num">{len(item.candidates)}</td>'
            "</tr>"
        )
    return (
        head + f'<p class="meta">{len(items)} item(s) in <code>{esc(str(triage_dir))}</code></p>\n'
        "<table>\n<thead><tr><th>File</th><th>Best score</th><th>Engine</th>"
        "<th>Reason held</th><th>Held at</th><th>Candidates</th></tr></thead>\n"
        "<tbody>\n" + "\n".join(rows) + "\n</tbody>\n</table>\n</body>\n</html>\n"
    )


class _Handler(BaseHTTPRequestHandler):
    """GET / and nothing else. The queue is re-read on every request, so the
    page follows the directory while a batch is still running."""

    triage_dir: Path  # set on the subclass make_server builds

    def do_GET(self) -> None:  # noqa: N802 - http.server's naming
        if self.path.split("?", 1)[0] != "/":
            self.send_error(404, "Only / is served")
            return
        body = render(queue(self.triage_dir), self.triage_dir).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - http.server's signature
        print(f"    {self.address_string()} {format % args}", file=sys.stderr)


def make_server(triage_dir: Path, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """A server for the queue page, bound to the loopback address.

    Port 0 asks the OS for a free one, which is what the tests use; the
    address it actually bound is ``server.server_address``.
    """
    handler = type("TriageHandler", (_Handler,), {"triage_dir": Path(triage_dir)})
    return ThreadingHTTPServer((HOST, port), handler)


def serve(triage_dir: Path, port: int = DEFAULT_PORT) -> int:
    """Serve the queue page until interrupted."""
    with make_server(triage_dir, port) as server:
        host, bound = server.server_address[:2]
        print(f"Serving the triage queue at http://{host}:{bound}/  (Ctrl-C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0
