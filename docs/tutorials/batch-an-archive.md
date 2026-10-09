# Batch an archive

A walk through the pipeline on a folder of scans, from an empty workspace to
catalogue-ready PDFs and a worked triage queue. It assumes you have
[installed](../installation.md) the package with the `qa` extra, Tesseract
and poppler, and at least one more engine for `auto-local` to choose
between: `[vision]` on a Mac, or `[easyocr]` anywhere.

If you have a checkout of the repository, the evaluation corpus under
`evaluation/ocr/corpus/images/` is a ready-made folder of material chosen to
break OCR in different ways, and the commands below use it. Any folder of
JPEG, PNG, TIFF or PDF scans works the same way.

## 1. Set up the workspace

The pipeline works out of `workspace/` in your current directory, so start
from the folder you want to keep the transcripts in:

```bash
mkdir -p workspace/scans
cp evaluation/ocr/corpus/images/* workspace/scans/
```

## 2. See what would happen

Before running anything expensive, ask what a backend would do with the
folder:

```bash
tetrak-ocr batch --backend auto-local --dry-run
```

```text
Backend: auto-local (dry run)
Would process 23 file(s):
  bancroft-magician-poster.jpg
  camera-1919.pdf
  carthay-circle-postcard-back.png
  ...
```

Now the same for an engine that cannot read PDFs:

```bash
tetrak-ocr batch --backend easyocr --dry-run
```

```text
Would skip 7 file(s) easyocr cannot read:
  camera-1919.pdf
  christmas-carol-1887.pdf
  ...
```

That is the thing a dry run exists to show. The pipeline filters the folder
by what the backend declares it can read, so without this a PDF would simply
vanish from an `easyocr` run and nothing would say so.

## 3. Run it

```bash
tetrak-ocr batch --backend auto-local
```

The header names the run log, then each file gets a block. For a file that
is read well:

```text
  Processing: carthay-circle-postcard-back.png
    Backend         Quality  Words  Effective      Time
    --------------  -------  -----  ---------  --------
    vision            …
    easyocr           …
    tesseract-auto    …
    [auto-local → vision]  effective=…  quality=…
    → carthay-circle-postcard-back.png
    → carthay-circle-postcard-back.md
```

One row per engine that ran: its raw quality score, how many words it
recovered, its score adjusted for that word count (which is what the winner
is chosen on), and how long it took. The last column is the one to watch
when a run is slow; it says which engine is spending the time.

For a file nothing reads acceptably, the block ends differently:

```text
  Processing: kar-mi-troupe-poster.jpg
    …
    → TRIAGE: kar-mi-troupe-poster.jpg
    → TRIAGE: kar-mi-troupe-poster.md
```

And the run ends with a summary:

```text
Triaged (1): kar-mi-troupe-poster.jpg
Done. 22 file(s) processed, 1 sent to triage.
```

That poster is a vaudeville chromolithograph with hand-lettered display type
arched over an illustration, colour on colour. Local engines read almost
nothing on it, and that is the limit of shape-matching OCR rather than a
misconfiguration. It is worth seeing once.

## 4. Watch a long run

`auto-local` prints a file's score table only after every engine has
finished with it, so a file that takes forty minutes looks exactly like one
that has hung. The run log is the live view. In another terminal:

```bash
tail -f workspace/telemetry.jsonl
```

Each line is one event. `file_start` says which file the run is on, one
`backend_finish` per engine says how long it took and what it scored, and
`file_finish` says where the file went. Once a run has accumulated, the log
answers which engines are worth their time on your material; see [the run
log](../guide/command-line.md#the-run-log) for a `jq` query that ranks them.

## 5. Read the output

```text
workspace/
  scans/                                  empty
  processed/
    carthay-circle-postcard-back.png      the original, moved here
    carthay-circle-postcard-back.md       its transcript
    ...
  triage/
    kar-mi-troupe-poster.jpg              the original, moved here
    kar-mi-troupe-poster.md               the manifest
  telemetry.jsonl
```

The transcript is the text under a heading:

```markdown
# carthay-circle-postcard-back

POST CARD
...
```

The triage manifest is a different kind of file. It records what every
engine produced and how each scored, so that the decision about what to do
next can be made without re-running anything:

```markdown
# kar-mi-troupe-poster

## Quality scores

| Backend | Score |
|---|---|
| vision | … |
| easyocr | … |
| tesseract-auto | … |

## Transcript excerpts

### vision

…
```

What to do with a triaged file is a judgement, and the manifest is there to
inform it. The usual options are to rescan at a higher resolution, to send
it to the Claude backend (which reads decorative and hand-lettered type that
local engines cannot, at the cost of sending the image to an API), or to
transcribe it by hand. The point of the queue is that this judgement is made
by a person, rather than a bad transcript entering the catalogue looking like
a good one.

## 6. Send the triage queue to Claude

The `claude` backend needs the `[claude]` extra and `ANTHROPIC_API_KEY` in
`.env` or the environment. Move the triaged originals back into the input
folder and run the single backend over them:

```bash
mkdir -p done && mv workspace/triage/*.md done/     # keep the manifests
mv workspace/triage/*.jpg workspace/scans/
tetrak-ocr batch --backend claude
```

Claude's transcripts go to `workspace/processed/` beside the others. Two
things to know before relying on it: it does not reproduce between runs,
recovering the same words in a different order, and it is the one backend
that sends your images off the machine.

## 7. Produce catalogue-ready PDFs

A catalogue indexes the file it holds, so the transcript needs to be inside
it. The `pdf` format writes the scan with the transcript as an invisible
text layer, which is what Preservica, CONTENTdm, Omeka and AtoM index and
what a screen reader reads. Run the batch with it from the start:

```bash
tetrak-ocr batch --backend auto-local --format markdown,pdf
```

or, equivalently, `--pdf`. For a single-page scan that costs a file write.
For the 21-page programme it costs about twice the OCR time, because a
searchable PDF needs a transcript per page and the engine returns one per
document, so the pipeline transcribes it page by page and says so:

```text
  Processing: king-of-kings-souvenir-1927.pdf
    21 pages, transcribing individually for the PDF
```

It is written as `king-of-kings-souvenir-1927.searchable.pdf`, so it cannot
overwrite the original moved in beside it. Check the text layer with
`pdftotext -raw`, which preserves the order the layer was written in:

```bash
pdftotext -raw workspace/processed/king-of-kings-souvenir-1927.searchable.pdf - | head
```

The PDF is an access copy: large images are downsampled and JPEG-encoded to
a size an institution can serve. Add `--pdf-full-size` when the PDF is the
deliverable rather than a derivative.

## Where next

- [Choosing a backend](../guide/backends.md) for what `auto-local` ran and
  why, and when to name an engine instead.
- [Using the command line](../guide/command-line.md) for every flag.
- [Build your own pipeline](scripting.md) for the same run from Python.
