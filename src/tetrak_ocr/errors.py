"""Exceptions raised by the package.

These exist mainly so that a missing optional backend fails as a library
should — with a catchable exception naming the extra to install — rather than
by printing to stderr and calling ``sys.exit(1)``, which is what the original
scripts did. That was reasonable when each file was run directly; it is not,
when a caller imports one backend and wants to fall back to another.
"""

from __future__ import annotations

from pathlib import Path


class OcrPipelineError(Exception):
    """Base class for every error this package raises."""


class MissingBackendError(OcrPipelineError):
    """A backend was requested but its optional dependency is not installed.

    The message names the extra to install, because "No module named
    'paddleocr'" tells a user what broke but not what to do about it.
    """

    def __init__(self, backend: str, extra: str, packages: str) -> None:
        self.backend = backend
        self.extra = extra
        self.packages = packages
        # `packages` may name one package or several, so avoid a trailing
        # relative clause that would have to agree in number with it.
        super().__init__(
            f"The '{backend}' backend needs {packages}, not installed here.\n"
            f"Install with:  pip install 'tetrak[{extra}]'"
        )


class BackendWithdrawnError(MissingBackendError):
    """A backend's extra has been withdrawn, so no ``pip install`` enables it.

    A :class:`MissingBackendError`, so callers that fall back to another
    backend still do, but the message must not name an extra that no longer
    exists: pip would warn and install nothing, and the user would be back
    where they started.
    """

    def __init__(self, backend: str, packages: str, reason: str) -> None:
        self.backend = backend
        self.extra = None
        self.packages = packages
        self.reason = reason
        OcrPipelineError.__init__(
            self,
            f"The '{backend}' backend needs {packages}, which this version of "
            f"Tetrak cannot be installed alongside.\n{reason}",
        )


class MissingFeatureError(OcrPipelineError):
    """An option was asked for whose optional dependency is not installed.

    :class:`MissingBackendError` for something that is not a backend, such as
    ``--orient armenian``, so the message does not call it one.
    """

    def __init__(self, feature: str, extra: str, packages: str) -> None:
        self.feature = feature
        self.extra = extra
        self.packages = packages
        super().__init__(
            f"{feature} needs {packages}, not installed here.\n"
            f"Install with:  pip install 'tetrak[{extra}]'"
        )


class UnknownBackendError(OcrPipelineError):
    """A backend name was requested that does not exist."""

    def __init__(self, name: str, known: list[str]) -> None:
        self.name = name
        self.known = known
        super().__init__(f"Unknown backend '{name}'. Choose from: {', '.join(known)}")


class UnknownFormatError(OcrPipelineError):
    """An output format was requested that does not exist.

    Carries the valid names: the useful thing to tell someone who typed
    ``--format pdff`` is what they could have typed instead.
    """

    def __init__(self, name: str, valid: list[str]) -> None:
        self.name = name
        self.valid = sorted(valid)
        super().__init__(f"Unknown output format '{name}'. Choose from: {', '.join(self.valid)}")


class MultiPageNotSupportedError(OcrPipelineError):
    """A multi-frame image was given to a backend that reads only frame 0.

    Raised instead of transcribing page one and returning it as though it were
    the whole document. Archival TIFF is often multi-page, and a partial
    transcript that looks complete is the failure mode this package treats as
    worst: it passes quality scoring, enters the archive, and misleads every
    reader after that.
    """

    def __init__(self, path: Path, backend: str, pages: int, use_instead: str) -> None:
        self.path = path
        self.backend = backend
        self.pages = pages
        self.use_instead = use_instead
        super().__init__(
            f"{path.name} has {pages} pages and the '{backend}' backend reads only the "
            f"first. Refusing rather than returning a partial transcript.\n"
            f"Use --backend {use_instead}, which reads every page, or split the file."
        )


class MultiPagePdfError(OcrPipelineError):
    """A searchable PDF was asked for on a document with more than one page.

    The text layer carries the transcript the pipeline chose, and a backend
    returns one transcript for a whole document rather than one per page.
    There is no honest way to divide it: the pages would be guesses, and a
    reader searching a 21-page programme would be sent to the wrong leaf while
    the file looked entirely correct.

    So this refuses, for the same reason
    :class:`MultiPageNotSupportedError` does. Per-page transcripts arrive with
    the positioned text layer -- see
    brief 008 (searchable PDF).
    """

    def __init__(self, path: Path, pages: int) -> None:
        self.path = path
        self.pages = pages
        super().__init__(
            f"{path.name} has {pages} pages, and a searchable PDF needs one transcript "
            f"per page rather than one for the document.\n"
            f"Refusing rather than putting every page's text on page one. Transcribe "
            f"without --pdf, or split the file into single pages first."
        )
