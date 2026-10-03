"""Sphinx configuration for the tetrak CLI/API reference.

Published to GitHub Pages by .github/workflows/sphinx-docs.yml. Scoped to
CLI + Python API reference only -- narrative content (corpus, engines,
routing, licensing) lives on the Hugo site at https://tetrak.dev/.
"""

from __future__ import annotations

project = "tetrak"
copyright = "2026, Stephen Masters, Yvette Mankerian"
author = "Stephen Masters, Yvette Mankerian"

try:
    from tetrak_ocr._version import version as release
except ImportError:  # a bare checkout, not yet built with hatch-vcs
    release = "0.0.0"

# Sphinx's default page title is "{project} {release} documentation", and
# hatch-vcs derives `release` from git describe -- so on any commit that is
# not exactly a tag it carries PEP 440 build metadata: "5.10.2.dev2+g9f4085a79".
# The segment after "+" is the commit hash, which is noise in a browser tab
# and was being published verbatim.
#
# Stripped for display only. The `.devN` part stays: it is the honest signal
# that a build came from an untagged commit, and hiding it would let the docs
# claim a version that was never released. A release build has neither part
# and reads simply "tetrak 5.11.0 documentation".
version = release.split("+", 1)[0]
html_title = f"{project} {version} documentation"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxarg.ext",
    "myst_parser",
]

autosummary_generate = True
autodoc_member_order = "bysource"
napoleon_google_docstring = True
napoleon_numpy_docstring = True

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
root_doc = "index"

html_theme = "furo"
html_theme_options = {
    "source_repository": "https://github.com/scattercode/tetrak",
    "source_branch": "main",
    "source_directory": "docs/",
}
