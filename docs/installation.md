# Installation

Tetrak is a Python package. It needs Python 3.11 or later, two system tools
that are not Python packages, and whichever optional OCR engines you intend to
use.

## The package

```bash
pip install tetrak
```

The distribution is `tetrak`; the command it installs is `tetrak-ocr`, and
the import package is `tetrak_ocr`. A plain install gives you Tesseract (via
`pytesseract`), image handling, PDF rasterisation and the searchable-PDF
writer: enough to process a folder of scans offline.

Most people want more than that. The install we recommend adds quality
scoring, which is what turns on `auto-local`, the backend that runs every
engine you have and keeps the best transcript per file:

```bash
pip install 'tetrak[qa]'
```

`[qa]` installs no extra *engines*. With core plus `[qa]`, `auto-local` is
choosing between one engine. Add the extras below to give it a choice.

## System dependencies

Two things must be installed separately, because they are binaries rather
than Python packages. **Tesseract** is the OCR engine itself; `pytesseract`
only wraps it. **Poppler** provides `pdftoppm`, which `pdf2image` shells out
to when rasterising PDF pages. Without poppler, PDF input fails with
`PDFPageCountError`, which does not look like a missing-poppler problem.

macOS:

```bash
brew install tesseract poppler
```

Debian or Ubuntu:

```bash
sudo apt-get install tesseract-ocr poppler-utils
```

## Optional backends

Every heavy engine is an extra, so you install only what you intend to use.
The difference is not marginal: the core install is a few tens of megabytes,
while `[all]` pulls PyTorch, PaddlePaddle and several sets of model weights,
well over a gigabyte before any model downloads at first run.

| Extra | Enables | What it installs |
|---|---|---|
| `qa` | `auto-local`, `--quality-gate` | pyspellchecker, transformers, torch |
| `easyocr` | `easyocr` | EasyOCR |
| `armenian` | `easyocr-hy` | our Armenian recogniser, as an EasyOCR custom network (pulls in EasyOCR) |
| `paddle` | `paddle` | PaddleOCR and PaddlePaddle |
| `paddle-vl` | `paddle-vl` | PaddleOCR-VL, the document vision-language model in the same package |
| `marker` | `marker` | marker-pdf 1.x |
| `vision` | `vision` | `ocrmac`, a wrapper over Apple's Vision framework. macOS only |
| `claude` | `claude` | the Anthropic SDK |
| `ocr` | everything above except `armenian` | |
| `all` | the same as `ocr` | |

```bash
pip install 'tetrak[qa,easyocr]'          # a choice of two local engines
pip install 'tetrak[qa,vision]'           # on a Mac: the strongest local engine measured
pip install 'tetrak[all]'                 # everything, several gigabytes
pip install 'tetrak[armenian]'            # Armenian material
```

If you ask for a backend you have not installed, the error names the extra
rather than raising `ModuleNotFoundError`:

```console
$ tetrak-ocr ocr scan.jpg --backend paddle
error: The 'paddle' backend needs the 'paddleocr' and 'paddlepaddle' packages, not installed here.
Install with:  pip install 'tetrak[paddle]'
```

```{warning}
The `marker` extra is copyleft. `marker-pdf` and its Surya models are, as of
writing, GPL-3.0, with a commercial-use exception offered by their author.
That does not affect Tetrak itself, since extras are optional dependencies
resolved at install time and never vendored, but it does affect anyone
redistributing a bundle that includes them. Check the current terms upstream;
licence terms change. See [licensing](https://tetrak.dev/reference/licensing/).
```

## Model weights

The deep-learning backends download their weights on first use and cache them
locally, so the first call in a fresh environment is slow and later ones are
not. Approximate sizes:

| Backend | Download | Cached under |
|---|---|---|
| `easyocr` | ~100 MB | `~/.EasyOCR/` |
| `easyocr-hy` | ~15 MB for the recogniser, plus EasyOCR's detector | the EasyOCR cache |
| `paddle` | ~100 MB | `~/.paddleocr/` |
| `paddle-vl` | ~1 GB | `~/.paddlex/official_models/` |
| `marker` | ~500 MB to 1 GB | `~/.cache/marker/`, or the Hugging Face cache |
| `auto-local` (`qa`) | ~500 MB for GPT-2, used by the quality score | `~/.cache/huggingface/` |

`vision` downloads nothing: the model ships with macOS. `tesseract` uses the
language data installed with the Tesseract binary.

## Check what you have

```console
$ tetrak-ocr backends
 ✓ tesseract
 ✓ tesseract-auto
 · claude  (extra not installed)
 · easyocr  (extra not installed)
 ✓ easyocr-hy
 · paddle  (extra not installed)
 · paddle-vl  (extra not installed)
 · marker  (extra not installed)
 ✓ vision
 ✓ auto-local
```

A tick means installed and usable here; a dot names an extra that is
missing. The list is honest about more than packages: `auto-local` reports
as missing without the `qa` extra, because it cannot score transcripts
without it, and `vision` never appears usable off macOS.

To see which release is installed:

```bash
python -c "import tetrak_ocr; print(tetrak_ocr.__version__)"
```

## API credentials

Only the Claude backend makes network calls. It needs an API key, read with
`python-dotenv` from a `.env` file in your working directory, or from the
environment:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

If you are not using `claude`, nothing else in the package needs this.

## For development

```bash
git clone https://github.com/scattercode/tetrak.git
cd tetrak
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'       # add extras as needed: [dev,all,armenian] is everything
pytest -m "not slow"
```

`-m "not slow"` skips the tests that read the evaluation corpus and invoke a
real OCR engine; it runs in well under a second. The evaluation corpus and
harness live in `evaluation/` and are not part of the installed package, so
`tetrak-ocr evaluate` only works from a checkout.
