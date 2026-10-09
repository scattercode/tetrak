# Choosing a backend

Every backend exposes the same interface, so they are interchangeable and
selected by name with `--backend`. Seven engines, plus `auto-local`, a
strategy built on top of them.

| Backend | Extra | PDFs | What it is |
|---|---|:--:|---|
| `tesseract` | core | ✓ | The classical engine. Fast, offline, predictable: the baseline everything else is measured against |
| `tesseract-auto` | core | ✓ | The same engine, but inspecting each image first to pick a contrast factor and page-segmentation mode per file |
| `vision` | `[vision]` | ✗ | Apple's Vision framework. macOS only, ships with the OS: no weights, no download, no network |
| `easyocr` | `[easyocr]` | ✗ | Deep-learning detector and recogniser. Handles varied contrast and awkward grounds |
| `easyocr-hy` | `[armenian]` | ✗ | EasyOCR's detector with our own Armenian recogniser behind it. See [Armenian material](#armenian-material) |
| `paddle` | `[paddle]` | ✗ | Deep-learning detector and recogniser aimed at dense small text |
| `paddle-vl` | `[paddle-vl]` | ✓ | Document vision-language model. Reads PDFs and multi-page TIFFs; strongest local engine measured, but minutes per page |
| `marker` | `[marker]` | ✓ | Layout-aware document conversion, the only local backend that models reading order |
| `claude` | `[claude]` | ✓ | The Anthropic vision API. Reads material no local tool can |
| `auto-local` | `[qa]` | ✓ | **The recommended default.** Runs the viable local engines, scores each, keeps the best |

The measurements behind every claim on this page are on
[tetrak.dev](https://tetrak.dev/): the [engines
page](https://tetrak.dev/reference/engines/) for each backend's measured
strengths and failure cases, and the [research](https://tetrak.dev/research/)
for the full benchmark and what it does and does not establish. Figures are
deliberately not repeated here, where nothing would keep them current.

## Which to name

- **`tesseract-auto` over `tesseract`, always**, if you are naming a
  Tesseract backend by hand. Per-image tuning takes the same engine from
  nothing to a usable transcript on some of the corpus.
- **`auto-local` when you would rather not choose.** It is the best local
  option measured on the corpus and also the slowest, because it runs
  several engines per file.
- **`vision` is the strongest local engine measured on this corpus**, and
  the fastest worth using: the model ships with macOS, so there are no
  weights to download and no slow first call. It cannot read PDFs, and it
  has no Armenian, Greek, Hebrew, Georgian or Indic support.
- **`marker` is slow and GPU-gated inside `auto-local`.** It is the only
  local engine that gets multi-column newsprint into the right reading
  order, and it is much the most expensive engine in the set.
- **`claude` sends your images to an API** and needs `ANTHROPIC_API_KEY`,
  which rules it out for confidential material. It also does not reproduce
  between runs: it recovers the same words and orders them differently. It
  is the thing to reach for on decorative and hand-lettered type, where
  local engines collapse.
- **The deep-learning backends download weights on first run** and hold them
  in memory afterwards, so the first call is slow and later ones are not.
  That is fine for batch work and poor for one-shot interactive use.

## What `auto-local` does

`auto-local` is a strategy rather than an engine. For every file it:

1. **Works out which engines can read it**: what you have installed,
   whether a GPU is present (Marker is gated on one), the platform (Vision
   is macOS only), and whether the file is a PDF (Vision, EasyOCR and
   PaddleOCR cannot read those).
2. **Runs each of them in turn.** Sequentially, on purpose: these engines
   are individually heavy on CPU and RAM and several hold model singletons,
   so running three at once costs predictability rather than buying speed.
3. **Scores every transcript** with a reference-free quality score:
   dictionary coverage multiplied by inverse log-perplexity under GPT-2. No
   ground truth is needed, which is what makes it work on material nobody
   has transcribed.
4. **Keeps the highest scorer**, after adjusting for how much text each
   candidate recovered relative to the longest, so a noisy transcript cannot
   win on word count alone.

The pool, in the order the engines run:

| | Images | PDFs |
|---|---|---|
| GPU present and Marker installed | Marker, Vision, EasyOCR, PaddleOCR, Tesseract-auto | Marker, Tesseract-auto |
| No GPU | Vision, EasyOCR, PaddleOCR, Tesseract-auto | Tesseract-auto |

Each only if installed. Tesseract-auto is always there, so it is the floor
rather than a choice. With `--with-paddle-vl`, PaddleOCR-VL joins both lists
and runs first; it is opt-in because it runs in minutes where the rest of
the pool runs in seconds.

The winner then passes the quality gate. If its raw score falls below the
floor the file goes to [triage](command-line.md#the-triage-queue) with the
whole score table, which is what makes the triage manifest worth reading.
`--quality-gate` applies the same floor to any single backend.

The scoring reads English only. On Armenian or any other non-Latin
material, `auto-local` cannot rank its candidates, so name the backend
instead.

## Supported files

JPEG, PNG and TIFF everywhere; PDF on `tesseract`, `tesseract-auto`,
`paddle-vl`, `marker`, `claude` and `auto-local`. The batch pipeline filters
`workspace/scans/` by the chosen backend's supported extensions, so a PDF is
silently skipped under `easyocr`, `easyocr-hy`, `paddle` or `vision`;
`--dry-run` makes that visible.

**Multi-page TIFF is read in full or refused by name.** Pillow opens such a
file at frame 0 and says nothing about the rest, so the rule in this package
is that a multi-frame image is either read page by page or refused with
`MultiPageNotSupportedError`, which names the file, the page count and a
backend that will read it, rather than returning the cover as though it were
the whole document. The Tesseract backends and PaddleOCR-VL read every
page; the others refuse, and the batch pipeline's per-page route for
searchable PDFs is the way to put the rest of them to work on one.

## What a run costs

`auto-local` runs several engines per file and Marker is much the most
expensive of them, so a batch can take far longer than the file count
suggests. **Cost tracks the amount of text recovered**, not the page count
and not the file size: the recognition models decode token by token, per
region, so a dense ten-page trade weekly costs more than a 21-page
souvenir programme of light pages, and a single-page playbill of small type
costs more than a postcard. Estimate a job from how much text is on the
pages, not how many pages there are.

If a run is taking longer than expected, `tail -f workspace/telemetry.jsonl`
shows which file and which backend it is on, with the elapsed seconds for
every engine that has finished; see [the run
log](command-line.md#the-run-log).

To trade quality for speed, name a cheap backend instead of `auto-local`,
and keep the triage queue with `--quality-gate`:

```bash
tetrak-ocr batch --backend tesseract-auto --quality-gate
```

Asking for a searchable PDF on a multi-page document roughly doubles its OCR
time, because it has to be transcribed page by page; see [multi-page
documents](command-line.md#multi-page-documents).

## Armenian material

`easyocr-hy` is stock EasyOCR with a different recogniser: `tetrak_hy`,
trained for the Armenian script by
[tetrak-hy-trainer](https://github.com/scattercode/tetrak-hy-trainer) and
published as
[tetrak-easyocr-armenian](https://pypi.org/project/tetrak-easyocr-armenian/).
Detection is untouched, since EasyOCR's CRAFT detector already finds Armenian
text; reading it was the missing half. Stock EasyOCR reads essentially
nothing on Armenian.

Three steps sit between the raw recogniser and its output, and none is
retraining: a **word list** that corrects out-of-vocabulary readings from the
recogniser's own alternatives; a **script fold** that turns the Latin
look-alikes the recogniser sometimes emits inside an Armenian word back into
Armenian; and a **reading-order** pass that reads each column to its foot
before starting the next, and rejoins words a line break hyphenated.

```bash
pip install 'tetrak[armenian]'
tetrak-ocr ocr page.png --backend easyocr-hy
```

The recogniser's weights download on first use, pinned to one immutable
revision per release and checksum-verified. No PDFs: convert pages to images
first. The [Armenian tutorial](../tutorials/armenian.md) walks through a
whole book.

Tesseract can also read Armenian if its `hye` language data is installed,
through the `lang` argument of the Python API; the command line does not
expose it.
