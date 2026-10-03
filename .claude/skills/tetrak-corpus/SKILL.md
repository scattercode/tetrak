---
name: tetrak-corpus
description: Add an item to the Tetrak OCR evaluation corpus, or re-run and interpret the benchmark. Covers the full sequence — image, provenance in SOURCES.md, generated ground truth, thumbnails, the corpus page card, re-running the harness — plus the steps that fail silently if skipped, and when the Tesseract auto-configuration bands need re-fitting. Use this whenever adding a fixture or corpus image, regenerating ground truth, running tetrak-ocr evaluate, updating benchmark.csv, or asking why a corpus item is missing from the site.
---

# Adding a corpus item, and re-benchmarking

The evaluation corpus at `evaluation/ocr/corpus/` is what every published
figure rests on. Adding to it changes those figures, so the sequence below
ends with re-running the benchmark, not with committing the image.

**Nothing under `evaluation/<pipeline>/` is edited by hand.**
`benchmark.{csv,md}` and `runs/` are harness output; `corpus/expected/` is
generated. Regenerate rather than patch.

## The sequence

```bash
# 1. the image
cp <scan> evaluation/ocr/corpus/images/<name>.<ext>

# 2. provenance and rights — required, not optional
$EDITOR evaluation/ocr/corpus/SOURCES.md

# 3. ground truth
python tools/generate_expected.py --fixture evaluation/ocr/corpus/images/<name>.<ext>

# 4. site renditions  (committed, not built — see below)
python tools/generate_corpus_thumbnails.py

# 5. a card on the corpus page
$EDITOR site/content/reference/corpus.md          # add a {{< lightbox >}} entry

# 6. re-measure
tetrak-ocr evaluate --all --save
```

Commit the image, its `expected/` transcript, the SOURCES.md entry, the
renditions, the corpus page card, and the regenerated benchmark together.

## The two steps that fail silently

**Thumbnails (4) and the corpus card (5).** The renditions are committed
rather than built, so a new item is simply *missing* from the corpus page
until both are done. Nothing errors; the grid is one entry short and looks
entirely normal.

**SOURCES.md (2).** Nothing enforces it, and an image whose rights are not
recorded cannot be published — which is discovered much later, by someone who
has to work out where it came from.

## Re-check the Tesseract auto-configuration bands

`analyse_image()` picks contrast and PSM from pixel statistics, and its
thresholds in `src/tetrak_ocr/backends/tuning.py` were **fitted to part of
this corpus** — `FIT_PROVENANCE` in that module records exactly which images,
and which were not.

If the corpus changes materially, re-fit them with the calibration toolkit
under `evaluation/ocr/calibration/` rather than editing the numbers by hand.
Left un-refitted, `tesseract-auto` quietly becomes miscalibrated: it keeps
working, and merely gets worse.

**Do not fold held-out fixtures into a re-fit without saying so.** The images
added after the original fit are held-out data for `tesseract-auto` and
nothing special for any other backend. A band set scored only on the images it
was fitted to tells you nothing about whether it generalises — that property
is worth more than the accuracy it costs.

## A multi-page TIFF

Additionally exercises the paging path. See `tetrak_ocr.imaging` for which
backends read every frame and which refuse: Tesseract reads them all, and the
backends that would read only frame 0 raise `MultiPageNotSupportedError`
rather than returning page one as though it were the document.

## Reading the results honestly

Two caveats attach to every number the harness prints, and both belong in any
summary of them:

- **Claude generates the ground truth it is then scored against.** Its ~0.90
  average is self-consistency, not accuracy, and it is not stable run to run.
  Never quote it as a measurement of Claude. Human-checked ground truth is the
  single highest-value improvement available to this project.
- **Timing is wall clock and includes lazy first-call model loading.** The
  first fixture a heavy backend sees is much slower than the rest, so compare
  backends on their corpus totals, not on a single row.

`--save` writes `benchmark.{csv,md}` (the stable reference the site reads at
build time) and a dated, git-linked copy under `evaluation/ocr/runs/`. Those
dated runs are the historic record: commit them with the benchmark. (The
product team builds a private performance ledger from them; nothing in this
repository needs to.)

## Where the numbers may appear

Published figures come from `benchmark.csv` at build time. Prose — articles,
the deck, docstrings — must cite rather than transcribe. See the
`tetrak-articles` skill for the rule and the incident behind it.
