"""Positioned text: the vocabulary shared by the backends and the PDF writer.

An OCR engine knows more than the string it returns: four of the six backends
here compute a box per recognised region and then discard it, because the
registry contract is `-> str`. This module is where that information has a
shape, so the backends that keep it can agree on what it means.

Two backends read through it: the vision backend, whose reading-order logic
this originally was, lifted out and tested, and `easyocr-hy`, which needs the
column handling because the Armenian pages it exists for are set in two
columns. It is deliberately not wired into the searchable PDF
writer: a *positioned* text layer measured worse on reading order than the
plain transcript, badly so on multi-column pages, and that is what a screen
reader announces. See brief 008 (searchable PDF). The boxes become
load-bearing at ALTO/hOCR, where coordinates are the whole point.

Standard library only, so the fast tests can use it with no OCR stack
installed.

**This module has a twin.** `tetrak_hy_trainer.align` (in the public
tetrak-hy-trainer repository) carries its own copy of the gutter detection,
the baseline line-grouping and the three straddle constants below, because
that repository is public and this one is not, so they cannot share code. The
duplication is deliberate; the drift is not. A fix to the column logic here is
worth porting there, and vice versa -- the two solve the same problem on the
same two-column pages, and diverge only in what they do with a span that
crosses the gutter: this one must place it (dropping text is not an option
when the output *is* the text), the harvester drops it (the transcripts omit
running heads, so it has no truth token to pair with).

Coordinates
-----------
`TextSpan.bbox` is **pixels with a top-left origin** -- the Pillow convention.
That choice is deliberate, because three conventions are in play:

    Pillow, Tesseract, EasyOCR, Paddle   pixels,     top-left origin
    Apple Vision                         normalised, bottom-left origin
    PDF                                  points,     bottom-left origin

Four of the five sources already speak the Pillow convention, so it wins.
Vision converts at its own boundary and the writer converts once on the way
out. Anything in between is unambiguous.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class TextSpan:
    """One recognised piece of text, and where it sits on the page.

    Attributes:
        text:       The recognised characters.
        bbox:       (left, top, right, bottom) in pixels, top-left origin, or
                    None when the engine cannot say. A span with no box is not
                    an error -- `marker` and `claude` return prose and never
                    have one -- it simply cannot be positioned.
        confidence: 0-100 where the engine reports it, otherwise None.
    """

    text: str
    bbox: tuple[float, float, float, float] | None = None
    confidence: float | None = None

    @property
    def baseline(self) -> float:
        """The y used to group spans into lines. See `group_lines`."""
        return self.bbox[3] if self.bbox else 0.0

    @property
    def left(self) -> float:
        """The x used to order spans within a line."""
        return self.bbox[0] if self.bbox else 0.0

    @property
    def height(self) -> float:
        return (self.bbox[3] - self.bbox[1]) if self.bbox else 0.0


def _default_tolerance(spans: list[TextSpan]) -> float:
    """How far apart two spans can sit vertically and still be one line.

    Derived from the material rather than fixed, because a tolerance in pixels
    means nothing without knowing how big the page is: 10px separates lines on
    a postcard and splits a word on a 600dpi broadsheet. Half the median span
    height tracks the type size instead, which is the thing that actually
    determines line spacing.

    Too small and one line fragments into columns; too large and separate lines
    merge. The vision backend arrived at 1% of page height by experiment, and
    on its material this rule lands in the same place.
    """
    heights = [span.height for span in spans if span.bbox and span.height > 0]
    return statistics.median(heights) * 0.5 if heights else 0.0


def group_lines(spans: list[TextSpan], line_tolerance: float | None = None) -> list[list[TextSpan]]:
    """Bucket spans into visual lines, top to bottom, each ordered left to right.

    Spans are grouped on the **bottom** edge of the box, not the top. That edge
    approximates the baseline, and words on one line share a baseline far more
    reliably than they share a top edge -- capitals, ascenders and descenders
    all move the top edge and leave the baseline alone.

    A span with no box sorts to the top left, which is where the vision backend
    has always put it.
    """
    if not spans:
        return []

    tolerance = _default_tolerance(spans) if line_tolerance is None else line_tolerance
    ordered = sorted(spans, key=lambda span: (span.baseline, span.left))

    lines = [[ordered[0]]]
    for span in ordered[1:]:
        if abs(span.baseline - lines[-1][0].baseline) <= tolerance:
            lines[-1].append(span)
        else:
            lines.append([span])

    return [sorted(line, key=lambda span: span.left) for line in lines]


# Fraction of a page's spans allowed to cross a candidate gutter before it
# stops looking like one. On a genuinely two-column page almost nothing
# crosses it; on a single-column page most lines cross any x in the middle,
# so this separates the two cases cleanly.
_MAX_STRADDLE_SHARE = 0.05

# ...but a few spanning elements -- a centred running header, a rule, a wide
# caption -- are normal on any page whatever its span count, so the share is
# floored at an absolute allowance. Without it a sparse page is judged by a
# threshold below one span, and a single header hides a real gutter.
_STRADDLE_ALLOWANCE = 3

# Each column must hold at least this share of the page's spans, so one
# stray marginal note cannot "split" a single-column page.
_MIN_COLUMN_SHARE = 0.15


def find_gutter(spans: list[TextSpan]) -> float | None:
    """The x of the column gutter, or ``None`` if the page reads as one column.

    Scans candidate positions across the middle of the page and counts spans
    crossing each. A two-column page has a band almost nothing crosses; a
    single-column page has none, because most lines cross any x near the
    middle.

    This exists because grouping by baseline alone -- what :func:`group_lines`
    does, and all this module did originally -- reads *across* the gutter on a
    two-column page, interleaving the columns line by line. That is invisible
    in word-level metrics and ruinous in order-sensitive ones: the Armenian
    evaluation pages score around 0.12 character similarity against 0.70 for
    the same text in the right order.

    **No longer the serialisation path.** :func:`xy_cut_lines` replaced it
    there, and finds its own cuts through :func:`_vertical_cut`. This is
    kept as the module's answer to the narrower question it was written
    for -- *is this page two columns?* -- which is what the harvester's
    twin in ``tetrak_hy_trainer.align`` asks, and which is why the two
    are still worth keeping in step.
    """
    placed = [span for span in spans if span.bbox]
    if len(placed) < 4:
        return None

    page_left = min(span.bbox[0] for span in placed)
    page_right = max(span.bbox[2] for span in placed)
    width = page_right - page_left
    if width <= 0:
        return None

    low, high, steps = page_left + 0.3 * width, page_left + 0.7 * width, 80
    best: tuple[int, float] | None = None
    for step in range(steps + 1):
        candidate = low + (high - low) * step / steps
        crossing = sum(1 for span in placed if span.bbox[0] < candidate < span.bbox[2])
        if best is None or crossing < best[0]:
            best = (crossing, candidate)

    if best is None or best[0] > max(_STRADDLE_ALLOWANCE, _MAX_STRADDLE_SHARE * len(placed)):
        return None

    gutter = best[1]
    left = sum(1 for span in placed if span.bbox[2] <= gutter)
    right = sum(1 for span in placed if span.bbox[0] >= gutter)
    minimum = _MIN_COLUMN_SHARE * len(placed)
    return None if left < minimum or right < minimum else gutter


# --------------------------------------------------------------------------
# Recursive XY-cut (brief 012 Stage 3)
#
# The single-gutter split above handles exactly one page shape: two columns,
# optionally interrupted by full-width dividers. That is the encyclopedia, and
# it is most of what has been measured. It cannot describe three columns, a
# column that splits only below a heading, or a dictionary's nested entry
# blocks -- and the corpus now contains all three.
#
# XY-cut generalises it. Recursively look for a horizontal gap (which stacks
# the page into bands, read top to bottom) or a vertical gap (which splits it
# into columns, read left to right), and stop when neither is confident. The
# leaves are then grouped into lines exactly as a single-column page always
# was, so a page with no confident cut anywhere reads precisely as it does
# today -- the fail-safe the brief asks for is the recursion's base case
# rather than a special path.
#
# Nothing is ever dropped. Every span that enters the recursion leaves it in
# exactly one region, including the ones that straddle a cut: a transcript
# backend whose output *is* the text cannot discard any of it.
# --------------------------------------------------------------------------

# How deep the recursion may go. Real pages nest a heading over columns over
# paragraphs; six levels is far past anything this material has, and the cap
# exists so a pathological page cannot recurse until the stack gives out.
_MAX_CUT_DEPTH = 6

# A region with fewer spans than this is left alone. Matches the minimum
# find_gutter has always used, so a sparse two-column page -- a title page, a
# short entry -- still separates into columns rather than reading across.
_MIN_SPANS_TO_CUT = 4

# A horizontal gap counts as a band separation when it is this multiple of the
# region's *own* median line gap.
#
# Keying off the median gap rather than the type size is the whole of what
# makes this work, and the first attempt got it wrong: a threshold of one
# median span height fires between every pair of lines on any page whose
# leading exceeds its type size, which is most of them. Every line then
# becomes its own band, no band holds enough spans to find a gutter inside
# it, and a two-column page reads straight across -- the exact failure the
# module exists to prevent, reintroduced by the mechanism meant to generalise
# it.
#
# Ordinary leading is the median by construction, so a deliberate break has
# to stand well clear of it. Three times is conservative: it misses shallow
# paragraph breaks, which costs nothing (they are read top to bottom anyway)
# and keeps the recursion from inventing structure.
_BAND_GAP_MULTIPLE = 3.0

# ...under a floor of this many median span heights, because a gap thinner
# than a line of type is not a band whatever the leading around it is. It
# binds on tightly set text, where three times a very small median gap is
# still very small and any slightly wider gap would qualify.
#
# So both terms are relative, and to different things on purpose: the
# multiple above is relative to the region's *leading*, which is what
# distinguishes a deliberate break, and this floor is relative to its *type
# size*, which is what makes a gap large enough to mean anything. Neither is
# in pixels, for the reason _default_tolerance gives -- a pixel threshold
# means nothing without knowing the scan resolution.
_BAND_GAP_HEIGHT_FLOOR = 1.0


# How much of each box's horizontal extent to ignore when looking for a
# gutter, as a fraction of the region's median span height, from each end.
#
# EasyOCR's detector pads every box beyond the ink. On a page whose columns
# are set close -- the Armenian Soviet Encyclopedia's three columns are
# divided by about a third of a line height -- the padding alone closes the
# gutter: on one evaluation page 30 boxes "crossed" the first gutter and 17
# the second, so the region was never split and three columns were read
# straight across. Trimmed by a quarter of a line height, the same gutters
# are crossed by 2 and 0 boxes (brief 013 Stage 4).
_GUTTER_TRIM = 0.25

# A box crossing a gutter is a divider -- a running head, a wide caption --
# only if it reaches this many median span heights into *both* sides.
# Anything less is a column's box overhanging the gutter, and belongs to
# the column holding its centre. Before this rule every overhang was
# treated as a divider and split the region around it, which on a
# close-set page peeled the columns apart one line at a time until the
# recursion's depth cap gave up and read the rest across.
_DIVIDER_REACH = 2.0


# The narrower side of a vertical cut must span at least this share of the
# region's width, or at least _MIN_COLUMN_WIDTH_RATIO of the wider side's.
# A gutter between text columns leaves comparable widths of text on both
# sides; the gap beside a column of line numbers or page references in a
# critical apparatus leaves a sliver beside a full measure, and that page
# is a table, read row by row -- the transcripts write "էջ 255, տ 16
# <variant>" as one line. Without this, trimming the boxes (above) made
# those label columns separable, and Tumanyan's apparatus pages were read a
# column at a time. The ratio term keeps equal columns splittable however
# narrow they are.
_MIN_COLUMN_WIDTH_SHARE = 0.2
_MIN_COLUMN_WIDTH_RATIO = 0.5


def _trimmed_extent(span: TextSpan, trim: float) -> tuple[float, float]:
    """*span*'s horizontal extent less *trim* at each end, never inverted."""
    left, right = span.bbox[0] + trim, span.bbox[2] - trim
    if left >= right:
        middle = (span.bbox[0] + span.bbox[2]) / 2
        return middle, middle
    return left, right


def _typical_line_gap(spans: list[TextSpan]) -> float | None:
    """The median gap from each box to the nearest box directly above it.

    Measured per box rather than over the union of the boxes' heights, as
    :func:`_horizontal_cut` does: columns set a little out of step leave
    the union no gaps at all, while each column's own leading is still
    there to measure.
    """
    placed = [span for span in spans if span.bbox]
    gaps = []
    for span in placed:
        above = [
            span.bbox[1] - other.bbox[3]
            for other in placed
            if other is not span
            and other.bbox[3] <= span.bbox[1]
            and other.bbox[0] < span.bbox[2]
            and other.bbox[2] > span.bbox[0]
        ]
        if above:
            gaps.append(min(above))
    return statistics.median(gaps) if gaps else None


def _median_height(spans: list[TextSpan]) -> float:
    heights = [span.height for span in spans if span.bbox and span.height > 0]
    return statistics.median(heights) if heights else 0.0


def _horizontal_cut(spans: list[TextSpan]) -> float | None:
    """The y of the widest qualifying band gap, or ``None``.

    Works on the union of the spans' vertical extents: sort the boxes by
    top edge, sweep, and record where the running maximum bottom edge
    falls short of the next top edge. That is a band of the page no box
    occupies. The widest such band wins, provided it clears
    :data:`_BAND_GAP_MULTIPLE` against the region's own leading, clears
    :data:`_BAND_GAP_HEIGHT_FLOOR` against its type size, and leaves
    enough on both sides to be worth
    separating.
    """
    placed = [span for span in spans if span.bbox]
    if len(placed) < _MIN_SPANS_TO_CUT:
        return None

    # Sweep the union of the vertical extents, recording every gap no box
    # occupies. Two columns of text at the same heights collapse into one
    # interval per line, which is what makes the median below a measure of
    # this region's leading rather than of its column count.
    ordered = sorted(placed, key=lambda span: span.bbox[1])
    gaps: list[tuple[float, float]] = []
    reach = ordered[0].bbox[3]
    for span in ordered[1:]:
        gap = span.bbox[1] - reach
        if gap > 0:
            gaps.append((gap, reach + gap / 2))
        reach = max(reach, span.bbox[3])
    if not gaps:
        return None

    typical = statistics.median(gap for gap, _ in gaps)
    threshold = max(
        _median_height(placed) * _BAND_GAP_HEIGHT_FLOOR,
        typical * _BAND_GAP_MULTIPLE,
    )
    minimum = _MIN_COLUMN_SHARE * len(placed)

    best: tuple[float, float] | None = None
    for gap, middle in gaps:
        if gap <= threshold:
            continue
        above = sum(1 for other in placed if other.bbox[3] <= middle)
        below = len(placed) - above
        if above >= minimum and below >= minimum and (best is None or gap > best[0]):
            best = (gap, middle)

    return best[1] if best else None


def _vertical_cut(spans: list[TextSpan]) -> float | None:
    """The x of a column gutter within *spans*' own extent, or ``None``.

    The same test as :func:`find_gutter` -- a band almost nothing crosses,
    with substantial text either side -- but searched across a wider
    slice of the region. ``find_gutter`` looks only at the middle 40% of
    the page because it is asking "is this page two columns?", where the
    gutter is centred by construction. Under recursion the question is
    "does this region split?", and after one cut the answer's position is
    wherever the previous split left it: the second gutter of a
    three-column page sits near a third of the original width, and a
    region's own gutter can sit anywhere within it.

    Boxes are trimmed by :data:`_GUTTER_TRIM` first, and the crossing
    count is swept exactly over the boxes' edges rather than sampled: a
    close-set gutter can be narrower than any sampling step, and the
    detector's padding otherwise fills it.

    ``find_gutter`` is deliberately left alone rather than generalised.
    It is the documented twin of the harvester's copy in
    ``tetrak_hy_trainer.align``, and widening the search under it would
    change what that shared logic means on the pages both are tuned for.
    """
    placed = [span for span in spans if span.bbox]
    if len(placed) < _MIN_SPANS_TO_CUT:
        return None

    page_left = min(span.bbox[0] for span in placed)
    page_right = max(span.bbox[2] for span in placed)
    width = page_right - page_left
    if width <= 0:
        return None

    trim = _median_height(placed) * _GUTTER_TRIM
    extents = [_trimmed_extent(span, trim) for span in placed]
    low, high = page_left + 0.15 * width, page_left + 0.85 * width

    # Sweep the trimmed extents' edges. Between consecutive edges the
    # number of boxes crossing is constant, so every candidate gutter is
    # one of these segments. Candidates are tried fewest crossings first,
    # and among equals the widest -- the clearest gap -- and the first that
    # also leaves real columns on both sides wins. Taking only the best and
    # giving up when it failed lost the second gutter of a three-column
    # page to a narrower, emptier gap inside a column.
    allowance = max(_STRADDLE_ALLOWANCE, _MAX_STRADDLE_SHARE * len(placed))
    edges = sorted({low, high, *(x for extent in extents for x in extent if low < x < high)})
    candidates = []
    for start, end in zip(edges, edges[1:], strict=False):
        middle = (start + end) / 2
        crossing = sum(1 for left, right in extents if left < middle < right)
        if crossing <= allowance:
            candidates.append((crossing, -(end - start), middle))

    minimum = _MIN_COLUMN_SHARE * len(placed)
    for _, _, gutter in sorted(candidates):
        left_side = [extent for extent in extents if extent[1] <= gutter]
        right_side = [extent for extent in extents if extent[0] >= gutter]
        if len(left_side) < minimum or len(right_side) < minimum:
            continue
        narrowest, widest = sorted(
            max(right for _, right in side) - min(left for left, _ in side)
            for side in (left_side, right_side)
        )
        if (
            narrowest >= _MIN_COLUMN_WIDTH_SHARE * width
            or narrowest >= _MIN_COLUMN_WIDTH_RATIO * widest
        ):
            return gutter
    return None


def _regions(spans: list[TextSpan], depth: int = 0) -> list[list[TextSpan]]:
    """Split *spans* into regions, recursively, in reading order.

    Horizontal cuts are tried before vertical ones. That ordering is what
    makes a full-width heading come out above the columns it introduces
    rather than being forced into one of them: the band gap under the
    heading is found first, and the columns are then discovered inside
    the band below it.
    """
    placed = [span for span in spans if span.bbox]
    if depth >= _MAX_CUT_DEPTH or len(placed) < _MIN_SPANS_TO_CUT:
        return [spans] if spans else []

    y = _horizontal_cut(spans)
    if y is not None:
        above = [span for span in spans if span.bbox and span.bbox[3] <= y]
        below = [span for span in spans if not span.bbox or span.bbox[3] > y]
        return _regions(above, depth + 1) + _regions(below, depth + 1)

    x = _vertical_cut(spans)
    if x is not None:
        height = _median_height(placed)
        trim = height * _GUTTER_TRIM
        reach = height * _DIVIDER_REACH

        def alone_on_its_line(span: TextSpan) -> bool:
            """No other box shares *span*'s line outside its own extent.

            A running head or a caption sits alone across the columns. A
            box the detector merged across a gutter -- the end of one
            column's line and the start of the next column's, beside a
            figure that left the gap empty -- has the rest of a column's
            line beside it, and dividing the page there reads every column
            in two halves.
            """
            for other in placed:
                if other is span:
                    continue
                overlap = min(span.bbox[3], other.bbox[3]) - max(span.bbox[1], other.bbox[1])
                beside = other.bbox[0] >= span.bbox[2] or other.bbox[2] <= span.bbox[0]
                if beside and overlap >= 0.5 * min(span.height, other.height):
                    return False
            return True

        line_gap = _typical_line_gap(placed)

        def set_in_the_columns(span: TextSpan) -> bool:
            """*span* sits on both columns' line grid, so it is running text.

            The other shape of a merged box: one that covers both columns'
            text on its line entirely, so nothing is beside it, but is still
            a line of running text -- on both sides the nearest line above
            and below is at the region's ordinary line gap. A rule or a
            caption is set off the grid: further from the text, or squeezed
            between two lines closer than any two lines of text are.
            """
            if line_gap is None:
                return False

            def on_grid(gap: float | None) -> bool:
                return gap is not None and 0.5 * line_gap <= gap <= 1.5 * line_gap

            for lo, hi in ((span.bbox[0], x), (x, span.bbox[2])):
                beside = [o for o in placed if o is not span and o.bbox[0] < hi and o.bbox[2] > lo]
                above = [span.bbox[1] - o.bbox[3] for o in beside if o.bbox[3] <= span.bbox[1]]
                below = [o.bbox[1] - span.bbox[3] for o in beside if o.bbox[1] >= span.bbox[3]]
                if not (on_grid(min(above, default=None)) and on_grid(min(below, default=None))):
                    return False
            return True

        def side(span: TextSpan) -> str:
            left, right = _trimmed_extent(span, trim)
            if right <= x:
                return "left"
            if left >= x:
                return "right"
            if (
                min(x - left, right - x) >= reach
                and alone_on_its_line(span)
                and not set_in_the_columns(span)
            ):
                return "divider"
            # An overhang or a merged fragment, not a divider: the column
            # holding its centre.
            return "left" if (left + right) / 2 < x else "right"

        straddling = sorted(
            (span for span in spans if span.bbox and side(span) == "divider"),
            key=lambda span: span.baseline,
        )
        if straddling:
            # A span crossing the gutter is full width -- a running head, a
            # rule, a wide caption -- and divides the region rather than
            # belonging to either column. Split around the topmost one and
            # recurse; further dividers are found by the recursion.
            divider = straddling[0]
            limit = divider.baseline
            above = [s for s in spans if s is not divider and s.bbox and s.baseline <= limit]
            below = [s for s in spans if s is not divider and (not s.bbox or s.baseline > limit)]
            return _regions(above, depth + 1) + [[divider]] + _regions(below, depth + 1)

        left = [span for span in spans if span.bbox and side(span) == "left"]
        right = [span for span in spans if span.bbox and side(span) == "right"]
        unplaced = [span for span in spans if not span.bbox]
        # Every span lands in exactly one side: there are no dividers here,
        # so side() partitions the placed spans between left and right.
        return _regions(unplaced + left, depth + 1) + _regions(right, depth + 1)

    return [spans]


def xy_cut_lines(
    spans: list[TextSpan], line_tolerance: float | None = None
) -> list[list[TextSpan]]:
    """Visual lines across the page, ordered by recursive XY-cut.

    The alternative to :func:`_ordered_lines`, kept alongside it rather
    than replacing it while the two are compared on real fixtures. Brief
    012's rule is the midline-split precedent: if it does not beat the
    single gutter on multi-column material, it does not ship.

    The tolerance is derived from the whole page rather than per region,
    so a short column does not get a different idea of what a line is.
    """
    if not spans:
        return []
    tolerance = _default_tolerance(spans) if line_tolerance is None else line_tolerance
    return [line for region in _regions(spans) for line in group_lines(region, tolerance)]


def _ordered_lines(spans: list[TextSpan], line_tolerance: float | None) -> list[list[TextSpan]]:
    """Visual lines across the page, regions kept apart where there are any.

    Delegates to :func:`xy_cut_lines`, which replaced the single-gutter
    split after measurement (brief 012 Stage 3): on the eight held-out
    register sets it lifted mean character similarity from 0.529 to
    0.593, took the medical encyclopedia from 0.179 to 0.610 and the
    encyclopedia from 0.286 to 0.364, and left every single-column set
    and word recall untouched -- the last of which is the proof it
    reorders text rather than losing any.
    """
    return xy_cut_lines(spans, line_tolerance)


def reading_order(spans: list[TextSpan], line_tolerance: float | None = None) -> list[TextSpan]:
    """Return the spans in the order a person would read them.

    Region-aware: a page is cut recursively into bands and columns, so
    each column is read to its foot before the next begins and a heading
    is read above the columns it introduces, rather than straight across
    the page.
    """
    return [span for line in _ordered_lines(spans, line_tolerance) for span in line]


# Dashes a word broken across a line break can end with in this material.
# The same set the harvester's twin uses for the same purpose, so the two
# agree about what a line-break hyphen looks like.
_LINE_BREAK_DASHES = "-–—֊"


def dehyphenate(lines: list[str]) -> list[str]:
    """Rejoin words that a line break split in two.

    Print breaks a long word across lines with a hyphen; the transcripts
    reflow the text and write the word whole. Every such word therefore
    counts as two misreadings -- neither half matches, and the character
    metric is charged for the hyphen as well.

    The rule is deliberately narrow: a dash ends the line, a letter comes
    before it, and a letter begins the next line. That excludes the cases
    a dash is doing some other job -- a numeric range, a dialogue dash, a
    date left hanging at a line end -- because those do not have a word
    on both sides of the break.

    **Not the same normalisation the fold rejected.** The trainer's
    ``fold_script`` deliberately leaves dashes alone, because an en dash
    *inside* a token is Armenian's case-suffix marker (``Ա–ի``) and
    folding it broke more words than it fixed. This only ever joins at a
    line end, where a dash cannot be a suffix marker, which is why the
    en dash is admitted here and refused there.

    Measured on the eight held-out register sets before it shipped, as
    brief 012 requires of each hygiene delta separately: mean character
    similarity 0.5928 -> 0.6153, and word recall 0.8188 -> 0.8356. Word
    recall moving is the point rather than a warning here -- unlike a
    reordering, this puts back words that were not previously there to
    match.
    """
    joined: list[str] = []
    for line in lines:
        current = line.rstrip()
        if joined:
            previous = joined[-1].rstrip()
            if (
                len(previous) > 1
                and previous[-1] in _LINE_BREAK_DASHES
                and previous[-2].isalpha()
                and current[:1].isalpha()
            ):
                joined[-1] = previous[:-1] + current
                continue
        joined.append(current)
    return joined


def to_text(spans: list[TextSpan], line_tolerance: float | None = None) -> str:
    """Join spans into a transcript: one line per visual line, in reading order.

    Words split by a line break are rejoined, which :func:`reading_order`
    cannot do: a joined word is one string spanning two spans, and that
    has no representation in a list of spans. The two therefore differ by
    more than formatting, and this is the one that reads as prose.
    """
    lines = [" ".join(span.text for span in line) for line in _ordered_lines(spans, line_tolerance)]
    return "\n".join(dehyphenate(lines))
