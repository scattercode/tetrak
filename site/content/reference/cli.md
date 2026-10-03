---
title: "Command line"
kicker: "Reference"
aliases: ["/batch/"]
---

Installing the package provides an `tetrak-ocr` command.

## `tetrak-ocr backends`

List every backend and whether this environment can run it. `✓` means
installed and usable; `·` means the optional extra is missing.

```console
$ tetrak-ocr backends
 ✓ tesseract
 ✓ tesseract-auto
 · claude  (extra not installed)
 ✓ auto-local
```

## `tetrak-ocr ocr`

Transcribe a single file to stdout, or to `--output`.

```bash
tetrak-ocr ocr scan.jpg
tetrak-ocr ocr scan.jpg --backend tesseract-auto
tetrak-ocr ocr programme.pdf --backend marker --output programme.md
tetrak-ocr ocr faded.jpg --contrast 3.5 --psm 6
```

`--contrast`, `--psm` and `--auto` tune Tesseract per image. Any backend that
does not use them says so rather than dropping them silently.

### Output formats

One OCR pass can be written several ways. `--format` names the set; it is
repeatable and comma-separated, and `md`, `txt` and `plaintext` are accepted as
aliases.

| Format | Writes | For |
|---|---|---|
| `markdown` | `<name>.md` | The default — transcript under a heading |
| `text` | `<name>.txt` | Bare transcript, for anything that will parse it |
| `pdf` | `<name>.pdf` | Invisible text layer over the scan, for catalogue indexing |

```bash
tetrak-ocr batch --backend auto-local --format markdown,pdf
tetrak-ocr batch --backend auto-local -f markdown -f pdf   # identical
tetrak-ocr batch --backend auto-local --format text        # .txt only
```

`--format` is a **full specification**: naming `pdf` alone writes a PDF and no
Markdown. The OCR itself runs once regardless of how many formats are asked
for, so the second and third cost a file write rather than another pass.

`--pdf` predates it and stays additive, so existing commands keep working: it
means `--format markdown,pdf`.

On `tetrak-ocr ocr`, which prints to stdout by default, `--format` writes the
named files beside the source and leaves stdout alone.

### Searchable PDFs

The `pdf` format writes the scan with the transcript embedded as an invisible
text layer. That single file is what makes a transcript indexable in Preservica
Starter, CONTENTdm, Omeka and AtoM without asking a vendor for anything, and
it is the accessibility output too: the layer an indexer reads is the layer a
screen reader reads.

```bash
tetrak-ocr ocr scan.jpg --pdf                       # scan.pdf beside it
tetrak-ocr ocr scan.jpg --pdf catalogue-ready.pdf   # or name it
tetrak-ocr batch --backend auto-local --pdf         # workspace/processed/<name>.pdf
tetrak-ocr batch --backend auto-local -f pdf        # the PDF alone, no .md
```

The PDF is an **access copy**: images past 2400px are downsampled and
JPEG-encoded, which takes a 1.1MB postcard scan to a 171KB PDF an institution
can actually serve. `--pdf-full-size` embeds the source untouched instead, for
when the PDF is the deliverable rather than a derivative.

The text layer carries whichever backend's transcript the run produced, so it
matches the `.md` sidecar exactly. Read it back with `pdftotext -raw`; plain
`pdftotext` reflows and de-hyphenates, so the two will not look identical
through it.

### Multi-page documents

A searchable PDF needs one transcript per **page**; a backend returns one per
**document**. So the `pdf` format on a multi-page PDF or TIFF transcribes it
page by page — splitting a PDF into single-page PDFs, which keeps the text
layer that Marker reads instead of OCR-ing, then laying each page's words onto
the page they came from.

That costs **roughly 2× the OCR time**, and it is inherent per-document work in
the engine rather than overhead that can be removed. It is paid only when both
conditions hold — the `pdf` format was requested, *and* the document has more
than one page:

```bash
tetrak-ocr batch --backend auto-local --pdf   # multi-page: ~2x, gets a PDF
tetrak-ocr batch --backend auto-local         # multi-page: normal speed, no PDF
```

The `.md` and `.txt` come from the same pass, with the pages joined, so no
document is ever transcribed twice. When the per-page route is taken the run
says so, and the log records each page as it lands:

```text
Processing: king-of-kings-souvenir-1927.pdf
  21 pages, transcribing individually for the PDF
```

**Naming.** A PDF transcribed to a searchable PDF is written as
`<stem>.searchable.pdf`. It would otherwise collide with the original, which
the batch pipeline moves into the same directory — and one would silently
overwrite the other. Non-PDF sources keep the plain `<stem>.pdf`.

{{< note kind="warning" title="One thing it still refuses" >}}
**Scripts the font cannot encode.** The built-in font covers Western European
text; a system Unicode font is used automatically where one is needed and
present. Where neither can encode the transcript the PDF is refused, because
the alternative is a page of black boxes that extracts as nothing. Point
`--pdf-font` at a TrueType font that covers the script.
{{< /note >}}

The text is laid over the page rather than positioned word by word, so
selecting text in a viewer will not align with the words on the scan. That is
deliberate: a word-positioned layer measured markedly worse on reading order —
the thing a screen reader announces — on multi-column material.

## `tetrak-ocr batch`

Three directories under `workspace/`, resolved against your **current working
directory** — so run it from the folder holding your scans:

```text
workspace/
  scans/       input — put files here
  processed/   output — transcript plus the original, side by side
  triage/      quarantine — files whose transcript was too poor to trust
```

```bash
tetrak-ocr batch --backend auto-local
```

For each supported file in `workspace/scans/`, the pipeline runs OCR, writes
`workspace/processed/<name>.md`, and moves the original to
`workspace/processed/<name>.<ext>`.
Keeping the transcript beside its source means a transcript is never orphaned
from the image it came from.

Only extensions the chosen backend supports are picked up — EasyOCR and
PaddleOCR skip PDFs, because they cannot read them.

### The triage queue

`auto-local` refuses to return a transcript whose quality score falls below
the floor. When that happens the batch pipeline diverts the file to
`workspace/triage/` along with a manifest recording which backends were tried,
their scores, and an excerpt of each transcript — so you can decide whether to
rescan, send it to Claude, or transcribe by hand. `--quality-gate` applies the
same threshold to any single named backend. The reasoning is on [from findings
to design](../research/in-depth/#what-the-evidence-built).

### The run log

Every batch appends to `workspace/telemetry.jsonl`, one JSON object per line,
flushed per line so `tail -f` is a live progress view:

```bash
tail -f workspace/telemetry.jsonl
```

`auto-local` prints its score table only after every backend has finished, so
without this a forty-minute file is indistinguishable from a hung one. The log
carries `run_start`, `file_start`, one `backend_finish` per engine in the
fan-out, `file_finish` and `run_finish` — each with the file's path, size, type
and page count, and each backend's elapsed seconds.

| Flag | Effect |
|---|---|
| `--telemetry PATH` | Write the log somewhere other than the default |
| `--no-telemetry` | Do not write it |
| `TETRAK_NO_TELEMETRY=1` | The same, as an environment variable |

A logging failure never fails a run: the log disables itself, warns once, and
the batch carries on.

### Dry runs

```bash
tetrak-ocr batch --backend tesseract --dry-run
```

Lists what would be processed without touching anything — and, just as useful,
what would be **skipped** because the chosen backend cannot read it. The batch
pipeline filters `workspace/scans/` by the backend's supported extensions, so a
PDF simply vanishes under `easyocr` or `paddle`; a dry run is where that
becomes visible.

No OCR runs and nothing is moved, but the chosen backend's package does have
to be installed — the file list depends on which extensions that backend
declares it can read.

### Tuning Tesseract

```bash
tetrak-ocr batch --backend tesseract --contrast 3.0 --psm 6
tetrak-ocr batch --backend tesseract --auto
```

`--contrast` and `--psm` apply only to Tesseract; passing them with another
backend prints a note rather than silently ignoring them. `--auto` picks both
per image, and is usually better than either default — see
[the engines](engines/#tesseract-and-auto-configuration).

## `tetrak-ocr evaluate`

Benchmark backends against the evaluation corpus. Flags are passed straight
through to the harness.

```bash
tetrak-ocr evaluate --backend tesseract-auto
tetrak-ocr evaluate --all
tetrak-ocr evaluate --all --save
```

This one needs a checkout — the corpus is not shipped in the package, so
running it elsewhere reports that rather than failing obscurely.
