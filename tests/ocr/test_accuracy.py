"""Unit tests for the accuracy metrics.

These two numbers are what the whole benchmark rests on, and they had no unit
coverage — only an end-to-end threshold test that ran Tesseract for real
(now in test_thresholds.py). They are pure functions over strings, so their
behaviour can be pinned exactly and cheaply.
"""

from __future__ import annotations

import pytest

from tetrak_ocr.accuracy import character_similarity, normalise, word_recall


class TestNormalise:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Hello World", "hello world"),
            ("  leading and trailing  ", "leading and trailing"),
            ("collapses\n\nnewlines", "collapses newlines"),
            ("tabs\tand   spaces", "tabs and spaces"),
            ("", ""),
            ("   ", ""),
        ],
    )
    def test_normalisation(self, raw: str, expected: str) -> None:
        assert normalise(raw) == expected

    def test_armenian_full_stop_and_colon_are_equal(self) -> None:
        """Transcripts type ':' for '։'; neither engine nor transcript is penalised."""
        assert normalise("բժշկի։") == normalise("բժշկի:")

    def test_abbreviation_dot_and_full_stop_are_equal(self) -> None:
        """Transcripts type '.' for the Armenian abbreviation dot '․'."""
        assert normalise("Ա․ Գրկ․") == normalise("Ա. Գրկ.")

    def test_is_idempotent(self) -> None:
        """Normalising twice changes nothing — both metrics rely on this."""
        once = normalise("  Mixed\tCase\n\nText  ")
        assert normalise(once) == once


class TestCharacterSimilarity:
    def test_identical_text_scores_one(self) -> None:
        assert character_similarity("the same text", "the same text") == 1.0

    def test_case_and_whitespace_are_ignored(self) -> None:
        """Scoring runs on normalised text, so these must not be penalised."""
        assert character_similarity("THE  SAME\nTEXT", "the same text") == 1.0

    def test_unrelated_text_scores_low(self) -> None:
        assert character_similarity("qqqq zzzz", "the quick brown fox") < 0.5

    def test_empty_actual_scores_zero(self) -> None:
        assert character_similarity("", "expected text") == 0.0

    @pytest.mark.parametrize(
        ("actual", "expected"),
        [
            ("partial ma", "partial match here"),
            ("completely different", "nothing alike"),
            ("", ""),
        ],
    )
    def test_score_is_bounded(self, actual: str, expected: str) -> None:
        assert 0.0 <= character_similarity(actual, expected) <= 1.0

    def test_long_text_with_one_error_scores_near_one(self) -> None:
        """A page-length text must not be scored by difflib's autojunk.

        Past 200 characters difflib's default treats every common character
        as junk, and a page with a single misread letter scored far below
        what it read. One wrong character in ~1,000 should cost ~0.001.
        """
        expected = " ".join(f"word{i % 37} and some more text" for i in range(40))
        actual = expected.replace("word5", "wurd5", 1)
        assert character_similarity(actual, expected) > 0.99

    def test_near_miss_sits_between_noise_and_perfect(self) -> None:
        near = character_similarity("the quick brown fax", "the quick brown fox")
        noise = character_similarity("zzzzzzzzzzzzzzzzzzz", "the quick brown fox")
        assert noise < near < 1.0


class TestWordRecall:
    def test_all_words_found_scores_one(self) -> None:
        assert word_recall("alpha beta gamma", "alpha beta gamma") == 1.0

    def test_extra_words_do_not_reduce_recall(self) -> None:
        """Recall asks what share of expected words appeared, not precision.

        A backend that hallucinates extra text still recalled everything it was
        meant to; that failure surfaces in character similarity instead.
        """
        assert word_recall("alpha beta gamma delta epsilon", "alpha beta gamma") == 1.0

    def test_missing_words_reduce_recall(self) -> None:
        assert word_recall("alpha beta", "alpha beta gamma delta") == pytest.approx(0.5)

    def test_word_order_is_irrelevant(self) -> None:
        assert word_recall("gamma alpha beta", "alpha beta gamma") == 1.0

    def test_empty_actual_scores_zero(self) -> None:
        assert word_recall("", "alpha beta") == 0.0

    def test_punctuation_only_tokens_are_not_words(self) -> None:
        """A dot leader transcribed as a lone '-' is not a word to recall."""
        assert word_recall("term 274 other 275", "term - 274 other - 275") == 1.0

    def test_empty_expected_does_not_divide_by_zero(self) -> None:
        assert 0.0 <= word_recall("anything", "") <= 1.0


class TestTheMetricsMeasureDifferentThings:
    """Why there are two numbers rather than one.

    The benchmark analysis leans on this property: a backend that finds the
    right words but reads a two-column page in the wrong order keeps its
    recall and loses its character similarity. Two fixtures in the corpus fail
    only on recall for the opposite reason — text the engine never saw at all.
    """

    def test_scrambled_order_keeps_recall_but_loses_similarity(self) -> None:
        expected = "the first column text and then the second column text"
        scrambled = "second column text the and then text first column the"

        assert word_recall(scrambled, expected) == 1.0
        assert character_similarity(scrambled, expected) < 1.0

    def test_truncated_text_loses_recall_though_what_it_read_was_right(self) -> None:
        """Text the engine never saw costs recall, even when nothing is garbled.

        This is the corpus's other failure mode: two fixtures score well on
        character similarity and fail on recall alone, held back by marquee
        lettering the engine cannot see rather than by text it mangles.

        No ordering is asserted between the two metrics — for a simple
        truncation they land close together, and which is higher depends on
        the ratio of missing characters to missing words.
        """
        expected = "a legible line plus some unreadable marquee lettering"
        partial = "a legible line plus some"

        assert word_recall(partial, expected) < 1.0
        # Every word it did read was correct, so a scrambled read of the same
        # length scores worse on similarity than this clean truncation.
        scrambled = "some plus line legible a"
        assert character_similarity(partial, expected) > character_similarity(scrambled, expected)
