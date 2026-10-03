"""The OCR benchmark: harness, corpus and results.

`harness.py` scores every installed backend over `corpus/images/` against the
reference transcripts in `corpus/expected/`, and writes `benchmark.csv`, which
the documentation site reads at build time.
"""
