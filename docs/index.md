# Tetrak

Local-first OCR for archival material: postcards, posters, playbills,
programmes and trade papers. Point it at a folder and it runs several engines
per file, scores what each one produced, keeps the best, and quarantines
anything it could not read well enough to trust. Everything runs on your
machine unless you explicitly ask for the Claude backend.

This site is the user guide and reference for the `tetrak` package: how to
install it, how to drive it from the command line and from Python, and what
every command, flag and function does. It is built from the released code at
each release, so what it describes is the version on PyPI.

The research behind the tool lives on [tetrak.dev](https://tetrak.dev/): the
evaluation corpus, what each engine was measured to do and where it fails, the
evidence behind the routing, and the articles.

## In two minutes

```bash
pip install 'tetrak[qa]'                # the package, plus quality scoring
brew install tesseract poppler          # macOS; see Installation for Linux

tetrak-ocr backends                     # what this machine can run
tetrak-ocr ocr scan.jpg                 # one file, to stdout

mkdir -p workspace/scans
cp ~/archive/*.jpg workspace/scans/
tetrak-ocr batch --backend auto-local   # a folder, best engine per file
```

Transcripts land in `workspace/processed/` beside the originals; anything too
poor to trust goes to `workspace/triage/` with a note saying what was tried.
The [quick start](quickstart.md) walks through that output.

```{toctree}
:caption: Getting started
:maxdepth: 1

installation
quickstart
```

```{toctree}
:caption: User guide
:maxdepth: 2

guide/command-line
guide/backends
guide/python-api
```

```{toctree}
:caption: Tutorials
:maxdepth: 1

tutorials/batch-an-archive
tutorials/armenian
tutorials/scripting
```

```{toctree}
:caption: Reference
:maxdepth: 1

cli
api
```
