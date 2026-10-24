"""Tests for the reading-order harness.

The harness decides whether positioned output can ship, so what is pinned
here is that it measures what it says: that the line sort reproduces the
interleaving brief 008 found, that the column-aware pass undoes it on the
same spans, that word recall cannot tell the two apart, and that the save
path writes a table the site can read. Fast: synthetic spans, no engine.
"""

from __future__ import annotations

import csv
from pathlib import Path

from evaluation.ocr import reading_order as harness
from tetrak_ocr.layout import TextSpan


def two_column_page(rows: int = 6) -> tuple[list[TextSpan], str]:
    """Spans in *engine* order, which happens to interleave the columns, and
    the truth a person would read: the left column, then the right."""
    spans = []
    for row in range(rows):
        bottom = 200 + row * 30
        spans.append(TextSpan(text=f"L{row}", bbox=(100, bottom - 10, 260, bottom)))
        spans.append(TextSpan(text=f"R{row}", bbox=(500, bottom - 10, 660, bottom)))
    truth = "\n".join([f"L{r}" for r in range(rows)] + [f"R{r}" for r in range(rows)])
    return spans, truth


class TestStrategies:
    def test_the_line_sort_interleaves_the_columns(self) -> None:
        """The construction brief 008 measured: a positioned layer reads back
        top to bottom across the page."""
        spans, _ = two_column_page()
        assert harness.STRATEGIES["linesort"](spans).split("\n")[:2] == ["L0 R0", "L1 R1"]

    def test_the_column_aware_pass_reads_a_column_to_its_foot(self) -> None:
        spans, truth = two_column_page()
        assert harness.STRATEGIES["column"](spans) == truth.replace("\n", " ")

    def test_engine_order_is_untouched(self) -> None:
        spans, _ = two_column_page()
        assert harness.STRATEGIES["engine"](spans).split("\n")[:3] == ["L0", "R0", "L1"]


class TestScore:
    def test_character_similarity_separates_the_orders_and_word_recall_cannot(self) -> None:
        """The pairing the harness prints: chr moves with order, wrd is the
        tripwire that must stay put across serialisations of the same tokens."""
        spans, truth = two_column_page()

        scores = harness.score(spans, harness.STRATEGIES["engine"](spans), truth)

        assert scores["column_chr"] == 1.0
        assert scores["linesort_chr"] < scores["column_chr"]
        assert scores["engine_wrd"] == scores["linesort_wrd"] == scores["column_wrd"] == 1.0
        assert scores["transcript_chr"] == scores["engine_chr"]

    def test_every_column_is_scored(self) -> None:
        spans, truth = two_column_page()
        assert set(harness.score(spans, "", truth)) == set(harness.FIELDNAMES[3:])


class TestClassification:
    def test_the_multi_column_fixtures_are_rasters_in_the_corpus(self) -> None:
        """A stem that drifts from the corpus would silently shrink the set."""
        if not harness.raster_pairs():
            return  # no corpus checked out
        stems = {image.stem for image, _ in harness.raster_pairs()}
        assert harness.MULTI_COLUMN <= stems

    def test_pdfs_are_excluded(self) -> None:
        assert all(image.suffix != ".pdf" for image, _ in harness.raster_pairs())


def synthetic_rows() -> list[dict[str, object]]:
    def row(fixture: str, backend: str, layout: str, column: float) -> dict[str, object]:
        scores = {f"{name}_chr": 0.5 for name in harness.COLUMNS} | {
            f"{name}_wrd": 0.9 for name in harness.COLUMNS
        }
        scores["column_chr"] = column
        return {"fixture": fixture, "backend": backend, "layout": layout} | scores

    return [
        row("news-b", "paddle", "multi-column", 0.8),
        row("news-a", "paddle", "multi-column", 0.6),
        row("postcard", "paddle", "single-column", 0.9),
        row("news-a", "vision", "multi-column", 0.7),
    ]


class TestSave:
    def test_means_follow_each_group_and_are_the_groups_mean(self) -> None:
        rows = harness.with_means(synthetic_rows())

        labels = [(r["backend"], r["layout"], r["fixture"]) for r in rows]
        assert labels == [
            ("paddle", "multi-column", "news-a"),
            ("paddle", "multi-column", "news-b"),
            ("paddle", "multi-column", "mean"),
            ("paddle", "single-column", "postcard"),
            ("paddle", "single-column", "mean"),
            ("vision", "multi-column", "news-a"),
            ("vision", "multi-column", "mean"),
        ]
        assert rows[2]["column_chr"] == 0.7

    def test_the_csv_and_markdown_are_written_and_readable(self, tmp_path: Path) -> None:
        csv_path, md_path = tmp_path / "reading_order.csv", tmp_path / "reading_order.md"

        harness.write(synthetic_rows(), csv_path, md_path)

        with csv_path.open(encoding="utf-8") as handle:
            table = list(csv.DictReader(handle))
        assert table[0].keys() == set(harness.FIELDNAMES)
        means = [r for r in table if r["fixture"] == "mean"]
        assert [(r["backend"], r["layout"]) for r in means] == [
            ("paddle", "multi-column"),
            ("paddle", "single-column"),
            ("vision", "multi-column"),
        ]
        assert means[0]["column_chr"] == "0.7000"
        markdown = md_path.read_text(encoding="utf-8")
        assert "Do not edit" in markdown
        assert "## paddle" in markdown and "## vision" in markdown
