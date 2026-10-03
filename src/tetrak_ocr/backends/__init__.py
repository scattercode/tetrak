"""OCR backends.

Each module here exposes ``ocr_image(path) -> str`` and a
``SUPPORTED_EXTENSIONS`` set. Prefer :func:`tetrak_ocr.registry.get_backend`
over importing these directly — it reports missing extras usefully.
"""
