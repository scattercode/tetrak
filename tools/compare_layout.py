#!/usr/bin/env python3
"""Score reading-order strategies against each other on cached spans.

Brief 012 Stage 3 proposes recursive XY-cut in place of the single-gutter
split, under an explicit rule: it ships only if it beats the gutter on
multi-column fixtures. This is the measurement that decides, and it is
built to make the decision hard to fudge.

Both strategies serialise the *same* cached boxes, from
``tools/dump_layout_spans.py``, so nothing but the ordering differs.

Two metrics, and the pairing is the point:

``chr`` (character similarity) is order-sensitive and is the metric
reading order exists to move. ``wrd`` (word recall) is order-insensitive
and should be **unchanged** between strategies -- both emit the same
tokens, only in a different sequence. A serialisation that moves word
recall is not reordering text, it is losing or duplicating it, so the
column is printed as a tripwire rather than as a result.

Detector order is scored too, as the floor: the ordering both strategies
are improving on, and the number the trainer's own evaluation reports
because it applies no layout at all.

    .venv/bin/python tools/compare_layout.py \\
        --spans evaluation/layout/spans \\
        --eval-root ../tetrak-hy-trainer/runs/eval
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from tetrak_ocr.accuracy import character_similarity, word_recall  # noqa: E402
from tetrak_ocr.layout import (  # noqa: E402
    TextSpan,
    find_gutter,
    group_lines,
    to_text,
    xy_cut_lines,
)


def gutter_blocks(spans: list[TextSpan], gutter: float) -> list[list[TextSpan]]:
    """The single-gutter split, frozen here as the strategy XY-cut replaced.

    This is a copy of ``layout._blocks`` as it stood before brief 012
    Stage 3, kept in the measurement tool rather than in the module so
    the comparison has something to compare against. Once XY-cut became
    the serialiser, calling ``layout.to_text`` for both columns of the
    table silently scored the same code twice -- a comparison that can
    only ever report a tie.

    It is deliberately frozen. Its job is to answer "what did the old
    strategy score on this material?", and that answer must not move when
    the live module changes.
    """
    unplaced = [span for span in spans if not span.bbox]
    placed = [span for span in spans if span.bbox]
    full = sorted(
        (span for span in placed if span.bbox[0] < gutter < span.bbox[2]),
        key=lambda span: span.baseline,
    )
    left = [span for span in placed if span.bbox[2] <= gutter]
    right = [span for span in placed if span.bbox[0] >= gutter]

    blocks: list[list[TextSpan]] = []
    previous = float("-inf")
    for divider in full:
        limit = divider.baseline
        blocks.append([s for s in left if previous < s.baseline <= limit])
        blocks.append([s for s in right if previous < s.baseline <= limit])
        blocks.append([divider])
        previous = limit
    blocks.append([s for s in left if s.baseline > previous])
    blocks.append([s for s in right if s.baseline > previous])
    return [block for block in ([unplaced, *blocks]) if block]


def gutter_to_text(spans: list[TextSpan]) -> str:
    """The pre-XY-cut serialisation, for the comparison's baseline column."""
    if not spans:
        return ""
    gutter = find_gutter(spans)
    lines = (
        group_lines(spans)
        if gutter is None
        else [line for block in gutter_blocks(spans, gutter) for line in group_lines(block)]
    )
    return "\n".join(" ".join(span.text for span in line) for line in lines)


def load_spans(payload: dict, page: str) -> list[TextSpan]:
    return [
        TextSpan(
            text=item["text"],
            bbox=tuple(item["bbox"]) if item["bbox"] else None,
            confidence=item.get("confidence"),
        )
        for item in payload["pages"][page]
    ]


def detector_order_text(spans: list[TextSpan]) -> str:
    """What the trainer's evaluation sees: boxes joined as detected."""
    return "\n".join(span.text for span in spans)


def xy_text(spans: list[TextSpan]) -> str:
    return "\n".join(" ".join(span.text for span in line) for line in xy_cut_lines(spans))


def lines_only_text(spans: list[TextSpan]) -> str:
    """Baseline grouping with no column awareness at all."""
    return "\n".join(" ".join(span.text for span in line) for line in group_lines(spans))


def shipped_text(spans: list[TextSpan]) -> str:
    """What a caller of the module actually gets.

    layout.to_text, whole -- XY-cut ordering plus de-hyphenation. The
    xy-cut column above stops at the ordering so the two halves of Stage
    3 can be read apart; this one is the sum, and is the only column that
    tracks the shipped behaviour when either half changes.
    """
    return to_text(spans)


STRATEGIES = {
    "detector": detector_order_text,
    "lines": lines_only_text,
    "gutter": gutter_to_text,
    "xy-cut": xy_text,
    "shipped": shipped_text,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spans", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--set", action="append", help="only this set; repeatable")
    parser.add_argument("--per-page", action="store_true", help="print every page, not just means")
    args = parser.parse_args(argv)

    files = sorted(args.spans.glob("*.json"))
    if args.set:
        wanted = set(args.set)
        files = [path for path in files if path.stem in wanted]
    if not files:
        print(f"no cached spans under {args.spans}", file=sys.stderr)
        return 1

    names = list(STRATEGIES)
    header = f"{'register':<24}" + "".join(f"{name:>20}" for name in names)
    print(header)
    print(f"{'':<24}" + "".join(f"{'chr / wrd':>20}" for _ in names))
    print("-" * len(header))

    totals: dict[str, list[tuple[float, float]]] = {name: [] for name in names}
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        eval_dir = args.eval_root / path.stem
        scores: dict[str, list[tuple[float, float]]] = {name: [] for name in names}

        for page in sorted(payload["pages"], key=int):
            truth_file = eval_dir / "text" / f"{page}.txt"
            if not truth_file.exists():
                continue
            truth = truth_file.read_text(encoding="utf-8")
            spans = load_spans(payload, page)
            for name, strategy in STRATEGIES.items():
                text = strategy(spans)
                scores[name].append((character_similarity(text, truth), word_recall(text, truth)))
            if args.per_page:
                cells = "".join(
                    f"{scores[name][-1][0]:>9.4f} /{scores[name][-1][1]:>8.4f}" for name in names
                )
                print(f"  {path.stem[:14]:<12} p{page:<8}" + cells)

        if not scores[names[0]]:
            continue
        cells = ""
        for name in names:
            chr_mean = sum(c for c, _ in scores[name]) / len(scores[name])
            wrd_mean = sum(w for _, w in scores[name]) / len(scores[name])
            totals[name].append((chr_mean, wrd_mean))
            cells += f"{chr_mean:>9.4f} /{wrd_mean:>8.4f}"
        print(f"{path.stem:<24}" + cells)

    print("-" * len(header))
    cells = ""
    for name in names:
        chr_mean = sum(c for c, _ in totals[name]) / len(totals[name])
        wrd_mean = sum(w for _, w in totals[name]) / len(totals[name])
        cells += f"{chr_mean:>9.4f} /{wrd_mean:>8.4f}"
    print(f"{'MEAN OVER REGISTERS':<24}" + cells)
    return 0


if __name__ == "__main__":
    sys.exit(main())
