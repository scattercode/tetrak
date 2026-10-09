---
title: "Command line and Python API"
kicker: "Reference"
aliases: ["/batch/", "/reference/api/"]
---

How to install and drive the package is documented in the
[user guide](https://scattercode.github.io/tetrak/), which is built from the
released code at each release, so it describes the version on PyPI and
cannot drift from it. The reference pages here are the things the code
cannot document about itself: [the corpus](corpus/), [the engines](engines/)
as measured, [routing](routing/) and [licensing](licensing/).

In brief, installing the package provides one command:

```bash
pip install 'tetrak[qa]'                # plus: brew install tesseract poppler

tetrak-ocr backends                     # what this machine can run
tetrak-ocr ocr scan.jpg --backend tesseract-auto
tetrak-ocr batch --backend auto-local   # workspace/scans/ → processed/, failures to triage/
tetrak-ocr evaluate --all --save        # the benchmark, from a checkout
```

The guide covers the rest:

- [Installation](https://scattercode.github.io/tetrak/installation.html) — the
  package, the optional backend extras and what each pulls in, the system
  dependencies, model weights and credentials.
- [Quick start](https://scattercode.github.io/tetrak/quickstart.html) — one
  file, then a folder, and what comes back.
- [Using the command line](https://scattercode.github.io/tetrak/guide/command-line.html)
  — every subcommand, the output formats and searchable PDFs, the triage
  queue, the run log, dry runs and the evaluation harness.
- [Choosing a backend](https://scattercode.github.io/tetrak/guide/backends.html)
  — what each engine is for, what `auto-local` does, and what a run costs.
- [Using the Python API](https://scattercode.github.io/tetrak/guide/python-api.html)
  — the registry, the errors, backend options, fan-out and the quality
  gate, outputs, multi-page documents, the batch pipeline and the run log
  from code.
- Tutorials — [batch an archive](https://scattercode.github.io/tetrak/tutorials/batch-an-archive.html),
  [transcribe Armenian material](https://scattercode.github.io/tetrak/tutorials/armenian.html)
  and [build your own pipeline](https://scattercode.github.io/tetrak/tutorials/scripting.html).
- [Command line reference](https://scattercode.github.io/tetrak/cli.html) and
  [Python API reference](https://scattercode.github.io/tetrak/api.html) —
  every flag and every public function, generated from the parser and the
  docstrings.
