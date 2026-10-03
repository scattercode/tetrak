"""Tests for the register-comparison CSV emitter.

The CSV exists because two published articles carried the table by hand
and both went stale in the same cell. Replacing a hand-typed table with a
generated one only helps if the generator cannot itself emit a table that
looks complete and is not, so the two ways that could happen are pinned
here rather than left to review.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

from register_comparison import OURS, emit_csv  # noqa: E402

PAGES = frozenset({"1", "2", "3"})


def scored(*registers: str) -> list[tuple[str, dict[str, tuple[float, float]]]]:
    return [(r, {OURS: (0.5, 0.8), "rival": (0.6, 0.7)}) for r in registers]


def covering(
    *registers: str,
    short: dict[tuple[str, str], frozenset[str]] | None = None,
) -> dict[str, dict[str, frozenset[str]]]:
    """Full coverage everywhere, minus any (register, engine) in *short*."""
    out = {r: {OURS: PAGES, "rival": PAGES} for r in registers}
    for (register, engine), value in (short or {}).items():
        out[register][engine] = value
    return out


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class TestPageCoverage:
    def test_an_engine_missing_pages_is_dropped(self, tmp_path: Path, capsys) -> None:
        """The defect this file exists to prevent, one level down.

        A backend that failed nine pages of ten still appears in the
        baselines CSV with a one-page mean. Presence is therefore not
        evidence of comparability, and a column built from it would sit
        beside a ten-page mean as though the two were the same quantity.
        """
        out = tmp_path / "registers.csv"
        kept = emit_csv(
            out,
            scored("alpha", "beta"),
            covering("alpha", "beta", short={("beta", "rival"): frozenset({"1"})}),
        )

        assert kept == [OURS]
        assert "rival_wrd" not in read(out)[0]
        assert "missing pages in beta" in capsys.readouterr().out

    def test_a_page_no_engine_could_read_penalises_nobody(self, tmp_path: Path) -> None:
        """The reference set is the union of what any engine managed.

        A page every engine failed is absent from the corpus as measured,
        which is different from a page one engine alone failed. Only the
        second says anything about that engine.
        """
        out = tmp_path / "registers.csv"
        both_failed_page_three = frozenset({"1", "2"})
        kept = emit_csv(
            out,
            scored("alpha"),
            covering(
                "alpha",
                short={
                    ("alpha", "rival"): both_failed_page_three,
                    ("alpha", OURS): both_failed_page_three,
                },
            ),
        )
        assert set(kept) == {OURS, "rival"}


class TestShrinkGuard:
    def test_a_run_covering_fewer_registers_is_refused(self, tmp_path: Path) -> None:
        """A missing spans file must not quietly narrow the published mean.

        This is the dangerous direction: the emitter would succeed, the
        CSV would hold a mean over five registers, and every caption
        would go on describing eight.
        """
        out = tmp_path / "registers.csv"
        emit_csv(out, scored("alpha", "beta"), covering("alpha", "beta"))

        with pytest.raises(SystemExit) as exc:
            emit_csv(out, scored("alpha"), covering("alpha"))

        assert "beta" in str(exc.value)
        assert {r["register"] for r in read(out)} == {"alpha", "beta", "mean"}

    def test_allow_shrink_is_the_deliberate_escape(self, tmp_path: Path) -> None:
        """A register genuinely retired is a real case, just not a quiet one."""
        out = tmp_path / "registers.csv"
        emit_csv(out, scored("alpha", "beta"), covering("alpha", "beta"))
        emit_csv(out, scored("alpha"), covering("alpha"), allow_shrink=True)

        assert {r["register"] for r in read(out)} == {"alpha", "mean"}

    def test_a_first_write_is_not_a_shrink(self, tmp_path: Path) -> None:
        emit_csv(out := tmp_path / "new.csv", scored("alpha"), covering("alpha"))
        assert out.exists()


class TestTable:
    def test_the_mean_row_is_a_mean_of_the_register_rows(self, tmp_path: Path) -> None:
        """The row the published claim turns on."""
        out = tmp_path / "registers.csv"
        emit_csv(out, scored("alpha", "beta"), covering("alpha", "beta"))

        rows = read(out)
        mean = next(r for r in rows if r["register"] == "mean")
        others = [r for r in rows if r["register"] != "mean"]
        for column in (f"{OURS}_chr", f"{OURS}_wrd", "rival_chr", "rival_wrd"):
            expected = sum(float(r[column]) for r in others) / len(others)
            assert float(mean[column]) == pytest.approx(expected)

    def test_our_column_comes_first(self, tmp_path: Path) -> None:
        """The column a reader compares against belongs beside the label."""
        emit_csv(out := tmp_path / "r.csv", scored("alpha"), covering("alpha"))
        assert list(read(out)[0])[:3] == ["register", "label", f"{OURS}_chr"]
