# Transcribe Armenian material

A walk through a scanned Armenian book with `easyocr-hy`, the backend built
around our own Armenian recogniser. It assumes the package is
[installed](../installation.md) with Tesseract and poppler.

Stock OCR engines read essentially nothing on Armenian: EasyOCR's recogniser
has never seen the script, and Apple's Vision framework has no Armenian at
all. `easyocr-hy` keeps EasyOCR's detector, which already finds Armenian
text, and swaps in `tetrak_hy`, a recogniser trained for the script. Where
it stands against the other Armenian engines, register by register, is on
[tetrak.dev](https://tetrak.dev/reference/engines/#armenian-with-our-own-recogniser).

## 1. Install the recogniser

```bash
pip install 'tetrak[armenian]'
tetrak-ocr backends
```

`easyocr-hy` should now carry a tick. The extra installs
`tetrak-easyocr-armenian`, which depends on EasyOCR, so there is nothing
else to add. The recogniser's weights (about 15 MB) and EasyOCR's detector
weights download on the first call and are cached, pinned to one immutable
revision per release and checksum-verified.

## 2. Turn the scan into pages

`easyocr-hy` reads JPEG, PNG and TIFF, one page at a time; it does not read
PDFs, and it refuses a multi-page TIFF rather than reading its first page
and calling that the book. So the first step for a scanned PDF is to
rasterise it, which poppler's `pdftoppm` does:

```bash
mkdir -p workspace/scans
pdftoppm -r 300 -png book.pdf workspace/scans/book
ls workspace/scans
```

```text
book-01.png  book-02.png  book-03.png  ...
```

300 dpi is a sensible default for printed books. The pages are named with a
zero-padded number, so they sort in order.

## 3. Read one page

```bash
tetrak-ocr ocr workspace/scans/book-01.png --backend easyocr-hy
```

The transcript comes out one line per recognised line, in reading order:
where the page is set in columns, each column is read to its foot before the
next begins, and words a line break hyphenated are rejoined. Inside an
Armenian word, Latin look-alikes the recogniser sometimes emits (an `h` for
`հ`, a colon for the Armenian full stop `։`) are folded back to Armenian,
and out-of-vocabulary readings are corrected from the recogniser's own
alternatives against a word list built from proofread Wikisource transcripts
and the Nayiri lexicon.

## 4. Read the book

```bash
tetrak-ocr batch --backend easyocr-hy
```

Each page's transcript lands in `workspace/processed/book-NN.md` with the
image moved in beside it.

Two things are different from an English run, and both are deliberate:

**Do not use `auto-local`.** Its quality score counts recognised English
words and measures perplexity under an English language model, so it
cannot rank Armenian candidates; a perfectly good transcript scores 0.0.
Name the backend instead.

**`--quality-gate` is skipped, with a message.** The same score is what the
gate applies, so on a transcript that is not in the Latin script the
pipeline says so and writes the file rather than diverting an entire
Armenian run to triage and reporting every page as poor:

```text
    quality gate skipped: this transcript is not in the Latin script, and the score would be 0.0 whatever its quality
```

Pages with a Latin heading or a run of Russian in the apparatus are still
treated as Armenian: the check is on the share of letters, and half is the
boundary, so a page has to be mostly Latin before the gate applies.

## 5. Make a searchable PDF

The `pdf` format embeds the transcript as an invisible text layer, which is
what a catalogue indexes. The text layer needs a font that can encode
Armenian. The built-in font cannot; a system Unicode font is used
automatically where one is present (Arial Unicode on macOS, for example),
and where none is found the PDF is **refused** rather than written as a page
of black boxes. Point `--pdf-font` at any TrueType font that covers the
script:

```bash
tetrak-ocr batch --backend easyocr-hy --pdf --pdf-font /path/to/NotoSansArmenian-Regular.ttf
```

Noto Sans Armenian and DejaVu Sans both cover it. Check the layer with
`pdftotext -raw`, which keeps the order the layer was written in:

```bash
pdftotext -raw workspace/processed/book-01.pdf - | head
```

## 6. Measure it, if you have a reference

With a proofread transcript of a page, Tetrak's own metrics say how the
backend did on it. They are what the evaluation harness scores with:

```python
from pathlib import Path
from tetrak_ocr.accuracy import character_similarity, word_recall

actual = Path("workspace/processed/book-01.md").read_text(encoding="utf-8")
expected = Path("reference/book-01.txt").read_text(encoding="utf-8")

print(f"character similarity {character_similarity(actual, expected):.3f}")
print(f"word recall          {word_recall(actual, expected):.3f}")
```

Both normalise before comparing: lowercase, collapsed whitespace, and the
Armenian full stop `։` and the one-dot leader `․` folded onto their ASCII
look-alikes, so a reference typed with ASCII punctuation is not penalised.

## Tesseract, as a second opinion

Tesseract reads Armenian too, if its `hye` language data is installed
(`brew install tesseract-lang` on macOS; `apt-get install tesseract-ocr-hye`
on Debian or Ubuntu). The command line does not expose a language flag, but
the Python API does:

```python
from pathlib import Path
from tetrak_ocr.registry import get_backend

ocr = get_backend("tesseract")
text = ocr(Path("workspace/scans/book-01.png"), auto=True, lang="hye")
```

`auto=True` is `tesseract-auto`: it picks a contrast factor and
page-segmentation mode from the image before reading it.
