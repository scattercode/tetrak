"""The OCR benchmark: harness, corpus and results.

`harness.py` scores every installed backend over `corpus/images/` against the
reference transcripts in `corpus/expected/`, and writes `benchmark.csv`, which
the documentation site reads at build time.

`reading_order.py` scores the column-aware ordering of each span-carrying
backend's regions against the line order a positioned layer reads back as,
on the same fixtures, and writes `reading_order.csv` for the site likewise.
"""
