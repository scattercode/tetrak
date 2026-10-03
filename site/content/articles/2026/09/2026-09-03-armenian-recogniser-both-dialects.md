---
title: "The Armenian recogniser learns both dialects"
date: 2026-09-03
slug: "armenian-recogniser-both-dialects"
kicker: "Progress"
standfirst: "Two days after shipping v3 we built the evaluation that showed what it could not do: read anything but the encyclopedia it was tuned on. This is the story of v5 — a corpus three times wider, a filename bug that taught a model to hedge, and the first version to read Western Armenian at all"
author: stephen-masters
tags: [armenian, ocr, training, evaluation, project-notes, open-source]
---

> **Note added 2 October 2026.** The character similarity figures in this article were computed with a metric we have since found to be wrong: it used `difflib`'s `autojunk`, which on a page of text ignores most of the alphabet. Word recall was unaffected by that, though three smaller scoring corrections made at the same time moved it slightly. See [Beating the baselines, starting with our own ruler]({{< relref "/articles/2026/10/2026-10-02-beating-the-baselines.md" >}}) for what changed and the corrected comparison.

On Monday we
[shipped v3]({{< relref "/articles/2026/09/2026-09-01-shipping-the-armenian-recogniser.md" >}})
of our Armenian recogniser and called it the strongest permissively
licensed reader of the script we could measure. That sentence was true,
and we no longer like it, because every word of it rested on one
evaluation set: ten held-out pages of the Armenian Soviet Encyclopedia,
volume 2. One publisher, one typeface, one register, one dialect. A model
can be the strongest reader of that without being a reader of Armenian in
any useful sense — and it turned out ours was exactly that.

This article is about our next step where we confirmed that hypothesis,
fixed it, and shipped the fix. v5 is
[on Hugging Face](https://huggingface.co/tetrak/easyocr-armenian) and in the
[installable package](https://github.com/scattercode/tetrak-easyocr-armenian)
now. On the encyclopedia pages it leads every engine we have measured,
including the two we said last time still set the bar. More importantly,
it is the first version that holds up away from the encyclopedia — on
literature, on a scholarly history, on a second encyclopedia from a
different publisher, and on Western Armenian, a dialect the previous
model had never seen a line of.

The distance between those two paragraphs is mostly not a training story.
It is an evaluation story, a data-bug story, and — like
[last time]({{< relref "/articles/2026/09/2026-09-01-shipping-the-armenian-recogniser.md" >}})
— a story about what you cannot see when you only have one number.

## First, the instrument

Everything the project had published up to Monday was measured on the
same ten pages. That was a deliberate and defensible choice — the pages
are held out at the volume level, the transcripts are human-proofread,
and a fixed set keeps every published figure comparable. But it answers
exactly one question: *how well does the model read this encyclopedia, in
this face, at this scan width?* It cannot distinguish a model that learnt
Armenian better from one that learnt the encyclopedia better, and once
the training corpus was about to grow beyond the encyclopedia, that
distinction was about to become an even bigger issue.

So before training anything, we built the instrument. Armenian Wikisource
holds far more human-proofread material than the encyclopedia we started
with, and our
[census of it](https://github.com/scattercode/tetrak-hy-trainer)
had already catalogued the candidates. We harvested seven further works —
the collected works of Yervand Otyan, Vahan Totovents and Hagop Baronian
(all Western Armenian), volume five of Tumanyan's academic edition,
the 1968 scholarly translation of Faustus of Byzantium's history, a
popular medical encyclopedia from a different publisher, and an
Armenian–English dictionary — and for each one reserved a set of pages
*before anything trained on that work*, registered in the same held-out
module that already refuses encyclopedia volume 2. Each work becomes its
own evaluation set; the pages the evaluator downloads are, by
construction, exactly the pages the training samplers refuse.

Eight sets, two dialects, both orthographies, five genres. The reason to
insist on this before training rather than after is the same reason
clinical trials register their endpoints in advance: an evaluation set
chosen after you have seen the model's behaviour is a set chosen, however
honestly, by a person who knows where the model looks good.

The first thing the new instrument did was demolish our opinion of the
model we had just shipped.

## The specialist

Here is v3 — Monday's model, the "strongest permissively licensed reader
we can measure" — on the eight sets. Word recall, the order-insensitive
metric; the model's own raw output:

| Register | v3 |
| --- | ---: |
| Encyclopedia (ASE vol. 2) | **0.736** |
| Medical encyclopedia | 0.599 |
| Faustus of Byzantium (1968) | 0.500 |
| Totovents, *Works* | 0.334 |
| Baronian, *Works* | 0.284 |
| Dictionary (hy–en) | 0.242 |
| Otyan, *Works* | 0.234 |
| Tumanyan (academic edition) | 0.230 |

The encyclopedia number is real. Everything else collapses, and it
collapses worst precisely on the Western Armenian literary sources. v3
was pre-trained on encyclopedia text and fine-tuned on encyclopedia
crops; it is an encyclopedia specialist. If you took Monday's model to
read your grandmother's Otyan edition, it would read one word in four.

We are publishing that table for the same reason we published a
word-recall column of 0.274 a week ago: the honest number is the useful
one, and this particular honest number is the strongest argument we have
ever produced for measuring by register. Nothing about v3 changed between
Monday and Tuesday. Only the instrument did.

## The generalist, and the number that lied by staying still

The corpus widening itself was brief 012's plan: nineteen harvest
sources instead of five, eleven encyclopedia volumes instead of five,
the seven new works, fifteen rendering faces instead of three, and a
charset widened again (an ellipsis, square brackets, the numero sign
`№`, a superscript two — each found by diffing the corpus against the
charset, the lesson the
[abbreviation dot]({{< relref "/articles/2026/09/2026-09-01-shipping-the-armenian-recogniser.md" >}})
taught us). We pre-trained on 351,000 synthetic line crops drawn from
3.6 times the vocabulary, at identical compute to the previous
pre-train: same batch size, same iteration count.

On the encyclopedia pages, the new pre-train scored within noise of the
old one. Flat. If we still had one evaluation set, the conclusion would
have written itself: the wider corpus bought nothing; revert.

On the eight sets, the same two models:

| Register | old pre-train (v2) | new pre-train (v4) |
| --- | ---: | ---: |
| Encyclopedia (ASE vol. 2) | 0.607 | 0.606 |
| Medical encyclopedia | 0.577 | **0.838** |
| Faustus of Byzantium (1968) | 0.335 | **0.607** |
| Totovents, *Works* | 0.219 | **0.625** |
| Baronian, *Works* | 0.197 | **0.649** |
| Dictionary (hy–en) | 0.267 | **0.402** |
| Otyan, *Works* | 0.181 | **0.654** |
| Tumanyan (academic edition) | 0.171 | **0.569** |
| **Mean over registers** | 0.319 | **0.619** |

The mean nearly doubled. Every register the old model failed, the new
one roughly trebled. And the one register both models were saturated
with — the encyclopedia — is the one register where nothing moved, which
is to say: **the only number we used to have was the only number
incapable of showing the largest improvement we have ever measured.**
The same compute, spread over twice the data in five times the faces,
had bought generality at no cost to the specialism, and a single-set
evaluation would have called it a null result.

## The bug: one image, three labels

Then we fine-tuned on real crops, as we did for v3 — except this time
the crops came from all twelve scanned sources, 56,608 of them against
v3's 6,097 — and the result made no sense. The encyclopedia improved.
Most registers improved. And Otyan, a register the pre-train read at
0.654, collapsed to 0.323 — in a model that had just been *given* Otyan
crops for the first time.

Looking at the output made it stranger before it made it clearer. The
model was not misreading Otyan's pages; it was abbreviating them.
`ինչպես ըսինք` came out as `չպե ըք`; `իրարանցում` as `րարաո ր`.
Characters dropped from the middles of words — truncation, not
confusion, which is not a failure mode a recogniser drifts into on its
own.

It is, however, exactly the failure mode a CTC model learns when its
training labels are systematically shorter than its training images. And
ours were, for the daftest possible reason. Crop files were named
`v<volume>_<page>_<n>.png` — volume, page, box index — which was unique
back when every source *was* an encyclopedia volume. Seven of the new
works have no volume number at all. Every one of them fell back to `v0`,
and Baronian's page 100, Faustus's page 100 and Otyan's page 100 all
wrote the same file. The last writer's image survived; but every source
had already appended its own line to the label file, so the surviving
image carried every colliding source's label at once. One crop in our
training set was simultaneously labelled `իբր`, `բազմաթիվ` and
`ես վստահ եմ,` — three different lines, from three different books, one
image. **Twenty-seven per cent of the fine-tune's crops were involved in
a collision.** A model shown contradictory answers that often can reduce
its loss only by hedging towards short, noncommittal output, and hedging
is precisely what the Otyan pages showed us.

Two details of the diagnosis are the transferable part. First, the bug
was invisible at training time: loss went down, accuracy went up,
checkpoints were saved — nothing in the training loop knows that two
label lines point at one file. It surfaced only in the *per-register*
evaluation, as a register that regressed while its neighbours improved.
The instrument we built to measure generality turned out to be the only
smoke detector in the house. Second, we could not initially attribute
crops to sources at all, because the audit trail recorded volume and
page — and page ranges overlap across works. The very field whose
absence caused the collision was the field whose absence made it
undiagnosable. Both are fixed the same way: crops are now named for
their source work, the cutter refuses two sources that would collide,
and the audit trail records the work against every crop. The first
retraining on clean data confirmed the mechanism with unusual bluntness:
at iteration 500 the clean run's training loss was already twenty-six
times lower than the corrupted run's ever was, and its validation
accuracy at that first checkpoint exceeded the corrupted run's best from
any point in three hours.

We wrote on Monday that a model fine-tuned on transcribed text learns
the transcribers. The corollary earned this week: a model fine-tuned on
a broken dataset learns the bug. Neither is visible in the metrics that
watch the training; both are visible on the page.

## v5

Retrained on the collision-free crops — 51,078 of them, spanning all
twelve sources — the fine-tune behaved the way textbooks say fine-tunes
behave and ours never had: validation climbing smoothly, no overfitting
cliff, none of the checkpoint roulette that v3's tiny crop set forced on
us. The result shipped this morning as **v5**.

On the encyclopedia pages, raw output, no post-processing:

| Configuration | word recall |
| --- | ---: |
| `tetrak-hy` **v5** (ours, Apache 2.0) | **0.824** |
| `hye-paddle` (Calfa/PaddleOCR) | 0.807 |
| `hye-calfa-n` (Calfa, CC BY-NC 4.0) | 0.789 |
| `marker` (Surya) | 0.766 |
| v3, for scale | 0.736 |
| `tesseract -l hye` (stock) | 0.662 |

Monday's article carried a caution box: Calfa's `hye-paddle` had read
0.843 on an earlier page set, we had not yet run it on the current one,
and the best recall on the page might therefore not be in our table. We
have now run it on these pages. It scores 0.807, and v5 is ahead of it —
ahead, for the first time, of every engine we can measure on this
material. Calfa's `hye-calfa-n` remains far ahead on character
similarity, which on these two-column pages measures layout analysis
more than recognition; that story has not changed and we come back to it
below.

And across the registers, the number the encyclopedia table cannot show
— v5 against the specialist it replaces:

| Register | v3 | v5 |
| --- | ---: | ---: |
| Totovents, *Works* | 0.334 | **0.914** |
| Otyan, *Works* | 0.234 | **0.900** |
| Baronian, *Works* | 0.284 | **0.876** |
| Tumanyan (academic edition) | 0.230 | **0.861** |
| Encyclopedia (ASE vol. 2) | 0.736 | **0.824** |
| Faustus of Byzantium (1968) | 0.500 | **0.806** |
| Medical encyclopedia | 0.599 | **0.774** |
| Dictionary (hy–en) | 0.242 | **0.601** |
| **Mean over registers** | 0.395 | **0.818** |

The three Western Armenian literary sources — the registers v3 read
worst — are now the registers v5 reads best. Monday's article carried a
footnote saying the training corpus did not yet cover Western Armenian
and we made no claims for it. Claims: on held-out pages of Otyan,
Totovents and Baronian, nine words in ten.

One pleasing detail for readers of the last article: `fold_script()`,
the one-line fix that maps Latin homoglyphs back to their Armenian twins
and was worth eight and a half points of word recall to v2, is now worth
about half a point. v5 has stopped writing `h` inside Armenian words —
not because anything folds it, but because a model that has seen enough
Armenian, in enough faces, from enough books, no longer needs to be told.
The fold stays in the shipped path because it never hurts; it has been
demoted from crutch to insurance.

## What one number is hiding now

We are not going to repeat Monday's mistake with a better number. The
mean over registers is also one number, and here is what it is hiding.

**Layout is now the problem we need to solve.** Word recall ignores reading
order; character similarity collapses without it. Put v5's two metrics
side by side and the corpus splits cleanly in two: on the single-column
literary sources, character similarity runs from 0.56 to 0.72 — the
model reads the words *and* the page. On the two multi-column
encyclopedias it reads 0.08 to 0.16, against word recall of 0.77 and
0.82 on the same pages. The medical encyclopedia is the starkest case in
the table: nearly four words in five recovered, in an order so scrambled
the order-sensitive metric can barely find a matching run. The model
reads the words and loses the columns. That is brief 012's founding
premise — we wrote it down as a hypothesis before any of this training —
and it is now an isolated, measured fact rather than a hunch confounded
with recognition quality. Column-aware serialisation lifted the
encyclopedia's figure once already; doing it generally, for pages whose
column count nobody declared in advance, is the next stage of the plan.

**We have now run the external engines across every register, and we
do not lead most of them.** When this article was first published, the
cross-engine tables above were the encyclopedia's ten pages and nothing
else, and we said so rather than let them imply a comparison we had not
run. We have since run it. Word recall, per register, best engine
first:

{{< note kind="warning" title="Superseded on 24 September" >}}
One engine was still missing when this table was added: Calfa's
`hye-paddle`, whose model directory had gone. It has since been
downloaded and run across all eight registers, and it takes the mean
over registers as well as three of the registers credited to
`hye-calfa-n` here. The table below is left as published; the current
figures, rendered from the harness rather than typed in, are in
[The engine we had left out]({{< relref "/articles/2026/09/2026-09-24-the-engine-we-had-left-out.md" >}}).
{{< /note >}}

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

We take the mean and three registers; Calfa's `hye-calfa-n` takes three
and `marker` two. Two of our three are photo finishes — Totovents by
four ten-thousandths, and Baronian we *lose* by two. On character
similarity the picture is worse: we lead one register of eight, and
Calfa leads the mean 0.736 to our 0.615.

Two things follow that we had wrong. We attributed our weak character
similarity to multi-column reading order, but `hye-calfa-n` beats us on
that metric on five single-column literary registers too, where there
is no layout to get wrong — so a recognition-sharpness gap remains that
the XY-cut work does not touch. And `marker` wins both multi-column
encyclopedias on recall, which is the reverse of what Stage 0's
comparison predicted when Calfa's layout pipeline added nothing over
plain Tesseract on clean pages.

What survives is narrower and worth stating exactly: v5 leads the mean
across registers, leads the encyclopedia it was built for, and is the
strongest **permissively licensed** reader here — `hye-calfa-n` is
CC BY-NC, measurable but not shippable. It is not the strongest reader
of Armenian, and one register in three now belongs to somebody else.

**The dictionary is the weakest register and the most interesting one.**
Two columns, two scripts interleaved at the entry level, and the one
source where the per-token script fold faces real bilingual lines rather
than the odd Latin citation. Word recall of 0.601 is triple what v3
managed there, and it is still the bottom of the table.

**And the archival register remains unmeasured, for us and everyone.**
Everything above is set type, scanned well, transcribed by volunteers.
The damaged, handwritten, pre-reform material Tetrak exists for has no
held-out set yet; building one is harder precisely because proofread
transcripts of such material are what the whole field lacks.

## Where this goes

The site's own benchmark table still shows the `easyocr-hy` backend with
v3 weights; re-running the harness against v5 is queued behind the
release, and the [engines page]({{< relref "/reference/engines.md" >}})
will pick the new numbers up from the harness rather than from this
article. Brief 012's remaining stages are layout generality and the
external-engine sweep across the register sets. The model, the
[trainer](https://github.com/scattercode/tetrak-hy-trainer), the
[library](https://github.com/scattercode/tetrak-easyocr-armenian) and
[the weights with their full provenance](https://huggingface.co/tetrak/easyocr-armenian)
— including the collision, recorded against the release that dodged it,
because defects belong on the record even when they never shipped — are
public, as before.

Three articles ago this model read a quarter of the words on one
encyclopedia's pages. It now reads four fifths of them, and — the part
that matters — it is no longer a model of one encyclopedia. It reads
Otyan. If you have been waiting for the version worth pointing at your
own scans, this is the first one we would say that about.
