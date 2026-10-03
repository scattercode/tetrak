"""Command line entry point.

Replaces the old ``python scripts/ocr_tesseract.py image.jpg`` invocations with
a single ``tetrak-ocr`` command, so that callers do not need to know which
module implements which backend.

    tetrak-ocr backends
    tetrak-ocr ocr scan.jpg --backend tesseract-auto
    tetrak-ocr batch --backend auto-local
    tetrak-ocr evaluate --all --save
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import outputs, telemetry
from .errors import OcrPipelineError
from .registry import BACKENDS, available


def _cmd_backends(args: argparse.Namespace) -> int:
    """List backends, marking the ones this environment can actually run."""
    runnable = set(available())
    for name in BACKENDS:
        mark = "✓" if name in runnable else "·"
        note = "" if name in runnable else "  (extra not installed)"
        print(f" {mark} {name}{note}")
    return 0


def _cmd_ocr(args: argparse.Namespace) -> int:
    from .batch import build_ocr_fn

    # build_ocr_fn rather than get_backend: it applies the Tesseract tuning
    # flags and reports them when the chosen backend ignores them, which is
    # exactly what this subcommand needs and what batch already does.
    ocr = build_ocr_fn(args.backend, args.contrast, args.psm, args.auto, args.with_paddle_vl)
    path = Path(args.path)

    # Same rule as `batch`: a multi-page searchable PDF needs a transcript per
    # page, and nothing else does, so only that case pays for the per-page
    # pass. `--output`/stdout get the pages joined.
    from .batch import transcribe_per_page
    from .imaging import page_count

    wants_pdf = bool(args.formats and "pdf" in outputs.parse(args.formats)) or bool(
        args.pdf or args.pdf_full_size or args.pdf_font
    )
    page_transcripts = None
    if wants_pdf and page_count(path) > 1:
        page_transcripts = transcribe_per_page(path, ocr)
        text = "\n\n".join(t.strip() for t in page_transcripts if t.strip())
    else:
        text = ocr(path)

    # `--pdf PATH` names its own destination, so it stays on the direct route
    # rather than going through the format table, which writes beside the
    # source under the source's stem.
    explicit_pdf_path = args.pdf if isinstance(args.pdf, str) else None
    if explicit_pdf_path is not None:
        from .pdf_output import searchable_pdf_for

        destination = Path(explicit_pdf_path)
        searchable_pdf_for(
            path,
            text,
            destination,
            page_transcripts=page_transcripts,
            full_size=args.pdf_full_size,
            font_path=args.pdf_font,
        )
        print(f"Wrote {destination}", file=sys.stderr)

    # Unlike `batch`, this subcommand writes nothing unless asked: its default
    # output is stdout. So formats are only those explicitly requested, rather
    # than outputs.parse's default of Markdown.
    requested = outputs.parse(args.formats) if args.formats else []
    if explicit_pdf_path is None and (args.pdf or args.pdf_full_size or args.pdf_font):
        if "pdf" not in requested:
            requested = [*requested, "pdf"]

    for name in requested:
        written = outputs.write(
            name,
            path,
            text,
            path.parent,
            page_transcripts=page_transcripts,
            pdf_full_size=args.pdf_full_size,
            pdf_font=args.pdf_font,
        )
        print(f"Wrote {written}", file=sys.stderr)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    from . import batch

    forwarded = ["--backend", args.backend]
    if args.contrast is not None:
        forwarded += ["--contrast", str(args.contrast)]
    if args.psm is not None:
        forwarded += ["--psm", str(args.psm)]
    if args.auto:
        forwarded.append("--auto")
    if args.with_paddle_vl:
        forwarded.append("--with-paddle-vl")
    if args.quality_gate:
        forwarded.append("--quality-gate")
    if args.dry_run:
        forwarded.append("--dry-run")
    if args.telemetry:
        forwarded += ["--telemetry", args.telemetry]
    if args.no_telemetry:
        forwarded.append("--no-telemetry")
    for name in args.formats or []:
        forwarded += ["--format", name]
    if args.pdf or args.pdf_full_size or args.pdf_font:
        forwarded.append("--pdf")
    if args.pdf_full_size:
        forwarded.append("--pdf-full-size")
    if args.pdf_font:
        forwarded += ["--pdf-font", args.pdf_font]

    # `args=`, not `argv=` -- batch.main names its parameter `args`, and the
    # mismatch made `tetrak-ocr batch` raise TypeError on every invocation.
    return batch.main(args=forwarded)


def _cmd_evaluate(args: argparse.Namespace) -> int:
    # The harness lives outside the package, next to the corpus it reads, so
    # that evaluation data and evaluation code stay together. That also means
    # it is only importable from a checkout — evaluating needs the corpus, so
    # there is nothing useful to offer an installed-only user but a clear
    # explanation.
    # A console script does not get the working directory on sys.path the way
    # `python -m` does, so the harness is invisible without this even when the
    # user is standing in the repository root.
    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    try:
        from evaluation.ocr import harness
    except ImportError:
        print(
            "error: the evaluation harness was not found.\n"
            "Run `tetrak-ocr evaluate` from a checkout of the repository — it "
            "needs evaluation/ocr/corpus/, which is not shipped in the package.",
            file=sys.stderr,
        )
        return 1

    return harness.main(argv=args.harness_args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tetrak-ocr", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("backends", help="list backends and whether they are installed")
    p.set_defaults(func=_cmd_backends)

    def add_tuning_flags(parser: argparse.ArgumentParser) -> None:
        """Tesseract's per-image knobs, shared by `ocr` and `batch`.

        Declared in one place so the two subcommands cannot drift apart, and
        because the backend's own docstring documents these against `ocr` —
        they have to exist on both.
        """
        parser.add_argument(
            "--contrast",
            type=float,
            metavar="FACTOR",
            help="Contrast factor for Tesseract (default: 2.0); try 3.0 for faded originals.",
        )
        parser.add_argument(
            "--psm",
            type=int,
            metavar="MODE",
            help="Tesseract page segmentation mode (default: 3). 3=auto, 6=block, 11=sparse.",
        )
        parser.add_argument(
            "--auto",
            action="store_true",
            help="Auto-configure Tesseract contrast and PSM per image.",
        )
        parser.add_argument(
            "--with-paddle-vl",
            action="store_true",
            help=(
                "Add PaddleOCR-VL to the auto-local pool. It measures as the "
                "strongest local backend and wins where the rest of the pool is "
                "weakest, but costs minutes per page rather than seconds, so it "
                "is opt-in. Needs the paddle-vl extra; ignored by every other "
                "backend, which you name directly instead."
            ),
        )

    def add_format_flags(parser: argparse.ArgumentParser) -> None:
        """Output-format selection, shared by `ocr` and `batch`.

        Repeatable and comma-separated both work; `outputs.parse` reconciles
        them. The choices are not declared with argparse's `choices=` because
        that would reject `markdown,pdf` as a single token -- validation
        happens in `outputs.parse`, which understands both spellings and the
        aliases.
        """
        parser.add_argument(
            "--format",
            "-f",
            dest="formats",
            action="append",
            metavar="FORMAT",
            help="output format to write, repeatable or comma-separated. "
            f"Choose from: {', '.join(outputs.FORMATS)}. "
            f"Defaults to {outputs.DEFAULT_FORMAT}.",
        )

    def add_pdf_flags(parser: argparse.ArgumentParser) -> None:
        """Searchable-PDF flags, shared by `ocr` and `batch`."""
        parser.add_argument(
            "--pdf",
            nargs="?",
            const=True,
            default=False,
            metavar="PATH",
            help="shorthand for adding 'pdf' to --format: the scan with the "
            "transcript embedded as an invisible text layer, which is what "
            "makes it indexable in Preservica, CONTENTdm, Omeka and AtoM",
        )
        parser.add_argument(
            "--pdf-full-size",
            action="store_true",
            help="embed the source image untouched instead of a downsampled "
            "access copy. Implies --pdf. Larger files; use when the PDF is the "
            "deliverable rather than a derivative",
        )
        parser.add_argument(
            "--pdf-font",
            metavar="PATH",
            help="TrueType font for the text layer. Only needed for scripts the "
            "built-in font cannot encode; without one, such a transcript is "
            "refused rather than written as black boxes",
        )

    p = sub.add_parser("ocr", help="OCR a single file")
    p.add_argument("path", help="image or PDF to transcribe")
    p.add_argument("--backend", default="tesseract", choices=BACKENDS)
    p.add_argument("--output", help="write to this file instead of stdout")
    add_tuning_flags(p)
    add_format_flags(p)
    add_pdf_flags(p)
    p.set_defaults(func=_cmd_ocr)

    p = sub.add_parser("batch", help="process everything in workspace/scans/")
    p.add_argument("--backend", default="tesseract", choices=BACKENDS)
    p.add_argument(
        "--quality-gate",
        action="store_true",
        help="divert transcripts below the quality threshold to workspace/triage/ "
        "(needs the qa extra; English-only scoring, skipped for other scripts)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="list what would be processed, without running OCR or moving anything",
    )
    p.add_argument(
        "--telemetry",
        metavar="PATH",
        help=f"run log to append to (default: {telemetry.DEFAULT_LOG_PATH}); "
        "one JSON object per line, tail it to watch a long batch",
    )
    p.add_argument("--no-telemetry", action="store_true", help="do not write the run log")
    add_tuning_flags(p)
    add_format_flags(p)
    add_pdf_flags(p)
    p.set_defaults(func=_cmd_batch)

    # `evaluate` forwards its flags verbatim to the harness, which owns its own
    # argument parser. REMAINDER cannot do this — argparse rejects a leading
    # `--flag` before it reaches the positional — so main() uses
    # parse_known_args and hands the leftovers over.
    p = sub.add_parser(
        "evaluate",
        help="benchmark backends against the evaluation corpus",
        add_help=False,
    )
    p.set_defaults(func=_cmd_evaluate)

    return parser


def main(argv: list[str] | None = None) -> int:
    args, extra = build_parser().parse_known_args(argv)
    args.harness_args = extra
    if extra and args.command != "evaluate":
        print(f"error: unrecognized arguments: {' '.join(extra)}", file=sys.stderr)
        return 2
    try:
        return args.func(args)
    except OcrPipelineError as exc:
        # These carry actionable messages (which extra to install, which
        # backends exist); a traceback would bury them.
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
