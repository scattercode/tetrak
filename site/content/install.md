---
title: "Installation"
kicker: "Using it"
---

## Quick start

Four steps from nothing to a transcribed batch.

### 1. System dependencies and the package

{{< tabs >}}
{{< tab "macOS" >}}
```bash
brew install tesseract poppler
pip install "tetrak-ocr[all]"
```
{{< /tab >}}
{{< tab "Debian / Ubuntu" >}}
```bash
sudo apt-get install tesseract-ocr poppler-utils
pip install "tetrak-ocr[all]"
```
{{< /tab >}}
{{< /tabs >}}

`[all]` installs every optional backend. If you would rather start small, plain
`pip install tetrak-ocr` gives you Tesseract, image handling and PDF
rasterisation — see [the extras](#optional-backends) below for what each
addition buys.

### 2. Check what is available

```bash
tetrak-ocr backends
```

Engines report honestly: a backend whose dependency is missing says so, and
names the extra that would install it.

### 3. Run a batch

```bash
tetrak-ocr batch --backend auto-local
```

Put files in `workspace/scans/` first — the [tutorial](tutorial/) walks through
this on
real archive images. Add `--quality-gate` to get the same triage behaviour
from a single named engine.

### 4. Audit it yourself

```bash
tetrak-ocr evaluate --all --save
```

Runs the committed corpus through every installed backend and writes the
benchmark. Expect roughly 65 minutes, most of it Marker. This one needs a
checkout rather than just the package — the corpus ships with the repository.

## The package

```bash
pip install tetrak-ocr
```

That gives you Tesseract, image handling and PDF rasterisation — enough to
process a folder of scans offline. Everything else is an optional extra.

### Optional backends

Each heavy backend is an extra, so you install only what you intend to use:

```bash
pip install 'tetrak-ocr[claude]'     # Anthropic vision API
pip install 'tetrak-ocr[easyocr]'    # EasyOCR (CRAFT + CRNN)
pip install 'tetrak-ocr[paddle]'     # PaddleOCR
pip install 'tetrak-ocr[paddle-vl]'  # PaddleOCR-VL (document vision-language model)
pip install 'tetrak-ocr[marker]'     # Marker, layout-aware PDF/image conversion
pip install 'tetrak-ocr[qa]'         # quality scoring used by auto-local
pip install 'tetrak-ocr[all]'        # all of the above
```

They are separated because the difference is not marginal: the core install is
a few tens of megabytes, while `[all]` pulls PyTorch, PaddlePaddle and several
sets of model weights — well over a gigabyte before any model downloads at
first run.

If you call a backend you have not installed, the error tells you the exact
command rather than raising `ModuleNotFoundError`:

```console
$ tetrak-ocr ocr scan.jpg --backend paddle
error: The 'paddle' backend needs the 'paddleocr' and 'paddlepaddle' packages,
not installed here.
Install with:  pip install 'tetrak-ocr[paddle]'
```

{{< note kind="warning" title="The `marker` extra is copyleft" >}}
`marker-pdf` and its Surya models are, as of writing, **GPL-3.0**, with a
commercial-use exception offered by their author. This does not affect
`tetrak-ocr` itself — the extras are optional dependencies, resolved at
install time and never vendored — but it does affect anyone redistributing
a bundle that includes them. Check the current terms upstream; licence
terms change. See [licensing](reference/licensing/).
{{< /note >}}

## System dependencies

Two things are not Python packages and must be installed separately — the
commands are in the quick start above. **Tesseract** is the OCR engine itself —
`pytesseract` is only a wrapper around the binary. **Poppler** provides
`pdftoppm`, which `pdf2image` shells out to when rasterising PDF pages.
Without poppler, PDF input fails with `PDFPageCountError` rather than
anything obviously poppler-shaped.

## API credentials

The Claude backend needs an API key. Put it in a `.env` file at the root of
your working directory:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

It is read with `python-dotenv` at import time. Nothing else in the package
makes network calls, so if you are not using the Claude backend you can ignore
this entirely.

## For development

```bash
git clone https://github.com/scattercode/tetrak.git
cd tetrak
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest -m "not slow"
```

`-m "not slow"` skips the tests that read the evaluation corpus and invoke a
real OCR engine; it runs in well under a second. Drop the flag to run
everything, which takes a minute or two.

The evaluation corpus and harness live in `evaluation/` and are not part of the
installed package — benchmarking is something you do from a checkout.
