# Build your own pipeline

The `batch` subcommand is one arrangement of the package's parts. When your
material needs a different one (a different folder layout, a fallback order
of your own, transcripts written somewhere other than beside the source, or a
score kept rather than acted on), the same parts assemble from Python in a
few dozen lines. This tutorial builds that script. [Using the Python
API](../guide/python-api.md) describes each piece in more detail.

The script will:

1. pick the best backend this machine has, falling back down a list;
2. walk a folder, taking only the files that backend can read;
3. transcribe each one, page by page where a searchable PDF needs it;
4. score the transcript where the score means something;
5. write Markdown, plain text and a searchable PDF for each file;
6. keep a run log, and report what scored poorly at the end.

## The script

```python
#!/usr/bin/env python3
"""Transcribe every scan in SOURCE into DESTINATION, with a fallback across backends."""

from __future__ import annotations

import sys
from pathlib import Path

from tetrak_ocr import MissingBackendError, outputs, qa_score, telemetry
from tetrak_ocr.batch import transcribe_per_page
from tetrak_ocr.imaging import page_count
from tetrak_ocr.registry import get_backend, supported_extensions

# Best first. Vision ships with macOS and is the strongest local engine
# measured; EasyOCR is the fallback elsewhere; Tesseract is always present.
PREFERRED = ("vision", "easyocr", "tesseract-auto")
FORMATS = ("markdown", "text", "pdf")


def choose_backend():
    """The first preferred backend whose extra is installed here."""
    for name in PREFERRED:
        try:
            return name, get_backend(name)
        except MissingBackendError:
            continue
    raise SystemExit(f"none of {', '.join(PREFERRED)} is installed")


def transcribe(path: Path, ocr) -> tuple[str, list[str] | None]:
    """The transcript, and the per-page transcripts when there is more than one page."""
    if page_count(path) > 1:
        pages = transcribe_per_page(path, ocr)
        return "\n\n".join(t.strip() for t in pages if t.strip()), pages
    return ocr(path), None


def main(source: Path, destination: Path) -> int:
    name, ocr = choose_backend()
    readable = supported_extensions(name)
    files = sorted(p for p in source.iterdir() if p.suffix.lower() in readable)
    destination.mkdir(parents=True, exist_ok=True)

    telemetry.start_run(destination / "telemetry.jsonl", backend=name, files=len(files))
    print(f"{name}: {len(files)} file(s)")

    poor: list[str] = []
    for path in files:
        info = telemetry.describe_file(path)
        with telemetry.timed("file_finish", backend=name, **info):
            text, pages = transcribe(path, ocr)

            # The score reads English only, so apply it only where it can
            # say something, and record it rather than acting on it.
            if qa_score.is_available() and qa_score.scores_english_text(text):
                score = qa_score.combined_score(text)
                telemetry.record("scored", score=round(score, 4), **info)
                if score < qa_score.MIN_QUALITY_THRESHOLD:
                    poor.append(path.name)

            for fmt in FORMATS:
                outputs.write(fmt, path, text, destination, page_transcripts=pages)
        print(f"  {path.name}")

    telemetry.finish_run(files=len(files), poor=len(poor))
    if poor:
        print(f"\nscored below {qa_score.MIN_QUALITY_THRESHOLD}: {', '.join(poor)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), Path(sys.argv[2])))
```

```bash
python transcribe.py ~/archive/scans out/
```

## What each part is doing

**Choosing a backend.** `get_backend` raises `MissingBackendError` when the
extra is not installed, so a preference list is a loop with a `continue`.
The error's message is the `pip install` line, which is worth printing if
you decide to stop instead of falling back.

**Taking only readable files.** `supported_extensions(name)` is the
backend's own declaration. Filtering on it is what stops a PDF reaching
Vision, which cannot read one; the `batch` subcommand does the same, and
`--dry-run` is how it shows you the result.

**Page by page when it matters.** A searchable PDF needs one transcript per
page and a backend returns one per document, so `transcribe_per_page` splits
the document into single pages and transcribes each. It costs roughly twice a
whole-document pass, which is why the script only takes that route when
`page_count` says there is more than one page. It also means a multi-page
TIFF reaches Vision one frame at a time, where the whole file would have been
refused.

**Scoring without acting.** `combined_score` is the reference-free quality
score `auto-local` ranks with. Here it is kept in the run log and reported
at the end, so the decision about what to do with a poor transcript is left
to a person. `scores_english_text` guards it: on an Armenian page the score
would be 0.0 whatever the quality.

**Writing formats.** `outputs.write` names the file after the source's stem
and the format's extension, and writes `<stem>.searchable.pdf` when the
source is itself a PDF. `page_transcripts` is ignored by the text formats
and required by the PDF one for a multi-page document; passing it to all of
them is fine, because every writer tolerates options meant for another.

**The run log.** `start_run` opens the JSON Lines file and `finish_run`
closes it; between them, `timed` wraps each file with an event carrying the
elapsed seconds, success or not, and `record` adds anything else worth
keeping. `describe_file` gives every event the same file fields. With
`TETRAK_NO_TELEMETRY=1` in the environment every one of these is a no-op.

## Variations

- **Let `auto-local` choose, and catch its refusal.** Replace the preference
  list with `get_backend("auto-local")` and wrap the call in
  `except LowQualityError as exc`: `exc.scores` and `exc.transcripts` hold
  every engine's result, which is what the `batch` subcommand writes into a
  triage manifest.
- **Tune Tesseract.** `tetrak_ocr.batch.build_ocr_fn("tesseract-auto",
  contrast=3.0)` returns a one-argument callable with the options applied,
  so it drops into the script where `ocr` is.
- **Name the PDF's font.** For a script the built-in font cannot encode,
  pass `pdf_font="/path/to/font.ttf"` through `outputs.write`; without a
  font that can encode the transcript the PDF is refused with `PdfFontError`.
- **Re-use the pipeline's own file handling.** `tetrak_ocr.batch.process_file`
  does all of the above for one file, with the triage manifest and the move
  into `workspace/processed/`; it is the function the `batch` subcommand
  calls per file.
