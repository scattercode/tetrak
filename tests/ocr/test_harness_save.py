"""Cover the ``--save`` path of the evaluation harness.

This path had no test, and it is the most expensive one in the project to get
wrong: it runs only after every backend has been invoked against every fixture,
which is roughly an hour of compute and a handful of paid API calls. A crash
here discards all of it, because the results live only in memory.

That is exactly what happened. When per-backend timing was added, the tuples
carried through the harness widened from ``(char_sim, word_recall)`` to
``(char_sim, word_recall, seconds)``. The print path's accumulator and both
writers were widened to match; ``_save_comparison`` kept a two-element
accumulator and then wrote ``totals[b][2]``, so it raised IndexError on the
first entry it summed. Nothing caught it, because nothing had ever called
``_save_comparison``.

The tests below use synthetic results rather than real OCR output. The point is
not to check the scores -- other tests do that -- but to prove the save path
executes end to end and writes something a reader can parse.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from evaluation.ocr import harness

BACKENDS = ["tesseract", "easyocr", "marker"]


@pytest.fixture
def pairs(tmp_path: Path) -> list[tuple[Path, Path]]:
    """Two fixtures: one image, one PDF. Names are all the writers read."""
    return [
        (tmp_path / "a-postcard.jpg", tmp_path / "a-postcard.md"),
        (tmp_path / "b-programme.pdf", tmp_path / "b-programme.md"),
    ]


@pytest.fixture
def results() -> dict[str, list[tuple[float, float, float] | None]]:
    """Scores for two fixtures.

    ``easyocr`` is None on the PDF, which is real behaviour rather than
    padding: neither EasyOCR nor PaddleOCR can read PDFs, so the harness
    records a gap. Any accumulator that forgets to skip None entries, or any
    writer that cannot emit N/A, fails on this shape.
    """
    return {
        "tesseract": [(0.60, 0.50, 3.5), (0.45, 0.95, 12.0)],
        "easyocr": [(0.79, 0.62, 8.25), None],
        "marker": [(0.66, 0.62, 140.0), (0.66, 0.93, 610.5)],
    }


def test_save_writes_a_csv_and_a_markdown_table(tmp_path, pairs, results):
    """The regression test for the IndexError: this call used to raise."""
    harness._save_comparison(tmp_path, pairs, results, BACKENDS)

    assert (tmp_path / "benchmark.csv").exists()
    assert (tmp_path / "benchmark.md").exists()


def test_the_csv_carries_a_seconds_column_per_backend(tmp_path, pairs, results):
    """`<backend>_sec` sits after `_chr`/`_wrd`.

    The order matters beyond tidiness: the chart and presentation generators
    select columns by name, so seconds had to be appended rather than
    interleaved. A test pins that down, because "append, don't insert" is
    invisible in the code itself.
    """
    harness._save_comparison(tmp_path, pairs, results, BACKENDS)

    with (tmp_path / "benchmark.csv").open(newline="") as fh:
        rows = list(csv.reader(fh))

    header = rows[0]
    assert header[:4] == ["fixture", "tesseract_chr", "tesseract_wrd", "tesseract_sec"]
    for backend in BACKENDS:
        assert f"{backend}_sec" in header


def test_a_backend_that_cannot_read_a_fixture_is_recorded_as_na(tmp_path, pairs, results):
    """The PDF row must show easyocr as N/A rather than a zero.

    Zero would be a score, and would drag the average down; N/A says the
    question was never asked.
    """
    harness._save_comparison(tmp_path, pairs, results, BACKENDS)

    with (tmp_path / "benchmark.csv").open(newline="") as fh:
        rows = list(csv.reader(fh))

    header = rows[0]
    pdf_row = next(r for r in rows if r[0] == "b-programme.pdf")
    assert pdf_row[header.index("easyocr_chr")] == "N/A"


def test_averages_skip_the_missing_entries(tmp_path, pairs, results):
    """easyocr's average is over the one fixture it read, not both.

    Averaging over both would silently halve it. The seconds column is a
    *total* rather than an average, because the question a reader has is what
    a full pass costs.
    """
    harness._save_comparison(tmp_path, pairs, results, BACKENDS)

    with (tmp_path / "benchmark.csv").open(newline="") as fh:
        rows = list(csv.reader(fh))
    header, average = rows[0], rows[-1]

    assert average[0] == "Average"
    assert average[header.index("easyocr_chr")] == "0.7900"
    assert average[header.index("easyocr_sec")] == "8.25"
    # tesseract read both: (3.5 + 12.0) totalled, not averaged.
    assert average[header.index("tesseract_sec")] == "15.50"


def test_a_versioned_run_is_written_alongside_the_stable_one(tmp_path, pairs, results):
    """`run_id` adds a dated, git-linked copy for longitudinal tracking."""
    harness._save_comparison(tmp_path, pairs, results, BACKENDS, run_id=("abc1234", "2026-08-17"))

    versioned = tmp_path / "runs" / "2026-08-17_abc1234.csv"
    assert versioned.exists()
    assert (tmp_path / "runs" / "2026-08-17_abc1234.md").exists()
    # The stable copy is still written, and says the same thing.
    assert versioned.read_text() == (tmp_path / "benchmark.csv").read_text()


class TestMergingOneBackend:
    """``--merge``: add a column without re-measuring the other seven.

    A full ``--all`` pass is roughly an hour and a handful of paid API
    calls, so publishing an eighth engine by re-running the seven that
    have not changed is waste. The risk it introduces is that a merge
    aligns a score against the wrong image, which is invisible
    afterwards -- so the guard matters more than the happy path.
    """

    def existing(self, tmp_path: Path, pairs, results) -> Path:
        harness._save_comparison(tmp_path, pairs, results, BACKENDS)
        return tmp_path / "benchmark.csv"

    def rows(self, pairs) -> list[tuple[str, float, float, float]]:
        return [(pairs[0][0].name, 0.91, 0.97, 300.0), (pairs[1][0].name, 0.88, 0.94, 620.0)]

    def read(self, path: Path) -> tuple[list[str], list[list[str]]]:
        with path.open(newline="", encoding="utf-8") as handle:
            header, *body = list(csv.reader(handle))
        return header, body

    def test_the_new_column_appears_and_the_others_survive(self, tmp_path, pairs, results):
        before_header, before_body = self.read(self.existing(tmp_path, pairs, results))

        harness._merge_single_into_comparison(tmp_path, "paddle-vl", self.rows(pairs), pairs)

        header, body = self.read(tmp_path / "benchmark.csv")
        assert "paddle-vl_chr" in header
        # Every pre-existing cell is carried over untouched. A merge that
        # perturbed the other columns would republish figures nobody re-ran.
        for column in before_header[1:]:
            for before, after in zip(before_body, body, strict=True):
                assert after[header.index(column)] == before[before_header.index(column)]

    def test_the_column_lands_in_registry_order(self, tmp_path, pairs, results):
        """Not appended after the strategies, which would read as an
        afterthought and make the diff noisier than the change."""
        self.existing(tmp_path, pairs, results)
        harness._merge_single_into_comparison(tmp_path, "paddle-vl", self.rows(pairs), pairs)

        header, _ = self.read(tmp_path / "benchmark.csv")
        engines = [c[:-4] for c in header if c.endswith("_chr")]
        assert engines.index("paddle-vl") < engines.index("marker")

    def test_the_average_row_covers_the_merged_backend(self, tmp_path, pairs, results):
        self.existing(tmp_path, pairs, results)
        rows = self.rows(pairs)
        harness._merge_single_into_comparison(tmp_path, "paddle-vl", rows, pairs)

        header, body = self.read(tmp_path / "benchmark.csv")
        average = next(r for r in body if r[0] == "Average")
        assert float(average[header.index("paddle-vl_chr")]) == pytest.approx(
            sum(r[1] for r in rows) / len(rows), abs=1e-4
        )
        # Seconds total rather than average, as everywhere else in this table.
        assert float(average[header.index("paddle-vl_sec")]) == pytest.approx(
            sum(r[3] for r in rows), abs=1e-2
        )

    def test_re_merging_replaces_rather_than_duplicates(self, tmp_path, pairs, results):
        self.existing(tmp_path, pairs, results)
        harness._merge_single_into_comparison(tmp_path, "paddle-vl", self.rows(pairs), pairs)
        improved = [(name, sim + 0.05, rec, sec) for name, sim, rec, sec in self.rows(pairs)]
        harness._merge_single_into_comparison(tmp_path, "paddle-vl", improved, pairs)

        header, body = self.read(tmp_path / "benchmark.csv")
        assert header.count("paddle-vl_chr") == 1
        assert body[0][header.index("paddle-vl_chr")] == f"{improved[0][1]:.4f}"

    def test_the_average_row_does_not_drift_for_backends_not_re_run(self, tmp_path, pairs):
        """The defect the first real merge shipped.

        Per-fixture cells are written rounded, so recomputing a summary by
        summing them back up lands a hair off the original full-precision
        total. Five `_sec` averages moved by 0.01 that way -- published
        figures changing for engines nobody re-ran, which is the one thing
        a merge must not do.

        The scores here deliberately carry more precision than the CSV
        keeps. The original test used round numbers that survived the
        round trip, which is why it passed while the real data drifted.
        """
        lossy = {
            "tesseract": [(0.123456, 0.654321, 3.567), (0.456789, 0.987654, 12.891)],
            "easyocr": [(0.111111, 0.222222, 8.255), None],
            "marker": [(0.666666, 0.333333, 140.014), (0.777777, 0.888888, 610.567)],
        }
        harness._save_comparison(tmp_path, pairs, lossy, BACKENDS)
        before_header, before_body = self.read(tmp_path / "benchmark.csv")
        before_avg = next(r for r in before_body if r[0] == "Average")

        harness._merge_single_into_comparison(tmp_path, "paddle-vl", self.rows(pairs), pairs)

        header, body = self.read(tmp_path / "benchmark.csv")
        after_avg = next(r for r in body if r[0] == "Average")
        for column in before_header[1:]:
            assert after_avg[header.index(column)] == before_avg[before_header.index(column)], (
                f"{column} moved in the Average row for a backend that was not re-run"
            )

    def test_a_changed_corpus_is_refused(self, tmp_path, pairs, results):
        """The failure this guard exists for.

        Merging a run that saw different fixtures would align each score
        against whichever image happened to share its row, and the table
        would look entirely normal afterwards.
        """
        self.existing(tmp_path, pairs, results)
        stale = [("a-postcard.jpg", 0.91, 0.97, 300.0), ("c-new-fixture.jpg", 0.5, 0.5, 1.0)]

        with pytest.raises(SystemExit, match="corpus does not match"):
            harness._merge_single_into_comparison(tmp_path, "paddle-vl", stale, pairs)

    def test_merging_with_no_table_to_merge_into_is_refused(self, tmp_path, pairs):
        with pytest.raises(SystemExit, match="does not exist"):
            harness._merge_single_into_comparison(tmp_path, "paddle-vl", self.rows(pairs), pairs)


def test_merge_rejects_all_backends_without_crashing() -> None:
    """`--merge --all` must be a clean parser error, not an AttributeError.

    The guard read `args.all` while the flag stores into `args.all_backends`,
    so it raised on every `--merge` invocation instead of only on this one.
    A misspelled guard fails open on the case it guards and closed on every
    other, which is the worst of both.
    """
    from evaluation.ocr import harness

    with pytest.raises(SystemExit) as excinfo:
        harness.main(["--merge", "--save", "--all"])
    assert excinfo.value.code == 2  # argparse's usage error, not a traceback
