---
name: tetrak-ocr-design
description: "Design system for the Tetrak OCR documentation site — the themeless Hugo build in this repo. Use when adding or editing pages, writing shortcodes, changing styles or layouts, adding images or corpus scans, or touching anything under site/. Covers the palette, typography, spacing, the three-state theming rule, component classes, shortcode reference, image pipeline and content conventions."
---

# Tetrak OCR design system

Printed-page documentation for an OCR benchmark. Warm paper grounds, a single
clay accent, Playfair Display over Source Serif 4, and no boxes — hierarchy
comes from the type scale and from whitespace.

The site is **themeless** and lives in **`site/`**, its own npm project:
layouts in `site/layouts/`, styles in `site/assets/scss/`, pages in
`site/content/`. There is no `themes/` directory and no external theme. Every
npm command below is run from `site/`.

The Python package it documents sits at the repository root. The files the
site reads from there — `evaluation/ocr/benchmark.csv`,
`evaluation/ocr/registers.csv` and `LICENSING.md` — are mounted into Hugo's
assets by `[module.mounts]` in `site/config/_default/hugo.toml`, because
`os.ReadFile` cannot see above the project root. (The band table's data is
different: `tools/generate_tuning_data.py` writes `site/data/tuning.toml`
during `prebuild`.) Anything else the site needs from the repository needs a mount
too; that is deliberate, since it keeps the reach declared in one place.

## Provenance, and one thing not to undo

The design came from a Claude Design handoff that shipped two layers: a generic
newsprint kit called **Broadsheet** (`_ds/styles.css`) and a prototype page
(`OCR Pipeline Site.dc.html`) that loads it.

**The prototype overrides Broadsheet wholesale.** It defines its own `:root` —
warm paper/ink/clay, Playfair Display — and never references a single
`--color-*` token from Broadsheet. The rendered design, and therefore this
site, is the prototype's. Broadsheet's cyan `#0088b0` and magenta `#d6006c`
accents, its Source Serif 4 headings and its `.cmyk` process-plate image
treatment are **not** part of this system. Do not "restore" them.

What the site does keep from Broadsheet is structural, and it is worth keeping:

- Sections are separated by whitespace, never by rules, borders or cards.
- Layout is left-aligned and asymmetric; content hugs the left, air on the right.
- The serif is the interface chrome — no sans-serif is introduced for UI.
- The accent is used small and deliberately, like spot colour.

## Palette

| Token | Light | Dark | Use |
|---|---|---|---|
| `--paper` | `#f7f3ec` | `#1c1e21` | Page ground |
| `--paper-2` | `#efe9df` | `#25282c` | Code blocks, inset surfaces, search panel |
| `--paper-3` | `#e2dacd` | `#323639` | The deepest inset step |
| `--ink` | `#1e1c19` | `#f2eee6` | Body text |
| `--ink-soft` | `#6d675e` | `#a8a297` | Captions, kickers, secondary text |
| `--rule` | `#d8d0c2` | `#3c4045` | The only border colour in the system |
| `--clay` | `#b08d4f` | `#c9a86a` | The single accent: fills, marks, focus rings |
| `--clay-deep` | `#8a6a33` | `#dcc08a` | Accent text on paper — clears the contrast floor |
| `--amber` | `#c9a86a` | `#d8bc86` | Rare secondary warm |

**Engine colours** — `--engine-blue` `#5d7186`, `--engine-green` `#7f9384`,
`--engine-orange` `#a8543a`, `--engine-purple` `#8a7f93`. These exist only to
tell OCR engines apart in diagrams and charts. Never use them for interface
state.

`--clay` is the *only* interface accent. Do not add a second one.

## Typography

| Token | Face | Use |
|---|---|---|
| `--font-display` | Playfair Display | Headings. The reason the site reads as print rather than documentation |
| `--font-body` | Source Serif 4 | Body copy |
| `--font-mono` | IBM Plex Mono | Code, kickers, figures, anything tabular |

Fonts are self-hosted from `site/assets/fonts/`, vendored by
`node scripts/vendor-fonts.mjs` and committed — never link a font CDN. The
`@font-face` rules are in `_fonts.scss`; `fonts.html` publishes every face and
preloads the two above the fold.

**Publishing matters.** Hugo only emits an asset something asks for, so a face
that nothing references is silently dropped from the build while `@font-face`
goes on pointing at it — a 404 per face and a page rendering in its fallback
without saying so. `check-build-output.mjs` fails the build if the CSS
references a font that is not in `public/`.

- Sentence case for all headings, never title case.
- `##` is the top level inside a page; `#` is the page title, rendered by the
  template. Never use `#` in content.
- Numerals that line up in a column get `font-variant-numeric: tabular-nums`.

## Measure and rhythm

| Token | Value | Use |
|---|---|---|
| `--measure` | `60ch` | Default prose column |
| `--measure-tight` | `44ch` | Standfirsts, captions |
| `--page-max` | `1220px` | Outer page width |
| `--page-pad` | `32px` | Page gutter |
| `--rail` | `220px` | The on-this-page rail |
| `--gap` | `64px` | Column gap |

Spacing is done with flex/grid `gap`, not per-element margins.

## Theming — three states, not two

The reader has three states, and getting this wrong is the classic bug:

1. An explicit choice stamps `data-theme="dark"` or `data-theme="light"`.
2. The default "system" setting stamps **nothing** — only `prefers-color-scheme`
   separates light from dark.

So: `:root` carries the complete light palette; `@media (prefers-color-scheme:
dark)` redefines *only tokens*, guarded as `:root:not([data-theme="light"])`;
and `:root[data-theme="dark"]` redefines them again so the toggle wins both ways.
`_tokens.scss` does this with a `dark-tokens` mixin — follow that pattern.

**Never give a colour its only definition inside a media or `[data-theme]`
block.** A colour defined only there never applies in the un-stamped state, and
the page renders one theme's text on the other theme's ground.

The one exception in the codebase is `.lightbox-overlay__caption`, which is
fixed white because the overlay scrim is the same dark in both themes. It is
commented as such.

The stored choice is applied before first paint by an inline script in
`baseof.html`; `app.js` only handles the toggle.

## SCSS file structure

`site/assets/scss/main.scss` is the entry point. Edit the right partial:

| Partial | Holds |
|---|---|
| `_tokens.scss` | Custom properties, dark-mode mixin, resets, base type |
| `_components.scss` | Reusable UI: kicker, buttons, code blocks, admonitions, tabs, tables, figures, lightbox, search |
| `_app.scss` | Page-level layout: masthead, page grid, footer, home, motion, narrow screens |

Never put page-level rules in `_tokens.scss` or component rules in `_app.scss`.

Processed by Hugo Pipes with Dart Sass. `site/scripts/setup-dartsass.mjs` runs on
`npm install` and symlinks `node_modules/.bin/sass` to the native binary —
without it the build fails with "unexpected EOF when executing sass", because
`sass-embedded`'s JS wrapper does not implement the Embedded Sass Protocol.

## Component classes

| Class | What it is |
|---|---|
| `.kicker` | Small mono label above a heading. The section signature; most of what makes the pages read as a set |
| `.standfirst` | The lead paragraph, set larger and softer |
| `.btn-search`, `.btn-icon` | The masthead controls |
| `.highlight` | Code block — `--paper-2` ground with a clay rule down the left, no box |
| `.copy-btn` | Added by script, so a reader without JS is not shown a dead button |
| `.admonition` (`--warning`, `--caution`) | Marginalia: a left rule and a mono title, never a boxed callout |
| `.tabs` / `.tabs__label` / `.tabs__panel` | Radio-driven, so no script and free keyboard support |
| `.table-scroll` | Wraps wide tables so the page body never scrolls sideways |
| `.benchmark` | The results table, with `.is-best`, `.is-ceiling`, `__summary`, `__ref` |
| `.figure`, `.figure--themed` | Figures; the themed variant ships light and dark renditions |
| `.lightbox`, `.lightbox-overlay` | Corpus thumbnails and their overlay |
| `.search`, `.search__hit` | The search modal |
| `.people`, `.person` | The about page's bios: a clay rule above each, two columns, no box |
| `.tag`, `.tag-list` | An article's taxonomy labels. A mono label with a clay `#`, never a coloured pill — see below |
| `.article-row` | One article in a listing. A fixed date track on the left, title, lead, tags |
| `.articles`, `.articles__year-label` | The articles index and tag pages: rows grouped under a soft display-size year |
| `.article-meta` | Date · reading time · byline, under an article's standfirst |
| `.article-author` | Who wrote it, at the foot. `.person` seen smaller — a clay rule and air, no box |
| `.article-nav` | Previous and next, either side of a hairline |
| `.wt`, `.wt-*` | The walkthrough page only — see below |

There is no `.card`. The page is an open sheet — do not add boxes for layout.
`.person` is the closest the system comes to one, and it is still only a rule
above the block and air around it.

## The walkthrough page

`/research/walkthrough/` is the one page that sets out to be graphic rather
than quiet: it is the slide deck's argument laid out as a page. It gets there
**within** this system rather than around it, and that constraint is the whole
reason it still looks like the same site:

- No cards, no boxed callouts, no second accent. Scale comes from the corpus
  imagery, from display-size Playfair numerals, and from air.
- The only marks are `--rule` hairlines and 2px `--clay` rules above a block.
- The per-document score rows and the matplotlib chart colour engines with
  the `--engine-*` tokens and nothing else. There used to be a set of
  CSS-drawn average bars above the results table as well; they showed what the
  chart below the table already shows, and were removed in October 2026.

If a section here seems to want a border to hold it together, it wants more
space instead.

It is driven by `site/data/walkthrough.toml` (prose and structure) and
`evaluation/ocr/benchmark.csv` (every figure), rendered by
`layouts/research/walkthrough.html`. `tools/generate_presentation.py` renders
the same two into the slide deck. **Never type a figure into either renderer**,
and keep prose in the TOML free of numbers — the deck once carried sentences
like "0.91 against Claude's 0.98" in its source and disagreed with the harness
within a fortnight.

### `wide: true`

Front matter only the walkthrough sets. `.page` is a two-column grid with a
fixed `--rail` track, so a page that renders no rail still reserves 220px plus
the 64px gap and sits off-centre. `wide: true` makes `baseof.html` emit
`.page--wide`, which collapses the track, and suppresses the rail outright.

Full-bleed bands inside it use `margin-inline: calc(var(--page-pad) * -1)` —
**never** `calc(50% - 50vw)`, which overflows by the scrollbar width and trips
the suite's "no page scrolls sideways" test.

## The articles section

`/articles/` is the site's writing — the state of archive digitisation and OCR,
and progress notes on the pipeline and the Armenian model. It is a blog, and it
is the one part of the site that is dated and signed, but it is not a second
design: it opens with the same kicker, `h1` and standfirst as every other page,
and everything it adds is apparatus rather than decoration.

Where files go, how the URL is assembled, front matter, relref linking and the
rule against transcribed numbers are content rules: load the `tetrak-articles`
skill for those. What follows is the design side.

Layouts are `layouts/articles/list.html` and `layouts/articles/single.html`;
both listings — the index and the tag pages — render
`partials/article-list.html`, so a row looks the same wherever it appears.

### The author register

`data/authors.toml` is the byline register. Front matter carries a **key**, not
a name, and `partials/author.html` resolves it and fails the build on a missing
or unknown one — the same bargain the `figure`, `lightbox` and `person`
shortcodes make with a missing asset. The biographies stay in `content/about.md`
as prose; only the name, a one-line role and the LinkedIn handle live here, and
`linkedin` is the handle rather than a URL for the same reason `{{< person >}}`
insists on it.

Chain the guards rather than writing them as separate `if`s. `errorf` logs and
carries on, so an article with an unknown key would otherwise fail once for the
key and again for the name it could not have had, and the second message is the
one that scrolls into view.

### Tags get no colours

The other two sites give each tag its own accent, with a `.tag--<slug>` rule per
tag. **This one does not, and must not.** Clay is the single interface accent;
thirty tags in thirty hues is a second accent arriving by the back door. A tag
here is the kicker with a link on it: a small mono label, a clay `#`, and the
accent on hover like every other link.

`capitalizeListTitles = false` in `hugo.toml` keeps a tag lowercase on its own
page. Hugo title-cases derived list titles, which published the tag `ocr` as a
page headed "Ocr" — a word the site does not use anywhere else. The list pages
that want a real title have an `_index.md` giving them one, including
`content/tags/_index.md`, which exists for exactly that reason.

### Where the taxonomy templates live

`layouts/term.html` and `layouts/taxonomy.html`, **not** `layouts/_default/`.
Hugo 0.161 resolves the flat path first: with both present, `_default/term.html`
never matched and the term pages rendered through `_default/taxonomy.html`
instead — an empty tag index in place of the article list, with a green build.
`_default/list.html` and `_default/single.html` still work where they are, which
is what makes this easy to get wrong.

## Shortcodes

| Shortcode | Usage |
|---|---|
| `{{< figure src="design/x.webp" alt="…" caption="…" class="…" >}}` | Image through the asset pipeline. `src` is relative to `site/assets/images/` |
| `{{< figure-themed src="evaluation/benchmark-comparison" alt="…" >}}` | Light/dark pair, so a chart drawn on white does not glare on a dark page. `src` is the **base name**; it resolves `<src>-light.png` and `<src>-dark.png` |
| `{{< lightbox src="corpus/name" alt="…" title="…" width="170" >}}` | Corpus thumbnail linking to its large rendition. Resolves `<src>.webp` and `<src>-large.webp` |
| `{{< benchmark >}}` / `{{< benchmark metric="sec" >}}` | The corpus results table, read from `evaluation/ocr/benchmark.csv` at build time |
| `{{< registers >}}` / `{{< registers metric="chr" >}}` / `{{< registers view="summary" >}}` | The Armenian per-register table, read from `evaluation/ocr/registers.csv`. `bold-best="false"` drops the best-in-column marking |
| `{{< bands >}}` / `{{< bands setting="psm" >}}` / `{{< bands provenance="true" >}}` | The Tesseract auto-configuration bands, read from `site/data/tuning.toml` |
| `{{< note kind="warning" title="…" >}}…{{< /note >}}` | An admonition. `kind` is `note`, `warning` or `caution`; `title` optional |
| `{{< tabs >}}{{< tab "macOS" >}}…{{< /tab >}}{{< /tabs >}}` | Tabbed content. The tab label is a **positional** argument |
| `{{< include "LICENSING.md" >}}` | Inlines a file from the repo — positional, repo-root relative |
| `{{< people >}}{{< person name="…" role="…" linkedin="handle" >}}…{{< /person >}}{{< /people >}}` | The about page's bios. `linkedin` is the **profile handle**, not the URL |
| `{{% generated %}}` | Marks a page as machine-written — used by the API reference |

Both `figure` and `lightbox` call `errorf` when the asset is missing, so a bad
path fails the build rather than shipping a broken image.

`person` guards the same way: a missing `name` fails the build, and so does a
full URL passed as `linkedin` — the host is built in the template, because a
URL in a shortcode attribute trips markdownlint's MD034 and switching that rule
off would stop it catching bare URLs in the prose it is actually for.

**Several of these are partials with a shortcode wrapper**, because a layout
cannot call a shortcode and the walkthrough needs the same markup:
`partials/benchmark.html`, `partials/registers.html`, `partials/bands.html`,
`partials/lightbox.html` and `partials/figure-themed.html`. They take a dict rather than shortcode
arguments; the shortcode is a two-line wrapper that builds it. Change the
partial, not the wrapper. `partials/walkthrough-scores.html` is the one that
has no shortcode — it only ever had one caller.

**Never write raw markdown `![alt](path)` for images.** That was how 19 dead
images shipped: raw markdown bypasses the shortcodes' existence check.

## Images

- Everything lives under `site/assets/images/` — never `static/images/` — so Hugo's
  pipeline can resize and convert it.
- Corpus renditions are **committed**, generated by
  `tools/generate_corpus_thumbnails.py` into `site/assets/images/corpus/`. They need
  poppler and Pillow, which is why they are not built in CI. `{{< lightbox >}}`
  links the pair as-is rather than re-encoding an already-optimised WebP, so
  the sizes chosen in that script are the sizes shipped.
- Delete `site/resources/_gen/images/` to force a reprocess.

## Linking, and the baseURL trap

The site publishes at the **root** of `https://tetrak.dev/`, so the trap below is
currently dormant — but the convention it produced stays, because it is the
reason the move off a path-based URL cost nothing.

Under the old GitHub Pages URL, `https://scattercode.github.io/ocr-pipeline/`,
`relURL` and `absURL` treated a **leading slash as already rooted** and dropped
the baseURL's path segment:

| Expression | Result under a path baseURL | |
|---|---|---|
| `{{ "/licensing" \| relURL }}` | `/licensing` | wrong — loses `/ocr-pipeline` |
| `{{ "index.json" \| relURL }}` | `/ocr-pipeline/index.json` | right — no leading slash |
| `{{ .PageRef }}` | `/install` | the raw config string, not a link |
| `{{ .URL }}` on a menu entry | `/ocr-pipeline/install/` | right |

This took out the entire masthead once: every nav link pointed at the domain
root, and nothing failed, because the links were well-formed — just aimed
somewhere else.

**Link to pages, not to strings.** `site.Home.RelPermalink`, `.RelPermalink`,
`site.GetPage "/licensing"`, or `.URL` for a menu entry. Going through the page
means a rename fails the build instead of publishing a link that 404s. Where a
partial resolves a page by path, pair it with `errorf` in the `else` branch.

Keep doing this even though a root baseURL now forgives the shortcut. Writing
links through the page object is what made the domain move a one-line config
change instead of an audit of every template, and a future move to a path —
or a preview deploy served from a subdirectory — would reopen the trap.

`site/tests/site.spec.ts` follows every internal link on every page and checks the
masthead stays under the baseURL path.

## No mkdocs markup

The site was migrated from mkdocs-material. Its extensions are **not** available
and fail silently — Hugo renders the markdown and prints the rest as visible
text. None of these belong in `site/content/`:

- `{ loading=lazy }`, `{ .glightbox … }`, `{ width="…" }` — `attr_list`
- `<div … markdown>` — `md_in_html`
- `!!! note` / `=== "Tab"` — use `{{< note >}}` and `{{< tabs >}}`
- `:material-icon:` — no icon font is loaded

`site/tests/site.spec.ts` checks every page in the sitemap for leaked markup and for
images that fail to load. Both guards have been confirmed to fail when the
defect is reintroduced.

## Content conventions

- **British English** throughout: behaviour, colour, organise, serialise.
- Sentence case headings.
- Write for a competent developer who has already hit the problem. Depth beats
  brevity; there are no word limits.
- Claim nothing the data does not show. Where a number is published, it is
  read from `benchmark.csv`, `registers.csv` or `tuning.toml` by a shortcode,
  never transcribed, so the page cannot disagree with the data.
- `claude` is a **ceiling reference**, not a competitor: it generated the ground
  truth everything else is scored against. Mark it as such and exclude it from
  "best local".

## Build-time over runtime

The site's priority is a fast page for the reader; a longer build is an
acceptable trade. The benchmark table, the search index, the API reference and
every image are built. JavaScript is reserved for what genuinely needs the
browser: the search modal, the theme toggle, copy buttons, the lightbox.

## Before committing

All run from `site/`:

```bash
cd site
npm run lint          # ESLint, Stylelint, markdownlint
npm run build         # Hugo, after regenerating the API reference
npx playwright test   # starts its own server
```
