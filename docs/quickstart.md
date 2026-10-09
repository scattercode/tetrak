# Quick start

Ten minutes from an installed package to a transcribed folder. It assumes you
have [installed](installation.md) the package with the `qa` extra and the two
system tools.

## Transcribe one file

```bash
tetrak-ocr ocr scan.jpg
```

That prints the transcript to stdout using Tesseract, the backend every
install has. To pick a different engine, name it:

```bash
tetrak-ocr ocr scan.jpg --backend tesseract-auto     # Tesseract, tuned per image
tetrak-ocr ocr scan.jpg --backend vision             # Apple Vision, on a Mac
tetrak-ocr ocr programme.pdf --backend marker --output programme.md
```

`tesseract-auto` is worth knowing about straight away: it is the same engine
as `tesseract`, but it inspects each image first and picks a contrast factor
and page-segmentation mode to suit it. On faded or reversed-out material
that is the difference between a transcript and nothing at all.

## Batch a folder

This is what the tool is built to do. It works out of three directories
under `workspace/`, resolved against your current working directory, so run
it from the folder that holds your project:

```text
workspace/
  scans/       input: put files here
  processed/   output: transcript beside the original
  triage/      quarantine: anything too poor to trust
```

```bash
mkdir -p workspace/scans
cp ~/archive/*.jpg workspace/scans/
tetrak-ocr batch --backend auto-local
```

`auto-local` is a strategy rather than an engine. For every file it works
out which installed engines can read it, runs each in turn, scores every
transcript without needing a reference, and keeps the highest scorer. While
it runs you will see one score table per file, one row per engine that
ran, with the winner named underneath:

```text
  Processing: carthay-circle-premiere.jpg
    Backend         Quality  Words  Effective      Time
    --------------  -------  -----  ---------  --------
    vision            …
    tesseract-auto    …
    [auto-local → vision]  effective=…  quality=…
    → carthay-circle-premiere.jpg
    → carthay-circle-premiere.md
```

When it finishes, each file that cleared the quality floor is in
`workspace/processed/` as a Markdown transcript, with the original moved in
beside it so the two can never be separated:

```text
workspace/processed/
  carthay-circle-premiere.jpg    ← the original, moved from scans/
  carthay-circle-premiere.md     ← the transcript
```

`workspace/scans/` is left empty, so "what is still in scans?" always has a
meaningful answer.

## When it cannot read something

A failed transcript looks exactly like a successful one from the outside: it
is still a `.md` file with words in it. So a file whose best transcript still
scores below the quality floor does not reach `processed/` at all. It goes to
`workspace/triage/`, with a manifest recording every backend that was tried,
what each scored, and the first 500 characters each produced:

```text
  Processing: kar-mi-troupe-poster.jpg
    → TRIAGE: kar-mi-troupe-poster.jpg
    → TRIAGE: kar-mi-troupe-poster.md

Triaged (1): kar-mi-troupe-poster.jpg
Done. 0 file(s) processed, 1 sent to triage.
```

The triage folder is the list of things to rescan, send to a vision model, or
transcribe by hand. The point is that bad transcripts do not quietly enter a
catalogue looking like good ones.

## Ask for a searchable PDF

A catalogue needs the transcript inside the file it indexes. The `pdf`
format writes the scan with the transcript embedded as an invisible text
layer, which is what Preservica, CONTENTdm, Omeka and AtoM index, and what a
screen reader reads:

```bash
tetrak-ocr batch --backend auto-local --pdf
```

That writes `workspace/processed/<name>.pdf` alongside the Markdown. The OCR
runs once however many formats you ask for.

## Where next

- [Using the command line](guide/command-line.md): every subcommand, the
  output formats, the run log, dry runs and the evaluation harness.
- [Choosing a backend](guide/backends.md): what each engine is for, what
  `auto-local` actually does, and what a run costs.
- [Batch an archive](tutorials/batch-an-archive.md): the full walk-through,
  from an empty workspace to catalogue-ready PDFs and a worked triage queue.
- [Using the Python API](guide/python-api.md): the same pipeline from code.
