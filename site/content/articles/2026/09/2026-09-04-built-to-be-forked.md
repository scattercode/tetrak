---
title: "Built to be forked: how to get involved in the Armenian recogniser"
date: 2026-09-04
slug: "built-to-be-forked"
kicker: "Open source"
standfirst: "The trainer and the EasyOCR library behind our Armenian model are public, Apache 2.0, and put together so that somebody else can pick them up — to send us a fix, add a source, or train a recogniser for a script of their own. This is a tour of what a newcomer finds: the checks that run before code can land, the release automation, and the guidance files that give a coding assistant the same orientation we have"
author: stephen-masters
tags: [armenian, ocr, open-source, contributing, claude-code, project-notes]
---

Most of what we have written this week has been about numbers — which
engine reads which register, and by how much. This article is about
the two repositories those numbers come from, and it is written for a
different reader: not someone deciding whether to use the model, but
someone wondering whether to get their hands on it.

That might mean sending us a fix. It might mean adding a source we have
not harvested, or a typeface we have not rendered, or a held-out set for
material we do not have. It might mean none of those and instead taking
a fork to train a recogniser for a script that is not Armenian at all,
which the pipeline is shaped to allow. All of those are welcome, and the
repositories have been arranged so that each is possible without
asking us first. Here is how they are arranged, and why.

## Two repositories, one handshake

The model lives in two public repositories under the Apache 2.0
licence, and the split between them is the first thing to understand.

[**tetrak-hy-trainer**](https://github.com/scattercode/tetrak-hy-trainer)
*produces* the model. It owns the census of Armenian Wikisource, the
harvester that fetches proofread pages and their scans, the character
set, the synthetic renderer that draws corpus text in Armenian
typefaces with archival damage, the training and fine-tuning scripts,
the per-register evaluation, and the packaging step that emits the
three files EasyOCR needs. It is also where the
[training data](https://huggingface.co/datasets/tetrak/armenian-ocr-crops)
and
[the weights](https://huggingface.co/tetrak/easyocr-armenian)
are uploaded to Hugging Face from.

[**tetrak-easyocr-armenian**](https://github.com/scattercode/tetrak-easyocr-armenian)
*ships* it. It is a small installable library — `pip install
tetrak-easyocr-armenian` — whose whole job is to be the thing EasyOCR
imports when asked for the `tetrak_hy` network, to fetch the right
weights, and to prove they are the right weights before loading them.
Its audience is EasyOCR users, most of whom will never hear of Tetrak,
and its README is written for them.

The handshake between the two is deliberately narrow. The trainer
uploads a versioned model to Hugging Face. The library then pins that
upload by its *commit* — a forty-character identifier that can never
be moved, unlike a tag or a branch — alongside a checksum of the
weights file. A library release is therefore a weights release: one
version number covers the code, the weights and the provenance record
that says which data, fonts, crops and training configuration produced
them. Weights are never committed to either repository, and a URL
without its checksum is not allowed to ship. If you take a fork and
train your own model, this is the arrangement you inherit, and it is
the reason a user of your fork can trust that `pip install` gave them
the weights you meant.

## The first ten minutes

Both repositories set up the same way, and the setup is written down
in each one's `CONTRIBUTING.md` — a file whose opening line says that
it applies to us as much as to anyone sending a pull request, which is
true and is the point.

```bash
git clone https://github.com/scattercode/tetrak-hy-trainer
cd tetrak-hy-trainer
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
lefthook install        # or: git config core.hooksPath .githooks
pytest
```

The test suite runs in seconds and needs no OCR engine, no PyTorch, and
no GPU. That is a design decision rather than an accident: the parts
of the pipeline that can be tested without a trained model — the
character set, the packaging, the held-out registry, the harvest
manifests, the label writer — are the parts where a mistake is most
expensive and least visible, so they are the parts a newcomer can
check on a laptop before touching anything heavier. The library's
continuous-integration jobs go further and never install PyTorch at
all; the tests that need it are marked to skip in CI and run locally.

The last line of that block installs the git hooks, and that is where
the hardening starts.

## The checks that run whether or not you remember

Everything in this section is automatic. A contributor can run any of
it by hand, and `CONTRIBUTING.md` shows how, but none of it depends on
anyone remembering.

**Before a commit is accepted**, Ruff — a fast linter and formatter for
Python — checks the staged files against a rule set that is declared
explicitly in `pyproject.toml`. The explicitness matters: Ruff's
defaults change between versions, and a project that relies on them
ends up with a laptop and a CI server that disagree about whether the
code is clean. At the same time the lockfile is checked. A lockfile is
the fully resolved list of every package the project depends on,
including the packages *those* packages depend on, pinned to exact
versions; `pyproject.toml` says what we want, `uv.lock` says what we
actually get. It exists so that security scanning sees real versions
rather than ranges, and a change to the dependencies that arrives
without a regenerated lock is refused.

**Every commit message** must follow Conventional Commits: a type such
as `feat`, `fix`, `docs` or `ci`, an optional scope, and a description
with no trailing full stop. A dependency-free shell script under
`.githooks/` enforces it, and the same script lives, byte for byte, in
every repository we maintain. This is not house style for its own
sake. The release automation reads the commit types to decide the next
version number — a `fix` bumps the patch version, a `feat` the minor,
and a `!` marks a breaking change — and it writes the changelog from
the messages. So the message is written for the person reading the
changelog later, and a wrong type is not a cosmetic slip; it cuts the
wrong release.

**Before a push**, the whole test suite runs, through the project's own
interpreter rather than whatever `pytest` happens to be on the path.
That detail cost us a run of pushes that failed before a single test
ran, because the hook could not import the package, and the fix was to
put the knowledge in the hook rather than in the advice.

**On the server**, CI repeats the lint, the format check, the lockfile
check and the tests, and adds two things a laptop would not. Trivy
scans the resolved dependency tree for known vulnerabilities and
produces a software bill of materials — an SBOM, a machine-readable
list of every component in the build — that is attached to the run.
And a small job checks that the files we copy between repositories,
the commit hook and the changelog configuration among them, are still
identical to the shared originals, because we once had three copies of
the version-computation logic that were byte-identical and nothing
would have told us when they stopped being so. Dependabot opens a pull
request a week for dependency and action updates, with commit prefixes
chosen so its messages pass the same hook that ours do, and the
vulnerability scan re-runs every Monday morning whether or not anything
changed.

**On a merge to `main`**, the release happens without a human. A shared
action computes the next version from the commit history, git-cliff
prepends a section to `CHANGELOG.md`, the workflow tags the commit and
publishes a GitHub Release, builds the wheel, checks its metadata,
installs it in a clean environment to prove it imports, and publishes
it to PyPI through a Trusted Publisher — a mechanism by which PyPI
accepts uploads from a named GitHub workflow rather than from a
password or token that could leak. For the library, a further job
downloads the weights the new version pins, verifies their checksum,
and attaches them to the Release as a mirror. Nobody edits the
changelog, nobody creates a tag, nobody types a version number: the
version comes from the tag and the tag comes from the commits.

If that sounds like a great deal of machinery for a two-person
project, that is the wrong way round. It is *because* the project is
two people that the machinery is there. Each of those checks stands in
for a review we would otherwise have to remember to do, and each one
does its job identically for a stranger's pull request and for ours.

## Guidance written for a coding assistant, and useful to everyone

The part of the last few days we most want to draw attention to is
the least visible in a file listing. Both repositories carry a
`CLAUDE.md` at the root, and each carries a `.claude/skills/`
directory with a skill file inside. These are plain Markdown. Claude
Code reads them automatically when it opens the repository; any other
coding assistant can be pointed at them; and a person can simply read
them, which we would recommend before reading anything else.

`CLAUDE.md` is orientation. It says what the repository is and what
its neighbour is, and then it states the hard rules — not as a list of
prohibitions but with the reason attached to each, because a rule
without its reason gets worked around the first time it is
inconvenient. The trainer's version explains why the character set is
a single source of truth and why changing it is a new model version
rather than a patch (the set is positional, so adding a character
invalidates every weight file ever trained). It explains the held-out
split — which pages are reserved for evaluation, why the guard checks
the harvest manifest rather than the directory name so a renamed copy
cannot get past it, and why a guard that fires must be resolved by
changing the split deliberately rather than by working around it. It
explains the loading contract with EasyOCR, verified against EasyOCR's
source rather than its documentation, including the counter-intuitive
fact that the model has to be loaded with the language set to English
because EasyOCR ships no Armenian character file and the setting is
provably inert for a custom model anyway. It carries a table of which
of the three interpreters runs which script, because picking the wrong
one is the usual first five minutes lost. And it says where the
decisions live, so that a reader who wants to know *why* the space is
in the character set can find the answer rather than re-litigate it.

The skill files are procedure. `tetrak-hy-training`, in the trainer,
is the whole pipeline in the order it runs — census, harvest, character
check, fonts, synthetic pre-train, real crops, fine-tune, evaluate,
package, publish — with the command for each step and the trap beside
it. The traps are the valuable part, and they are valuable because
every one of them cost us a training run. The label file that the
vendored trainer reads with a regular expression rather than as CSV,
so that a standard CSV writer's quotation marks became part of 21% of
v1's labels and the model learned to invent a quotation mark. The
abbreviation dot that was missing from the character set, so that 6%
of the evaluation pages were unwinnable by construction. The crop
filenames built from an encyclopedia volume number that seven of the
new sources did not have, so that three books' page 100 wrote the same
file and one image carried three labels — the bug
[yesterday's article]({{< relref "/articles/2026/09/2026-09-03-armenian-recogniser-both-dialects.md" >}})
is largely about. Each of those is now a sentence in a file that the
assistant reads before it runs anything, which is a different thing
from being a sentence in an article that a person might remember.

`tetrak-hy-weights-release`, in the library, is the other half of the
handshake: how to resolve a Hugging Face tag to the commit behind it,
which three things must move together in the same change, which commit
type cuts the right version, and what the release workflow will then
do on its own. It is short, because the procedure is short, and it
exists because the procedure is also easy to get subtly wrong.

The effect we have noticed, working this way for a week, is not mainly
speed. It is that a fork keeps the lessons. If you clone the trainer
tomorrow to train a Georgian or a Syriac recogniser — swap the
character set, fetch different fonts, point the harvester at a
different Wikisource — the assistant you open it with will refuse to
train on your held-out pages, will tell you to diff the character set
before the first run, and will know not to write the label file with a
CSV writer. None of that knowledge is in our heads any more; it is in
the repository, where it belongs.

The pipeline's own repository, the one behind this site, works the
same way, with skills for the evaluation corpus, the site's design
system and the writing of articles like this one. We mention it
because the pattern is the point: a skill is written the first time a
procedure has to be done twice, and it is written down at the moment
the procedure has just gone wrong, while the cost is fresh.

## Ways in

Some concrete things a newcomer could do, roughly in order of how much
of the pipeline each one touches.

**Measure something.** The per-register evaluation sets are built from
Wikisource by a script, and the comparison against other engines is a
tool that reads their results. If you have an engine we have not
measured, or a machine that can run one we could not, a new row in
[the comparison]({{< relref "/articles/2026/09/2026-09-04-the-comparison-we-had-been-putting-off.md" >}})
is a contribution that needs no training at all.

**Add a source.** The census ranks every proofread work on Armenian
Wikisource; we have harvested fourteen. Adding one is a harvest
command, a character-set diff, and an entry in the held-out registry
choosing which of its pages are reserved for evaluation before anything
trains on it. The discipline is written down, the guard enforces it,
and the register you add becomes a row in every future evaluation.

**Add a face.** The renderer takes any font whose licence allows it and
checks, glyph by glyph, that the font can actually draw each line
rather than trusting its name. Armenian typefaces from a period or a
publisher we have not covered are a direct lever on the model's
generality, and the fetch script records each font's licence from the
file itself.

**Build a held-out set for material we do not have.** Every figure we
publish is set type, scanned well, transcribed by volunteers. The
damaged, handwritten, pre-reform material this project exists for has
no evaluation set, for us or for anyone, and a small proofread set of
such pages would be the most valuable contribution on this list by
some distance.

**Take a fork for another script.** The character set is one module,
the fonts are one script, the harvester works on any Wikisource with
scan-and-transcript pairs, and the detector needs no training because
it is script-agnostic. What the fork inherits is everything above: the
checks, the release automation, the provenance handshake, and the
guidance files.

One constraint applies to all of it and is stated at the top of both
`CONTRIBUTING.md` files. A separate, non-commercially licensed
Armenian OCR repository validated the approach we use, and nothing
derived from it — code, annotations or weights — can be accepted into
an Apache 2.0 project, however small the fragment. Re-implementing an
*idea* from it is fine; copying its expression is not. If you are not
sure which side of that line a contribution falls on, say so in the
pull request and we will work it out together.

Security reports go privately, through the `SECURITY.md` in either
repository, rather than the issue tracker. Everything else goes
through issues and pull requests in the usual way, and the hooks will
tell you what they think of your commit message before we do.
