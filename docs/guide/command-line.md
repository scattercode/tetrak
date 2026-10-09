# Using the command line

Installing the package provides one command, `tetrak-ocr`, with four
subcommands:

| Subcommand | What it does |
|---|---|
| `backends` | List every backend and whether this environment can run it |
| `ocr` | Transcribe a single file, to stdout or to files beside it |
| `batch` | Transcribe everything in `workspace/scans/` |
| `evaluate` | Benchmark backends against the evaluation corpus (needs a checkout) |

`tetrak-ocr --help` and `tetrak-ocr <subcommand> --help` list every flag; the
[command line reference](../cli.md) has the same text. This page is about
what the flags are for.

Errors the package raises itself are printed as one line beginning
`error:` with the thing to do about it, such as which extra to install,
and the command exits 1. Unrecognised arguments exit 2.

## `tetrak-ocr backends`

```console
$ tetrak-ocr backends
 ✓ tesseract
 ✓ tesseract-auto
 · claude  (extra not installed)
 ✓ auto-local
```

`✓` means installed and usable; `·` means the optional extra is missing.
The check is "can this actually run", not "is the package present":
`auto-local` reports as missing without the `qa` extra, and `paddle-vl`
reports as missing when `paddleocr` is installed but the pipeline it builds
cannot be constructed.

## `tetrak-ocr ocr`

Transcribe one file. The default is stdout; `--output` writes a file instead.

```bash
tetrak-ocr ocr scan.jpg
tetrak-ocr ocr scan.jpg --backend tesseract-auto
tetrak-ocr ocr programme.pdf --backend marker --output programme.md
tetrak-ocr ocr faded.jpg --contrast 3.5 --psm 6
```

`--backend` defaults to `tesseract`. [Choosing a backend](backends.md) is
about which to name; the short answer is `tesseract-auto` over `tesseract`
whenever you are naming a Tesseract backend by hand, and `auto-local` when
you would rather not choose.

`--format` and the `--pdf` flags, described under [output formats](#output-formats)
below, write files beside the source under its stem and leave stdout alone.
`--pdf` here takes an optional path, so a single file can be named rather than
placed:

```bash
tetrak-ocr ocr scan.jpg --pdf                       # scan.pdf beside it
tetrak-ocr ocr scan.jpg --pdf catalogue-ready.pdf   # or name it
```

## `tetrak-ocr batch`

The pipeline's normal mode. It uses three directories under `workspace/`,
resolved against your **current working directory**, so run it from the
folder holding your scans:

```text
workspace/
  scans/       input: put files here
  processed/   output: transcript plus the original, side by side
  triage/      quarantine: files whose transcript was too poor to trust
```

```bash
tetrak-ocr batch --backend auto-local
```

For each supported file in `workspace/scans/`, the pipeline runs OCR, writes
`workspace/processed/<name>.md`, and moves the original to
`workspace/processed/<name>.<ext>`. Keeping the transcript beside its source
means a transcript is never orphaned from the image it came from, and
`workspace/scans/` being empty afterwards means "what is still to do?" is a
question with an answer.

Only extensions the chosen backend supports are picked up. EasyOCR,
PaddleOCR and Vision skip PDFs, because they cannot read them; a
[dry run](#dry-runs) shows what would be skipped.

The exit code is 0 when every file was processed or triaged, and 1 if any
file raised an error or `workspace/scans/` does not exist. Errors on one file
do not stop the batch: the file is reported and the run carries on.

### The triage queue

`auto-local` refuses to return a transcript whose quality score falls below
the floor (0.10, `MIN_QUALITY_THRESHOLD`). When that happens the batch
pipeline diverts the file to `workspace/triage/` along with a manifest,
`workspace/triage/<stem>.md`, recording which backends were tried, their
scores, and the first 500 characters of each transcript, so you can decide
whether to rescan, send it to Claude, or transcribe by hand.

`--quality-gate` applies the same threshold to any single named backend:

```bash
tetrak-ocr batch --backend tesseract-auto --quality-gate
```

It is opt-in for single backends because it changes which files reach
`workspace/processed/`. It needs the `qa` extra, which is checked before the
first file rather than discovered halfway through a run.

The scoring reads English, and only English: it counts recognised English
words and measures GPT-2 perplexity. A transcript in another script would
score 0.0 however well it was read, so the gate is **skipped, with a message,
for transcripts that are not in the Latin script** rather than sending a
whole Armenian run to triage.

### The run log

Every batch appends to `workspace/telemetry.jsonl`, one JSON object per
line, flushed per line, so `tail -f` is a live progress view:

```bash
tail -f workspace/telemetry.jsonl
```

`auto-local` prints its score table only after every backend has finished, so
without this a forty-minute file is indistinguishable from a hung one. The
log carries `run_start`, `file_start`, one `backend_finish` per engine in the
fan-out, `page_finish` when a document is transcribed page by page,
`file_finish` and `run_finish`, each with the file's path, size, type and
page count, and each backend's elapsed seconds.

```json
{"event": "backend_finish", "file": "camera-1919.pdf", "backend": "marker",
 "seconds": 2246.8, "score": 0.31, "pages": 10, "bytes": 3475030}
```

Because it accumulates, the log is also the dataset for asking which engines
are worth their time on your material:

```bash
# median seconds per backend, slowest first
jq -rs 'map(select(.event=="backend_finish"))
        | group_by(.backend)[]
        | [.[0].backend, (length), (map(.seconds) | add / length | floor)]
        | @tsv' workspace/telemetry.jsonl | sort -k3 -rn
```

| Flag | Effect |
|---|---|
| `--telemetry PATH` | Write the log somewhere other than the default |
| `--no-telemetry` | Do not write it |
| `TETRAK_NO_TELEMETRY=1` | The same, as an environment variable |

A logging failure never fails a run: the log disables itself, warns once,
and the batch carries on.

### Dry runs

```bash
tetrak-ocr batch --backend tesseract --dry-run
```

Lists what would be processed without touching anything, and, just as
useful, what would be **skipped** because the chosen backend cannot read it.
The pipeline filters `workspace/scans/` by the backend's supported
extensions, so a PDF simply vanishes under `easyocr` or `paddle`; a dry run
is where that becomes visible.

No OCR runs and nothing is moved, but the chosen backend's package does have
to be installed: the file list depends on which extensions that backend
declares it can read.

### Tuning Tesseract

```bash
tetrak-ocr batch --backend tesseract --contrast 3.0 --psm 6
tetrak-ocr batch --backend tesseract --auto
```

`--contrast` (default 2.0; try 3.0 for faded originals) and `--psm` (default
3; 3 is automatic layout, 6 a single uniform block, 11 sparse text) apply to
the Tesseract backends only. Passing them with another backend prints a note
rather than silently ignoring them. `--auto` picks both per image from the
image's own statistics and is usually better than either default; naming
`tesseract-auto` is the same thing. A value you give explicitly wins over the
automatic one.

### Adding PaddleOCR-VL to the pool

```bash
tetrak-ocr batch --backend auto-local --with-paddle-vl
```

PaddleOCR-VL measures as the strongest local backend and wins where the rest
of the pool is weakest, on dense multi-column pages, but it costs minutes per
page rather than seconds, and fan-out would pay that on every file. So it is
opt-in. The flag needs the `paddle-vl` extra and only means anything to
`auto-local`; to run the engine on its own, name it with `--backend paddle-vl`.

## Output formats

One OCR pass can be written several ways. `--format` (or `-f`) names the set;
it is repeatable and comma-separated, and `md`, `txt`, `plain` and
`plaintext` are accepted as aliases.

| Format | Writes | For |
|---|---|---|
| `markdown` | `<name>.md` | The default: the transcript under a heading |
| `text` | `<name>.txt` | Bare transcript, for anything that will parse it |
| `pdf` | `<name>.pdf` | Invisible text layer over the scan, for catalogue indexing |

```bash
tetrak-ocr batch --backend auto-local --format markdown,pdf
tetrak-ocr batch --backend auto-local -f markdown -f pdf   # identical
tetrak-ocr batch --backend auto-local --format text        # .txt only
```

`--format` is a **full specification**: naming `pdf` alone writes a PDF and
no Markdown. The OCR runs once regardless of how many formats are asked for,
so the second and third cost a file write rather than another pass.

`--pdf` predates it and stays additive, so existing commands keep working: on
`batch` it means `--format markdown,pdf`, and combined with `--format` it adds
`pdf` to whatever was named. On `ocr`, which writes nothing unless asked,
`--pdf` writes the PDF and nothing else.

### Searchable PDFs

The `pdf` format writes the scan with the transcript embedded as an
invisible text layer. That single file is what makes a transcript indexable
in Preservica Starter, CONTENTdm, Omeka and AtoM without asking a vendor for
anything, and it is the accessibility output too: the layer an indexer reads
is the layer a screen reader reads.

The PDF is an **access copy**: images past 2400px on the long edge are
downsampled and JPEG-encoded, which takes a 1.1 MB postcard scan to a PDF an
institution can actually serve. `--pdf-full-size` embeds the source
untouched instead, for when the PDF is the deliverable rather than a
derivative. Both flags imply `--pdf`.

The text layer carries whichever backend's transcript the run produced, so
it matches the `.md` sidecar exactly. Read it back with `pdftotext -raw`;
plain `pdftotext` reflows and de-hyphenates, so the two will not look
identical through it.

The text is laid over the page rather than positioned word by word, so
selecting text in a viewer will not align with the words on the scan. That
is deliberate: a word-positioned layer measured markedly worse on reading
order, the thing a screen reader announces, on multi-column material.

```{warning}
**Scripts the font cannot encode.** The built-in font covers Western
European text; a system Unicode font is used automatically where one is
needed and present. Where neither can encode the transcript the PDF is
refused, because the alternative is a page of black boxes that extracts as
nothing. Point `--pdf-font` at a TrueType font that covers the script.
```

### Multi-page documents

A searchable PDF needs one transcript per **page**; a backend returns one per
**document**. So the `pdf` format on a multi-page PDF or TIFF transcribes it
page by page, splitting the document into single pages, which keeps the text
layer that Marker reads instead of OCR-ing, then laying each page's words
onto the page they came from.

That costs **roughly twice the OCR time**, and it is inherent per-document
work in the engine rather than overhead that can be removed. It is paid only
when both conditions hold: the `pdf` format was requested, *and* the document
has more than one page.

```bash
tetrak-ocr batch --backend auto-local --pdf   # multi-page: ~2x, gets a PDF
tetrak-ocr batch --backend auto-local         # multi-page: normal speed, no PDF
```

The `.md` and `.txt` come from the same pass with the pages joined, so no
document is ever transcribed twice. When the per-page route is taken the run
says so, and the log records each page as it lands:

```text
Processing: king-of-kings-souvenir-1927.pdf
  21 pages, transcribing individually for the PDF
```

**Naming.** A PDF transcribed to a searchable PDF is written as
`<stem>.searchable.pdf`. It would otherwise collide with the original, which
the batch pipeline moves into the same directory, and one would silently
overwrite the other. Non-PDF sources keep the plain `<stem>.pdf`.

## `tetrak-ocr evaluate`

Benchmark backends against the evaluation corpus: every fixture is
transcribed and scored against its committed ground truth on character
similarity and word recall.

```bash
tetrak-ocr evaluate --backend tesseract-auto
tetrak-ocr evaluate --all
tetrak-ocr evaluate --all --save
tetrak-ocr evaluate --backend vision --save --merge
```

This one needs a checkout of the repository: the corpus is not shipped in the
package, and running it elsewhere says so rather than failing obscurely.
`--all` runs every backend you have installed, side by side. `--save` writes
`evaluation/ocr/benchmark.{csv,md}` plus a dated, git-linked snapshot under
`evaluation/ocr/runs/`. `--merge`, for a single-backend run, splices that
backend's column into the committed benchmark without re-measuring the
others, which costs hours and real API spend on `claude`; it refuses if the
corpus has changed since.

The flags are passed straight through to the harness, so
`tetrak-ocr evaluate --help` prints the harness's own help.

```{note}
`--save` overwrites the committed benchmark with whatever it managed to run.
On a partial install, keep the output rather than committing it.
```
