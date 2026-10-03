---
title: "The comparison we had been putting off"
date: 2026-09-04
slug: "the-comparison-we-had-been-putting-off"
kicker: "Benchmark"
standfirst: "Until now, every cross-engine number we had published for Armenian came from ten encyclopedia pages. We have now run the other engines across all eight of our evaluation registers. Our model still leads on average, but it loses one register in three, and two things we thought we knew about where the gap lives turned out to be wrong"
author: stephen-masters
tags: [armenian, ocr, benchmarks, evaluation, project-notes, open-source]
---

> **Note added 2 October 2026.** The character similarity figures in this article were computed with a metric we have since found to be wrong: it used `difflib`'s `autojunk`, which on a page of text ignores most of the alphabet. Word recall was unaffected by that, though three smaller scoring corrections made at the same time moved it slightly. See [Beating the baselines, starting with our own ruler]({{< relref "/articles/2026/10/2026-10-02-beating-the-baselines.md" >}}) for what changed and the corrected comparison.

Yesterday's article on
[v5]({{< relref "/articles/2026/09/2026-09-03-armenian-recogniser-both-dialects.md" >}})
carried a paragraph we were not proud of but were determined to keep.
It said that every table comparing our recogniser with other engines
was built from the same ten pages of the Armenian Soviet Encyclopedia,
that we had not yet run those engines on the seven new register sets,
and that "v5 leads every engine we can measure" was therefore a claim
about one encyclopedia rather than about Armenian. We would rather
write that sentence than let a table imply a comparison we had not run.

We have now run it. This article is about what came back, which is not
what we hoped, and about the two working assumptions it took with it.
It also closes out the plan that started at the beginning of the week — brief 012, the one
that widened the corpus, trained v5, replaced the column splitter and
scheduled this very measurement as its last stage — so the second half
is a plain account of where that plan stands and what it leaves open.

## What was measured

Three external engines read every page of every register: stock
Tesseract with its Armenian model (`tesseract -l hye`), Calfa's
`hye-calfa-n` (a much stronger Tesseract model, licensed CC BY-NC, so
we can measure it but never ship it), and `marker`, the Surya-based
pipeline that does its own layout analysis. Between them that is 65
held-out pages across the seven new sets — ten each for the literary
and encyclopedia registers, five for the bilingual dictionary — plus
the ten encyclopedia pages every published number since v0 has used.
One engine is missing that should not be: Calfa's `hye-paddle`, which
held the best encyclopedia recall until v5 overtook it, has only ever
been run on the encyclopedia pages, because its model directory has
since gone and needs downloading again. Its row is absent rather than
guessed.

{{< note kind="warning" title="Superseded on 24 September" >}}
`hye-paddle` has since been downloaded and run across all eight
registers, and it changes the result this article reports. It takes the
mean over registers, and on word recall it takes all three of the
registers awarded to `hye-calfa-n` below, plus the medical encyclopedia.
The tables here are left exactly as published; the current figures,
rendered from the harness rather than typed in, are in
[The engine we had left out]({{< relref "/articles/2026/09/2026-09-24-the-engine-we-had-left-out.md" >}}).
{{< /note >}}

One thing about the "ours" column needs saying before any of the
numbers, because it changes what they mean. Every previous per-register
table in these articles reported the recogniser's *raw* output — what
the weights emit, with no layout handling and no clean-up. This one
reports what a user of the pipeline actually gets: v5's weights, then
the recursive column splitter, then the step that rejoins words a line
break had hyphenated, then the script fold. That is the fair basis for
comparing against `marker`, which brings its own layout analysis, and
it is why our encyclopedia figure here is a little higher than
yesterday's. The two numbers are not interchangeable, and the tool that
builds these tables says so in its own docstring so that nobody quotes
one as the other.

## Word recall: a three-way split

Word recall is the order-insensitive metric — what fraction of the
words on the page came out, regardless of where. It is the number that
matters most if the transcript is going into a search index, and the
one we lead. Per register, best engine in bold:

| Register | Ours | `hye-calfa-n` | `marker` | `tesseract -l hye` |
| --- | ---: | ---: | ---: | ---: |
| Encyclopedia (ASE vol. 2) | **0.835** | 0.789 | 0.766 | 0.662 |
| Totovents, *Works* | **0.936** | 0.936 | 0.806 | 0.708 |
| Otyan, *Works* | **0.918** | 0.905 | 0.815 | 0.694 |
| Baronian, *Works* | 0.900 | **0.900** | 0.779 | 0.716 |
| Tumanyan (academic edition) | 0.867 | **0.892** | 0.711 | 0.668 |
| Faustus of Byzantium (1968) | 0.821 | **0.881** | 0.839 | 0.700 |
| Medical encyclopedia | 0.795 | 0.838 | **0.903** | 0.888 |
| Dictionary (hy–en) | 0.612 | 0.107 | **0.672** | 0.059 |
| **Mean over registers** | **0.836** | 0.781 | 0.786 | 0.637 |

Read the mean first and it is a good day: we lead by five points over
`marker` and `hye-calfa-n`, which are close to each other, with stock
Tesseract a long way back. Read the rows and it is a different story.
The eight registers split three ways. We take the encyclopedia we
were built on and two of the three Western Armenian literary sources;
`hye-calfa-n` takes the other Western source, the Tumanyan academic
edition and the Faustus history; `marker` takes both multi-column
encyclopedias. And two of our three wins are photo finishes — Totovents
by four ten-thousandths, and Baronian, which the rounded table shows as
a tie, we actually lose by two.

Three details in that table deserve more than a glance.

**Stock Tesseract beats us on the medical encyclopedia.** Not Calfa's
model — the free one that ships with Tesseract, which reads two words
in three on the other prose registers, reads nearly nine in ten on this one
and outscores v5 by nine points. Word recall does not care about column
order, so this is not a layout result; it is a recognition result on a
face that Tesseract's training happens to suit and ours, so far, does
not. We do not yet know which characters are going wrong there. The
per-register confusion tables that brief 012 asked for and we have not
yet built are exactly the instrument for that question, and this row
moves them up the list.

**The dictionary defeats Armenian-only models outright.** Both Tesseract
models fall from around 0.9 on prose to 0.06 and 0.11 on the bilingual
dictionary, because half of every entry is English and an Armenian-only
model has no way to read it. `marker` and v5 are the only two readers
in the table that cope at all, and `marker` copes better. Five pages is
a small set and we would not lean hard on the ordering, but the shape
of the failure is not in doubt.

**`marker` winning both multi-column registers is the reverse of what
we predicted.** At the start of the week we ran Calfa's full layout
pipeline — a region detector, a recursive cut, then `hye-calfa-n` —
on the encyclopedia pages and found it added nothing over plain
Tesseract on those clean columns. We took that as evidence that layout
machinery cannot be judged on pages whose layout is simple — it needs
test pages with more columns or nested regions, where there is
something for it to do — which was true, and also as evidence that it
did not matter much, which was not. On the two registers with real
column structure, the engine with the most elaborate layout analysis
is the one that reads the most words.

## Character similarity: the assumption that did not survive

Character similarity is the order-sensitive metric. It rewards a
transcript that reads like the page, top to bottom, and it punishes
every scrambled line, split word and stray space. Here the picture is
not close:

| Register | Ours | `hye-calfa-n` | `marker` | `tesseract -l hye` |
| --- | ---: | ---: | ---: | ---: |
| Encyclopedia (ASE vol. 2) | 0.398 | **0.840** | 0.258 | 0.697 |
| Totovents, *Works* | 0.733 | **0.741** | 0.476 | 0.326 |
| Otyan, *Works* | 0.759 | **0.884** | 0.679 | 0.399 |
| Baronian, *Works* | 0.757 | **0.819** | 0.613 | 0.326 |
| Tumanyan (academic edition) | 0.593 | **0.750** | 0.351 | 0.289 |
| Faustus of Byzantium (1968) | 0.752 | **0.851** | 0.728 | 0.549 |
| Medical encyclopedia | 0.655 | 0.788 | 0.621 | **0.796** |
| Dictionary (hy–en) | **0.277** | 0.215 | 0.218 | 0.112 |
| **Mean over registers** | 0.615 | **0.736** | 0.493 | 0.437 |

Calfa's model leads seven registers of eight and the mean by twelve
points. The one register we lead is the dictionary, where every engine
is poor and ours is least poor. Stock Tesseract leads the medical
encyclopedia on this metric too.

The number that matters most in this table is not a lead or a mean. It
is the size of Calfa's margin on the five single-column literary and
scholarly registers: between one and sixteen points, on pages that
have no columns at all. For the whole of this week our explanation for
the weak character-similarity figures has been reading order — the
model reads the words and loses the columns, and once the columns are
handled the metric will follow. That story was true as far as it went.
The recursive column splitter we shipped this week lifted the
medical encyclopedia's figure from below 0.2 to above 0.6, and lifted
the encyclopedia's by about a quarter. But it cannot be the whole story, because a
single column of Otyan has nothing to get in the wrong order, and
Calfa still reads it twelve points more faithfully than we do.

What is left once ordering is taken out is what we have been calling
recognition sharpness, and it has two parts that the table hints at.
One is the reading itself: a word that comes out one letter wrong
costs word recall nothing if the metric still matches it, and costs
character similarity every letter that follows until the alignment
recovers. The other is granularity. Our detector hands the recogniser
short fragments, not lines, and each fragment boundary is a place
where a word can be cut in half or a space can appear inside one. The
tell is stock Tesseract's encyclopedia row: it reads fewer words than
we do — 0.66 recall to our 0.84 — yet its character similarity is
0.70 to our 0.40, because what it does read comes out as whole lines
in the right order. An experiment at the start of the week, recorded
in the brief, had already found that ordering our own boxes
*perfectly* — by where each one's text sits in the transcript — would
not improve the encyclopedia's figure over the splitter we ship; this
sweep confirms it from the outside, on material where there was never
anything to order.

## What survives

We are not going to replace one overreaching sentence with a slightly
smaller one. Here is the claim the measurement supports, and no more.

v5 has the highest mean word recall across the eight registers of any
engine we have measured, and the highest on the encyclopedia it was
built for. It is the strongest **permissively licensed** reader of
Armenian we can find: `hye-calfa-n`, which beats it on three registers
for recall and seven for character similarity, is CC BY-NC and cannot
be shipped in a product or bundled with one. Ours is Apache 2.0 from
the training data to the weights.

It is not the strongest reader of Armenian. On one register in three,
somebody else reads more of the words; on nearly every register,
somebody else reads them more faithfully. If your material is
single-column scholarly print and your use is non-commercial, Calfa's
model is the better reader today and we would tell you so. If your
material has columns and you can live with the licence, `marker` may
read more of it. What ours offers is the widest coverage under a
licence you can build on, and a training pipeline that has moved the
numbers every time we have run it.

## Where brief 012 stands

The plan we wrote at the start of the week had five stages, and this sweep was the
last of them. In four days:

The **census** of Armenian Wikisource replaced a guess with a count:
418 of its 629 scan-and-transcript indexes hold proofread pages,
86,599 in all, including several hundred pages each of Western
Armenian from three authors the model had never seen. The **corpus**
then grew from one publication to fourteen sources and 5,521 pages,
and the check that compares each new source's characters against the
model's alphabet found four things that belonged in it and two
transcriber habits that did not. **v5** was trained on that corpus,
by way of a filename collision that taught its predecessor to hedge
and a per-register evaluation that was the only thing able to see it.
The **recursive column splitter** and **de-hyphenation** shipped on
measurement, each judged on whether it moved the order-sensitive
metric without touching the order-insensitive one. And the **external
sweep** above did what a last stage should: it tested the claims the
earlier stages had made, and narrowed them.

What the plan leaves open, in the order we would take it:

The **site's own benchmark and engines page still describe v3.** The
reference page carries a hand-typed row for the `easyocr-hy` backend
with v3's figures and says Calfa leads both columns on the
encyclopedia, which was true when written and is not now. Re-running
the harness against v5 and letting the page read from it is overdue,
and the fact that a transcribed number went stale within three days is
the argument for never transcribing one, made again.

The **recognition-sharpness gap** now has a measurement and no plan.
The levers we can see are the training data again — more real crops,
from more faces, on the registers where Calfa's margin is widest — and
the detector, which could hand the recogniser lines rather than
fragments. The per-register confusion tables come first, because they
say which of those two the gap belongs to.

The **column splitter is untested on the shape it was built for.** It
handles nested regions and any number of columns by design, and it was
measured on two-column pages, because the corpus holds nothing else.
A three-column or nested fixture would let us find out whether the
design survives contact.

**`hye-paddle`** needs downloading again and running on the seven new
sets, so that the engine which set the encyclopedia bar until this
week has a row on every register. And the crops that trained v5 need
their own configuration on
[the published dataset](https://huggingface.co/datasets/tetrak/armenian-ocr-crops),
alongside v1's, so that the model's provenance is as complete as its
predecessors'.

And the register we started this project for — damaged, handwritten,
pre-reform archival material — still has no held-out set, for us or
for anyone, because human-proofread transcripts of such material are
exactly what the field lacks. Everything in both tables above is set
type, scanned well. That caveat has appeared at the foot of every
article in this series and it will keep appearing until it is no
longer true.

The model, the
[trainer](https://github.com/scattercode/tetrak-hy-trainer), the
[installable library](https://github.com/scattercode/tetrak-easyocr-armenian),
[the weights](https://huggingface.co/tetrak/easyocr-armenian) and the
tool that builds the tables in this article are all public. So is the
brief, with its decision log — including the entry for this sweep,
which begins with the words "it narrows the claim rather than
confirming it". That is what a last stage is for.
