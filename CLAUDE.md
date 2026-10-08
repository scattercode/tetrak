# CLAUDE.md

Guidance for Claude Code when working in this repository.

This file is orientation and conventions. The reference material — backend
behaviour, routing, benchmark results, method and its caveats — lives in
`site/content/` and is published to Cloudflare Pages at https://tetrak.dev/. When you
need the detail, read the
site page rather than expecting to find it here, and when you change behaviour,
update that page rather than restating it here. Anything documented in two
places will drift.

## What this repository is

The public half of the project: the pipelines, what measures them, and the
site that publishes the results. Separable things that share a repo
deliberately, because the coupling is real: the site reads
`evaluation/ocr/benchmark.csv` and `registers.csv` at build time through module
mounts, and a publisher serves both pipelines rather than either. Product
management (briefs, decisions, research) lives in the private
`tetrak-product` repository; see "Briefs, decisions and research" below.

| Part | Path | What it is |
|---|---|---|
| The OCR pipeline | `src/tetrak_ocr/` | OCR backends behind one interface, a batch pipeline, and the metrics |
| The audio pipeline | `src/tetrak_audio/` | Placeholder. Audio transcription, to be built to the same shape |
| Publishing | `src/tetrak_publish/` | Placeholder. Transcripts to a destination; belongs to neither pipeline because both produce them |
| The evaluations | `evaluation/<pipeline>/` | One subpackage per pipeline: its corpus, its harness, its results. `evaluation/ocr/` is the only one so far |
| The tests | `tests/<pipeline>/` | Likewise. `conftest.py` stays at `tests/` — it is shared fixture setup |
| The site | `site/` | The Hugo documentation site — its own npm project, with `content/`, `layouts/` and `assets/` inside it |
| The Pages Functions | `functions/` | Cloudflare Pages Functions proxying Plausible. At the repository root, not in `site/`, because Cloudflare resolves them against the Pages root directory |

The Omeka S demo, with its pinned local stack, lives in its own repository,
`tetrak-omeka`, which uses Tetrak as an installed package.

The distribution is named `tetrak`, not `tetrak-ocr` — it carries all three
packages. The console script stays `tetrak-ocr`; `[project.scripts]` is
independent of the distribution name.

**A pipeline must not import another.** `tetrak_ocr` and `tetrak_audio` share
a distribution, not a dependency, and `tetrak_publish` depends on neither.

`tools/` holds things that are neither shipped nor tested: the presentation,
ground-truth and thumbnail generators. Their outputs are build artefacts —
`collateral/` is gitignored, and the deck is regenerated on demand rather than
committed. `tools/tetrak_theme.py` is the one port of the site's design tokens
into Python; the chart and the deck both draw from it, so neither can end up in
a different design from the pages they sit beside.

The deck and the site's `/research/walkthrough/` page render the same source:
prose and structure from `site/data/walkthrough.toml`, every figure from
`evaluation/ocr/benchmark.csv` at render time. Change the argument in the TOML;
never type a number into either renderer.

## Setup

```bash
brew install tesseract poppler          # macOS system dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'                 # add extras as needed: [dev,all,armenian] is everything
```

The Claude backend needs `ANTHROPIC_API_KEY` in `.env` at the repo root.

EasyOCR, PaddleOCR and Marker download model weights on first use (~100 MB,
~300 MB and ~500 MB–1 GB respectively), cached under `~/.EasyOCR/`,
`~/.paddleocr/` and the HuggingFace cache.

## Commands

Everything runs through the `tetrak-ocr` console script. See
[`site/content/reference/cli.md`](site/content/reference/cli.md) for the full surface.

```bash
tetrak-ocr backends                          # what is installed, and what each needs
tetrak-ocr ocr <path> --backend tesseract-auto
tetrak-ocr batch --backend auto-local        # workspace/: scans/ → processed/, failures to triage/
tetrak-ocr evaluate --all --save             # → evaluation/ocr/benchmark.{csv,md} + runs/

pytest -m "not slow"                           # the fast loop; what CI gates on
pytest                                         # adds the corpus-backed threshold tests
ruff check src tests evaluation tools
ruff format src tests evaluation tools

cd site && npm run start                       # the site at :1313
cd site && npm run lint                        # eslint, stylelint, markdownlint; covers functions/ too
cd site && npm run build                       # regenerates the API reference, then Hugo
cd site && npx playwright test                 # browser checks; starts its own server
python tools/generate_presentation.py          # → collateral/*.pptx (gitignored), Tetrak-themed, from the benchmark
python tools/generate_expected.py              # regenerate ground truth; needs an API key
python tools/generate_corpus_thumbnails.py     # → site/assets/images/corpus/ renditions
```

Backend names: `tesseract`, `tesseract-auto`, `easyocr`, `easyocr-hy`, `paddle`,
`paddle-vl`, `claude`, `marker`, `vision`, `auto-local`. `easyocr-hy` is stock EasyOCR with
the project's own Armenian recogniser swapped in — its own name, like
`tesseract-auto`, so the harness scores the difference rather than asserting it. `vision` is macOS-only — Apple's Vision
framework via `ocrmac`, declared with a `sys_platform` marker so `[all]` still
installs on Linux. `registry.py` is the single source of truth for that
list — add a backend there and the CLI, the harness and the docs all pick it up.

`batch --quality-gate` sends a poor transcript from any backend to
`workspace/triage/`. It judges a transcript, not an engine, so it is a flag
rather than a backend (an `auto-local-fast` backend was tried and withdrawn).
It is opt-in because it changes which files reach `workspace/processed/`, and
needs the `qa` extra, checked up front rather than on the first file.

## Conventions that matter

**The backend interface is fixed.** Every backend exposes
`SUPPORTED_EXTENSIONS: set[str]` and `ocr_image(path: Path, ...) -> str`.
Tesseract adds optional `contrast`, `psm`, `auto` and `lang`. Nothing else varies. That
uniformity is what lets `registry.py`, the batch pipeline and the harness treat
backends interchangeably; a backend that needs a different signature needs an
adapter, not a special case in the callers.

**Missing extras raise `MissingBackendError`, not `ImportError`.** Each backend
module sets `_IMPORT_OK` rather than exiting at import time, so the registry can
report which extra to install. Keep that pattern when adding a backend —
importing `tetrak_ocr` must never require every extra to be installed.

**Directories in `batch.py` are resolved from the working directory**, not from
`__file__`. `workspace/scans/`, `workspace/processed/` and `workspace/triage/`
are the user's directories, wherever they are running. They sit under
`workspace/` so the top of a project stays readable and the scans → processed →
triage flow is visible in one place. Their contents are gitignored; only
`.gitkeep` is committed, so be careful with new ignore rules.

**Nothing under `evaluation/<pipeline>/` is edited by hand.** `benchmark.{csv,md}` and
`runs/` are harness output; `corpus/expected/` is generated by
`tools/generate_expected.py`. Regenerate rather than patch.

**The ruff rule set is declared explicitly in `pyproject.toml`.** Do not remove
it and fall back to defaults: those differ between ruff versions — 0.15 and 0.16
reported 26 and 36 problems on identical code here — which means CI and a
developer's machine can disagree purely on which ruff got installed. Line length
is left to `ruff format`; `E501` is deliberately off.

**`slow` marks anything that reads the corpus or drives a real OCR engine.**
`pytest -m "not slow"` has to stay genuinely fast, because it is the loop
everyone actually runs.

## Things that will catch you out

**The auto-config bands are generated, not written.** `analyse_image()` in the
Tesseract backend picks contrast and PSM from two pixel statistics; the edges
live in `backends/tuning.py` between `GENERATED` markers, and
`evaluation/ocr/calibration/fit.py --write` produces them by minimising mean
regret over a committed configuration sweep. Do not edit the numbers —
`tests/ocr/test_calibration.py` re-derives them from the sweep and fails if
they disagree, and `ci.yml` runs `fit.py --check` — the same assertion — as a
merge gate, because that test is marked `slow` and the job that runs `slow`
tests only fires after merge. To change the bands, change the sweep, the split
or the fitter, and re-run it.

No number from that module belongs in prose, here or anywhere. The values were
copied into five places while they were hand-fitted and never moved; the first
honest re-fit changed every one of them. `tools/generate_tuning_data.py`
publishes them to the site at build time, the same way the benchmark tables are
read rather than typed.

**Four fixtures are held out, and the model is now the limit.** The corpus
doubled on 2026-09-28 — eight rasters that had sat untranscribed since August
were generated and then human-checked — which restored a real held-out set
after brief 007 spent the old one to repair `kinema-theater-ad-1920`. The
split is `wide-corpus` in `splits.toml`: twelve fitted, four held back.
`original-corpus` and `all-rasters` are frozen historical records; do not fit
to them.

What the widening showed is not what it was expected to show. Leave-one-out
regret sits at **~0.265 whatever the band budget**, and it got *worse* as the
corpus grew — 0.20 over eight fixtures, 0.265 over twelve — because the
material is now genuinely varied and linen postcards, newsprint, a playbill
and lithographed posters do not share one mapping from two pixel statistics to
a configuration. Neither the band count nor the corpus size is the binding
constraint any more. Read `tesseract-auto`'s corpus figures as in-sample. New
scans still go in `[excluded]` until someone classifies them.

**`features.py` already measures a third feature, `interior_gutters`, and
deliberately does not fit on it** — the note there says eight fixtures could
not support one. There are sixteen now, and the leave-one-out figure is the
argument for trying.

**Claude generates the ground truth it is then scored against.** Its ~0.90
average is self-consistency, not accuracy, and it is not stable run to run. Do
not quote it as a measurement of Claude. Human-checked ground truth is the
single highest-value improvement available to this project.

**Which transcripts have been checked is recorded**, per fixture, under
"Ground truth" in
[`evaluation/ocr/corpus/SOURCES.md`](evaluation/ocr/corpus/SOURCES.md). Read it
before trusting a score: an unverified reference is a known unknown in every
number derived from it, the band fit included. The first correction, on
`bancroft-magician-poster`, moved that fixture's character similarity +0.05 and
its word recall -0.08 — in opposite directions, both correctly. Correcting a
transcript invalidates its rows in the sweep; `sweep --fixture <stem> --save`
re-measures just that fixture.

**The Claude backend must keep raising on truncation.** It once used
`max_tokens=4096` and returned partial transcripts silently, which corrupted the
ground truth for the 21-page PDF and made Marker look like the worst backend on
PDFs when it is the best. The failure was self-concealing: the truncation was
reproducible, so Claude scored 0.95 against its own partial output. If you
change `MAX_OUTPUT_TOKENS`, keep the `stop_reason == "max_tokens"` guard.
[`site/content/research/in-depth.md`](site/content/research/in-depth.md) records the retraction.

**PaddleOCR v3 changed its constructor.** `use_gpu`, `show_log` and
`use_angle_cls` are gone; use `use_textline_orientation`. Its INFO logging is
suppressed at import via `logging.disable` and `GLOG_v=0` — remove those
temporarily if you need to debug Paddle itself.

**TIFF is handled differently per backend.** Tesseract and Marker take it
natively; Claude and EasyOCR convert to PNG in memory; PaddleOCR needs a real
file path, so it writes a temp PNG and cleans up in a `finally`.

**EasyOCR, PaddleOCR and Marker use module-level singletons.** First call in a
process is slow (weights load); subsequent calls are fast. Fine for batch work,
poor for one-shot interactive use.

**PDF support is not universal.** Tesseract (via poppler), Claude and Marker
read PDFs; EasyOCR and PaddleOCR do not. The batch pipeline filters `workspace/scans/` by
the selected backend's `SUPPORTED_EXTENSIONS`, so PDFs are silently skipped for
those two. That is intended.

**Walking the sitemap in a browser test: use `allPages`.** The sitemap carries
production URLs, because that is what a sitemap is for. Parsing it yourself and
visiting the `<loc>` values crawls **tetrak.dev** rather than the working tree,
so a deliberately broken page keeps passing. `allPages(request, baseURL)` in
`site/tests/site.spec.ts` keeps the path and drops the origin. It exists because
this happened once; it happened again when two new tests re-parsed the sitemap
by hand, and only a review caught it.

It does not bite under `npx playwright test`, which runs against `hugo server` —
that rewrites baseURL, so the sitemap under test already carries localhost. It
bites the moment anything points the suite at `public/`. Treat the helper as the
only supported way to enumerate pages.

**Navigating to an alias will destroy your execution context.** Aliases build as
`<meta http-equiv="refresh">` stubs, so `page.goto()` lands on the stub and the
redirect fires underneath whatever runs next — `page.evaluate` dies with
"Execution context was destroyed, most likely because of a navigation". It is a
race, so it passes locally and fails in CI. Skip them:

```ts
if (await page.locator('meta[http-equiv="refresh"]').count()) continue;
```

`allPages` returns aliases too, because they are in the sitemap. Any test that
navigates rather than just fetching needs that guard.

## Adding things

**A backend** — add `src/tetrak_ocr/backends/<name>.py` exposing
`SUPPORTED_EXTENSIONS` and `ocr_image`, guarding its import with `_IMPORT_OK`;
register it in `registry.py`; add its extra to `pyproject.toml`; add a page
section to [`site/content/reference/engines.md`](site/content/reference/engines.md). The CLI needs no change.

`_IMPORT_OK` must answer "can this actually run", not "did the import
statement succeed". `paddle-vl` imports its class from `paddleocr` and then
builds its pipeline through `paddlex`, so importing alone would have the
registry advertise a backend that fails on the first file with somebody
else's dependency error instead of `MissingBackendError`.

Two more steps once it reaches the benchmark, neither obvious from the code:

- Add an `[[engine]]` entry to [`site/data/walkthrough.toml`](site/data/walkthrough.toml)
  with `key` matching the CSV column stem, an `accent` token, and its prose.
  The walkthrough draws its bars from `benchmark.csv` but takes their names
  and colours from there, so a column with no entry renders one bar short
  and fails the browser suite rather than the build.
- Run `tetrak-ocr evaluate --backend <name> --save --merge` to put its column
  into `benchmark.{csv,md}`. `--all` re-runs every engine, which costs hours
  and paid API calls for figures that have not changed.

**An output format** — add a writer to `_FORMATS` in
[`src/tetrak_ocr/outputs.py`](src/tetrak_ocr/outputs.py) with its extension and a
one-line description, and nothing else: the CLI takes its `--format` choices,
help text and validation from that table. A writer takes
`(source, transcript, destination, **options)` and must tolerate options meant
for another format, because one dict is passed to all of them. Add an alias to
`_ALIASES` only for a spelling people will actually type. Document it in
[`site/content/reference/cli.md`](site/content/reference/cli.md).

**A telemetry event** — call `telemetry.record("<event>", **fields)` from
wherever the fact is known. The sink is process-global and a no-op when no run
is active, so nothing needs threading through a signature — which is the point,
since backends have a fixed `ocr_image(path) -> str`. Use
`telemetry.describe_file(path)` for the file fields so every event describes a
file the same way, and never let a new event raise: the log must not be able to
fail a run.

**A corpus item** — load the `tetrak-corpus` skill. It carries the whole
sequence (image, `SOURCES.md`, generated ground truth, thumbnails, the corpus
page card, re-running the benchmark), the two steps that fail silently, and
when the Tesseract auto-config bands need re-fitting.

**A site page** — add the file under `site/content/` and give it front matter; the
nav is built from the section structure. Load the `tetrak-ocr-design` skill
before touching layouts, styles or shortcodes.

**An article** — load the `tetrak-articles` skill. `site/content/articles/`
is the site's writing; the skill covers the archetype, how the URL is
actually assembled (neither segment comes from where you would think), the
`authors.toml` key, the standfirst's three jobs, relref linking, and the rule
that benchmark numbers are cited and never transcribed.

## Briefs, decisions and research

Product management (briefs, architecture decisions, design and user research,
the roadmap, article drafts) lives in the private `tetrak-product` repository,
not here. This repository's history starts at the split on 3 October 2026;
`tetrak-product`'s history holds everything before it, including the record of
this code.

From the code and the site, **cite it by number, never by path or link**:
"brief 008 (searchable PDF)", "ADR 001". A reader of the public repository
cannot follow a link into the private one. `site/tests/site.spec.ts` fails the
build if site content links into `product/`. When the reasoning behind a
decision matters to users, put a paragraph of it on the site's research pages
instead.

A feature that came from a brief usually lands as two pull requests: the code
here, and the brief's status in `tetrak-product`.

## CI

- `ci.yml` — ruff plus `pytest -m "not slow"` on every push and PR, installing
  core plus `[dev]` only. The heavy backends are not installed: they take
  minutes and every test touching them mocks the dependency.
- `corpus.yml` — `pytest -m slow` (real OCR over the corpus). On merge to
  `main` only when `src/`, `tests/`, `evaluation/` or `pyproject.toml`
  changed, plus weekly, so engine or dependency drift is still caught.
- `docs.yml` — `npm run build` plus the Playwright smoke tests. A build check only:
  Cloudflare Pages builds the site itself on every push to `main`, so nothing here
  deploys.
- `sphinx-docs.yml` — builds the `docs/` Sphinx site on every push and PR as a
  check. It deploys to GitHub Pages only when called by `release.yml` with a
  tag, after the wheel is on PyPI. See Deployment below.
- `pr-title.yml` — the pull request title must be a Conventional Commit, since
  squash-merging makes it the commit on `main` that the release reads.
- `release.yml` — see below.

The site and Sphinx checks skip paths they cannot be affected by (`docs/**`
for the site build, `site/**` for the Sphinx build) on push, never on pull
requests, where they are required checks. Every check workflow cancels
superseded in-flight runs.

## Deployment

The documentation site is deployed to **Cloudflare Pages** at
[tetrak.dev](https://tetrak.dev/), which builds and deploys automatically on
every push to `main`. No manual step is required.

The Sphinx CLI/API reference in `docs/` publishes separately, to GitHub Pages
at `https://scattercode.github.io/tetrak/`, via
`.github/workflows/sphinx-docs.yml`. Every push to `main` builds it as a
check, but nothing deploys from that path: `release.yml` calls the workflow
with the new tag as the last step of a release, after the publish job, so the
published reference matches the version that is on PyPI. Deploying from the
push itself used to publish an honest but unreleased `X.Y.Z.devN` title after
any merge that cut no release (`chore`, `ci`, `docs`, `test`), which is what
the page showed after the first post-split chore merge. So a change under
`docs/` reaches the published reference with the next release, not before.
To redeploy by hand, dispatch from `main` with the tag as an input
(`gh workflow run sphinx-docs.yml --ref main -f tag=5.14.1`): the
`github-pages` environment admits deployments from `main` only, so a dispatch
against the tag ref builds correctly and is then refused. It is scoped
strictly to the CLI and Python API reference; narrative content stays on the
Hugo site.

The Cloudflare Pages project:

| Setting | Value |
|---|---|
| Build command | `pip install -e . && cd site && npm ci && npm run build` |
| Output directory | `site/public` |
| Root directory | `/` |
| `NODE_VERSION` | `24` |
| `PYTHON_VERSION` | `3.11` |
| `HUGO_BASEURL` | `https://tetrak.dev/` |

Two things make that build command work, and both are load-bearing:

- **`pip install -e .` comes first.** `prebuild` regenerates
  `site/content/reference/api.md` by importing the installed package. The file
  is gitignored, so without the install the build fails rather than shipping a
  page of placeholders. Only the core dependencies are installed — the heavy OCR
  backends are extras and a docs build does not need them.
- **The mermaid SVGs are committed.** `prebuild` also runs
  `scripts/render-mermaid.mjs`, which now exits early when every diagram already
  has its rendered SVG. Cloudflare's build image has no browser and no way to
  `playwright install --with-deps`, so a diagram that is *not* committed cannot
  be drawn there. `docs.yml` runs `render-mermaid.mjs --check` to make sure that
  never reaches `main`.

Note the same caveat as scattercode.dev: Cloudflare deploys on push to `main`
regardless of whether the GitHub Actions checks passed. The checks gate the PR,
not the deploy.

## Analytics

Web analytics are **Plausible** behind a first-party proxy, the same
arrangement as scattercode.dev and velostevie. Load the
`plausible-proxy-installer` skill (scatterskills) for the method, why the
client IP must be forwarded, and how to verify it after deploy — it is not
restated here, because three copies of it is how the copies drift.

What is specific to this site:

| | |
|---|---|
| Dashboard | https://plausible.io/tetrak.dev |
| Snippet | `site/layouts/_default/baseof.html`, emitted only when `hugo.IsProduction` |
| Snippet path setting | `site/config/_default/hugo.toml` → `[params.analytics] plausible_src` |
| Script proxy | `functions/js/script.js.js` — **the upstream hashed URL lives here**, not in config |
| Event proxy | `functions/api/event.js` |

**`functions/` sits at the repository root, not in `site/`.** Cloudflare
resolves it against the Pages project's root directory, which is `/` here, so a
`site/functions/` would silently never be found. This is also why they need
their own lint script: ESLint will not read files above its config, so
`npm run lint:functions` runs from the repository root with
`--config site/eslint.config.mjs`.

## Git hooks

Managed by [Lefthook](https://lefthook.dev) (`lefthook.yml`), installed by
`npm ci` in `site/` or by `lefthook install`.

- **pre-commit** — `ruff check` and `ruff format --check` on staged Python, and
  the site's linters when site files are staged.
- **commit-msg** — [Conventional Commits](https://www.conventionalcommits.org/)
  via the shared `.githooks/commit-msg`.

Format: `<type>[(scope)][!]: <description>`. Types: `feat`, `fix`, `docs`,
`style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. The
description is non-empty with no trailing full stop; the header is 100
characters or fewer (72 preferred); a body is separated by a blank line.

## Releases and changelog

Releases are automated — do not perform them by hand.

- Every push to `main` runs `release.yml`: git-cliff computes the next semantic
  version from the commit history, tags it, publishes a GitHub Release, and
  then commits the regenerated `CHANGELOG.md` and pushes it to `main` with
  the tag in one atomic push, as the release App. The changelog commit *is*
  the tagged commit, so the tag's tree contains its own changelog and `main`
  never sits ahead of the tag.
- **`main` takes nothing by direct push, with exactly one exception.** The
  `scattercode-release` GitHub App (app id 5084449, org-wide) is the sole
  bypass actor on the ruleset, and `release.yml` pushes the changelog commit
  and its tag as that App. Everything else, every person included, goes
  through a pull request and the seven required checks.

  It holds **Contents: write and nothing else**, so the most it can do is
  commit and tag. Its credentials are the org secrets `RELEASE_CLIENT_ID`
  and `RELEASE_APP_PRIVATE_KEY`.

  Why an App: a ruleset bypass must name an actor, and GitHub Actions is not
  an installable app, so it cannot be named; a changelog pull request opened
  with `GITHUB_TOKEN` never triggers the required checks, so it could never
  merge either. Issuing CI an admin token was the alternative and was
  declined. Tags are unaffected: a tag is not a branch.
- After tagging, `release.yml` builds the sdist and wheel from the tag and
  publishes them to PyPI as **`tetrak`** through a Trusted Publisher (the
  `pypi` GitHub environment; no token is stored). The distribution is
  `tetrak`, the import package `tetrak_ocr` and the command `tetrak-ocr` —
  install instructions and error messages say `pip install tetrak`, never
  `tetrak-ocr`, which is a name we do not own.
- Once the wheel is published, `release.yml` calls `sphinx-docs.yml` with the
  tag to deploy the API reference at that version. The reference never
  deploys from a plain push to `main`.
- Never edit `CHANGELOG.md` by hand — change the commit messages or the
  `commit_parsers` in `cliff.toml` instead.
- Never create tags or Releases manually.
- **The package version comes from the git tag**, via `hatch-vcs`. Do not add a
  `version = "..."` literal back to `pyproject.toml`: nothing updates it, so it
  silently goes stale. `src/tetrak_ocr/_version.py` is generated at build time
  and gitignored.
- `fix` → patch, `feat` → minor, `!` → major. Choose types accordingly.
- Tooling commits use `chore(release):` or `chore(changelog):` so the parser
  skips them.
