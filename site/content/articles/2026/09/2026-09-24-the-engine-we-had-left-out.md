---
title: "The engine we had left out"
date: 2026-09-24
draft: false
slug: "the-engine-we-had-left-out"
kicker: "Benchmark"
standfirst: "Three weeks ago we published a cross-engine comparison with one row missing, because the model had gone and we would not guess at it. We have now downloaded it and run it over every register. It takes the mean off us, and it takes every register the previous table had given to Calfa's Tesseract model"
author: stephen-masters
tags: [armenian, ocr, benchmarks, evaluation, project-notes]
---

> **Note added 2 October 2026.** The tables in this article are rendered from the current comparison, so they now show v6 under a corrected metric, while the prose describes 24 September. Most of the character-similarity gap it discusses turned out to be the metric itself. See [Beating the baselines, starting with our own ruler]({{< relref "/articles/2026/10/2026-10-02-beating-the-baselines.md" >}}).

The [cross-engine comparison]({{< relref "/articles/2026/09/2026-09-04-the-comparison-we-had-been-putting-off.md" >}})
we published on 4 September carried an admission in its third paragraph.
Three external engines had read every page of every register, but a
fourth had not: Calfa's `hye-paddle`, which had held the best
encyclopedia recall until v5 overtook it, had only ever been run on the
encyclopedia pages, because the model directory it needed had since
gone. We wrote that its row was absent rather than guessed and left it
at that.

It is no longer absent. The model is still on Hugging Face, it
downloaded in seconds, and running it across the seven register sets
took twenty-two minutes for sixty-five pages.

## What it changes

{{< registers >}}

Read the mean row first, because it is the sentence that has to be
withdrawn. On 4 September we wrote that we led the mean by five points
over `marker` and `hye-calfa-n`. With the fourth engine measured, we do
not lead the mean at all — `hye-paddle` takes it, by a margin small
enough that the honest description is a tie rather than a defeat, but
the lead is gone and the bolding in that older table is now wrong.

The row-by-row picture moves further than the mean does. The previous
table split eight registers three ways: three to us, three to
`hye-calfa-n`, two to `marker`. `hye-paddle` now takes four, and it
takes them almost entirely from Calfa's Tesseract model — the Western
Armenian source, the Tumanyan academic edition and the Faustus history,
all three of the registers that table had given to `hye-calfa-n`, plus
the medical encyclopedia off `marker`. The engine that had been the
external bar for this whole line of work now wins nothing on word
recall. Our own three registers are untouched: we keep the encyclopedia
we were built on and two of the three Western Armenian literary
sources.

### The dictionary is holding the mean up

One register is doing almost all of the work keeping us level, and it
is worth being plain about which. `hye-paddle` is an Armenian-only
recogniser, and the bilingual dictionary is half English; it reads that
set far worse than it reads anything else. Drop that one register and
average the other seven and the gap is no longer a tie — `hye-paddle`
leads us by nearly three points.

That is not a reason to drop the register. A bilingual dictionary is
exactly the kind of page an archive actually holds, and an engine that
cannot read one is worse at the job even if it is better at Armenian.
But "we are level on the mean" and "we are level because one of the
eight registers is a test the other engine cannot sit" are different
claims.

### Character similarity is the same story as before

Nothing in the order-sensitive metric has changed hands in a way that
rescues the earlier reading. Switch the table over and see for
yourself:

{{< registers metric="chr" >}}

`hye-paddle` takes three registers here, all of them single-column
literary sources, and it is the worst engine in the table on both
multi-column encyclopedias — worse than stock Tesseract, by a distance
that looks like a broken engine until you notice which sets it happens
on. It is not broken. It is a recognition model in a stock PaddleOCR
pipeline with no column handling, so on a two-column page it reads both
columns correctly and interleaves them. Word recall does not care;
character similarity is destroyed. The same weights score near the top
of the table on prose that happens to run in one column.

That is the clearest illustration we have yet had of why we report both
figures, and it is the argument for the per-register instrument in one
engine: a single averaged number for `hye-paddle` would have described
a model that does not exist.

Calfa's Tesseract model still leads the character-similarity mean, and
still leads it over us by the same margin it did three weeks ago. That
part of the 4 September article stands unaltered.

## What survives

Two claims come through this intact, and they are narrower than the one
we started with.

We still lead the encyclopedia we were built for, on the metric that
matters most for a search index. And `hye-paddle` is CC BY-NC 4.0, the
same licence as `hye-calfa-n` — measurable, not shippable. So "the
strongest permissively licensed reader of Armenian we have measured"
survives, and it is now doing considerably more of the work than it was
when we first wrote it. Both of the engines ahead of us on either mean
are ones nobody can put in a commercial pipeline.

What does not survive is "v5 leads the mean". We had three weeks of
believing that, and the reason we believed it is that the row which
would have contradicted it was the one we had not run.

## The tables now come from the harness

There is a process failure here as well as a result, and it is the more
useful half.

Both September articles carried their comparison table as markdown
typed into the article. We have a rule against exactly this — figures
on the research pages are read out of the benchmark CSV at build time
so a page cannot disagree with the data — and a shortcode that exists
because a hand-transcribed table had already gone stale once. The
register tables escaped it for a mundane reason: neither input is in
the repository. The trainer's run directory is gitignored in full, and
so are the cached layout spans our own column is computed from, so
unlike the fixture benchmark there was nothing a build could recompute.
Hand-typing was the path of least resistance, and it worked for
nearly three weeks.

It stopped working the moment this measurement landed. Two published
tables, both wrong in the same cell, and nothing that would have told
us.

So `tools/register_comparison.py` now takes an `--emit` flag and writes
the table to a CSV that is committed, and the tables above are rendered
from it at build time by a `{{</* registers */>}}` shortcode. The
articles hold no copy. Re-scoring a register and regenerating the CSV
updates every page that shows it, including this one — which means this
article will contradict its own prose if the numbers move far enough,
and that is the correct failure mode. Prose that argues about a
relationship can go stale honestly; a table that quietly disagrees with
the harness cannot.

The emitter also enforces something the hand-typed tables could not. It
writes only engines measured on *every* register, so a column's mean is
always a mean over the same pages as the column beside it. Under that
rule `hye-paddle` would have been excluded from the September tables
outright rather than appearing with an encyclopedia-only average — and
an excluded column is a great deal harder to forget than a footnote
saying a row is missing.

## What is still open

The register sets now have a complete set of external comparators,
which was the last measurement the corpus-and-layout work had left
outstanding, so the comparison is finally measuring what it always
claimed to. Three things it has surfaced are not yet answered.

**We do not know what `hye-paddle` is doing better.** It beats us on
four registers spread across literary prose, a scholarly history and a
medical encyclopedia, which is too broad a spread to be a font or a
register effect. Per-register confusion tables would say; we have not
built them.

**The medical encyclopedia remains our worst prose register.** The
4 September article noted that stock Tesseract outscored us there and
that we did not know which characters were going wrong. That is still
true, and `hye-paddle` now outscores us on it by more.

**The dictionary is the only register we win on character similarity**,
and we win it while reading barely two words in three. A register where
every engine does badly is not a strength; it is a set we should
probably grow before anyone reads a lead on it as meaningful.
