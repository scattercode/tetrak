#!/usr/bin/env python3
"""Generate ground-truth transcripts for the corpus using the Anthropic vision API.

Sends each image in evaluation/ocr/corpus/images/ to Claude and asks it to
transcribe the text as accurately as possible. The result is written to
evaluation/ocr/corpus/expected/<name>.md, which is the reference every backend is
scored against by the evaluation harness and by tests/test_thresholds.py.

This is an occasional step, not part of a normal run: the transcripts are
committed precisely so the reference does not move between runs. Re-run it only
when adding a corpus item, or deliberately refreshing the reference — and note
that refreshing shifts every score in the benchmark, so regenerate the benchmark
alongside it.

Requirements:
    ANTHROPIC_API_KEY must be set in .env or in the environment.
    pip install -e '.[claude]'

Options:
    --overwrite     Replace existing transcripts (default: skip them)
    --fixture PATH  Process a single image instead of the whole corpus
"""

import argparse
import sys
from pathlib import Path

# The Claude backend handles .env loading and the Anthropic API.
from tetrak_ocr.backends.claude import SUPPORTED_EXTENSIONS, ocr_image

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "evaluation" / "ocr" / "corpus"
FIXTURES_DIR = CORPUS_DIR / "images"
EXPECTED_DIR = CORPUS_DIR / "expected"


def process_image(image_path: Path, overwrite: bool) -> None:
    """Transcribe one image and write the expected Markdown file."""
    expected_path = EXPECTED_DIR / f"{image_path.stem}.md"

    if expected_path.exists() and not overwrite:
        print(f"  Skipping (already exists): {image_path.name}")
        return

    print(f"  Transcribing: {image_path.name} ...", end=" ", flush=True)
    text = ocr_image(image_path)
    expected_path.write_text(text.strip() + "\n", encoding="utf-8")
    print(f"→ {expected_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate expected OCR output using the Anthropic vision API."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing expected files (default: skip them).",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        metavar="PATH",
        help="Process a single image instead of all fixtures.",
    )
    args = parser.parse_args()

    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    if args.fixture:
        images = [args.fixture]
    else:
        images = sorted(
            f
            for f in FIXTURES_DIR.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        )

    if not images:
        print("No fixture images found.")
        return

    print(f"Generating expected files for {len(images)} image(s).\n")
    for image_path in images:
        try:
            process_image(image_path, overwrite=args.overwrite)
        except Exception as exc:
            print(f"  ERROR: {image_path.name}: {exc}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()
