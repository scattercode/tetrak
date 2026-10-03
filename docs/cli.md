# Command line

Installing the package provides a `tetrak-ocr` command.

```{argparse}
:module: tetrak_ocr.cli
:func: build_parser
:prog: tetrak-ocr
```

## `evaluate`'s flags

`evaluate` uses `add_help=False` and forwards its arguments verbatim to
`evaluation.ocr.harness`, which builds its `argparse.ArgumentParser` inline
inside `main()` rather than in a reusable function -- there is nothing here
for sphinx-argparse to introspect for that one subcommand. Documented by
example instead:

```bash
tetrak-ocr evaluate --backend tesseract-auto
tetrak-ocr evaluate --all --save
```
