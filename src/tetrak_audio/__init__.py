"""Audio transcription, alongside the OCR pipeline rather than inside it.

Deliberately empty. The package exists so the second pipeline has an obvious
home before there is code to put in it, rather than being bolted onto
`tetrak_ocr` later because that is where the machinery happened to live.

The shape to follow is `tetrak_ocr`: backends behind one interface, a
`registry` module that is the single source of truth for what exists, and a
batch pipeline that resolves its directories from the working directory. That
uniformity is what lets the CLI, the harness and the docs treat backends
interchangeably.

Nothing here should import from `tetrak_ocr`, and `tetrak_ocr` must never
import from here. They share a distribution, not a dependency.
"""
