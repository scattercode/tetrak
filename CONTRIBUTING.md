# Contributing

Thanks for your interest in Tetrak. This document covers how we work in this
repository: the checks, the commit style, and the automation they feed. It
applies to us as much as to anyone sending a pull request.

`CLAUDE.md` is the fuller orientation (the layout, the conventions and the
things that will catch you out), and [tetrak.dev](https://tetrak.dev/) is the
reference for how the backends behave and how they are measured.

## Getting set up

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'                  # add extras for the backends you need
brew install tesseract poppler           # or apt-get install tesseract-ocr poppler-utils
cd site && npm ci                        # the documentation site
```

`npm ci` also installs the git hooks (Lefthook): Ruff and the site's linters
before each commit, and the Conventional Commits check on every commit
message. If they are not active, run `lefthook install`.

## The checks

Everything CI runs, runnable by hand:

```bash
ruff check src tests evaluation tools docs
ruff format --check src tests evaluation tools docs
pytest -m "not slow"                     # fast; the heavy backends are mocked
pytest -m slow                           # real OCR over the corpus; minutes
cd site && npm run lint && npm run build && npx playwright test
```

The fast suite and the site checks gate every pull request. The slow suite
runs on merge and weekly.

## Benchmark figures

Published figures come from `evaluation/ocr/benchmark.csv`, which the harness
writes; the site reads it at build time. Never type a benchmark number into a
page, an article or a docstring: cite it. And never edit the harness's output
by hand: re-run `tetrak-ocr evaluate --all --save`.

## Commit style

Pull requests are squash-merged, so **the pull request title becomes the
commit on `main`**, and it must be a
[Conventional Commit](https://www.conventionalcommits.org/):

```text
<type>[(scope)][!]: <description>
```

- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
  `build`, `ci`, `chore`, `revert`.
- The description is non-empty, has no trailing full stop, and the header is
  100 characters or fewer (72 or fewer preferred).

This is load-bearing, not cosmetic: the release automation computes the next
version from the commit types (`fix` → patch, `feat` → minor, `!` → major)
and writes `CHANGELOG.md` from the messages. A check fails a pull request
whose title does not parse.

## Releases and the changelog

Releases are fully automated; never perform one by hand. Every push to `main`
runs `release.yml`, which computes the next version, updates `CHANGELOG.md`,
tags and publishes a GitHub Release. Never edit `CHANGELOG.md` or create tags
yourself. The package version comes from the git tag via `hatch-vcs`.

## Conventions

- British English throughout; sentence case for headings.
- Docs and articles are written in the first person plural: this is a
  collaborative project.
- Corpus images arrive with their source and rights recorded in
  `evaluation/ocr/corpus/SOURCES.md`; an image whose rights are not recorded
  cannot be published.

## Security

Please report suspected vulnerabilities privately: see
[SECURITY.md](SECURITY.md), not the issue tracker.
