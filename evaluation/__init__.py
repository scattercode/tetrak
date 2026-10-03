"""Evaluation harnesses and corpora, one subpackage per pipeline.

Deliberately not part of the installed package: benchmarking is something you
do *to* a pipeline from a checkout, and it needs the corpus that sits beside
the harness. `tetrak-ocr evaluate` imports `evaluation.ocr` from the
repository root.

Each pipeline keeps its harness and its corpus together under its own
subpackage, so a second pipeline adds a directory rather than interleaving
with the first.
"""
