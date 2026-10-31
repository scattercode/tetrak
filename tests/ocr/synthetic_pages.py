"""Synthetic page images for the orientation tests.

Drawn from a seed rather than loaded, so the fast loop needs no data files and
no page needs a licence. Each stands in for what one of
:mod:`tetrak_ocr.orientation`'s measures reads, not for a real hand or face:

- :func:`latin_page`: lines of zigzag letters, some with a stroke above the
  line's body and fewer with one below. That is the asymmetry the Latin
  up-share reads.
- :func:`armenian_page`: lines of separate u- and n-shaped letters, more of
  them u. That is what the concavity share reads: in Armenian type the shapes
  open upward (ս, ւ) outweigh those open downward (ո, ռ).

Both are upright as drawn; a test turns them.
"""

from __future__ import annotations

import random

from PIL import Image, ImageDraw

PAPER = 225
INK = 50
SIZE = (1400, 2000)


def latin_page(
    seed: int = 0,
    lines: int | None = None,
    ascenders: float = 0.45,
    descenders: float = 0.12,
    size: tuple[int, int] = SIZE,
) -> Image.Image:
    """Handwriting-like lines; `ascenders` and `descenders` are the share of
    letters with a stroke above or below the body."""
    rng = random.Random(seed)
    body = 14

    def letters(draw: ImageDraw.ImageDraw, x: int, baseline: int) -> int:
        word = []
        for _ in range(rng.randint(3, 8)):
            w = rng.randint(7, 12)
            word += [(x, baseline), (x + w // 2, baseline - body)]
            if rng.random() < ascenders:
                draw.line(
                    [(x + w // 2, baseline - body), (x + w // 2, baseline - 2 * body)],
                    fill=INK,
                    width=2,
                )
            if rng.random() < descenders:
                draw.line([(x + w, baseline), (x + w, baseline + body)], fill=INK, width=2)
            x += w
        word.append((x, baseline))
        draw.line(word, fill=INK, width=2)
        return x

    return _page(rng, size, lines, body, letters)


def armenian_page(
    seed: int = 0,
    lines: int | None = None,
    open_up: float = 0.65,
    size: tuple[int, int] = SIZE,
) -> Image.Image:
    """Lines of separate letters, each a u (open upward) or an n (open downward);
    `open_up` is the share of u."""
    rng = random.Random(seed)
    body = 14

    def letters(draw: ImageDraw.ImageDraw, x: int, baseline: int) -> int:
        for _ in range(rng.randint(3, 8)):
            w = rng.randint(8, 12)
            top, bottom = baseline - body, baseline
            if rng.random() < open_up:
                shape = [(x, top), (x, bottom), (x + w, bottom), (x + w, top)]
            else:
                shape = [(x, bottom), (x, top), (x + w, top), (x + w, bottom)]
            draw.line(shape, fill=INK, width=2)
            x += w + 4  # a gap, so each letter is its own shape
        return x

    return _page(rng, size, lines, body, letters)


def _page(rng: random.Random, size, lines, body, letters) -> Image.Image:
    w, h = size
    margin = 100
    pitch = 4 * body
    im = Image.new("L", size, PAPER)
    draw = ImageDraw.Draw(im)
    baseline = margin + 2 * body
    count = 0
    while baseline + 2 * body <= h - margin and (lines is None or count < lines):
        right = margin + int((w - 2 * margin) * rng.uniform(0.7, 1.0))  # a ragged line end
        x = margin + rng.randint(0, 30)
        while x < right:
            x = letters(draw, x, baseline) + rng.randint(10, 18)  # the gap between words
        baseline += pitch
        count += 1
    return im


def blank(size: tuple[int, int] = SIZE) -> Image.Image:
    return Image.new("L", size, PAPER)


def title_card(size: tuple[int, int] = SIZE) -> Image.Image:
    """A dark frame, as a reel's title card or a void between frames reads."""
    im = Image.new("L", size, 30)
    ImageDraw.Draw(im).rectangle((500, 900, 900, 1100), fill=230)
    return im
