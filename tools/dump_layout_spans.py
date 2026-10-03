#!/usr/bin/env python3
"""Cache positioned OCR output for the layout experiments, once.

Brief 012 Stage 3 asks whether recursive XY-cut beats the single-gutter
split in :mod:`tetrak_ocr.layout`, and the rule is that it only ships if
it wins on real fixtures. Answering that means serialising the *same*
detected boxes several ways and scoring each -- so re-running OCR per
variant would spend fifteen minutes to change one function.

Detection is also the part that does not vary: reading order is computed
from box geometry, which comes from EasyOCR's CRAFT detector and is the
same whichever recogniser reads the crops. So the boxes are cached once
here, and every serialisation experiment afterwards is instant and reads
exactly the same input -- which also makes the comparison fair by
construction rather than by care.

Input is an evaluation set in the harvester's shape, as
``tetrak-hy-trainer``'s ``scripts/build_eval_sets.py`` produces::

    <eval-dir>/manifest.json
    <eval-dir>/images/<page>.jpg
    <eval-dir>/text/<page>.txt

Output is one JSON file per evaluation set: page number -> the spans, as
``{text, bbox, confidence}`` with bbox already reduced to the
``(left, top, right, bottom)`` pixel convention :mod:`tetrak_ocr.layout`
uses. The transcripts are not copied -- the scorer reads them from the
evaluation set, so there is one copy of the truth.

Prerequisites: easyocr and torch. Point ``--bundle`` at a packaged
bundle directory from the trainer (``runs/<run>/bundle``), which carries
``tetrak_hy.{pth,yaml,py}``.

    .venv/bin/python tools/dump_layout_spans.py \\
        --eval-root ../tetrak-hy-trainer/runs/eval \\
        --bundle ../tetrak-hy-trainer/runs/v6/bundle \\
        --out evaluation/layout/spans

``--wordlist`` decodes with the released word list, as the shipped
backend does from brief 013 on. The cached spans are then the shipped
recogniser's output, not greedy decoding's.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

NETWORK_NAME = "tetrak_hy"


def build_reader(bundle: Path):
    """An EasyOCR reader wired to a packaged bundle.

    ``["en"]`` rather than ``["hy"]`` is not a placeholder: EasyOCR ships
    no ``hy_char.txt``, so ``["hy"]`` raises FileNotFoundError, and the
    language list is inert for a custom recognition network anyway.
    """
    import easyocr

    return easyocr.Reader(
        ["en"],
        recog_network=NETWORK_NAME,
        user_network_directory=str(bundle),
        model_storage_directory=str(bundle),
        verbose=False,
    )


DECODER = "greedy"


def use_wordlist(reader, wordlist: Path) -> None:
    """Decode with ``tetrak_hy.lexicon`` and *wordlist*, as the shipped backend does.

    The cached text is then what ``easyocr-hy`` emits when its library
    has released a word list (brief 013), so the register table's own row
    measures the shipped decoder rather than greedy decoding.
    """
    global DECODER
    from tetrak_hy import lexicon

    lexicon.use_lexicon(reader, lexicon.load_wordlist(wordlist))
    DECODER = "beamsearch"


def spans_for_page(reader, image: Path) -> list[dict]:
    """Every detected box on one page, as a serialisable span.

    EasyOCR returns each box as four corner points, which allows for
    rotated text; the layout module works in axis-aligned rectangles, so
    the corners are reduced to their extremes here rather than in the
    scorer. Rotation is not something these scans have, and pretending
    otherwise downstream would only make the geometry harder to read.
    """
    spans = []
    for corners, text, confidence in reader.readtext(
        str(image), detail=1, paragraph=False, decoder=DECODER
    ):
        xs = [float(point[0]) for point in corners]
        ys = [float(point[1]) for point in corners]
        spans.append(
            {
                "text": text,
                "bbox": [min(xs), min(ys), max(xs), max(ys)],
                "confidence": float(confidence) if confidence is not None else None,
            }
        )
    return spans


def dump_set(reader, eval_dir: Path, out_dir: Path) -> tuple[int, int]:
    """Cache one evaluation set. Returns (pages, spans)."""
    manifest = json.loads((eval_dir / "manifest.json").read_text(encoding="utf-8"))
    pages: dict[str, list[dict]] = {}
    total = 0
    for entry in manifest["pages"]:
        image = eval_dir / "images" / f"{entry['page_number']}.jpg"
        if not image.exists():
            continue
        spans = spans_for_page(reader, image)
        pages[str(entry["page_number"])] = spans
        total += len(spans)
        print(f"  p{entry['page_number']}: {len(spans)} spans", flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"eval_dir": str(eval_dir), "index": manifest.get("index"), "pages": pages}
    (out_dir / f"{eval_dir.name}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return len(pages), total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--set", action="append", help="only this evaluation set; repeatable")
    parser.add_argument(
        "--wordlist",
        type=Path,
        default=None,
        help="decode with tetrak_hy.lexicon and this word list (wordlist.tsv.gz)",
    )
    args = parser.parse_args(argv)

    sets = sorted(
        directory
        for directory in args.eval_root.iterdir()
        if (directory / "manifest.json").exists() and (directory / "images").is_dir()
    )
    if args.set:
        wanted = set(args.set)
        sets = [directory for directory in sets if directory.name in wanted]
    if not sets:
        print(f"no evaluation sets under {args.eval_root}", file=sys.stderr)
        return 1

    reader = build_reader(args.bundle)
    if args.wordlist:
        use_wordlist(reader, args.wordlist)
    for eval_dir in sets:
        print(f"=== {eval_dir.name} ===", flush=True)
        pages, spans = dump_set(reader, eval_dir, args.out)
        print(f"{eval_dir.name}: {pages} pages, {spans} spans", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
