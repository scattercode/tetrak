"""Text similarity metrics for OCR evaluation.

Two metrics are provided:

character_similarity
    Uses Python's difflib.SequenceMatcher to compare the two texts
    character-by-character.  Returns a ratio from 0.0 (nothing in common)
    to 1.0 (identical after normalisation).  Good for detecting small
    transcription errors and OCR noise.

word_recall
    Computes what fraction of the words in the expected text were also
    found in the actual OCR output.  This is a recall-oriented metric:
    it rewards capturing all the content, and is tolerant of reordering
    or extra words introduced by the OCR engine.

Both functions normalise their inputs first (lowercase, collapsed
whitespace) so that trivial formatting differences do not affect scores.
"""

import difflib
import re

# Armenian punctuation -> the ASCII character it is visually identical to.
_PUNCTUATION_HOMOGLYPHS = str.maketrans({"։": ":", "․": "."})

# The two-letter եւ and the ligature և are one thing for scoring (brief 014,
# decided 2026-10-08). Classical-orthography presses split 21 to 16 on which
# they set, reformed presses set the ligature, and transcribers follow the
# page or do not; ground truth stays as printed so the model learns to read
# both, and the metric refuses to rank an engine on which form it emitted.
# Applied after lowercasing, so Եւ and ԵՒ fold too. The trainer's copy of
# this module carries the same change.
_EW_LIGATURE = ("եւ", "և")


def _is_word(token: str) -> bool:
    """A token with at least one letter or digit; ``-`` or ``…`` alone is not."""
    return any(character.isalnum() for character in token)


def normalise(text: str) -> str:
    """Lowercase, equate Armenian punctuation homoglyphs, collapse whitespace.

    Two Armenian marks are scored as the ASCII character they print
    identically to: the full stop ``։`` as the colon, and the abbreviation
    dot ``․`` (U+2024) as the full stop. Transcribers type the ASCII form
    so often (the medical encyclopedia's transcripts use the colon
    throughout; every register uses ``.`` for ``․``) that holding an engine
    to either form would rank engines on which habit their output happens
    to share with the transcript, not on what they read. Mapped towards
    ASCII so that text with no Armenian in it is unaffected. The two-letter
    ``եւ`` is scored as the ligature ``և`` for the same reason (brief 014).
    """
    lowered = text.lower().translate(_PUNCTUATION_HOMOGLYPHS).replace(*_EW_LIGATURE)
    return re.sub(r"\s+", " ", lowered).strip()


def character_similarity(actual: str, expected: str) -> float:
    """Return character-level similarity as a ratio 0.0–1.0.

    Uses difflib.SequenceMatcher, which finds the longest common
    subsequences between the two strings.

    Args:
        actual:   The text produced by OCR.
        expected: The reference (ground-truth) text.

    Returns:
        A float in [0.0, 1.0].  1.0 means the texts are identical
        after normalisation.

    ``autojunk`` is off, and must stay off. With difflib's default, any
    string over 200 characters has every character making up more than 1%
    of it treated as junk -- on a page of text, most of the alphabet and
    the space -- so the ratio reflects where the few surviving matches
    happen to fall rather than how much of the text was read. Brief 013
    found it scoring a near-perfect Armenian page at 0.76 instead of 0.98.
    """
    return difflib.SequenceMatcher(
        None, normalise(actual), normalise(expected), autojunk=False
    ).ratio()


def word_recall(actual: str, expected: str) -> float:
    """Return the fraction of expected words present in the OCR output.

    This measures recall: how much of the expected content did we capture?
    It is tolerant of the OCR engine producing extra words or changing
    word order, which is common with complex layouts.

    Args:
        actual:   The text produced by OCR.
        expected: The reference (ground-truth) text.

    Returns:
        A float in [0.0, 1.0].  1.0 means every expected word was found.
    """
    # Punctuation-only tokens are not words. The medical encyclopedia's
    # index prints dot leaders that its transcripts type as a standalone
    # "-", and counting those charged every engine that read the page
    # correctly with a missed word per index entry (brief 013).
    expected_words = [word for word in normalise(expected).split() if _is_word(word)]
    if not expected_words:
        return 1.0
    actual_words = set(normalise(actual).split())
    found = sum(1 for w in expected_words if w in actual_words)
    return found / len(expected_words)
