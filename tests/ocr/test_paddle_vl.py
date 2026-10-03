"""Tests for the PaddleOCR-VL backend.

Accuracy belongs in the benchmark, not here: `evaluate --all` measures it
against the corpus, and pinning a score in a unit test would make a model
revision look like a code regression. What these check is the contract
around it, and one property the benchmark cannot see at all.

The pipeline is never constructed. It loads about a gigabyte of weights
and takes minutes per page, so the heavy dependency is mocked exactly as
CI runs it -- which is also the only way to assert what arguments the
real constructor would have received.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tetrak_ocr.backends import paddle_vl


class Block:
    """One parsed layout region, shaped like PaddleOCRVLBlock.

    Attribute access, not subscripting: the real class exposes ``keys()``
    but raises TypeError on ``block["label"]``, which cost a debugging
    round the first time.
    """

    def __init__(self, label: str, content: str | None) -> None:
        self.label = label
        self.content = content


class Page(dict):
    """One page of results, shaped like PaddleOCRVLResult."""

    def __init__(self, *blocks: Block) -> None:
        super().__init__(parsing_res_list=list(blocks))


@pytest.fixture
def pipeline(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Install a fake pipeline and record how it was constructed."""
    record: dict[str, Any] = {"kwargs": None, "predicted": []}

    class FakePipeline:
        def __init__(self, **kwargs: Any) -> None:
            record["kwargs"] = kwargs

        def predict(self, target: str) -> list[Page]:
            record["predicted"].append(target)
            return record.get("pages", [Page(Block("text", "hello"))])

    monkeypatch.setattr(paddle_vl, "PaddleOCRVL", FakePipeline, raising=False)
    monkeypatch.setattr(paddle_vl, "_IMPORT_OK", True)
    monkeypatch.setattr(paddle_vl, "_ocr_instance", None)
    return record


def image(tmp_path: Path, name: str = "scan.png") -> Path:
    path = tmp_path / name
    path.write_bytes(b"not really an image")
    return path


class TestLocalInferenceOnly:
    """The constraint that cannot be seen in a transcript.

    A backend advertised as local that posted images to a hosted endpoint
    would produce output indistinguishable from the real thing, score the
    same in the benchmark, and breach the entire on-premises positioning.
    Nothing downstream can catch it, so it is pinned here.
    """

    def test_no_server_url_and_no_api_key_are_passed(
        self, tmp_path: Path, pipeline: dict[str, Any]
    ) -> None:
        paddle_vl.ocr_image(image(tmp_path))

        kwargs = pipeline["kwargs"]
        assert "vl_rec_server_url" not in kwargs
        assert "vl_rec_api_key" not in kwargs
        assert not any("server" in key or "api_key" in key for key in kwargs)

    def test_the_native_backend_is_named_explicitly(
        self, tmp_path: Path, pipeline: dict[str, Any]
    ) -> None:
        """Not left to the package default, which could change under us."""
        paddle_vl.ocr_image(image(tmp_path))
        assert pipeline["kwargs"]["vl_rec_backend"] == "native"
        assert paddle_vl.VL_BACKEND == "native"

    def test_every_other_supported_backend_is_a_server(self) -> None:
        """Why the explicit name matters: `native` is the only local one.

        If paddleocr renames it, this fails here rather than the day
        someone notices images leaving the machine.
        """
        paddleocr_vl = pytest.importorskip("paddleocr._pipelines.paddleocr_vl")
        supported = paddleocr_vl._SUPPORTED_VL_BACKENDS
        assert paddle_vl.VL_BACKEND in supported
        assert all(b.endswith("-server") for b in supported if b != paddle_vl.VL_BACKEND)


class TestPinning:
    def test_the_pipeline_version_is_pinned(self, tmp_path: Path, pipeline: dict[str, Any]) -> None:
        """It moved v1.0 to v1.6 in a month. Unpinned, the benchmark
        silently re-measures a different model on a routine install."""
        paddle_vl.ocr_image(image(tmp_path))
        assert pipeline["kwargs"]["pipeline_version"] == paddle_vl.PIPELINE_VERSION
        assert paddle_vl.PIPELINE_VERSION.startswith("v")


class TestTextExtraction:
    def test_structured_output_is_reduced_to_plain_text(
        self, tmp_path: Path, pipeline: dict[str, Any]
    ) -> None:
        """The model emits markdown natively; our metric scores plain text
        against plain-text ground truth, so returning the markdown document
        would penalise the backend for its own formatting."""
        pipeline["pages"] = [Page(Block("header", "PAGE SIX"), Block("text", "First line"))]
        assert paddle_vl.ocr_image(image(tmp_path)) == "PAGE SIX\nFirst line"

    def test_non_text_regions_are_dropped(self, tmp_path: Path, pipeline: dict[str, Any]) -> None:
        pipeline["pages"] = [
            Page(
                Block("image", None),
                Block("text", "Real words"),
                Block("seal", "ignored"),
            )
        ]
        assert paddle_vl.ocr_image(image(tmp_path)) == "Real words"

    def test_blank_blocks_do_not_produce_blank_lines(
        self, tmp_path: Path, pipeline: dict[str, Any]
    ) -> None:
        pipeline["pages"] = [Page(Block("text", "   "), Block("text", "Words"))]
        assert paddle_vl.ocr_image(image(tmp_path)) == "Words"

    def test_pages_are_joined_in_order(self, tmp_path: Path, pipeline: dict[str, Any]) -> None:
        """Multi-page input returns one result object per page, and the
        transcript has to keep them in the order they were read."""
        pipeline["pages"] = [
            Page(Block("text", "page one")),
            Page(Block("text", "page two")),
        ]
        out = paddle_vl.ocr_image(image(tmp_path, "doc.pdf"))
        assert out == "page one\npage two"


class TestInputHandling:
    def test_pdfs_are_accepted(self) -> None:
        """Unlike `paddle`, this backend reads documents as well as rasters,
        which is why it carries no reject_multi_page guard."""
        assert ".pdf" in paddle_vl.SUPPORTED_EXTENSIONS

    def test_the_file_is_passed_through_without_conversion(
        self, tmp_path: Path, pipeline: dict[str, Any]
    ) -> None:
        """`paddle` rewrites TIFFs to PNG, which flattens a multi-frame
        file to frame 0 and is why that backend must refuse multi-page
        input. This pipeline walks frames, so converting would lose pages."""
        tiff = image(tmp_path, "scan.tif")
        paddle_vl.ocr_image(tiff)
        assert pipeline["predicted"] == [str(tiff)]

    # Both of these take the `pipeline` fixture for its _IMPORT_OK, not for
    # the fake pipeline: availability is checked before the path is, so
    # without it they passed here (paddleocr installed) and failed in CI
    # (paddleocr absent) on the RuntimeError instead of the error under
    # test. They are about input handling; the environment should not decide
    # what they assert.
    def test_missing_file_raises(self, pipeline: dict[str, Any]) -> None:
        with pytest.raises(FileNotFoundError):
            paddle_vl.ocr_image(Path("does-not-exist.png"))

    def test_unsupported_extension_is_refused(
        self, tmp_path: Path, pipeline: dict[str, Any]
    ) -> None:
        path = tmp_path / "notes.txt"
        path.write_text("hello", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported file type"):
            paddle_vl.ocr_image(path)

    def test_unavailable_backend_explains_why(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The registry's _IMPORT_OK contract: importable everywhere, honest
        about whether it can actually run."""
        monkeypatch.setattr(paddle_vl, "_IMPORT_OK", False)
        with pytest.raises(RuntimeError, match="paddle-vl is unavailable"):
            paddle_vl.ocr_image(image(tmp_path))


class TestSingleton:
    def test_the_pipeline_is_built_once(self, tmp_path: Path, pipeline: dict[str, Any]) -> None:
        """A gigabyte of weights per call would make batch use unusable."""
        first = paddle_vl._get_ocr()
        assert paddle_vl._get_ocr() is first
