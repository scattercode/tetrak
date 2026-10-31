"""Which way up a page is, read from the ink, and the turn that rights it.

Scans come in on their side or on their head -- microfilm frames shot however
the pages lay, a postcard turned on the glass -- and nothing in the file says
so. This reads it from the picture, deterministically and with no model, in
two questions asked in order:

1. **Is there text, and do its lines run across or down?** The page is cut
   into a grid, and in each block holding textured ink the variance of the
   row sums is set against the variance of the column sums: lines of text
   make one peaky and the other flat. The median over the blocks decides, so
   a gutter or a page edge that fools a few blocks does not carry the page.
   This works for any script (design research 002: 220 of 221 Armenian
   pages clear the threshold). It is measured at 2000 px on the long side;
   at full resolution the column profile starts to resolve letter strokes
   and the ratio shrinks.

2. **With the lines across, which way is up?** This depends on the script,
   which is why the caller names it rather than leaving it to be guessed:

   - **Latin**: more ink sits above a line's body (ascenders, capitals, dots)
     than below it (descenders), so the share of a line's outer ink lying
     above it is well over a half upright and well under on its head. It
     does not hold for Armenian, whose letters put as much ink below the
     line as above it (design research 002).
   - **Armenian**: which way the open sides of the letters face, after
     Aradhye (2005). Background enclosed by a letter's ink on three sides
     and open upward (the bowl of ս) outweighs that open downward (the arch
     of ո) in every Armenian face measured: 18 registers, every text page
     right both ways up (design research 003). The same measure is poor on
     Latin print and no better than a coin on handwriting.

   Both want detail, so they are measured at up to 4000 px (design research
   002, finding 4).

**Unsure means untouched.** Turning a correct page upside down is worse than
leaving a wrong one alone, so a page is turned only when both answers are
clear; otherwise :class:`Orientation` says why not, for a person to check.
The margins below come from the studies' saved per-page readings, not from
judgement: inside them, every reading the studies called wrong falls.

The Latin measures were written for the Empire on Trial reading site and are
carried here with its two corrections: adjacent maxima in a typeset line's
profile are merged before a line is judged, and an up-share resting on fewer
than half the lines the finder saw is not trusted.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageChops, ImageFilter, ImageOps

from .errors import MissingFeatureError, OcrPipelineError

SCRIPTS = ("latin", "armenian")
"""The scripts whose up/down measure has been measured. Nothing else is offered."""

LINES_SIZE = 2000  # longest side for the line-direction vote
UP_SIZE = 4000  # longest side for the up/down measures, which need the detail
GRID = 12  # blocks per side for the line-direction vote
STRIPS = 8  # vertical strips for finding lines; each lies within one column of a spread
LINES_THRESHOLD = 1.0  # |median log variance ratio| needed to call the line direction
MIN_BLOCKS = 8  # textured blocks needed before a page's vote counts
PAPER_MIN = 96  # a median brightness below this is a title card or a void, not paper
MIN_LINES = 5  # lines needed before the Latin up-share is trusted
MIN_COMPONENTS = 50  # letter-sized shapes needed before the Armenian share is trusted

# How far from a half a share must be before it is believed. Set from the
# studies' per-page results: for Latin, print read at native resolution has
# none wrong and 3 of 36 readings inside 0.05, the Empire on Trial manuscripts
# 2 wrong and 4 inside of 524; for Armenian, 220 text pages have none wrong
# and 10 of 440 readings inside 0.02.
MARGINS = {"latin": 0.05, "armenian": 0.02}

_TURNS = {
    0: None,
    90: Image.Transpose.ROTATE_270,  # PIL turns anticlockwise; this is a quarter turn clockwise
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_90,
}


@dataclass(frozen=True)
class Orientation:
    """What was read from one page, and the turn that rights it."""

    script: str
    turn: int  # clockwise degrees that right the page: 0, 90, 180 or 270; 0 when unsure
    lines: float  # median log(row variance / column variance): > 0 lines run across, < 0 down
    blocks: int  # textured blocks that voted on the line direction
    share: float | None = None  # up share with the lines turned across; None when not measured
    unsure: str | None = None  # why the page is left as it is, or None when the reading is clear

    @property
    def sideways(self) -> bool:
        return self.blocks >= MIN_BLOCKS and self.lines <= -LINES_THRESHOLD

    def describe(self) -> str:
        """One line for a person: what was done, or why nothing was."""
        if self.unsure:
            return f"orientation unsure ({self.unsure}); read as it is"
        if self.turn:
            return f"turned {self.turn}° clockwise to read"
        return "upright"


def require(script: str) -> None:
    """Fail now, not on the first page, if *script* cannot be measured here."""
    if script not in SCRIPTS:
        raise ValueError(
            f"No orientation measure for '{script}'. Choose from: {', '.join(SCRIPTS)}"
        )
    if script == "armenian":
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
        except ImportError:
            raise MissingFeatureError(
                "--orient armenian", "orientation", "NumPy and OpenCV"
            ) from None


def turn(image: Image.Image, degrees: int) -> Image.Image:
    """Rotate clockwise by a multiple of 90 degrees."""
    method = _TURNS[degrees % 360]
    return image.transpose(method) if method is not None else image


def detect(image: Image.Image | Path, script: str) -> Orientation:
    """How many degrees clockwise turn *image* upright, for a page in *script*.

    An EXIF orientation tag is honoured first, so a frame someone has already
    turned is judged as it displays.
    """
    require(script)
    if isinstance(image, Path):
        with Image.open(image) as im:
            grey = ImageOps.exif_transpose(im).convert("L")
    else:
        grey = ImageOps.exif_transpose(image).convert("L")

    small = grey.copy()
    small.thumbnail((LINES_SIZE, LINES_SIZE))
    paper = _median(small)
    if paper < PAPER_MIN:
        return Orientation(script, 0, 0.0, 0, unsure="too dark to be a page of text")
    lines, blocks = _line_direction(_ink(small, paper))

    def unsure(reason: str, share: float | None = None) -> Orientation:
        return Orientation(script, 0, lines, blocks, share, unsure=reason)

    if blocks < MIN_BLOCKS:
        return unsure("no text to read")
    if abs(lines) < LINES_THRESHOLD:
        return unsure("the lines run neither clearly across nor clearly down")

    quarter = 90 if lines < 0 else 0
    across = turn(grey, quarter)
    across.thumbnail((UP_SIZE, UP_SIZE))
    share = _latin_share(across) if script == "latin" else _armenian_share(across)
    if share is None:
        return unsure(_FEW[script])

    margin = MARGINS[script]
    if share >= 0.5 + margin:
        degrees = quarter
    elif share <= 0.5 - margin:
        degrees = (quarter + 180) % 360
    else:
        return unsure(f"cannot tell which way is up: {share:.2f} is too near a half", share)
    return Orientation(script, degrees, lines, blocks, share)


_FEW = {
    "latin": "too few clear lines of writing to tell which way is up",
    "armenian": "too few letters to tell which way is up",
}


@contextmanager
def upright(path: Path, script: str | None) -> Iterator[tuple[Path, Orientation | None]]:
    """The file to read for *path*, turned upright if it needs it.

    Yields ``(path, None)`` when *script* is None, and when the file holds
    more than one page: turning a page inside a document means rewriting the
    document, which this does not do. Otherwise yields the reading and the
    path to transcribe -- *path* itself when no turn is needed, or a turned
    PNG copy with the same stem, in a directory that lasts for the block. The
    scan itself is never written to.

    A file that cannot be decoded is reported as unsure rather than raised:
    the OCR that follows fails on it with the error that belongs to it.
    """
    if script is None:
        yield path, None
        return
    from .imaging import page_count

    if path.suffix.lower() == ".pdf" or page_count(path) > 1:
        yield path, None
        return
    try:
        found = detect(path, script)
    except OcrPipelineError:
        raise
    except Exception as exc:
        yield path, Orientation(script, 0, 0.0, 0, unsure=f"could not be read: {exc}")
        return
    if not found.turn:
        yield path, found
        return
    with Image.open(path) as im, TemporaryDirectory(prefix="tetrak-upright-") as tmp:
        copy = Path(tmp) / f"{path.stem}.png"
        turn(ImageOps.exif_transpose(im), found.turn).save(copy)
        yield copy, found


# Shared by both questions


def _median(grey: Image.Image) -> int:
    hist = grey.histogram()
    half = sum(hist) / 2
    acc = 0
    for value, count in enumerate(hist):
        acc += count
        if acc >= half:
            return value
    return 255


def _ink(grey: Image.Image, paper: int) -> Image.Image:
    """Ink as darkness below the local background, 0 to 255, with large dark regions
    (the film border, page edges, deep shadow) filled with the paper tone first."""
    w, h = grey.size
    # Quarter scale: the regions are big, and MaxFilter is slow.
    dark = grey.resize((max(w // 4, 1), max(h // 4, 1)), Image.Resampling.BOX).point(
        lambda v: 255 if v < 90 else 0
    )
    region = (
        dark.filter(ImageFilter.BoxBlur(2))
        .point(lambda v: 255 if v > 140 else 0)
        .filter(ImageFilter.MaxFilter(5))
    )
    grey = Image.composite(
        Image.new("L", grey.size, paper), grey, region.resize((w, h), Image.Resampling.NEAREST)
    )
    background = grey.filter(ImageFilter.BoxBlur(12))
    # (background - grey - 15) * 4
    return ImageChops.subtract(background, grey, scale=0.25, offset=-60)


def _profile(ink: Image.Image, axis: int) -> list[float]:
    """Mean ink per row (axis 0) or per column (axis 1), 0 to 1."""
    w, h = ink.size
    strip = ink.resize((1, h) if axis == 0 else (w, 1), Image.Resampling.BOX)
    return [v / 255 for v in strip.tobytes()]


# Question 1: which way the lines run


def _line_direction(ink: Image.Image) -> tuple[float, int]:
    w, h = ink.size
    bw, bh = w // GRID, h // GRID
    votes = []
    for j in range(GRID):
        for i in range(GRID):
            block = ink.crop((i * bw, j * bh, (i + 1) * bw, (j + 1) * bh))
            rows, cols = _profile(block, 0), _profile(block, 1)
            mean = sum(rows) / len(rows)
            if not 0.005 <= mean <= 0.5:
                continue  # bare paper, or a solid
            if max(rows) > 8 * mean or max(cols) > 8 * mean:
                continue  # an edge, not texture
            vr, vc = statistics.pvariance(rows), statistics.pvariance(cols)
            if vr + vc == 0:
                continue
            votes.append(math.log((vr + 1e-9) / (vc + 1e-9)))
    if not votes:
        return 0.0, 0
    return statistics.median(votes), len(votes)


# Question 2, Latin: the share of a line's outer ink above it


def _latin_share(grey: Image.Image) -> float | None:
    """The median up-share over the lines found, or None when it is not to be trusted."""
    paper = _median(grey)
    if paper < PAPER_MIN:
        return None
    share, found, seen = _share_above(_ink(grey, paper))
    if found < seen / 2:
        return None  # the finder rejected most of the lines it saw: whatever it measured, it was not the page
    return share


def _smooth(xs: list[float], window: int) -> list[float]:
    half = window // 2
    out = []
    acc = sum(xs[:half])
    n = half
    for i in range(len(xs)):
        if i + half < len(xs):
            acc += xs[i + half]
            n += 1
        if i - half - 1 >= 0:
            acc -= xs[i - half - 1]
            n -= 1
        out.append(acc / n)
    return out


def _lines(rows: list[float]) -> tuple[list[tuple[int, int, int]], list[float], int]:
    """Text lines in a row profile as (upper valley, peak, lower valley), keeping only
    well-formed ones: a peak at least twice its valleys, each side 3 to 80 rows. Also
    returns how many candidate lines there were, well-formed or not."""
    sm = _smooth(rows, 3)
    n = len(sm)
    peaks: list[int] = []
    for y in range(2, n - 2):
        if sm[y] > sm[y - 1] and sm[y] >= sm[y + 1] and sm[y] > 0.01:
            if peaks and y - peaks[-1] < 6:
                if sm[y] > sm[peaks[-1]]:
                    peaks[-1] = y
            else:
                peaks.append(y)

    # A handwritten line is one hump in the profile; a typeset line is a plateau, the
    # x-height body flat for ten rows or more, whose wobble reads as two or three maxima
    # that the valley test below would then reject in pairs. Two maxima with no dip
    # below half the lower of them between them are one line.
    merged: list[int] = []
    for p in peaks:
        if merged and min(sm[merged[-1] : p + 1]) > 0.5 * min(sm[merged[-1]], sm[p]):
            if sm[p] > sm[merged[-1]]:
                merged[-1] = p
        else:
            merged.append(p)
    peaks = merged

    def valley(lo: int, hi: int) -> int:
        # The middle of the lowest run, so neither side is favoured.
        floor = min(sm[lo : hi + 1])
        idx = [y for y in range(lo, hi + 1) if sm[y] <= floor + 1e-9]
        return idx[len(idx) // 2]

    lines = []
    candidates = 0
    for k, p in enumerate(peaks):
        lo = peaks[k - 1] if k else max(0, p - 80)
        hi = peaks[k + 1] if k + 1 < len(peaks) else min(n - 1, p + 80)
        a, b = valley(lo, p), valley(p, hi)
        if 3 <= p - a <= 80 and 3 <= b - p <= 80:
            candidates += 1
            if max(sm[a], sm[b]) <= 0.5 * sm[p]:
                lines.append((a, p, b))
    return lines, sm, candidates


def _share_above(ink: Image.Image) -> tuple[float | None, int, int]:
    """Across all lines found, the median share of outer ink (beyond half the line's
    peak height) that lies above the line rather than below it, with the number of
    lines it rests on and the number of candidate lines the finder saw."""
    w, h = ink.size
    sw = w // STRIPS
    shares = []
    seen = 0
    for s in range(STRIPS):
        lines, sm, candidates = _lines(_profile(ink.crop((s * sw, 0, (s + 1) * sw, h)), 0))
        seen += candidates
        for a, p, b in lines:
            half = sm[p] * 0.5
            ha = next((y for y in range(p, a - 1, -1) if sm[y] < half), a)
            hb = next((y for y in range(p, b + 1) if sm[y] < half), b)
            above, below = sum(sm[a:ha]), sum(sm[hb + 1 : b + 1])
            if above + below > 0:
                shares.append(above / (above + below))
    if len(shares) < MIN_LINES:
        return None, len(shares), seen
    return statistics.median(shares), len(shares), seen


# Question 2, Armenian: which way the open sides of the letters face


def _armenian_share(grey: Image.Image) -> float | None:
    """Concavity area open upward over that open upward or downward, summed over the
    letter-sized shapes on the page; None when there are too few to judge."""
    import cv2
    import numpy as np

    pixels = np.asarray(grey)
    background = cv2.blur(pixels, (51, 51))
    # Divide out the local background so shading and gutters do not bind to the letters.
    norm = np.clip(
        pixels.astype(np.float32) / np.maximum(background.astype(np.float32), 1.0) * 200.0, 0, 255
    ).astype(np.uint8)
    _, ink = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    body = stats[1:, cv2.CC_STAT_HEIGHT][stats[1:, cv2.CC_STAT_AREA] >= 12]
    if len(body) < MIN_COMPONENTS:
        return None
    median_height = float(np.median(body))
    up = down = kept = 0
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        # Letter-sized, and not shaped like a rule or a picture.
        if area < 12 or not (0.5 * median_height <= h <= 2.5 * median_height):
            continue
        if w > 4 * h or h > 6 * max(w, 1):
            continue
        u, d = _open_up_down(labels[y : y + h, x : x + w] == i)
        up += u
        down += d
        kept += 1
    if kept < MIN_COMPONENTS or up + down == 0:
        return None
    return up / (up + down)


def _open_up_down(mask) -> tuple[int, int]:
    """Background within one shape enclosed by its ink left, right and on one side
    vertically: the area open upward, and the area open downward."""
    import numpy as np

    above = np.maximum.accumulate(mask, axis=0)  # ink at or above, per column
    below = np.maximum.accumulate(mask[::-1], axis=0)[::-1]
    sides = (
        np.maximum.accumulate(mask, axis=1) & np.maximum.accumulate(mask[:, ::-1], axis=1)[:, ::-1]
    )
    bg = ~mask & sides
    return int((bg & ~above & below).sum()), int((bg & above & ~below).sum())
