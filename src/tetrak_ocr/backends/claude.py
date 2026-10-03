#!/usr/bin/env python3
"""OCR a single image or PDF file using the Anthropic Claude vision API.

This module exposes the same interface as every other backend --
``SUPPORTED_EXTENSIONS`` and ``ocr_image(path) -> str`` -- so that the registry,
the batch pipeline and the evaluation harness can swap between them on a single
command-line flag.

Requires:
    - An ANTHROPIC_API_KEY set in the environment or in a .env file.
    - pip install anthropic python-dotenv

Usage (standalone):
    tetrak-ocr ocr workspace/scans/my-postcard.jpg --backend claude
    tetrak-ocr ocr workspace/scans/my-document.pdf --backend claude

Unlike the Tesseract backend, no local OCR engine is required and no
preprocessing is performed — Claude interprets the file directly.
PDFs are sent as base64-encoded document blocks (no conversion needed).
"""

from __future__ import annotations

import base64
from pathlib import Path

from ..imaging import reject_multi_page

try:
    import anthropic
except ImportError:  # pragma: no cover - depends on installed extras
    _IMPORT_OK = False
else:
    _IMPORT_OK = True

# Load a .env so ANTHROPIC_API_KEY can live in a file rather than the shell.
#
# Searched from the working directory upwards, rather than derived from
# __file__. The path here used to be `__file__.parent.parent`, which was the
# repository root while this module lived in scripts/; moving it to
# src/tetrak_ocr/backends/ put it two levels deeper, so it resolved to
# src/tetrak_ocr/.env -- a file that has never existed. Nothing failed at
# import, and the backend then failed on every single call with "Could not
# resolve authentication method".
#
# Walking up from the working directory is also the right behaviour for an
# installed copy, where there is no repository root to point at: it finds the
# .env belonging to whatever project the user is running in.
try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(usecwd=True))
except ImportError:
    pass


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".pdf"}

# The Claude model used for transcription.
MODEL = "claude-opus-4-8"

# Maximum output tokens for one transcription.  A 21-page souvenir programme
# transcribes to roughly 7,000 tokens, so this leaves substantial headroom.
# Anything above ~16,000 must stream — see the call site.
MAX_OUTPUT_TOKENS = 64000

# The prompt sent alongside each image.
TRANSCRIPTION_PROMPT = """\
Please transcribe all of the text visible in this image as accurately as possible.

Rules:
- Preserve the original wording exactly — do not paraphrase or correct errors.
- Preserve paragraph breaks.
- Do not add formatting such as headers, bullet points, or bold unless they
  genuinely appear in the original.
- If a word is unclear, make your best guess and continue — do not add notes or
  explanations.
- Output only the transcribed text. Do not add any preamble such as "Here is the
  transcription:" — just the text itself.
"""


def _to_base64(path: Path) -> tuple[str, str]:
    """Encode a file as base64 and return (data, media_type).

    TIFF images are converted to PNG in memory using Pillow before encoding.
    PDFs are encoded directly and returned as application/pdf.

    Returns:
        A tuple of (base64-encoded string, MIME type string).
    """
    suffix = path.suffix.lower()

    if suffix in {".jpg", ".jpeg"}:
        return base64.standard_b64encode(path.read_bytes()).decode(), "image/jpeg"
    elif suffix == ".png":
        return base64.standard_b64encode(path.read_bytes()).decode(), "image/png"
    elif suffix in {".tif", ".tiff"}:
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.open(path).save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode(), "image/png"
    elif suffix == ".pdf":
        return base64.standard_b64encode(path.read_bytes()).decode(), "application/pdf"
    else:
        raise ValueError(f"Unsupported file type for Claude backend: {suffix}")


def ocr_image(path: Path) -> str:
    """Extract text from an image file using the Claude vision API.

    Args:
        path: Path to the image file.

    Returns:
        The transcribed text as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is not supported.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{path.suffix}' for Claude backend. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Multi-page TIFF: this backend reads frame 0 only, so refuse rather than
    # return page one as though it were the document. See tetrak_ocr.imaging.
    reject_multi_page(path, "claude")

    encoded, media_type = _to_base64(path)
    client = anthropic.Anthropic()

    if media_type == "application/pdf":
        file_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": media_type, "data": encoded},
        }
    else:
        file_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": encoded},
        }

    # Stream: at this max_tokens a non-streaming request risks the SDK's HTTP
    # timeout on long documents.
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        messages=[
            {
                "role": "user",
                "content": [
                    file_block,
                    {"type": "text", "text": TRANSCRIPTION_PROMPT},
                ],
            }
        ],
    ) as stream:
        message = stream.get_final_message()

    # Fail loudly rather than returning a partial transcription.  This backend
    # generates the ground truth the whole benchmark is scored against, so a
    # silently truncated result corrupts every downstream number.  It has
    # happened: at the previous 4096-token limit the 21-page souvenir programme
    # was cut off two thirds of the way through, and because the cut-off point
    # was reproducible, Claude appeared to score 0.95 against its own truncated
    # reference while the local backends were penalised for transcribing the
    # rest of the document.
    if message.stop_reason == "max_tokens":
        raise RuntimeError(
            f"Transcription of {path.name} hit the {MAX_OUTPUT_TOKENS}-token "
            "output limit and is incomplete. Raise MAX_OUTPUT_TOKENS, or split "
            "the document, and re-run. Do not use this output as ground truth."
        )
    if message.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined to transcribe {path.name}.")

    return "".join(block.text for block in message.content if block.type == "text")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCR a single image using the Claude vision API.")
    parser.add_argument("path", type=Path, help="Path to the image file.")
    args = parser.parse_args()

    print(ocr_image(args.path))
