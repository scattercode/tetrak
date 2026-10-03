"""Publishing transcripts to a destination.

Deliberately empty. Both pipelines produce transcripts, so a publisher belongs
to neither: putting it inside `tetrak_ocr` would make the audio pipeline depend
on the OCR package to reach a destination it shares.

The shape to follow is `tetrak_ocr.registry`: destinations behind one
interface, discovered from a registry that is the single source of truth, so
adding one touches a single file. Omeka S is the first destination -- see
`deploy/omeka/` for a local instance to develop against -- and
brief 006 (the DAM proof of concept) contemplates a second.
"""
