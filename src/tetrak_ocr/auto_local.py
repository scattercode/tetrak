#!/usr/bin/env python3
"""auto-local OCR backend: fan out over the local engines and keep the best.

Runs every eligible local backend, scores each transcript with
qa_score.combined_score() (dictionary coverage x inverse log-perplexity), and
returns the highest-ranked one.  It exists because no single local engine wins
across document types, so choosing per file beats choosing per batch.

The winning transcript passes a quality gate: if it falls below
qa_score.MIN_QUALITY_THRESHOLD, LowQualityError is raised so the caller can
route the document to the triage queue rather than silently writing a bad
result.  The same gate is available for any single backend via
`tetrak-ocr batch --quality-gate`; this one additionally carries the
per-backend score table, which is what makes the triage manifest worth
reading.

Backend eligibility:

  GPU available + Marker installed:
    Images: Marker, Vision, EasyOCR, Paddle, Tesseract-auto  (each if installed)
    PDFs:   Marker, Tesseract-auto

  No GPU:
    Images: Vision, EasyOCR, Paddle, Tesseract-auto  (each if installed)
    PDFs:   Tesseract-auto

  With `--with-paddle-vl`, PaddleOCR-VL joins both lists, images and PDFs
  alike. It is opt-in rather than automatic because it runs in minutes where
  the rest of the pool runs in seconds -- see _build_candidates().

Vision, EasyOCR and Paddle cannot read PDFs, so all three are excluded for
those.  Vision is additionally macOS-only; on any other platform its extra
cannot install and it simply never appears as a candidate.

Fan-out runs its backends **sequentially, by design**.  Running them in parallel
looks like free speed and is not: these engines are individually heavy on CPU
and RAM, and several hold module-level model singletons.  Starting two or three
at once on one machine risks memory pressure and contention that would make
runtimes less predictable, not more -- which matters most on exactly the large
batch jobs where the time would otherwise be worth saving.

There was briefly a second strategy here, `auto-local-fast`, which ran only the
top-ranked eligible backend.  The benchmark retired it: in every installed
configuration it was at best equal to running `tesseract-auto` directly, and on
a GPU machine it resolved to Marker and cost twenty-four times as much for less
accuracy.  If a single cheap engine is what you want, name it -- and add
`--quality-gate` if you want the triage queue with it.

Public API:
  has_gpu()             -> bool  — True if CUDA, ROCm, or Apple MPS is detected
  ocr_image(path)       -> str   — OCR a file; raises LowQualityError if poor
  SUPPORTED_EXTENSIONS           — set of supported file extensions

Model weights are downloaded on first use and cached locally.  Singleton
patterns (same as EasyOCR, PaddleOCR) ensure each model loads only once.
"""

import importlib.util
import sys
import time
from pathlib import Path

from . import qa_score, telemetry
from .backends import paddle_vl as paddle_vl_backend

# SUPPORTED_EXTENSIONS is re-exported: it is part of this module's public
# surface (see the docstring above), so callers can ask what auto-local
# accepts without importing the Tesseract backend directly.
from .backends.tesseract import (  # noqa: F401
    SUPPORTED_EXTENSIONS,
)
from .backends.tesseract import (
    ocr_image as _tesseract_ocr,
)
from .qa_score import MIN_QUALITY_THRESHOLD, LowQualityError, combined_score


def has_gpu() -> bool:
    """Return True if a GPU is available for neural-network acceleration.

    Detects NVIDIA CUDA, AMD ROCm, and Apple Metal Performance Shaders (MPS).
    Returns False if torch is not importable or no supported GPU is found.
    """
    try:
        import torch

        if torch.cuda.is_available():
            return True
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return True
    except ImportError:
        pass
    return False


_GPU = has_gpu()
_MARKER_AVAILABLE = importlib.util.find_spec("marker") is not None
_PADDLE_AVAILABLE = importlib.util.find_spec("paddleocr") is not None
_EASYOCR_AVAILABLE = importlib.util.find_spec("easyocr") is not None
# ocrmac is declared with a sys_platform marker, so this is False off macOS
# without needing a platform check of its own.
_VISION_AVAILABLE = importlib.util.find_spec("ocrmac") is not None

# Scoring the transcripts needs the `qa` extra. Without it this backend imports
# fine and then fails on the first file with "No module named 'spellchecker'";
# declaring it here lets the registry report the missing extra up front, the
# same as any other backend. The requirement list lives in qa_score, which is
# what actually imports them.
_IMPORT_OK = qa_score.is_available()

_marker_ocr = None
_vision_ocr = None
_paddle_ocr = None
_paddle_vl_ocr = None
_easyocr_ocr = None

if _MARKER_AVAILABLE and _GPU:
    from .backends.marker import ocr_image as _marker_ocr

if _VISION_AVAILABLE:
    from .backends.vision import ocr_image as _vision_ocr

if _PADDLE_AVAILABLE:
    from .backends.paddle import ocr_image as _paddle_ocr


# The backend's own verdict, not a second guess at it. Probing package names
# here would admit a candidate on a machine where paddleocr is present but
# the VL pipeline cannot actually build -- `--with-paddle-vl` would then run
# a guaranteed failure against every file in the batch.
if paddle_vl_backend._IMPORT_OK:
    from .backends.paddle_vl import ocr_image as _paddle_vl_ocr

if _EASYOCR_AVAILABLE:
    from .backends.easyocr import ocr_image as _easyocr_ocr


# Weight given to a candidate's raw combined_score, independent of how much
# text it recovered relative to the longest candidate. A candidate at
# max_words always gets full credit regardless of this value; one with fewer
# words gets `LENGTH_WEIGHT` of its score as a floor, rising linearly to full
# credit as its word count approaches max_words.
#
# Fitted by evaluation/ocr/calibration/router_sweep.py, which minimises mean
# *regret* (brief 007, the calibration toolkit) over splits.toml's
# original-corpus fit set -- see brief 010 (the router length weight)
# for the full result and the error taxonomy (product analytics) ("The router's
# own error rate") for the problem this replaces.
#
# The previous value, 0.5, let a noisy tesseract-auto transcript on
# carthay-circle-premiere.jpg win on word count alone: it emitted 77 words
# (mostly noise from the textured background) against 11 for marker, vision
# and EasyOCR, so at weight 0.5 its word-count ratio of 1.0 outweighed its
# combined_score being the *lowest* of the four candidates. Raising the
# weight to 0.8 -- the least-changed value that still avoids that failure,
# on the "intervene least when the measurement cannot tell settings apart"
# principle sweep.py already uses for its own ties -- fixes it: regret on
# that fixture falls from 0.40 to 0.14. Re-scored under the corrected
# character similarity (brief 013 turned difflib's autojunk off), mean regret
# on the fit set falls from 0.1336 to 0.0904 and 0.8 still wins the sweep, but
# one fixture, graumans-chinese-theatre, now scores fractionally worse (regret
# 0.055 to 0.059). Under the old metric the fall was 0.0828 to 0.0316, with no
# fixture scoring worse. The residual 0.14 is not a length
# problem: at weight 0.8 the winner is Marker, whose combined_score is
# fractionally the highest of the four even though its char_sim (0.76) trails
# Vision's (0.89) -- a ranking error in combined_score itself, out of this
# constant's reach.
LENGTH_WEIGHT = 0.8


def _effective_score(score: float, word_count: int, max_words: int) -> float:
    """Return `score` adjusted for `word_count` relative to `max_words`.

    Pure function, no backend or corpus needed -- see
    tests/ocr/test_auto_local.py for the hand-built cases this is checked
    against, and evaluation/ocr/calibration/router_sweep.py for how
    `LENGTH_WEIGHT` was chosen.

    Args:
        score: A candidate's raw combined_score.
        word_count: That candidate's transcript word count.
        max_words: The largest word count among all candidates being ranked.

    Returns:
        `score` unchanged if `max_words` is non-positive (nothing to compare
        against); otherwise `score` scaled by a value in [LENGTH_WEIGHT, 1.0].
    """
    if max_words <= 0:
        return score
    # Clamped so the documented [LENGTH_WEIGHT, 1.0] factor holds for any
    # caller, not just ocr_image() (whose max_words is by construction the
    # maximum of the counts it passes).
    ratio = min(max(word_count / max_words, 0.0), 1.0)
    return score * (LENGTH_WEIGHT + (1.0 - LENGTH_WEIGHT) * ratio)


def _build_candidates(path: Path, with_paddle_vl: bool = False) -> list[tuple[str, object]]:
    """Return an ordered list of (name, ocr_fn) pairs eligible for this file.

    This is an eligibility filter, not a choice: it answers "which backends
    *could* read this file here", based on what is installed, whether a GPU was
    found, and whether the file is a PDF.

    Order matters: backends run in this sequence, and the first is the
    tiebreaker when scores are equal.

    Marker leads when available: it is the only candidate that models reading
    order, which is what the structured documents need, and it is GPU-gated so
    it is absent on the machines where that would be expensive.  Vision follows
    it: on the evaluation corpus it is the strongest local engine measured, and
    it is also the cheapest to run -- the model ships with macOS, so there are
    no weights to download and no first-call penalty.  EasyOCR is ranked above
    PaddleOCR because it measures better on the evaluation corpus, ahead on
    every image where either engine reads anything at all.  Tesseract-auto is
    last because it is the one backend guaranteed to be present, so it is the
    floor rather than a choice.

    The scores behind that ranking live in site/content/research/in-depth.md,
    generated from the benchmark and versioned with it.  They are deliberately
    not repeated here: a figure copied into a docstring goes stale the first
    time the corpus changes, and nothing would catch it.  Re-check the ranking
    when the benchmark moves.
    """
    is_pdf = path.suffix.lower() == ".pdf"
    candidates = []

    # Opt-in, via `--with-paddle-vl`. It measures as the strongest local
    # backend on the corpus and wins where the rest of this pool is weakest,
    # on the dense multi-column pages -- but it runs in minutes where they
    # run in seconds, and fan-out pays that on every file, including the
    # ones where `vision` still beats it. Hence a choice rather than a
    # default.
    #
    # The scores behind that live in site/content/reference/engines.md and
    # in evaluation/ocr/benchmark.csv, deliberately not here: the docstring
    # above makes the same point about the ranking below, and a figure typed
    # into a comment goes stale the first time the corpus moves with nothing
    # to catch it.
    #
    # Ranked first on that measured average, and this order is the
    # tiebreaker when two candidates score equally. It reads PDFs, so unlike
    # vision, EasyOCR and Paddle it is not excluded for those.
    if with_paddle_vl and _paddle_vl_ocr is not None:
        candidates.append(("paddle-vl", _paddle_vl_ocr))

    if _marker_ocr is not None:
        candidates.append(("marker", _marker_ocr))

    if not is_pdf and _vision_ocr is not None:
        candidates.append(("vision", _vision_ocr))

    if not is_pdf and _easyocr_ocr is not None:
        candidates.append(("easyocr", _easyocr_ocr))

    if not is_pdf and _paddle_ocr is not None:
        candidates.append(("paddle", _paddle_ocr))

    candidates.append(("tesseract-auto", lambda p: _tesseract_ocr(p, auto=True)))

    return candidates


def ocr_image(path: "Path | str", with_paddle_vl: bool = False) -> str:
    """OCR a file by running every eligible local backend and keeping the best.

    Args:
        path: Path to an image or PDF file.
        with_paddle_vl: Admit the PaddleOCR-VL backend to the pool. Off by
            default because it costs minutes per page against the rest of
            the pool's seconds; see :func:`_build_candidates`. The CLI
            exposes it as ``--with-paddle-vl``. An optional keyword rather
            than a change to the ``ocr_image(path) -> str`` contract, the
            same way the Tesseract backend takes ``contrast`` and ``psm``.

    Fan-out exists because no single local backend wins across document types,
    so choosing per file beats choosing per batch -- see
    ``tetrak-ocr evaluate --all`` for the measurement behind that.

    The winning transcript passes a quality gate, so a file that no backend
    reads acceptably reaches the triage queue instead of being written out.

    Returns:
        Extracted text as a string.

    Raises:
        LowQualityError: If the winning combined score falls below
            MIN_QUALITY_THRESHOLD.  The exception carries .scores and
            .transcripts dicts for triage queue reporting.
    """
    path = Path(path)
    candidates = _build_candidates(path, with_paddle_vl=with_paddle_vl)

    transcripts: dict[str, str] = {}
    scores: dict[str, float] = {}
    durations: dict[str, float] = {}

    for name, fn in candidates:
        # Timed individually because the fan-out's whole cost problem is that
        # one candidate can dominate it, and the score table alone cannot say
        # which -- it reports quality, not time.
        started = time.perf_counter()
        try:
            text = fn(path)
            score = combined_score(text)
            transcripts[name] = text
            scores[name] = score
            durations[name] = time.perf_counter() - started
            telemetry.record(
                "backend_finish",
                backend=name,
                seconds=round(durations[name], 3),
                score=round(score, 4),
                chars=len(text),
                words=len(text.split()),
                ok=True,
                **telemetry.describe_file(path),
            )
        except Exception as exc:
            durations[name] = time.perf_counter() - started
            telemetry.record(
                "backend_finish",
                backend=name,
                seconds=round(durations[name], 3),
                ok=False,
                error=type(exc).__name__,
                **telemetry.describe_file(path),
            )
            print(f"    [{name}] failed: {exc}", file=sys.stderr)
            continue

    if not scores:
        tried = ", ".join(name for name, _ in candidates)
        raise RuntimeError(f"All backends failed for {path.name} (tried: {tried})")

    # Rank by quality adjusted for relative word count -- see
    # _effective_score() and LENGTH_WEIGHT above for what this prevents and
    # where the weight came from.
    word_counts = {name: len(transcripts[name].split()) for name in scores}
    max_words = max(word_counts.values()) or 1
    effective_scores = {
        name: _effective_score(scores[name], word_counts[name], max_words) for name in scores
    }

    _print_score_table(scores, effective_scores, word_counts, durations)

    best_name = max(effective_scores, key=lambda k: effective_scores[k])
    # Use the raw combined_score for the quality threshold — the triage gate
    # should reflect output quality, not quality × length.
    best_raw_score = scores[best_name]

    if best_raw_score < MIN_QUALITY_THRESHOLD:
        raise LowQualityError(
            f"Best transcript ({best_name}, score={best_raw_score:.4f}) is below "
            f"threshold {MIN_QUALITY_THRESHOLD:.4f}",
            scores=scores,
            transcripts=transcripts,
        )

    print(
        f"    [auto-local → {best_name}]"
        f"  effective={effective_scores[best_name]:.4f}"
        f"  quality={best_raw_score:.4f}",
        file=sys.stderr,
    )
    return transcripts[best_name]


def _print_score_table(
    scores: dict[str, float],
    effective_scores: dict[str, float],
    word_counts: dict[str, int],
    durations: dict[str, float] | None = None,
) -> None:
    """Print a compact per-backend score summary to stderr.

    The elapsed column is here because the table is the one moment the run
    accounts for itself, and "which of these cost me the twenty minutes" is
    not answerable from quality and word count.
    """
    durations = durations or {}
    col = max(len(n) for n in scores)
    print(
        f"    {'Backend':<{col}}  {'Quality':>7}  {'Words':>5}  {'Effective':>9}  {'Time':>8}",
        file=sys.stderr,
    )
    print(
        f"    {'-' * col}  {'-------':>7}  {'-----':>5}  {'---------':>9}  {'--------':>8}",
        file=sys.stderr,
    )
    for name in scores:
        elapsed = durations.get(name)
        shown = f"{elapsed:>7.1f}s" if elapsed is not None else " " * 8
        print(
            f"    {name:<{col}}  {scores[name]:>7.4f}  {word_counts[name]:>5}  "
            f"{effective_scores[name]:>9.4f}  {shown}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="OCR a file using the best-scoring available local backend."
    )
    parser.add_argument("path", type=Path, help="Path to the image or PDF file.")
    args = parser.parse_args()

    if not _GPU:
        gpu_status = "no GPU"
    else:
        try:
            import torch

            gpu_status = "CUDA/ROCm" if torch.cuda.is_available() else "MPS"
        except ImportError:
            gpu_status = "GPU"

    backends = [n for n, _ in _build_candidates(args.path)]
    print(f"Backends: {', '.join(backends)}  [{gpu_status}]", file=sys.stderr, flush=True)

    try:
        result = ocr_image(args.path)
        print(result)
    except LowQualityError as e:
        print(f"\nLow quality — would route to triage queue: {e}", file=sys.stderr)
        sys.exit(1)
