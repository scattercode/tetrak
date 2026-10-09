# Tetrak OCR

**Custodian of the forgotten.** A local-first OCR orchestrator for archival
material — postcards, posters, playbills, programmes and trade papers.

> Install it as `pip install tetrak`. The command it provides is still
> `tetrak-ocr`, so every command below is unchanged.

**📖 [User guide and reference](https://scattercode.github.io/tetrak/)** · **[Research and benchmark](https://tetrak.dev/)**

No single OCR engine wins across document types. Tetrak's answer is not to make
you choose: point it at a folder and it runs several engines per file, scores
what each one produced, keeps the best, and quarantines anything it could not
read well enough to trust. Everything runs on your machine unless you
explicitly ask for the Claude backend.

## Install

```bash
pip install tetrak              # core: Tesseract, images and PDFs
pip install 'tetrak[qa]'        # enables auto-local — the recommended default
pip install 'tetrak[all]'       # everything, several gigabytes
```

`[qa]` is what turns `auto-local` on, because scoring needs a spell checker and
GPT-2 perplexity. It does not install any extra *engines* — `auto-local` picks
the best of whatever is present, so with core plus `[qa]` it is choosing
between one engine. Add `[easyocr]`, `[paddle]`, `[marker]` or `[vision]` to
give it something to choose between, or `[all]` for the lot.

Plus the system dependencies Tesseract and poppler:

```bash
brew install tesseract poppler                 # macOS
sudo apt install tesseract-ocr poppler-utils   # Debian/Ubuntu
```

The heavy backends are extras because most people want one or two of them, and
EasyOCR, PaddleOCR and Marker together pull in more than a gigabyte of model
weights. `tetrak-ocr backends` lists what you have and what each one needs.

## Batch a folder with `auto-local`

**This is what the tool is built to do.** Everything else is a way of doing
part of it by hand.

Tetrak works out of three directories under `workspace/`, resolved against your
current working directory:

```text
workspace/
  scans/       input — drop your files here
  processed/   output — transcript beside the original
  triage/      quarantine — anything too poor to trust
```

Create them, drop images in, and run:

```bash
mkdir -p workspace/{scans,processed,triage}
cp ~/archive/*.jpg workspace/scans/

tetrak-ocr batch --backend auto-local
```

### What happens to each file

`auto-local` is a strategy rather than an engine. For every file in
`workspace/scans/` it:

1. **Works out which engines can read it** — what you have installed, whether
   a GPU is present (Marker is gated on one), the platform (Vision is macOS
   only), and whether the file is a PDF (Vision, EasyOCR and PaddleOCR cannot
   read those).
2. **Runs each of them in turn.** Sequentially, on purpose: these engines are
   individually heavy on CPU and RAM and several hold model singletons, so
   running three at once costs predictability rather than buying speed.
3. **Scores every transcript** with a reference-free quality score —
   dictionary coverage against inverse log-perplexity. No ground truth needed,
   which is what makes it work on material nobody has transcribed.
4. **Keeps the highest scorer** and discards the rest.

A transcript that clears the quality floor is written to
`workspace/processed/<name>.md`, and the original image is moved in beside it.
Keeping the two together means a transcript is never orphaned from the page it
came from:

```text
workspace/processed/
  carthay-circle-premiere.jpg    ← original, moved from scans/
  carthay-circle-premiere.md     ← transcript
```

`workspace/scans/` is left empty. That is deliberate — it makes "what is still
in scans?" a meaningful question rather than an ambiguous one.

### When it cannot read something

If the best transcript still scores below the quality floor of **0.10**, the
file does not reach `processed/` at all. It goes to `workspace/triage/`, along
with a manifest recording every backend that was tried, what each one scored,
and the first 500 characters each produced:

```text
Processing: kar-mi-troupe-poster.jpg
  quality=0.0618
  → TRIAGE: kar-mi-troupe-poster.jpg
  → TRIAGE: kar-mi-troupe-poster.md

Triaged (1): kar-mi-troupe-poster.jpg
Done. 0 file(s) processed, 1 sent to triage.
```

This is the part that matters for an archive. A failed transcript looks exactly
like a successful one from the outside — it is still a `.md` file with words in
it. The triage queue is what stops bad transcripts quietly entering a catalogue
looking like good ones, and turns "which ones did it get wrong?" into a folder
you can actually work through.

### Output formats

By default each transcript is written as Markdown. `--format` asks for others,
and you can ask for several at once — the OCR runs **once** per file no matter
how many formats you want, so a second format costs a file write rather than
another pass over the image.

| Format | Writes | What it is for |
|---|---|---|
| `markdown` | `<name>.md` | The default. Transcript under a heading, for reading |
| `text` | `<name>.txt` | Bare transcript, no markup — for anything that will parse it |
| `pdf` | `<name>.pdf` | The scan with an invisible text layer, so catalogues can index it |

Repeatable or comma-separated, whichever you reach for first:

```bash
tetrak-ocr batch --backend auto-local --format markdown,pdf
tetrak-ocr batch --backend auto-local -f markdown -f pdf   # the same thing
```

`md`, `txt` and `plaintext` are accepted as aliases.

**`--format` is a full specification, not an addition.** `--format pdf` writes
a PDF *instead of* the Markdown, because you named the set you wanted. To keep
the Markdown, name it too — `--format markdown,pdf`.

The older `--pdf` flag is the exception, and stays additive so that existing
commands keep doing what they did: it is shorthand for `--format markdown,pdf`.

Two things worth knowing about the PDF format specifically. `--pdf-full-size`
embeds the source image untouched rather than a downsampled access copy, for
when the PDF is the deliverable rather than a derivative. And a **multi-page
document costs about twice as much** under this format, because it has to be
transcribed page by page to put each page's words on the right page — see
[below](#multi-page-documents-cost-about-twice-as-much).

### The run log

Every batch appends to `workspace/telemetry.jsonl` — one JSON object per line,
flushed as it goes, so you can watch a long run from another terminal:

```bash
tail -f workspace/telemetry.jsonl
```

That matters because `auto-local` is quiet while it works: it prints its score
table only once every backend has finished, so a file that takes forty minutes
looks exactly like one that has hung. The log says which file it is on, which
backend is running, and how long each one took.

```json
{"event": "backend_finish", "file": "camera-1919.pdf", "backend": "marker",
 "seconds": 2246.8, "score": 0.31, "pages": 10, "bytes": 3475030}
```

Events are `run_start`, `file_start`, `backend_finish` (one per engine in the
fan-out), `file_finish` and `run_finish`. Each carries the file's path, size,
type and **page count** — the last is the one that explains most surprises, as
a 3 MB PDF that is ten pages is ten documents of work.

Because it accumulates, the log is also the dataset for asking which engines
are worth their time on your material:

```bash
# median seconds per backend, slowest first
jq -rs 'map(select(.event=="backend_finish"))
        | group_by(.backend)[]
        | [.[0].backend, (length), (map(.seconds) | add / length | floor)]
        | @tsv' workspace/telemetry.jsonl | sort -k3 -rn
```

`--telemetry PATH` writes somewhere else; `--no-telemetry` or
`TETRAK_NO_TELEMETRY=1` turns it off. A logging failure never fails a run — it
warns once and carries on.

## The backends

Every backend exposes the same interface, so they are interchangeable and
selected by name with `--backend`. Seven engines, plus two strategies built on
top of them.

| Backend | Extra | PDFs | What it is |
|---|---|:--:|---|
| `tesseract` | core | ✓ | The classical engine. Fast, offline, predictable — the baseline everything else is measured against |
| `tesseract-auto` | core | ✓ | The same engine, but inspecting each image first to pick a contrast factor and page-segmentation mode per file |
| `vision` | `[vision]` | ✗ | Apple's Vision framework. macOS only, ships with the OS — no weights, no download, no network |
| `easyocr` | `[easyocr]` | ✗ | Deep-learning detector/recogniser. Handles varied contrast and awkward grounds |
| `paddle` | `[paddle]` | ✗ | Deep-learning detector/recogniser aimed at dense small text |
| `paddle-vl` | `[paddle-vl]` | ✓ | Document vision-language model. Reads PDFs and multi-page TIFFs; strongest local engine measured, but minutes per page. Join it to auto-local with `--with-paddle-vl` |
| `marker` | `[marker]` | ✓ | Layout-aware document conversion — the only local backend that models reading order |
| `claude` | `[claude]` | ✓ | The Anthropic vision API. Reads material no local tool can |
| `auto-local` | `[qa]` | ✓ | **The recommended default.** Runs the viable local engines, scores each, keeps the best |

A few things worth knowing before you pick one:

- **`tesseract-auto` over `tesseract`, always**, if you are naming a Tesseract
  backend by hand. Per-image tuning is the difference between 0.00 and 0.49
  character similarity on some of the corpus — the same engine, the same file.
- **`marker` is slow and GPU-gated inside `auto-local`.** It is the only local
  engine that gets multi-column newsprint into the right reading order, and it
  takes roughly 18 minutes of a 70-minute benchmark run to do it.
- **`claude` sends your images to an API** and needs `ANTHROPIC_API_KEY`, which
  rules it out for confidential material. It also does not reproduce between
  runs — it recovers the same words and orders them differently. It is the
  thing to reach for on decorative and hand-lettered type, where local engines
  collapse.
- **`vision` is the strongest local engine measured on this corpus**, and the
  fastest worth using — the model ships with macOS, so there are no weights to
  download and no slow first call. `auto-local` runs it second, after Marker.
- **The deep-learning backends download weights on first run** and hold them in
  memory afterwards, so the first call is slow and later ones are not.

## What to expect on timing

`auto-local` runs several engines per file and Marker is much the most
expensive of them, so a batch can take far longer than the file count suggests.
Worth knowing before you start a long run.

**Cost tracks the amount of text recovered — not the page count, and not the
file size.** On an M1 Max via the Apple GPU, Marker runs at roughly **13–18
seconds per 1,000 characters** of transcript. Measured on real archive material:

| Document | Pages | Transcript | Took |
|---|---:|---:|---:|
| Trade weekly, dense multi-column | 10 | 337,000 chars | **90 min** |
| Souvenir programme | **21** | 33,000 chars | 7 min |
| Illustrated book | 10 | 12,000 chars | 3 min |
| Playbill | **1** | 7,000 chars | 5 min |
| Picture postcard | 1 | 175 chars | 12 sec |

A 21-page programme finished in 7 minutes while a 10-page trade weekly took 90.
A single-page playbill took 5 minutes while a single-page postcard took 12
seconds. If you are estimating a job, estimate from how much text is on the
pages, not how many pages there are.

The reason is that the recognition model decodes token by token, per region:
more text means proportionally more sequential work. It is also why **there is
no batch-size setting that fixes this** — we measured the full range and the
spread is 6%, with the defaults fastest.

`tetrak-ocr backends` will tell you what is installed. If a run is taking
longer than you expected, `tail -f workspace/telemetry.jsonl` shows which file
and which backend it is on, with the elapsed seconds for every engine that has
finished.

To trade quality for speed, name a cheap backend instead of `auto-local` —
Tesseract measured **2.4 seconds per page** on the same material that took
Marker 90 minutes:

```bash
tetrak-ocr batch --backend tesseract-auto --quality-gate
```

### Multi-page documents cost about twice as much

A searchable PDF needs one transcript per **page**, and a backend returns one
per **document** — so asking for the `pdf` format on a multi-page PDF or TIFF
makes the pipeline transcribe it page by page instead of whole. That is
**roughly 2× the OCR time**, and it is unavoidable: it is inherent per-document
work in the engine, not overhead we can remove. Reusing one Marker converter
across the pages was measured and made no difference.

You only pay it when you ask for it. The per-page route is taken when **both**
are true — the `pdf` format was requested, and the document has more than one
page:

```bash
tetrak-ocr batch --backend auto-local --pdf     # multi-page: ~2x, gets a PDF
tetrak-ocr batch --backend auto-local           # multi-page: normal speed, no PDF
```

Single-page inputs are unaffected either way, and the `.md` and `.txt` come
from the same single OCR pass — the pages are simply joined.

When it takes the per-page route it says so, and the run log records each page
as it completes, so a long document is not silent:

```text
Processing: king-of-kings-souvenir-1927.pdf
  21 pages, transcribing individually for the PDF
```

**A PDF transcribed to a searchable PDF is named `<stem>.searchable.pdf`**, not
`<stem>.pdf` — otherwise it and the original would collide in
`workspace/processed/` and one would quietly overwrite the other. Sources that
are not themselves PDFs keep the plain `<stem>.pdf`.

## Other ways to run it

```bash
tetrak-ocr backends                                    # what is installed here
tetrak-ocr ocr postcard.jpg --backend tesseract-auto   # a single file
tetrak-ocr batch --backend tesseract --dry-run         # list, change nothing
```

A dry run is the quickest way to catch a backend that silently cannot read half
your folder: it lists what would be processed *and* what would be skipped
because the chosen engine does not support that file type.

`auto-local` always applies the quality gate, because it has scored every
engine it ran. To get the same triage queue from a single cheap backend, ask
for it:

```bash
tetrak-ocr batch --backend tesseract-auto --quality-gate
```

### Supported files

JPEG, PNG and TIFF everywhere; PDF on `tesseract`, `tesseract-auto`, `marker`,
`claude` and `auto-local`. Multi-page TIFF is read in full — Pillow opens such
a file at frame 0 and says nothing about the rest, so backends that cannot page
through one refuse it by name rather than returning the cover as though it were
the whole document.

## Layout

```text
src/tetrak_ocr/     the package: backends, batch pipeline, metrics, registry
workspace/          your working directories: scans, processed, triage
evaluation/         the corpus, the harness, and committed benchmark results
site/               the Hugo documentation site published at tetrak.dev
tools/              ground truth, thumbnail and benchmark-chart generators (not shipped)
tests/              unit tests, plus corpus-backed threshold tests marked `slow`
```

## Develop

```bash
git clone https://github.com/scattercode/tetrak.git
cd tetrak
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
lefthook install

pytest -m "not slow"       # the fast loop
cd site && npm run start   # the site at :1313
```

[`CLAUDE.md`](CLAUDE.md) covers conventions and the things that catch people
out. Commits follow [Conventional Commits](https://www.conventionalcommits.org/);
releases and `CHANGELOG.md` are generated by git-cliff and should never be
written by hand.

## The benchmark

The repository also holds a published evaluation of which OCR tool to reach for
and why, measured against a corpus of Los Angeles stage and picture-palace
ephemera from roughly 1910 to 1945. Every claim it makes can be re-run — the
corpus, the ground truth and the harness are all here:

```bash
tetrak-ocr evaluate --all --save    # ~65 minutes with everything installed
```

The results, the method and its limitations are on
**[tetrak.dev](https://tetrak.dev/research/in-depth/)**. One caveat before
quoting any of it: ground truth was generated by Claude and Claude is then
scored against it, so its ~0.90 average is self-consistency rather than
accuracy.

## The corpus

Nine items chosen to break OCR in different ways: a 1930 Los Angeles
theatrical trade weekly (cover and interior), a c. 1914 vaudeville
chromolithograph, two linen postcards of Hollywood picture palaces, a 21-page
1927 roadshow souvenir programme, a 1926 theatre playbill and a 1920 newspaper
display advertisement — the last two archival TIFFs, added after the
auto-configuration bands were fitted, which makes them the only held-out data
in the set. Every item is in the public domain in the United States; provenance
and rights are in
[`evaluation/ocr/corpus/SOURCES.md`](evaluation/ocr/corpus/SOURCES.md).

## Licence

Code is [MIT](LICENSE). The documentation, benchmark results and ground-truth
transcripts are [CC BY 4.0](LICENSE-CC-BY-4.0.txt). The corpus images are
public domain and carry neither — we hold no copyright in them to license.

[`LICENSING.md`](LICENSING.md) sets out which licence covers what, how to
attribute the benchmark, and one dependency caveat worth reading before you
build on the `marker` extra.
