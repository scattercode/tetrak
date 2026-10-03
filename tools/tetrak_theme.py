"""The Tetrak OCR design tokens, ported once for the Python tooling.

Two generators draw things that end up beside the site's own pages -- the
benchmark chart, which is embedded in them, and the slide deck, which is the
same material in another medium. Both need the site's palette and faces, and
both used to carry their own copy: the chart's was correct, the deck's was a
verbatim lift of *scattercode.dev*'s tokens, so the deck arrived in cobalt and
yellow with Memphis pop-cards while the chart beside it was warm paper and
clay. This module is the single port, so that cannot happen again.

The source of truth is `site/assets/scss/_tokens.scss`. When a value changes
there, change it here; nothing generates one from the other, because the SCSS
is compiled by Hugo and neither generator has a Sass toolchain. The values
below were checked against that file on 2026-08-19.

Fonts are the ones the site actually serves, vendored as TrueType in
`tools/fonts/` by `site/scripts/vendor-fonts.mjs` -- matplotlib cannot read
woff2, and PowerPoint wants a family name it can resolve locally. The stacks
fall back through the same faces the site's tokens name.
"""

from __future__ import annotations

from pathlib import Path

# --- Palette -----------------------------------------------------------------
# Warm off-white grounds three steps deep, a near-black that keeps a little
# brown in it, and one accent. `rule` is the only border colour in the system.
#
# `clay` is the *single* interface accent. There is no second one, and the
# engine colours below are not a licence to introduce one: they exist solely to
# tell OCR engines apart in a chart or a table, never to signal state.

LIGHT: dict[str, str] = {
    "paper": "#f7f3ec",
    "paper_2": "#efe9df",
    "paper_3": "#e2dacd",
    "ink": "#1e1c19",
    "ink_soft": "#6d675e",
    "rule": "#d8d0c2",
    "clay": "#b08d4f",
    "clay_deep": "#8a6a33",
    "amber": "#c9a86a",
    "engine_blue": "#5d7186",
    "engine_green": "#7f9384",
    "engine_orange": "#a8543a",
    "engine_purple": "#8a7f93",
    "engine_teal": "#5e8784",
}

# Dark is a genuine inversion rather than a recolour: the same hues with the
# paper steps darkened and the ink lifted, and clay moved up to amber's
# register so it still reads as an accent against a dark ground.
DARK: dict[str, str] = {
    "paper": "#1c1e21",
    "paper_2": "#25282c",
    "paper_3": "#323639",
    "ink": "#f2eee6",
    "ink_soft": "#a8a297",
    "rule": "#3c4045",
    "clay": "#c9a86a",
    "clay_deep": "#dcc08a",
    "amber": "#d8bc86",
    "engine_blue": "#8ea3b8",
    "engine_green": "#9db3a4",
    "engine_orange": "#c9765a",
    "engine_purple": "#a99fb2",
    "engine_teal": "#92b5b2",
}

# The names used in site/data/walkthrough.toml, which writes tokens the way the
# CSS does. Both generators read that file, so both need to resolve a token
# name to a colour without knowing which palette they are drawing in.
TOKEN_ALIASES = {
    "engine-blue": "engine_blue",
    "engine-green": "engine_green",
    "engine-orange": "engine_orange",
    "engine-purple": "engine_purple",
    "engine-teal": "engine_teal",
    "ink-soft": "ink_soft",
    "clay-deep": "clay_deep",
    "paper-2": "paper_2",
    "paper-3": "paper_3",
}


def token(name: str, palette: dict[str, str] | None = None) -> str:
    """Resolve a design-token name to a hex string.

    Accepts either the CSS spelling (`engine-blue`, as written in
    walkthrough.toml) or the Python one (`engine_blue`), so a caller reading
    the data file does not have to translate. Unknown names raise rather than
    falling back to a default: a token that has been renamed in the SCSS should
    stop the generator, not silently draw everything in one colour.
    """
    palette = LIGHT if palette is None else palette
    key = TOKEN_ALIASES.get(name, name).replace("-", "_")
    if key not in palette:
        raise KeyError(f"unknown design token {name!r} -- check site/assets/scss/_tokens.scss")
    return palette[key]


# --- Type --------------------------------------------------------------------
# Playfair Display carries the headings and is the reason the site reads as
# print rather than documentation. Source Serif 4 is the body face.
#
# There is deliberately no sans-serif here. The system's rule is that the serif
# *is* the interface chrome; the deck previously set every body run in Space
# Grotesk, which is what made it read as a different product.

FONT_DISPLAY = "Playfair Display"
FONT_BODY = "Source Serif 4"
FONT_MONO = "IBM Plex Mono"

# Fallback stacks, for matplotlib and anything else that resolves a list. They
# end at a face that ships with the renderer so a checkout that has not run
# `node site/scripts/vendor-fonts.mjs` still draws something.
DISPLAY_STACK = [FONT_DISPLAY, "Georgia", "DejaVu Serif"]
BODY_STACK = [FONT_BODY, "Georgia", "Charter", "DejaVu Serif"]
MONO_STACK = [FONT_MONO, "Menlo", "DejaVu Sans Mono"]

# TrueType copies of the three faces above, written here by the site's font
# vendoring script alongside the woff2 files it writes into site/assets/fonts/.
FONT_DIR = Path(__file__).resolve().parent / "fonts"


def register_matplotlib_fonts() -> None:
    """Make the vendored TrueType faces visible to matplotlib.

    Silent when the directory is absent, so the chart draws in the fallbacks
    rather than failing in a checkout that has not vendored them.
    """
    if not FONT_DIR.is_dir():
        return

    from matplotlib import font_manager

    for path in sorted(FONT_DIR.glob("*.ttf")):
        font_manager.fontManager.addfont(str(path))


# --- Chart mapping -----------------------------------------------------------
# How the two benchmark metrics are coloured wherever they are drawn together.
# Character similarity takes an engine colour and word recall takes the accent,
# so the pair is distinguishable without introducing a second interface colour.
# The ceiling reference is set back in `ink_soft`, exactly as the site's
# benchmark table sets back its `claude` column.
METRIC_TOKENS = {
    "chr": "engine_blue",
    "wrd": "clay",
    "ceiling": "ink_soft",
}


def chart_theme(mode: str) -> dict[str, str]:
    """The flat colour dict the chart generator draws with, for one mode.

    `mode` is "light" or "dark". Keys are the roles matplotlib is configured
    with rather than token names, because the chart sets each one in a
    different rcParam and reading `theme["grid"]` at the call site says more
    than reading `theme["rule"]`.
    """
    palette = {"light": LIGHT, "dark": DARK}[mode]
    return {
        "ground": palette["paper"],
        "ink": palette["ink"],
        "ink_soft": palette["ink_soft"],
        "grid": palette["rule"],
        "accent": palette["clay"],
        "chr": palette[METRIC_TOKENS["chr"]],
        "wrd": palette[METRIC_TOKENS["wrd"]],
        "ceiling": palette[METRIC_TOKENS["ceiling"]],
    }
