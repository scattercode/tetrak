"""Turning pages upright before OCR (brief 020).

On synthetic pages from `synthetic_pages.py`, drawn so that each shows the
asymmetry one measure reads. They test that the code does what the measures
say, in every turn; how well the measures do on real pages is design research
002 and 003's question, not these tests'.

The Armenian measure needs NumPy and OpenCV (the `orientation` extra, which
`dev` installs); its tests skip without them.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest
import synthetic_pages as pages
from PIL import Image, ImageChops

from tetrak_ocr import batch, cli, orientation
from tetrak_ocr.batch import main as run_batch
from tetrak_ocr.errors import MissingFeatureError
from tetrak_ocr.orientation import Orientation

TURNS = [0, 90, 180, 270]

needs_cv2 = pytest.mark.skipif(
    not all(importlib.util.find_spec(name) for name in ("cv2", "numpy")),
    reason="needs the orientation extra",
)


def same(a: Image.Image, b: Image.Image) -> bool:
    return a.size == b.size and ImageChops.difference(a, b).getbbox() is None


@pytest.fixture(scope="module")
def latin() -> Image.Image:
    return pages.latin_page(seed=1)


@pytest.fixture(scope="module")
def armenian() -> Image.Image:
    return pages.armenian_page(seed=1)


class TestLatin:
    @pytest.mark.parametrize("filmed", TURNS)
    def test_every_turn_is_righted(self, latin, filmed):
        found = orientation.detect(orientation.turn(latin, filmed), "latin")
        assert found.unsure is None
        assert (found.turn + filmed) % 360 == 0
        assert same(orientation.turn(orientation.turn(latin, filmed), found.turn), latin)

    def test_it_reads_the_ascenders(self):
        """More descenders than ascenders reads as a page on its head."""
        found = orientation.detect(
            pages.latin_page(seed=2, ascenders=0.1, descenders=0.45), "latin"
        )
        assert found.turn == 180

    def test_an_even_hand_is_left_alone(self):
        found = orientation.detect(pages.latin_page(seed=3, ascenders=0.3, descenders=0.3), "latin")
        assert found.turn == 0
        assert "near a half" in found.unsure

    def test_a_sparse_page_still_reads(self, latin):
        sparse = pages.latin_page(seed=4, lines=3)
        assert orientation.detect(orientation.turn(sparse, 90), "latin").turn == 270

    def test_an_up_share_from_few_of_the_lines_seen_is_not_trusted(self, latin, monkeypatch):
        monkeypatch.setattr(orientation, "_share_above", lambda ink: (0.8, 4, 40))
        found = orientation.detect(latin, "latin")
        assert found.turn == 0
        assert found.unsure == orientation._FEW["latin"]


@needs_cv2
class TestArmenian:
    @pytest.mark.parametrize("filmed", TURNS)
    def test_every_turn_is_righted(self, armenian, filmed):
        found = orientation.detect(orientation.turn(armenian, filmed), "armenian")
        assert found.unsure is None
        assert (found.turn + filmed) % 360 == 0

    def test_it_reads_which_way_the_letters_open(self):
        """More n-shapes than u-shapes reads as a page on its head."""
        assert orientation.detect(pages.armenian_page(seed=2, open_up=0.25), "armenian").turn == 180

    def test_the_two_turns_mirror(self, armenian):
        up = orientation.detect(armenian, "armenian").share
        down = orientation.detect(orientation.turn(armenian, 180), "armenian").share
        assert up + down == pytest.approx(1, abs=1e-9)

    def test_too_few_letters_is_unsure(self, armenian, monkeypatch):
        monkeypatch.setattr(orientation, "MIN_COMPONENTS", 10**6)
        found = orientation.detect(armenian, "armenian")
        assert (found.turn, found.unsure) == (0, orientation._FEW["armenian"])


class TestNothingToRead:
    @pytest.mark.parametrize("script", ["latin", "armenian"])
    def test_a_blank_leaf(self, script):
        if script == "armenian":
            pytest.importorskip("cv2")
        found = orientation.detect(pages.blank(), script)
        assert (found.turn, found.unsure) == (0, "no text to read")

    def test_a_dark_frame(self):
        found = orientation.detect(pages.title_card(), "latin")
        assert (found.turn, found.unsure) == (0, "too dark to be a page of text")

    def test_lines_neither_across_nor_down(self, latin, monkeypatch):
        monkeypatch.setattr(orientation, "_line_direction", lambda ink: (0.4, 50))
        assert "neither clearly across" in orientation.detect(latin, "latin").unsure


class TestExif:
    def test_a_turn_already_tagged_is_honoured(self, latin, tmp_path):
        """A frame someone has turned with an EXIF tag is judged as it displays."""
        exif = Image.Exif()
        exif[0x0112] = 6  # stored a quarter turn left; displays after a quarter turn right
        path = tmp_path / "p.jpg"
        orientation.turn(latin, 270).save(path, exif=exif, quality=95)
        assert orientation.detect(path, "latin").turn == 0


class TestRequire:
    def test_an_unmeasured_script_is_refused(self):
        with pytest.raises(ValueError, match="syriac"):
            orientation.require("syriac")

    def test_armenian_without_the_extra_names_it(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "cv2", None)  # makes `import cv2` raise ImportError
        with pytest.raises(MissingFeatureError, match=r"tetrak\[orientation\]"):
            orientation.require("armenian")

    def test_latin_needs_nothing_extra(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "cv2", None)
        orientation.require("latin")


class TestTurn:
    def test_turns_are_clockwise(self, latin):
        assert same(orientation.turn(latin, 90), latin.rotate(-90, expand=True))
        assert same(orientation.turn(latin, 270), latin.rotate(90, expand=True))

    def test_zero_is_the_image_itself(self, latin):
        assert orientation.turn(latin, 0) is latin


class TestLineFinder:
    def test_a_plateau_with_two_maxima_is_one_line(self):
        """A typeset line's flat body wobbles into two maxima with a shallow dip."""
        line = [0.2, 0.4, 0.6, 0.62, 0.6, 0.55, 0.5, 0.48, 0.5, 0.55, 0.6, 0.62, 0.6, 0.4, 0.2]
        found, _, candidates = orientation._lines([0.0] * 20 + line + [0.0] * 20)
        assert len(found) == candidates == 1

    def test_lines_with_a_gap_stay_apart(self):
        line = [0.2, 0.5, 0.6, 0.6, 0.6, 0.5, 0.2]
        found, _, candidates = orientation._lines(
            [0.0] * 20 + line + [0.0] * 10 + line + [0.0] * 20
        )
        assert len(found) == candidates == 2


class TestDescribe:
    def test_the_three_outcomes(self):
        assert Orientation("latin", 90, -2.0, 50, 0.8).describe() == "turned 90° clockwise to read"
        assert Orientation("latin", 0, 2.0, 50, 0.8).describe() == "upright"
        assert (
            Orientation("latin", 0, 0.0, 0, unsure="no text to read").describe()
            == "orientation unsure (no text to read); read as it is"
        )


class TestUpright:
    def test_no_script_is_no_check(self, tmp_path):
        path = tmp_path / "p.png"
        with orientation.upright(path, None) as (read, found):
            assert (read, found) == (path, None)

    def test_an_upright_page_is_read_where_it_is(self, latin, tmp_path):
        path = tmp_path / "p.png"
        latin.save(path)
        with orientation.upright(path, "latin") as (read, found):
            assert read == path
            assert found.turn == 0

    def test_a_turned_page_is_read_from_an_upright_copy(self, latin, tmp_path):
        path = tmp_path / "p.tif"
        orientation.turn(latin, 90).save(path)
        before = path.read_bytes()
        with orientation.upright(path, "latin") as (read, found):
            assert found.turn == 270
            assert read != path and read.stem == path.stem and read.suffix == ".png"
            with Image.open(read) as copy:
                assert same(copy.convert("L"), latin)
        assert not read.exists()  # the copy goes when the block ends
        assert path.read_bytes() == before  # and the scan was never written

    def test_a_pdf_is_not_checked(self, tmp_path):
        path = tmp_path / "doc.pdf"
        path.write_bytes(b"%PDF-1.4\n")
        with orientation.upright(path, "latin") as (read, found):
            assert (read, found) == (path, None)

    def test_a_multi_page_tiff_is_not_checked(self, latin, tmp_path):
        path = tmp_path / "doc.tif"
        latin.save(path, save_all=True, append_images=[latin])
        with orientation.upright(path, "latin") as (read, found):
            assert (read, found) == (path, None)

    def test_a_file_that_cannot_be_decoded_is_unsure_not_raised(self, tmp_path, monkeypatch):
        path = tmp_path / "broken.png"
        path.write_bytes(b"not a png")
        monkeypatch.setattr("tetrak_ocr.imaging.page_count", lambda p: 1)
        with orientation.upright(path, "latin") as (read, found):
            assert read == path
            assert found.turn == 0 and found.unsure.startswith("could not be read")


class TestBatch:
    """The OCR is stubbed: what is under test is which file it was handed."""

    @pytest.fixture
    def read_paths(self, monkeypatch) -> list[Path]:
        seen: list[Path] = []

        def ocr(path: Path) -> str:
            with Image.open(path) as im:
                im.load()
            seen.append(path)
            return "A transcript"

        monkeypatch.setattr(batch, "build_ocr_fn", lambda *a, **k: ocr)
        return seen

    def test_a_sideways_scan_is_read_upright_and_moved_untouched(
        self, working_dirs, read_paths, latin, capsys
    ):
        scan = working_dirs["scans"] / "frame.png"
        orientation.turn(latin, 90).save(scan)
        before = scan.read_bytes()
        manifest = working_dirs["scans"].parent / "manifest.csv"

        assert run_batch(["--orient", "latin", "--manifest", "--no-telemetry"]) == 0

        (read,) = read_paths
        assert read != scan and read.name == "frame.png"  # a copy, named for the scan
        assert (working_dirs["processed"] / "frame.png").read_bytes() == before
        assert "turned 270° clockwise to read" in capsys.readouterr().out
        with manifest.open(newline="", encoding="utf-8") as handle:
            (row,) = csv.DictReader(handle)
        assert row["note"] == "turned 270° clockwise to read"

    def test_without_the_flag_the_scan_is_read_as_it_is(self, working_dirs, read_paths, latin):
        scan = working_dirs["scans"] / "frame.png"
        orientation.turn(latin, 90).save(scan)

        assert run_batch(["--no-telemetry"]) == 0

        assert read_paths == [scan]

    def test_the_pdf_embeds_the_upright_copy(self, working_dirs, read_paths, latin, monkeypatch):
        """The text layer's boxes are measured on what the OCR read, so the page
        the PDF shows must be that too."""
        embedded: list[Path] = []
        monkeypatch.setattr(
            batch.outputs, "write", lambda name, source, *a, **k: embedded.append(source) or source
        )
        orientation.turn(latin, 180).save(working_dirs["scans"] / "frame.png")

        assert run_batch(["--orient", "latin", "--format", "pdf", "--no-telemetry"]) == 0

        assert embedded == read_paths

    def test_a_missing_extra_stops_the_run_before_any_file(
        self, working_dirs, read_paths, monkeypatch, capsys
    ):
        scan = working_dirs["scans"] / "frame.png"
        scan.touch()
        monkeypatch.setitem(sys.modules, "cv2", None)

        assert run_batch(["--orient", "armenian", "--no-telemetry"]) == 1

        assert scan.exists() and read_paths == []
        assert "tetrak[orientation]" in capsys.readouterr().err


class TestOcrCommand:
    def test_reads_the_upright_copy_and_says_so(self, latin, tmp_path, monkeypatch, capsys):
        seen: list[Path] = []
        monkeypatch.setattr(
            batch, "build_ocr_fn", lambda *a, **k: lambda p: seen.append(p) or "text"
        )
        scan = tmp_path / "frame.png"
        orientation.turn(latin, 270).save(scan)

        assert cli.main(["ocr", str(scan), "--orient", "latin"]) == 0

        assert seen and seen[0] != scan
        captured = capsys.readouterr()
        assert "frame.png: turned 90° clockwise to read" in captured.err
        assert captured.out.strip() == "text"

    def test_batch_forwards_the_flag(self, monkeypatch):
        seen: list[list[str]] = []
        monkeypatch.setattr(batch, "main", lambda args: seen.append(args) or 0)

        assert cli.main(["batch", "--orient", "armenian"]) == 0

        (forwarded,) = seen
        assert forwarded[forwarded.index("--orient") + 1] == "armenian"
