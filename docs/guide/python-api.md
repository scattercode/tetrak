# Using the Python API

Everything the command line does is a call into `tetrak_ocr`, and the package
is built to be used as a library: a missing optional dependency raises an
exception naming the extra to install rather than exiting the process, the
run log is a no-op until you start one, and every backend has the same shape.
This page covers the surface a caller reaches for. The [API
reference](../api.md) is generated from the docstrings and has the rest.

## Resolve a backend

Every backend exposes the same callable, `ocr_image(path) -> str`. Resolve
one by name through the registry rather than importing it directly, so that
a missing extra becomes an actionable error instead of a `NameError` from
deep inside the call:

```python
from pathlib import Path
from tetrak_ocr.registry import get_backend

ocr = get_backend("tesseract-auto")
text = ocr(Path("scan.jpg"))
```

The registry also answers what this machine can run:

```python
from tetrak_ocr.registry import BACKENDS, available, is_available, supported_extensions

BACKENDS  # every name the package knows, in order
available()  # the ones whose dependencies are installed here
is_available("vision")  # one of them
supported_extensions("easyocr")  # {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
```

`available()` is what `tetrak-ocr backends` prints, and the check is "can
this actually run": `auto-local` is absent without the `qa` extra.

## Errors

Every exception the package raises is a subclass of
`tetrak_ocr.OcrPipelineError`, so one `except` catches the lot:

| Exception | Raised when |
|---|---|
| `UnknownBackendError` | The name does not exist. Carries `.known`, the valid names |
| `MissingBackendError` | The backend exists but its extra is not installed. Carries `.extra`, and its message is the `pip install` line |
| `UnknownFormatError` | An output format name does not exist. Carries `.valid` |
| `MultiPageNotSupportedError` | A multi-frame TIFF was given to a backend that reads only frame 0. Carries `.pages` and `.use_instead`, a backend that will read it |
| `MultiPagePdfError` | A searchable PDF was asked for on a multi-page document without per-page transcripts |

Which makes falling back across backends straightforward:

```python
from tetrak_ocr import MissingBackendError
from tetrak_ocr.registry import get_backend

for name in ("vision", "easyocr", "tesseract-auto"):
    try:
        ocr = get_backend(name)
    except MissingBackendError:
        continue
    break
```

The backends themselves raise `FileNotFoundError` for a missing file and
`ValueError` for an extension they do not support.

## Backend options

The `ocr_image(path) -> str` contract is fixed; some backends take optional
keyword arguments on top of it.

**Tesseract** (`tesseract` and `tesseract-auto`) takes `contrast`, `psm`,
`auto` and `lang`. A value left as `None` with `auto=True` is filled from the
image's own statistics; a value you give wins. `lang` is a Tesseract language
code such as `"hye"` or `"hye+eng"`, which the command line does not expose:

```python
ocr = get_backend("tesseract")
ocr(Path("faded.jpg"), contrast=3.0, psm=6)
ocr(Path("faded.jpg"), auto=True)  # the same as tesseract-auto
ocr(Path("armenian.png"), auto=True, lang="hye")  # needs Tesseract's hye data installed
```

**Vision** takes `languages`, a list of codes such as `["en-GB"]`, and
`recognition_level`, `"accurate"` (the default) or `"fast"`. Naming a
language is usually worth it on archival material, because auto-detection
on a page with little text can pick wrongly and the failure is silent.
`tetrak_ocr.backends.vision.supported_languages()` lists what this Mac's
Vision build can recognise; Apple publishes no list.

**auto-local** takes `with_paddle_vl=True` to admit PaddleOCR-VL to the pool.

`tetrak_ocr.batch.build_ocr_fn` is the command line's way of applying the
Tesseract and auto-local options to any backend name: it returns a
one-argument callable, and prints a note when an option is ignored by the
backend you named.

```python
from tetrak_ocr.batch import build_ocr_fn

ocr = build_ocr_fn("tesseract-auto", contrast=3.0)  # auto PSM, your contrast
ocr = build_ocr_fn("auto-local", with_paddle_vl=True)
```

## Fan-out and the quality gate

`auto-local` runs every eligible local engine on a file, scores each
transcript, and returns the best. When even the best falls below the quality
floor it raises `LowQualityError`, which carries the whole score table:

```python
from tetrak_ocr.qa_score import LowQualityError
from tetrak_ocr.registry import get_backend

ocr = get_backend("auto-local")
try:
    text = ocr(path)
except LowQualityError as exc:
    for backend, score in exc.scores.items():
        print(backend, round(score, 4), exc.transcripts[backend][:80])
```

`exc.scores` and `exc.transcripts` are dicts keyed by backend name, for every
backend that ran. That is what the batch pipeline writes into a triage
manifest.

The scoring is available on its own, for applying the same gate to any
transcript. It needs the `qa` extra, and it reads English only:

```python
from tetrak_ocr import qa_score

qa_score.is_available()  # True when the qa extra is installed
qa_score.scores_english_text(text)  # False for a transcript in another script
qa_score.combined_score(text)  # dictionary coverage x inverse log-perplexity
qa_score.MIN_QUALITY_THRESHOLD  # 0.10, the floor the pipeline applies
```

`combined_score` returns 0.0 for empty or letterless text, which is correct:
such output *is* poor. It also returns roughly 0.0 for a perfectly good
Armenian transcript, which is not, so check `scores_english_text` before
gating material that may not be English. `dictionary_coverage` and
`perplexity_score` are exposed separately.

## Writing outputs

`tetrak_ocr.outputs` is the format table the command line's `--format` reads
from. `write` takes a format name, the source file, the transcript and a
destination directory, and returns the path it wrote; the filename is the
source's stem plus the format's extension:

```python
from tetrak_ocr import outputs

for name in outputs.parse(["markdown,pdf"]):  # ['markdown', 'pdf']
    written = outputs.write(name, source, text, Path("out"))
```

`outputs.FORMATS` lists the canonical names, `outputs.parse` resolves aliases
and both the repeated and comma-separated spellings, and
`outputs.extension(name)` gives the suffix. A PDF transcribed to the `pdf`
format is written as `<stem>.searchable.pdf`, so it cannot overwrite its own
source.

The PDF writer takes three options through `write(..., **options)`:
`page_transcripts`, a list with one string per page, required for a
multi-page document; `pdf_full_size=True` to embed the source image untouched
rather than a downsampled access copy; and `pdf_font`, a path to a TrueType
font for scripts the built-in font cannot encode. Without a font that can
encode the transcript it raises `tetrak_ocr.pdf_output.PdfFontError` rather
than writing black boxes.

`tetrak_ocr.pdf_output.searchable_pdf_for(path, transcript, destination,
page_transcripts=..., full_size=..., font_path=...)` is the same writer
with an explicit destination, for when the file should not be named after
its source.

## Multi-page documents

`tetrak_ocr.imaging` is where pages are counted and split, for PDFs and for
multi-frame TIFFs alike:

```python
from tetrak_ocr.imaging import page_count, page_documents, iter_pages

page_count(path)  # without rendering anything

with page_documents(path) as pages:  # one single-page file per page, in a temp dir
    transcripts = [ocr(page) for page in pages]

for image in iter_pages(path):  # each page as a Pillow image
    ...
```

`page_documents` is a context manager; the files it yields are deleted on
exit. Splitting a PDF into single-page PDFs, rather than rasterising it,
keeps the text layer that Marker reads instead of OCR-ing. A single-page
document yields itself unchanged.

`tetrak_ocr.batch.transcribe_per_page(path, ocr_fn)` does exactly the loop
above, with a `page_finish` event in the run log per page. It is what the
pipeline uses to build a multi-page searchable PDF:

```python
from tetrak_ocr.batch import transcribe_per_page

pages = transcribe_per_page(path, ocr)
text = "\n\n".join(t.strip() for t in pages if t.strip())
outputs.write("pdf", path, text, Path("out"), page_transcripts=pages)
```

## The batch pipeline from code

`tetrak_ocr.batch` is the `batch` subcommand. Its three directories are
module-level `Path`s relative to the current working directory
(`SCANS_DIR`, `PROCESSED_DIR`, `TRIAGE_DIR` under `WORKSPACE_DIR`), and the
tests drive a temporary directory by reassigning them.

`process_file` does everything the pipeline does for one file: OCR, the
quality gate, every requested format, the move into `workspace/processed/`,
the triage manifest if it came to that, and the run-log events.

```python
from tetrak_ocr import batch

ocr = batch.build_ocr_fn("auto-local")
triaged: list[str] = []
for path in sorted(batch.SCANS_DIR.iterdir()):
    batch.process_file(
        path,
        ocr,
        triaged=triaged,
        backend="auto-local",
        formats=["markdown", "pdf"],
    )
```

`quality_gate=True` applies the floor to a single backend's transcript, the
way `--quality-gate` does. To run the whole subcommand with its own argument
parsing, `batch.main(args=["--backend", "auto-local", "--pdf"])` returns the
exit code.

## The run log

`tetrak_ocr.telemetry` is the JSON Lines log that `batch` writes. It is
process-global and a no-op until a run is started, which is what keeps the
library usable as a library:

```python
from tetrak_ocr import telemetry

log = telemetry.start_run(backend="vision", files=12)  # or start_run(path)
with telemetry.timed("backend_finish", backend="vision", **telemetry.describe_file(path)):
    text = ocr(path)
telemetry.record("file_finish", outcome="processed", **telemetry.describe_file(path))
telemetry.finish_run(processed=12)
```

`start_run` returns `None`, and every call stays a no-op, when
`TETRAK_NO_TELEMETRY` is set. `describe_file` gives the file's path, size,
type and page count so every event describes a file the same way. `timed`
emits its event with the elapsed seconds whether or not the block raised. A
logging failure never raises into your code: the log disables itself and
warns once.

## Measuring against ground truth

`tetrak_ocr.accuracy` is what the evaluation harness scores with, and it is
usable on your own material once you have a reference transcript:

```python
from tetrak_ocr.accuracy import character_similarity, word_recall

character_similarity(actual, expected)  # 0.0 to 1.0, difflib ratio after normalisation
word_recall(actual, expected)  # fraction of expected words present in actual
```

Both normalise first: lowercase, collapsed whitespace, and Armenian
punctuation folded onto its ASCII look-alikes, so trivial formatting
differences do not move the score. `normalise` is exposed for applying the
same treatment elsewhere.

## The installed version

```python
import tetrak_ocr

tetrak_ocr.__version__
```

Written from the git tag at build time; it reads `0+unknown` from an
unbuilt checkout.
