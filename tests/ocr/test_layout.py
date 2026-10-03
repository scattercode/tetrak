"""Tests for reading-order reconstruction.

Fast: this is geometry and sorting, with no OCR anywhere near it.
"""

from tetrak_ocr.layout import (
    TextSpan,
    dehyphenate,
    find_gutter,
    group_lines,
    reading_order,
    to_text,
    xy_cut_lines,
)


def span(text: str, left: float, bottom: float, height: float = 10.0) -> TextSpan:
    """A span placed by its left edge and baseline, sized like ordinary type."""
    return TextSpan(text=text, bbox=(left, bottom - height, left + 20.0, bottom))


def test_words_on_one_line_are_ordered_left_to_right() -> None:
    spans = [span("world", 100, 50), span("hello", 10, 50)]
    assert to_text(spans) == "hello world"


def test_lines_are_ordered_top_to_bottom() -> None:
    spans = [span("second", 10, 80), span("first", 10, 40)]
    assert to_text(spans) == "first\nsecond"


def test_slightly_uneven_baselines_stay_one_line() -> None:
    """Two words on a line rarely share an exact baseline.

    A tolerance that is too tight fragments a line into columns, which is the
    failure the vision backend hit before it bucketed.
    """
    spans = [span("hello", 10, 50), span("world", 100, 51.5)]
    assert len(group_lines(spans)) == 1


def test_genuinely_separate_lines_do_not_merge() -> None:
    spans = [span("first", 10, 50), span("second", 10, 200)]
    assert len(group_lines(spans)) == 2


def test_grouping_uses_the_baseline_not_the_top_edge() -> None:
    """A capital and a lower-case word share a baseline, not a top edge.

    The tall span here starts much higher up; keyed on the top edge it would
    fall out of the line, and the sentence would come apart.
    """
    spans = [span("x-height", 10, 50, height=8), span("TALL", 100, 50, height=20)]
    assert len(group_lines(spans)) == 1
    assert to_text(spans) == "x-height TALL"


def test_a_span_with_no_box_sorts_to_the_top() -> None:
    """Where the vision backend has always put it."""
    spans = [span("positioned", 10, 50), TextSpan(text="unplaced")]
    assert reading_order(spans)[0].text == "unplaced"


def test_empty_input_is_empty_output() -> None:
    assert group_lines([]) == []
    assert to_text([]) == ""


# ---------------------------------------------------------------------------
# Two-column pages
#
# Grouping by baseline alone reads straight across the gutter, interleaving
# the columns line by line. Word-level metrics cannot see that; order-sensitive
# ones collapse under it, which is why the Armenian evaluation pages scored
# around 0.12 character similarity against 0.70 for the same text in order.
# ---------------------------------------------------------------------------


def column_page(rows: int = 6, header: bool = False) -> list[TextSpan]:
    """A two-column page: L0..Ln down the left, R0..Rn down the right."""
    spans = []
    for row in range(rows):
        bottom = 200 + row * 30
        spans.append(TextSpan(text=f"L{row}", bbox=(100, bottom - 10, 260, bottom)))
        spans.append(TextSpan(text=f"R{row}", bbox=(500, bottom - 10, 660, bottom)))
    if header:
        spans.append(TextSpan(text="HEADER", bbox=(100, 90, 660, 100)))
    return spans


def test_a_column_is_read_to_its_foot_before_the_next_begins() -> None:
    spans = column_page()
    assert [s.text for s in reading_order(spans)] == [f"L{r}" for r in range(6)] + [
        f"R{r}" for r in range(6)
    ]


def test_columns_do_not_share_lines() -> None:
    """Left and right text at the same height are two lines, not one."""
    assert to_text(column_page(rows=2)) == "L0\nL1\nR0\nR1"


def test_a_single_column_page_is_unaffected() -> None:
    """Full-width lines cross every candidate, so nothing looks like a gutter."""
    spans = [
        TextSpan(text=f"line{row}", bbox=(100, 200 + row * 30 - 10, 600, 200 + row * 30))
        for row in range(6)
    ]
    assert [s.text for s in reading_order(spans)] == [f"line{row}" for row in range(6)]


def test_a_full_width_header_is_read_before_both_columns() -> None:
    """It must be placed, not dropped: the output *is* the text."""
    assert to_text(column_page(rows=2, header=True)) == "HEADER\nL0\nL1\nR0\nR1"


def test_a_full_width_divider_splits_both_columns_around_it() -> None:
    """Everything above it in either column is read before it.

    The rule sits at baseline 245, between row 1 (230) and row 2 (260),
    so which side each row falls is unambiguous.
    """
    spans = column_page(rows=4)
    spans.append(TextSpan(text="RULE", bbox=(100, 235, 660, 245)))
    assert to_text(spans) == "L0\nL1\nR0\nR1\nRULE\nL2\nL3\nR2\nR3"


def test_a_lopsided_split_is_not_treated_as_columns() -> None:
    """One stray marginal note beside a column of text is not a second column."""
    spans = [
        TextSpan(text=f"line{row}", bbox=(100, 200 + row * 30 - 10, 260, 200 + row * 30))
        for row in range(20)
    ]
    spans.append(TextSpan(text="note", bbox=(600, 190, 660, 200)))
    assert find_gutter(spans) is None


def test_too_few_spans_to_judge() -> None:
    assert find_gutter([span("only", 10, 50)]) is None


def test_a_gutter_is_found_between_the_columns() -> None:
    gutter = find_gutter(column_page())
    assert gutter is not None
    assert 260 < gutter < 500


# ---------------------------------------------------------------------------
# Recursive XY-cut (brief 012 Stage 3)
#
# The cases here are the ones the single-gutter split cannot express at all,
# plus the two promises the brief makes about the generalisation: a page it
# cannot cut reads exactly as before, and no span is ever lost.
#
# These call xy_cut_lines by name, though reading_order and to_text now
# reach the same code through _ordered_lines. Naming it keeps each test's
# subject unambiguous: the two that compare the recursion against the older
# single-gutter behaviour would otherwise read as comparing a function with
# itself, which is exactly the mistake the measurement tool made once the
# swap landed.
# ---------------------------------------------------------------------------


def wide(text: str, left: float, bottom: float, width: float, height: float = 10.0) -> TextSpan:
    """A span of an explicit width, for headings and rules that cross columns."""
    return TextSpan(text=text, bbox=(left, bottom - height, left + width, bottom))


def xy_order(spans: list[TextSpan]) -> list[str]:
    return [s.text for line in xy_cut_lines(spans) for s in line]


def two_column_page(rows: int = 6, start: float = 20.0) -> list[TextSpan]:
    spans = []
    for row in range(rows):
        bottom = start + row * 20
        spans.append(span(f"left{row}", 10, bottom))
        spans.append(span(f"right{row}", 110, bottom))
    return spans


def test_three_columns_are_read_one_at_a_time() -> None:
    """The case the single gutter cannot express.

    find_gutter returns one x, so a three-column page is read as two and
    the middle column merges into whichever side of that x it falls on.
    The recursion splits again inside each half.

    Each column is a full line of text, wider than its gutter, as on a
    printed page: a column only as wide as one short word beside two
    others reads as a label column (``_MIN_COLUMN_WIDTH_RATIO``), which is
    the critical apparatus's shape rather than a three-column page's.
    """
    spans = []
    for row in range(6):
        bottom = 20 + row * 20
        for column, left in (("a", 10), ("b", 110), ("c", 210)):
            spans.append(
                TextSpan(text=f"{column}{row}", bbox=(left, bottom - 10, left + 80, bottom))
            )

    assert xy_order(spans) == [f"{column}{row}" for column in "abc" for row in range(6)]


def test_columns_set_closer_than_the_detectors_padding_are_still_split() -> None:
    """The Armenian Soviet Encyclopedia's case (brief 013 Stage 4).

    The detector pads each box past the ink, so on a close-set page the
    boxes of neighbouring columns overlap and no x is free of them. Every
    overhanging box used to count as a full-width divider; the region was
    peeled apart a line at a time and the rest read straight across.
    """
    spans = []
    for row in range(8):
        bottom = 30 + row * 30
        spans.append(TextSpan(text=f"left{row}", bbox=(0, bottom - 20, 104, bottom)))
        spans.append(TextSpan(text=f"right{row}", bbox=(98, bottom - 20, 200, bottom)))

    assert xy_order(spans) == [f"left{row}" for row in range(8)] + [
        f"right{row}" for row in range(8)
    ]


def test_a_line_merged_across_the_gutter_is_not_a_divider() -> None:
    """The detector sometimes boxes one line of both columns together.

    It sits on the columns' line grid, with text at ordinary leading
    above and below it on both sides, and is read as running text --
    not as a divider that would read each column in two halves.
    """
    spans = []
    for row in range(8):
        bottom = 30 + row * 30
        if row == 4:
            spans.append(TextSpan(text="merged", bbox=(0, bottom - 20, 200, bottom)))
            continue
        spans.append(TextSpan(text=f"left{row}", bbox=(0, bottom - 20, 95, bottom)))
        spans.append(TextSpan(text=f"right{row}", bbox=(105, bottom - 20, 200, bottom)))

    order = xy_order(spans)
    assert order.index("left7") < order.index("right0")


def test_a_column_of_line_numbers_is_read_with_its_lines() -> None:
    """A critical apparatus is a table: "տ 16 <variant>" is one line.

    The line numbers sit in a sliver of their own beside the full-width
    variants, separated by a clear gap. Splitting there would read every
    number first and every variant after (brief 013 Stage 4).
    """
    spans = []
    for row in range(6):
        bottom = 20 + row * 20
        spans.append(TextSpan(text=f"n{row}", bbox=(10, bottom - 10, 30, bottom)))
        spans.append(TextSpan(text=f"text{row}", bbox=(50, bottom - 10, 400, bottom)))

    assert to_text(spans).splitlines() == [f"n{row} text{row}" for row in range(6)]


def test_one_gutter_cannot_separate_three_columns() -> None:
    """Pins the gap the recursion closes, so its justification cannot rot.

    find_gutter answers with a single x. Whichever x it picks, one side of
    it still holds two of the three columns -- which is the structural
    reason a single split cannot express this page, independent of how
    well it picks the split.
    """
    spans = []
    for row in range(6):
        bottom = 20 + row * 20
        spans.append(span(f"a{row}", 10, bottom))
        spans.append(span(f"b{row}", 110, bottom))
        spans.append(span(f"c{row}", 210, bottom))

    gutter = find_gutter(spans)
    assert gutter is not None

    left = {s.text[0] for s in spans if s.bbox[2] <= gutter}
    right = {s.text[0] for s in spans if s.bbox[0] >= gutter}
    assert len(left) == 2 or len(right) == 2, "one side must still hold two columns"


def test_a_heading_is_read_above_the_columns_it_introduces() -> None:
    """A band gap under a full-width heading is found before the gutter."""
    spans = [wide("HEADING", 10, 20, width=220), *two_column_page(start=60)]

    order = xy_order(spans)

    assert order[0] == "HEADING"
    assert order[1:7] == [f"left{row}" for row in range(6)]
    assert order[7:] == [f"right{row}" for row in range(6)]


def test_a_region_that_splits_only_below_a_heading() -> None:
    """Nesting: one band is single-column, the band below it is not."""
    spans = [wide(f"intro{row}", 10, 20 + row * 20, width=220) for row in range(3)]
    spans += two_column_page(start=140)

    order = xy_order(spans)

    assert order[:3] == [f"intro{row}" for row in range(3)]
    assert order[3:9] == [f"left{row}" for row in range(6)]
    assert order[9:] == [f"right{row}" for row in range(6)]


def test_a_page_with_no_confident_cut_reads_exactly_as_before() -> None:
    """The fail-safe, stated as an equality rather than a judgement.

    Not "looks reasonable" -- identical to the existing serialisation, so
    a page the recursion cannot cut cannot regress.
    """
    spans = [span(f"line{row}", 10, 20 + row * 20) for row in range(10)]

    assert xy_cut_lines(spans) == group_lines(spans)


def test_two_columns_still_read_as_they_did() -> None:
    """The shape everything published so far was measured on."""
    spans = two_column_page()

    assert xy_order(spans) == [s.text for s in reading_order(spans)]


def test_no_span_is_ever_dropped_by_either_path() -> None:
    """A transcript backend cannot discard text, whatever the geometry.

    Asserted for the single gutter as well as the recursion: _blocks used
    to filter to spans that had a box and never put the rest back, which
    deleted them from the transcript of any page that read as two
    columns. The vision backend emits bbox=None whenever Vision returns
    an annotation without a box, so that was reachable.
    """
    spans = [
        wide("divider", 10, 140, width=220),
        TextSpan(text="unplaced"),
        *two_column_page(),
        *two_column_page(start=180),
    ]

    for ordered in (reading_order(spans), [s for line in xy_cut_lines(spans) for s in line]):
        assert len(ordered) == len(spans)
        assert sorted(s.text for s in ordered) == sorted(s.text for s in spans)


# ---------------------------------------------------------------------------
# De-hyphenation (brief 012 Stage 3)
#
# Print breaks a long word across lines with a hyphen and the transcripts
# write it whole, so every broken word costs two misreadings plus the hyphen.
# The rule has to be narrow: a dash at a line end does several other jobs.
# ---------------------------------------------------------------------------


def test_a_word_split_across_lines_is_rejoined() -> None:
    assert dehyphenate(["նահանգի Արագա-", "ծոտն գավառի"]) == ["նահանգի Արագածոտն գավառի"]


def test_every_line_break_dash_in_this_material_is_handled() -> None:
    """ASCII hyphen, en dash, em dash and the Armenian yentamna."""
    for dash in "-–—֊":
        assert dehyphenate([f"հարձակ{dash}", "վել է"]) == ["հարձակվել է"]


def test_a_dash_with_no_word_before_it_is_left_alone() -> None:
    """A date or a range left at a line end is not a broken word."""
    assert dehyphenate(["1850 –", "թվականին"]) == ["1850 –", "թվականին"]


def test_a_dash_before_a_line_that_starts_with_a_digit_is_left_alone() -> None:
    assert dehyphenate(["էջ 12-", "360 համարում"]) == ["էջ 12-", "360 համարում"]


def test_a_line_that_merely_ends_in_a_letter_is_untouched() -> None:
    assert dehyphenate(["առաջին տողը", "երկրորդ տողը"]) == ["առաջին տողը", "երկրորդ տողը"]


def test_the_case_suffix_marker_inside_a_token_is_not_this_rule() -> None:
    """An en dash mid-line is Armenian's case-suffix marker, not a break.

    fold_script refuses to touch dashes for exactly this reason. The rule
    here only ever fires at a line end, where a dash cannot be a suffix
    marker -- which is why the en dash is admitted here and refused there.
    """
    assert dehyphenate(["Ա–ի մասին", "հաջորդ տողը"]) == ["Ա–ի մասին", "հաջորդ տողը"]


def test_to_text_rejoins_but_reading_order_cannot() -> None:
    """The two outputs differ by more than formatting, on purpose.

    A joined word is one string spanning two spans, which has no
    representation in a list of spans.
    """
    spans = [span("Արագա-", 10, 20), span("ծոտն", 10, 40)]

    assert to_text(spans) == "Արագածոտն"
    assert [s.text for s in reading_order(spans)] == ["Արագա-", "ծոտն"]
