#!/usr/bin/env python3
"""OCR a file using PaddleOCR-VL and return the extracted text.

PaddleOCR-VL is a document vision-language model: a ~0.9B-parameter
NaViT-style vision encoder over a small ERNIE decoder, published by Baidu
under Apache 2.0. Unlike the classical `paddle` backend, which detects
glyph boxes and classifies each one, this *generates* the transcript
conditioned on the image.

It ships in the same `paddleocr` package as `paddle` and is a separate
backend rather than a flag on it, for the same reason `tesseract-auto`
is separate: the harness scores backends, so the difference between the
two becomes a measurement instead of a claim.

Requires:
    pip install "tetrak-ocr[paddle-vl]"

Usage (standalone):
    tetrak-ocr ocr workspace/scans/my-postcard.jpg --backend paddle-vl

On first run the model weights (~1 GB) download automatically and are
cached under ~/.paddlex/official_models/, so the first call is slow and
later ones are not. It is slow even warm -- on CPU a dense newspaper page
took over ten minutes against tesseract's fraction of a second -- which
makes it a batch backend rather than an interactive one.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path

# PaddlePaddle's C++ layer reads these as glog initialises, which happens
# during the import below -- so they are set before it rather than after,
# where they had nothing left to suppress. See the note in paddle.py.
os.environ.setdefault("GLOG_v", "0")
os.environ.setdefault("GLOG_logtostderr", "0")

try:
    from paddleocr import PaddleOCRVL
except ImportError:  # pragma: no cover - depends on installed extras
    _IMPORT_OK = False
else:
    # The class importing is not enough. PaddleOCRVL builds its pipeline
    # through paddlex, and without paddlex's own `ocr` extra it raises a
    # DependencyError at construction -- so a machine with paddleocr but
    # not paddlex[ocr] would have the registry report this backend as
    # runnable and then fail on the first file with paddlex's error rather
    # than our MissingBackendError. Probed by spec rather than imported,
    # because importing paddlex is slow and the registry imports every
    # backend just to list them.
    _IMPORT_OK = importlib.util.find_spec("paddlex") is not None

# Silenced by name and at construction rather than at import, for the
# reason paddle.py documents at length: the registry imports every backend
# to report which are installed, so a module-level `logging.disable` here
# would mute warnings across the whole process on machines that have no
# paddleocr at all.
_NOISY_LOGGERS = ("ppocr", "paddle", "paddleocr", "paddlex")

# The pipeline is pinned, not left to the package default.
#
# `PaddleOCRVL()` resolved to v1.0 when brief 009 was written and v1.6 a
# month later. Unpinned, a routine `pip install` silently re-measures a
# different model: the benchmark moves, every published figure moves with
# it, and nothing in the diff says why. Bump this deliberately, and re-run
# `evaluate --all --save` in the same commit.
PIPELINE_VERSION = "v1.6"

# In-process inference only.
#
# `PaddleOCRVL` also speaks to vLLM, SGLang, FastDeploy, MLX and llama.cpp
# servers, and takes a `vl_rec_server_url` and `vl_rec_api_key` to reach
# them. A backend advertised as local that posted archive images to a
# third-party endpoint would breach the whole positioning, and do it
# quietly -- brief 009 raised that risk for GLM-OCR and it turned out to
# apply here too. "native" is named explicitly rather than left to the
# default so that a future change of default cannot start sending images
# off the machine; tests assert no server URL and no key are ever passed.
VL_BACKEND = "native"

# Rasters and PDFs alike. Unlike `paddle`, this backend needs no
# `reject_multi_page` guard: it walks every page of a multi-page PDF and
# every frame of a multi-frame TIFF, returning one result object per page
# with that page's own text. Verified before the guard was omitted, on a
# synthesised three-page PDF and a synthesised three-frame TIFF, because
# no corpus fixture is actually multi-frame -- both `.tif` fixtures are
# single-frame and the multi-page material is all PDF.
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".pdf"}

# Blocks that hold no transcribable text. The model labels layout regions
# as it parses, and an image or a seal contributes a region with no words
# on the page -- including it would add markup or a placeholder to a
# transcript scored against plain text.
_NON_TEXT_LABELS = frozenset({"image", "figure", "seal", "chart", "formula_number"})

# Module-level singleton: constructing the pipeline loads ~1 GB of weights.
_ocr_instance: PaddleOCRVL | None = None


def _get_ocr() -> PaddleOCRVL:
    """Return (and lazily build) the module-level PaddleOCR-VL pipeline."""
    global _ocr_instance
    if _ocr_instance is None:
        for name in _NOISY_LOGGERS:
            logging.getLogger(name).setLevel(logging.ERROR)
        _ocr_instance = PaddleOCRVL(
            pipeline_version=PIPELINE_VERSION,
            vl_rec_backend=VL_BACKEND,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
        )
    return _ocr_instance


def _page_text(page) -> str:
    """Plain text from one parsed page, in the model's reading order.

    The model natively emits structured markdown -- headings, tables,
    formulae. That structure is a real capability, but our metric scores
    character similarity against plain-text ground truth, so returning the
    markdown document would penalise the backend for its own formatting.
    The recognised text is pulled out of the structured result instead,
    exactly as `paddle` pulls it from `rec_texts`.

    Structured output belongs to brief 008's searchable-PDF and layout
    work, not here.
    """
    parts = []
    for block in page["parsing_res_list"]:
        if (block.label or "").lower() in _NON_TEXT_LABELS:
            continue
        content = block.content
        if content and str(content).strip():
            parts.append(str(content).strip())
    return "\n".join(parts)


def ocr_image(path: Path) -> str:
    """Extract text from an image or PDF using PaddleOCR-VL.

    Args:
        path: Path to the file.

    Returns:
        Extracted text, one block per line, pages joined in order.

    Raises:
        ValueError: If the file extension is not supported.
        FileNotFoundError: If the file does not exist.
        RuntimeError: If the backend's optional dependency is missing.
    """
    path = Path(path)

    if not _IMPORT_OK:
        raise RuntimeError(
            'paddle-vl is unavailable: install it with pip install "tetrak-ocr[paddle-vl]"'
        )

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{path.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    results = _get_ocr().predict(str(path))

    # No TIFF-to-PNG conversion, deliberately. `paddle` converts because
    # its pipeline "may not handle all TIFF variants", but that conversion
    # flattens a multi-frame TIFF to frame 0 -- which is precisely why that
    # backend then has to refuse multi-page files. This pipeline reads the
    # corpus's archival TIFFs directly, frames and all, so converting would
    # discard pages for no gain.
    return "\n".join(text for page in results if (text := _page_text(page)))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCR a file using PaddleOCR-VL.")
    parser.add_argument("path", type=Path, help="Path to the image or PDF.")
    args = parser.parse_args()

    print(ocr_image(args.path))
