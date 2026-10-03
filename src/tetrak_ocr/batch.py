#!/usr/bin/env python3
"""Batch OCR processor.

Scans the `workspace/scans/` directory for supported image and PDF files, runs
OCR on each one, writes the extracted text to a Markdown file in
`workspace/processed/`, and moves the original file in alongside it.

After processing, each file pair looks like:
    workspace/processed/
      my-postcard.jpg   ← original moved here
      my-postcard.md    ← extracted text

Usage (run from the repository root):
    tetrak-ocr batch
    tetrak-ocr batch --backend auto-local
    tetrak-ocr batch --backend claude
    tetrak-ocr batch --backend tesseract --contrast 3.0
"""

import argparse
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .qa_score import LowQualityError

from . import outputs, telemetry
from .imaging import page_documents
from .registry import BACKENDS, get_backend
from .registry import supported_extensions as _registry_extensions

# Working directories are resolved against the *current* directory, not the
# package location. As loose scripts these were derived from __file__, which
# happened to be the repository root; once installed as a package that path
# points inside site-packages, which is nobody's scan folder. Treating them as
# CWD-relative is both correct for an installed tool and what a user expects
# from `cd myproject && tetrak-ocr batch`.
#
# They are module-level so tests can monkeypatch them, which is how the batch
# tests drive a tmp_path directory.
# The three live under workspace/ so the top of a project stays readable and the
# scans → processed → triage flow is visible in one place.
WORKSPACE_DIR = Path("workspace")
SCANS_DIR = WORKSPACE_DIR / "scans"
PROCESSED_DIR = WORKSPACE_DIR / "processed"
TRIAGE_DIR = WORKSPACE_DIR / "triage"


def build_ocr_fn(
    backend: str,
    contrast: float | None = None,
    psm: int | None = None,
    auto: bool = False,
    with_paddle_vl: bool = False,
) -> Callable[[Path], str]:
    """Return the OCR callable for the chosen backend.

    Backend resolution lives in :mod:`tetrak_ocr.registry` — this used to
    duplicate it as an if/elif chain of imports, which meant a new backend had
    to be registered in two places and a missing optional dependency surfaced
    as a bare ImportError.

    Only Tesseract takes tuning arguments and only auto-local takes
    `--with-paddle-vl`; the rest ignore them, and passing one is reported
    rather than silently dropped.

    Both Tesseract names take the flags. `tesseract-auto` is the same backend
    with auto-configuration switched on by the registry, so it honours
    `--contrast` and `--psm` for whichever of the two you name; it used to drop
    them, because the wiring below tested `== "tesseract"` where the warning
    above tests `startswith`, leaving that one name in neither branch.

    **A value left as None is what lets auto-configuration fill it.**
    `analyse_image()` supplies exactly the parameters the caller did not, so
    substituting a default here silently turns auto off -- which is what made
    `--auto` inert on the `tesseract` backend: contrast and psm were always
    filled before the backend could look at the image.
    """
    if not backend.startswith("tesseract") or with_paddle_vl:
        ignored = [
            flag
            for flag, given in (
                ("--contrast", contrast is not None and not backend.startswith("tesseract")),
                ("--psm", psm is not None and not backend.startswith("tesseract")),
                ("--auto", auto and not backend.startswith("tesseract")),
                # Only auto-local has a pool to admit it to. Naming paddle-vl
                # directly is `--backend paddle-vl`, not this flag.
                ("--with-paddle-vl", with_paddle_vl and backend != "auto-local"),
            )
            if given
        ]
        if ignored:
            print(
                f"Note: {', '.join(ignored)} {'is' if len(ignored) == 1 else 'are'} "
                f"ignored by the {backend} backend.",
                file=sys.stderr,
            )

    ocr = get_backend(backend)

    if backend == "auto-local":
        return lambda path: ocr(path, with_paddle_vl=with_paddle_vl)

    if not backend.startswith("tesseract"):
        return ocr

    from .backends.tesseract import DEFAULT_CONTRAST, DEFAULT_PSM

    # The registry already switches auto on for `tesseract-auto`; saying so
    # here too keeps the decision about defaults below readable.
    auto = auto or backend == "tesseract-auto"

    if not auto:
        contrast = contrast if contrast is not None else DEFAULT_CONTRAST
        psm = psm if psm is not None else DEFAULT_PSM

    return lambda path: ocr(path, contrast=contrast, psm=psm, auto=auto)


def supported_extensions(backend: str) -> set[str]:
    """File extensions *backend* accepts.

    auto-local routes PDFs to Tesseract, so it reports Tesseract's full set —
    the registry reads this from each backend's own SUPPORTED_EXTENSIONS.
    """
    if backend == "auto-local":
        from .backends.tesseract import SUPPORTED_EXTENSIONS

        return set(SUPPORTED_EXTENSIONS)
    return _registry_extensions(backend)


def _send_to_triage(image_path: Path, error: "LowQualityError") -> None:
    """Move a file to the triage queue and write its manifest.

    The manifest (workspace/triage/<stem>.md) contains a score table and a short
    excerpt from each backend's transcript for human review.

    Args:
        image_path: Original file path (inside workspace/scans/).
        error:      LowQualityError carrying .scores and .transcripts.
    """
    TRIAGE_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# {image_path.stem}",
        "",
        "## Quality scores",
        "",
        "| Backend | Score |",
        "|---|---|",
    ]
    for name, score in error.scores.items():
        lines.append(f"| {name} | {score:.4f} |")

    lines += ["", "## Transcript excerpts", ""]
    for name, text in error.transcripts.items():
        excerpt = text.strip()[:500].replace("\n", " ")
        lines += [f"### {name}", "", excerpt, ""]

    manifest_path = TRIAGE_DIR / f"{image_path.stem}.md"
    manifest_path.write_text("\n".join(lines), encoding="utf-8")

    dest = TRIAGE_DIR / image_path.name
    shutil.move(str(image_path), dest)

    print(f"    → TRIAGE: {dest.name}")
    print(f"    → TRIAGE: {manifest_path.name}")


def transcribe_per_page(image_path: Path, ocr_fn: Callable[[Path], str]) -> list[str]:
    """Transcribe *image_path* one page at a time, returning a text per page.

    Needed only for a multi-page searchable PDF, which has to lay each page's
    words onto the page they came from. It costs roughly **twice** a
    whole-document pass -- measured, and not caused by anything we can avoid:
    reusing one Marker converter across the pages made no difference. See
    design research note 001 (Marker throughput and multi-page PDFs).

    That is why the caller takes this route only when the `pdf` format is
    actually asked for on a multi-page document, rather than always.
    """
    with page_documents(image_path) as pages:
        transcripts = []
        for number, page in enumerate(pages, start=1):
            with telemetry.timed("page_finish", page=number, of=len(pages), file=image_path.name):
                transcripts.append(ocr_fn(page))
        return transcripts


def process_file(
    image_path: Path,
    ocr_fn: Callable[[Path], str],
    triaged: list[str] | None = None,
    quality_gate: bool = False,
    backend: str | None = None,
    formats: list[str] | None = None,
    pdf_full_size: bool = False,
    pdf_font: str | None = None,
) -> None:
    """OCR a single file, write Markdown output, and move it to workspace/processed/.

    A transcript that scores below MIN_QUALITY_THRESHOLD goes to the triage
    queue instead of workspace/processed/, so a bad read is triaged rather than silently
    written out. There are two routes to that, because there are two things
    that know a transcript is poor:

    - ``auto-local`` scores every backend it ran in order to pick a winner, so
      it raises LowQualityError itself and hands over the whole score table.
      That table is what makes the triage manifest worth reading.
    - Any other backend produces one transcript and no opinion about it. When
      *quality_gate* is set, this function scores that transcript and applies
      the same threshold.

    The gate is opt-in for single backends rather than always on: it changes
    which files reach workspace/processed/, and turning it on silently would start
    diverting output for anyone already running `--backend tesseract`.

    Args:
        image_path:   Path to the file inside workspace/scans/.
        ocr_fn:       The OCR callable to use.
        triaged: Optional list to append filenames routed to triage.
        quality_gate: Score this backend's transcript and gate on it.
        backend:      Backend name, used to label the triage manifest.
        formats:      Output formats to write, defaulting to Markdown alone.
                      Every requested format is written for the same
                      transcript -- the OCR runs once regardless of how many
                      are asked for.
    """
    from .qa_score import LowQualityError

    print(f"  Processing: {image_path.name}")
    file_info = telemetry.describe_file(image_path)
    telemetry.record("file_start", backend=backend, **file_info)
    started = time.perf_counter()

    def _elapsed() -> float:
        return round(time.perf_counter() - started, 3)

    def _triage(exc: "LowQualityError") -> None:
        _send_to_triage(image_path, exc)
        if triaged is not None:
            triaged.append(image_path.name)
        telemetry.record(
            "file_finish",
            backend=backend,
            outcome="triaged",
            seconds=_elapsed(),
            reason=str(exc),
            **file_info,
        )

    # A multi-page searchable PDF needs one transcript per page, so that case
    # transcribes page by page. Everything else keeps the single
    # whole-document call, which is about twice as fast -- nobody should pay
    # the per-page cost for a format they did not ask for.
    pages = file_info.get("pages", 1)
    per_page = bool(formats) and "pdf" in formats and pages > 1
    page_transcripts: list[str] | None = None

    try:
        if per_page:
            print(f"    {pages} pages, transcribing individually for the PDF")
            page_transcripts = transcribe_per_page(image_path, ocr_fn)
            text = "\n\n".join(t.strip() for t in page_transcripts if t.strip())
        else:
            text = ocr_fn(image_path)
    except LowQualityError as exc:
        _triage(exc)
        return
    except Exception as exc:
        telemetry.record(
            "file_finish",
            backend=backend,
            outcome="error",
            seconds=_elapsed(),
            error=type(exc).__name__,
            reason=str(exc),
            **file_info,
        )
        raise

    if quality_gate:
        from .qa_score import MIN_QUALITY_THRESHOLD, combined_score, scores_english_text

        # The metrics are English-only, so a transcript in another script
        # scores 0.0 however well it was read. Gating on that would divert an
        # entire Armenian run to triage and report every file as poor quality.
        # Skipped with a reason rather than applied to a number that cannot
        # mean anything.
        quality_gate = scores_english_text(text)
        if not quality_gate:
            print(
                "    quality gate skipped: this transcript is not in the Latin script, "
                "and the score would be 0.0 whatever its quality",
                file=sys.stderr,
            )

    if quality_gate:
        score = combined_score(text)
        print(f"    quality={score:.4f}")
        if score < MIN_QUALITY_THRESHOLD:
            label = backend or "backend"
            _triage(
                LowQualityError(
                    f"Transcript ({label}, score={score:.4f}) is below "
                    f"threshold {MIN_QUALITY_THRESHOLD:.4f}",
                    scores={label: score},
                    transcripts={label: text},
                )
            )
            return

    # Written before the image moves: the PDF format embeds the scan, so every
    # format has to be produced while the file is still where it was read from.
    try:
        written = [
            outputs.write(
                name,
                image_path,
                text,
                PROCESSED_DIR,
                page_transcripts=page_transcripts,
                pdf_full_size=pdf_full_size,
                pdf_font=pdf_font,
            )
            for name in (formats or [outputs.DEFAULT_FORMAT])
        ]
    except Exception as exc:
        telemetry.record(
            "file_finish",
            backend=backend,
            outcome="error",
            stage="output",
            seconds=_elapsed(),
            error=type(exc).__name__,
            reason=str(exc),
            **file_info,
        )
        raise

    dest = PROCESSED_DIR / image_path.name
    shutil.move(str(image_path), dest)

    print(f"    → {dest.name}")
    for path in written:
        print(f"    → {path.name}")

    telemetry.record(
        "file_finish",
        backend=backend,
        outcome="processed",
        seconds=_elapsed(),
        chars=len(text),
        words=len(text.split()),
        outputs=[p.name for p in written],
        **file_info,
    )


def main(args=None) -> int:
    """Parse arguments and process all supported files found in workspace/scans/.

    Returns a process exit code -- 0 on success, 1 if any file failed or
    ``workspace/scans/`` is missing -- so that callers can propagate a partial failure
    instead of reporting success. Every failure this function decides on is
    returned rather than raised, which is what lets ``cli.main`` honour its own
    ``-> int`` contract.

    The one exception is not ours: argparse raises ``SystemExit`` on an
    unparseable argument list before this function regains control. Callers
    driving it programmatically with untrusted arguments should expect that.
    """
    parser = argparse.ArgumentParser(
        description="Batch OCR processor. Processes all images in workspace/scans/."
    )
    parser.add_argument(
        "--backend",
        choices=BACKENDS,
        default="tesseract",
        help=(
            "OCR backend to use (default: tesseract). "
            "'auto-local' selects the best available local backend per file: "
            "paddle or easyocr for images, tesseract-auto for PDFs. "
            "tesseract/tesseract-auto run locally without extra packages; "
            "easyocr/paddle use deep-learning models (downloaded on first run); "
            "claude uses the Anthropic vision API."
        ),
    )
    parser.add_argument(
        "--contrast",
        type=float,
        default=None,
        metavar="FACTOR",
        help="Contrast enhancement factor for the Tesseract backend (default: 2.0). "
        "1.0 = no change; try 3.0 for very faded originals. Ignored by all other backends.",
    )
    parser.add_argument(
        "--psm",
        type=int,
        default=None,
        metavar="MODE",
        help="Tesseract page segmentation mode (default: 3). "
        "3=auto, 6=uniform block, 11=sparse text. Ignored by all other backends.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-configure Tesseract contrast and PSM per image based on image analysis.",
    )
    parser.add_argument(
        "--with-paddle-vl",
        action="store_true",
        help=(
            "Add PaddleOCR-VL to the auto-local pool. Strongest local backend "
            "measured, and minutes per page rather than seconds, so it is opt-in."
        ),
    )
    parser.add_argument(
        "--format",
        "-f",
        dest="formats",
        action="append",
        metavar="FORMAT",
        help="output format to write, repeatable or comma-separated. "
        f"Choose from: {', '.join(outputs.FORMATS)}. "
        f"Defaults to {outputs.DEFAULT_FORMAT} when not given.",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="shorthand for --format markdown,pdf: also write "
        "workspace/processed/<name>.pdf, the scan with the transcript embedded "
        "as an invisible text layer, which is what makes it indexable in Preservica, "
        "CONTENTdm, Omeka and AtoM.",
    )
    parser.add_argument(
        "--pdf-full-size",
        action="store_true",
        help="embed the source image untouched rather than a downsampled access copy. "
        "Implies --pdf.",
    )
    parser.add_argument(
        "--pdf-font",
        default=None,
        metavar="PATH",
        help="TrueType font for the PDF text layer. Only needed for scripts the built-in "
        "font cannot encode.",
    )
    parser.add_argument(
        "--quality-gate",
        action="store_true",
        help="Score each transcript and divert anything below the quality threshold to "
        "workspace/triage/ for triage. Needs the 'qa' extra. auto-local always gates; this "
        "extends the same threshold to any single backend. The scoring is English-only, so "
        "it is skipped for a transcript in another script rather than failing it.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be processed, then stop without running OCR or moving anything.",
    )
    parser.add_argument(
        "--telemetry",
        default=None,
        metavar="PATH",
        help=f"Run log to append to (default: {telemetry.DEFAULT_LOG_PATH}). "
        "One JSON object per line; tail it to watch a long batch progress.",
    )
    parser.add_argument(
        "--no-telemetry",
        action="store_true",
        help="Do not write the run log.",
    )
    args = parser.parse_args(args)

    # --pdf predates --format and stays additive: it means "what I get by
    # default, plus a PDF". --format is a full specification, so `--format pdf`
    # writes only a PDF. Combining them unions the two, which is the reading
    # that cannot surprise anyone.
    formats = outputs.parse(args.formats)
    if (args.pdf or args.pdf_full_size or args.pdf_font) and "pdf" not in formats:
        if not args.formats:
            formats = [outputs.DEFAULT_FORMAT, "pdf"]
        else:
            formats = [*formats, "pdf"]

    # Fail here rather than on the first file. The gate needs the `qa` extra,
    # and discovering that mid-batch would leave some files processed and the
    # rest not.
    if args.quality_gate:
        from .qa_score import REQUIREMENTS, is_available

        if not is_available():
            print(
                f"Error: --quality-gate needs the 'qa' extra ({', '.join(REQUIREMENTS)}).\n"
                "Install it with: pip install -e '.[qa]'",
                file=sys.stderr,
            )
            return 1

    if not SCANS_DIR.exists():
        print(f"Error: scans directory not found at {SCANS_DIR}", file=sys.stderr)
        return 1

    extensions = supported_extensions(args.backend)
    files = sorted(f for f in SCANS_DIR.iterdir() if f.is_file() and f.suffix.lower() in extensions)

    if args.dry_run:
        # Answered before creating workspace/processed/ and before any OCR runs. It is
        # not free of the backend, though: knowing which files a backend can
        # read means reading its SUPPORTED_EXTENSIONS, so the extra has to be
        # installed. That beats duplicating the extension sets here, where they
        # would drift from the backends that own them.
        print(f"Backend: {args.backend} (dry run)")
        if not files:
            print(f"No files in {SCANS_DIR}/ with an extension {args.backend} can read.")
            return 0
        print(f"Would process {len(files)} file(s):")
        for f in files:
            print(f"  {f.name}")
        skipped = sorted(
            f.name
            for f in SCANS_DIR.iterdir()
            if f.is_file() and f.suffix.lower() not in extensions and not f.name.startswith(".")
        )
        if skipped:
            # The batch pipeline filters by the backend's supported extensions,
            # so a PDF simply vanishes under easyocr. Saying so is the whole
            # point of a dry run.
            print(f"\nWould skip {len(skipped)} file(s) {args.backend} cannot read:")
            for name in skipped:
                print(f"  {name}")
        return 0

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    if not files:
        print("No files to process in workspace/scans/")
        return 0

    print(f"Backend: {args.backend}")
    print(f"Found {len(files)} file(s) to process.\n")

    if not args.no_telemetry:
        log = telemetry.start_run(
            args.telemetry,
            backend=args.backend,
            formats=formats,
            files=len(files),
            bytes_total=sum(f.stat().st_size for f in files),
            scans_dir=str(SCANS_DIR),
            quality_gate=bool(args.quality_gate),
        )
        if log is not None:
            print(f"Run log: {log.path}  (run {log.run_id})\n")

    run_started = time.perf_counter()

    # Build after printing the header so any auto-local detection messages
    # appear after "Backend: auto-local" rather than before it.
    ocr_fn = build_ocr_fn(args.backend, args.contrast, args.psm, args.auto, args.with_paddle_vl)

    errors = []
    triaged = []
    for f in files:
        try:
            process_file(
                f,
                ocr_fn,
                triaged=triaged,
                quality_gate=args.quality_gate,
                backend=args.backend,
                formats=formats,
                pdf_full_size=args.pdf_full_size,
                pdf_font=args.pdf_font,
            )
        except Exception as exc:
            print(f"  ERROR processing {f.name}: {exc}", file=sys.stderr)
            errors.append(f.name)

    ok = len(files) - len(triaged) - len(errors)
    telemetry.finish_run(
        seconds=round(time.perf_counter() - run_started, 3),
        files=len(files),
        processed=ok,
        triaged=len(triaged),
        errors=len(errors),
    )

    print()
    if triaged:
        print(f"Triaged ({len(triaged)}): {', '.join(triaged)}")
    if errors:
        print(f"Completed with {len(errors)} error(s): {', '.join(errors)}")
        return 1

    print(f"Done. {ok} file(s) processed, {len(triaged)} sent to triage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
