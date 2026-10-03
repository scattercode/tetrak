---
title: "Shipping the Armenian recogniser: what the language taught the model, and us"
date: 2026-09-01
slug: "shipping-the-armenian-recogniser"
kicker: "Progress"
standfirst: "Three training runs after a model that read a quarter of the words on a page, our Apache-licensed Armenian recogniser reads three quarters of them — and most of what we learned on the way is about Armenian itself: letters with Latin twins, a full stop that looks like a colon, and punctuation that taught our model its own bad habits"
author: stephen-masters
tags: [armenian, ocr, training, unicode, project-notes, open-source]
---

> **Note added 2 October 2026.** The character similarity figures in this article were computed with a metric we have since found to be wrong: it used `difflib`'s `autojunk`, which on a page of text ignores most of the alphabet. Word recall was unaffected by that, though three smaller scoring corrections made at the same time moved it slightly. See [Beating the baselines, starting with our own ruler]({{< relref "/articles/2026/10/2026-10-02-beating-the-baselines.md" >}}) for what changed and the corrected comparison.

Two days ago we published
[our first honest Armenian numbers]({{< relref "/articles/2026/08/2026-08-30-armenian-ocr-measured.md" >}}):
a survey of who builds Armenian OCR, a benchmark across ten engines, and our
own first training run sitting at the bottom of the table reading a quarter
of the words on a page. We said we would report whatever happened next,
including the numbers we did not like.

This is what happened next. The short version: three training runs later the
model reads, it ships today as an installable package and a Tetrak backend,
and on our evaluation pages it is the strongest permissively licensed reader
of Armenian we can measure — still behind Calfa's, which sets a high bar.

The longer version is more interesting than the numbers, because almost
everything that moved them was something the Armenian language did that we
had not planned for. If you read Armenian, some of this article is your
alphabet seen from an unusual angle: through the eyes of a model that knows
the shapes but not the language. If you are training a recogniser for another
under-served script, the second half is the list of traps we found by
stepping on them.

## What v3 is, and how to use it

The model is EasyOCR's standard recognition architecture trained for
Armenian from scratch: the full alphabet in both cases, the `և` ligature,
Armenian punctuation, digits and basic Latin for the mixed material real
pages contain. v1 trained on 175,500 synthetic line crops rendered from
proofread encyclopedia text and degraded to look scanned; v2 retrained after
two data defects were found and fixed (both described below, both
instructive); v3 fine-tuned v2 on 6,097 crops cut from real scanned pages —
the first time the model had ever seen actual 1970s letterpress rather than
a rendering of it.

Three ways to use it, all Apache 2.0:

- `pip install tetrak-easyocr-armenian` — two lines of Python and an
  [EasyOCR](https://github.com/JaidedAI/EasyOCR) reader that speaks
  Armenian, weights fetched and checksum-verified on first use.
- `pip install "tetrak-ocr[armenian]"` — the `easyocr-hy` backend, which
  adds the two output-path steps described below and is what produced the
  numbers here. See [the engines page]({{< relref "/reference/engines.md" >}}).
- [`tetrak/easyocr-armenian`](https://huggingface.co/tetrak/easyocr-armenian)
  on Hugging Face — the weights themselves, with a provenance record naming
  the exact data that trained them, and a model card that keeps every
  version's defects on the record.

Measured on ten fresh held-out pages of the Armenian Soviet Encyclopedia,
volume 2 — a different page set from the last article's, so numbers shift
slightly everywhere — with human-proofread transcripts as ground truth:

| Configuration                       | char similarity | word recall |
| ----------------------------------- | --------------: | ----------: |
| `hye-calfa-n` (Calfa, CC BY-NC 4.0) |       **0.840** |   **0.789** |
| `easyocr-hy` (ours, v3, Apache 2.0) |           0.255 |       0.769 |
| `marker` (Surya)                    |           0.258 |       0.766 |
| `tesseract -l hye` (stock)          |           0.697 |       0.662 |
| `easyocr` (stock)                   |           0.035 |       0.031 |

Two days ago our word-recall column read 0.274. The run that fixed the
charset took it to 0.607, the fine-tune on real crops to 0.736, and the
shipped pipeline — with the script fold and column-aware reading order
described below — to 0.769.

Read the table the way we asked last time. **Calfa's model is the strongest
Armenian OCR we can measure, on these pages as on the last set**, and we
downloaded it fresh and ran it on these exact pages before writing this
sentence, precisely so that this table could not flatter us by omission. It
is CC BY-NC 4.0, which means an archive can use it but nobody can bundle or
sell tools built on it. Ours is two points behind on word recall and Apache
2.0 end to end — the "permissively licensed alternative" we said at the
outset would be a real reason to build this, and which is now the measured
position rather than a hope. Character similarity is a layout story, not a
recognition story, and we return to it at the end.

{{< note kind="caution" title="Still unmeasured" >}}
Calfa's `hye-paddle` read 0.843 word recall on the previous page set inside
a stock PaddleOCR pipeline, and we have not yet run it on this one. The best
recall on this page may therefore still not be the best available. Same
policy as last time: we would rather say so than publish a table that
quietly omits the competitor most likely to win it.
{{< /note >}}

## A thirty-second tour of Armenian punctuation

Everything in the next four sections follows from one fact: Armenian
punctuation and Latin punctuation share shapes without sharing
meanings.[^orthography]

The Armenian full stop — `։`, the *verjaket* — is two dots stacked
vertically. To a reader of English it looks exactly like a colon. Meanwhile
the mark that ends an English sentence, the single low dot, exists in
Armenian too — but there it is the *mijaket*, doing roughly the work an
English colon or semicolon does. The two writing systems assigned opposite
jobs to the same two shapes.

It gets better. The Armenian question mark — `՞` — does not sit at the end
of the sentence at all: it perches on the stressed vowel of the word being
questioned, in the middle of the sentence. The exclamation mark `՜` behaves
the same way. There is a pause mark, `՝`, that has no Latin counterpart, an
emphasis mark `՛`, and quotations are set in guillemets, `«»`. An
abbreviation is closed with a dot — and the proofread transcripts we train
from encode that dot as U+2024 ONE DOT LEADER, a deliberate choice that
keeps it distinct from both the ASCII full stop and the mijaket.

A human reader carries all of this without noticing. A character-level
recogniser carries none of it, and the gap between those two states is
where nearly every finding below comes from.

## The twins: letters that are also Latin letters

The most common single mistake our v1 and v2 models made was writing the
Latin letter `h` inside Armenian words — `hրապարակումներ` for
`հրապարակումներ`. On ten evaluation pages, v1 did it 302 times.

It is worth looking at those two characters — `հ` and `h` — until you can
see the difference, because in most typefaces there barely is one. The same
goes for `օ` and `o`, and there the resemblance is not even a coincidence:
`օ` entered the Armenian alphabet in the Middle Ages, borrowed from the
shape used in Greek and Latin, some eight centuries after Mesrop Mashtots
created the original thirty-six letters. One of our model's confusions is
older than the printing press.

Add `։` against `:` from the tour above and you have a set of cross-script
twins that no character-level model can tell apart, because at the level of
ink on paper *there is nothing to tell apart*. The model's charset contains
both scripts — real pages carry Latin names and citations, so it must — and
its CTC head reads one character at a time with no language model to whisper
that a word which starts `հրապարակ` is unlikely to contain a Latin letter.

The fix costs one function call, not a training run. `fold_script()`, in
the published package, looks at each word the model read and, if the word
already contains an Armenian letter, folds any Latin twin in it back to the
Armenian form. A wholly Latin word — a name, a citation — is left alone.
On v1's saved predictions that one rule recovered 449 words and broke
none, and every version since ships with it.

## The dash that turned out to be grammar

The fold's first draft also normalised dashes — the confusion table showed
the model occasionally reading an en dash where the page has a hyphen, and
folding `–` to `-` looked like a freebie.

It broke more than it fixed, and the reason is grammatical. Armenian
attaches case endings to things that cannot take them directly — numerals,
initials, abbreviations — with a dash: `1886-ին`, *in 1886*; `Ա–ի`, *of
A.*, where `Ա` abbreviates the article's headword. The encyclopedia's
transcribers use an en dash for many of these, and on our ten pages they do
it 184 times. Folding every en dash to a hyphen "corrected" 74 words the
model had read perfectly, to recover 66 it had genuinely misread. We
measured, reverted, and kept the measurement in the function's
documentation so nobody re-adds it in good faith.

The lesson generalises to any language you do not read natively: **a
normalisation that looks like free accuracy can be a grammatical feature
you have not met yet.** Measure each one on real predictions before
shipping it; the difference between a twin and a meaning is invisible in
the code and obvious in the data.

## The dot that was not in the charset

The single most-missed word across the entire evaluation was two characters
long: `ա․` — the abbreviation of a headword, closed with that U+2024
abbreviation dot. Missed 112 times out of 112. Not misread: *unwinnable*.

The dot was not in v1's character set. We had built the charset from the
alphabet, the named Armenian punctuation, digits, Latin and common
punctuation — and the transcripts' abbreviation dot, sitting in a Unicode
block we never thought to look in, was not on the list. That did two things,
both silent. At training time, the pipeline dropped every synthetic crop
containing the character, so the model never saw an abbreviation. At
inference time, the model had no class to emit it with, so every one of the
518 abbreviated words on the evaluation pages — 5.8% of all words, in an
encyclopedia, a genre that abbreviates constantly — was lost before the
model saw a single pixel.

v2's charset added the dot (and `°`, for the temperatures and coordinates
an encyclopedia is full of). The model went from emitting U+2024 zero times
across 6,672 detected regions to emitting it 221 times, and the most-missed
word in the corpus became winnable.

The generalisable version: **diff your charset against the actual
codepoints of your corpus before you train.** Not against the alphabet,
not against the punctuation the language is documented to have — against
a frequency count of every character in the text you will train from.
Five minutes of `collections.Counter` would have found this before it cost
a training run.

## When the ground truth has habits of its own

The strangest finding came from the fine-tune, and Armenian typists will
recognise it instantly.

Typing the verjaket requires an Armenian keyboard layout. The ASCII colon
is on every keyboard in the world, and in most typefaces the two are
indistinguishable on screen. So some of the proofread transcripts —
excellent, human-verified, two-review transcripts — write `:` where the
page prints `։`. Not systematically; occasionally, the way any habit
surfaces.

Our fine-tune cut its training crops from real pages and labelled them with
those transcripts. Which produced crops like this one: the page prints
`Բայերը (1603)։`, the model read `Բայերը (1603)։` — correctly, verjaket and
all — and the label said `Բայերը (1603):`, so the training process marked
the model *wrong* and nudged it towards the colon. After fine-tuning, the
model's verjaket-as-colon confusions had risen from 37 to 60. The model
read the page more faithfully than its own ground truth, and we trained
the fidelity back out of it.

In the shipped pipeline this is harmless — the fold maps `:` back to `։`
inside Armenian text on the way out. But as a finding about training data
it is the sharpest one we have: **a model fine-tuned on transcribed text
learns the transcribers, not just the language.** The same pages gave us
`առըն չությունների` for `առընչությունների` — a line-break hyphenation
reassembled with a space in it — and `հայպարսկական` where the page prints
`հայ-պարսկական`, a real hyphen dropped. Proofread means a human checked
the words. It does not mean the text is consistent at the level a
character model trains at, because no human reader ever needed it to be.

## The gotchas, for whoever does this next

Shorter, blunter, and none of them Armenian-specific. Each of these cost us
a day or a training run; all of them are cheap to check up front.

**Check your fonts' character maps, not just their names.** One of our
three rendering faces — Mshtakan, which ships with macOS — has no glyphs
for Latin letters, the degree sign, or the abbreviation dot. Pillow does
not warn about a missing glyph; it draws the font's fallback shape, which
looks plausible enough that nothing fails. A third of our synthetic crops
containing Latin characters were teaching the model a shape that was not
the labelled character. Read the font's `cmap` table with `fontTools` and
exclude a face from rendering any string it cannot fully draw.

**Read your trainer's label parser before you write labels.** The
EasyOCR-family trainer does not parse `labels.csv` as CSV: it splits each
line at the first comma and takes the rest verbatim. Python's `csv.writer`,
meanwhile, wraps any label containing a comma in quotation marks. The
result was that 21% of our labels — 36,918 crops — carried quote marks the
images did not show, and the single commonest error in the published v1
model's output was inventing a quotation mark. Our fault, in our tooling,
found only by reading the training data by eye. The defect and its fix are
recorded on the model card, because people run those weights.

**Per-crop validation accuracy is a poor proxy for page-level accuracy.**
We ran the fine-tune for 10,000 iterations and for 3,000, to the same 95%
held-out crop accuracy. The short run beat the long one by nearly six
points of page-level word recall — the long run had spent 7,000 iterations
overfitting while crop accuracy sat in a band whose width, on a 700-crop
validation set, is about four crops. Trust the page metric and stop early.

**Character similarity measures reading order, not reading.** These pages
are two-column. Join the detected regions in detector order and the columns
interleave; the words are all present and the order-sensitive metric
collapses. Serialising output column by column — read the left column to
its foot, then the right — lifted our character similarity by three
quarters with the weights untouched, and improved every page. Tesseract's
towering figure in that column is a layout achievement more than a
recognition one, and it is the next thing worth learning from.

**Hold out data at the level that correlates.** Our evaluation pages come
from volume 2; training text and crops come from volumes 1 and 3–6, and the
harvesting tool refuses volume 2 outright rather than trusting anyone to
remember. Crops from a single page share its paper, ink and scanning, so
we split train from validation by page, never within one.

## Where this goes

More real crops, first — the alignment tooling yields roughly two hundred
labelled crops per proofread page and there are thousands of proofread
pages, so v3's 6,097 is a floor, not a ceiling. Calfa's `hye-paddle` needs
measuring on the current pages. The archival register — damaged pages,
pre-reform orthography, the material Tetrak actually exists for — remains
unmeasured for every engine including ours, and encyclopedia print is the
easy end. And Tetrak's router still needs to learn what a language is
before `easyocr-hy` joins the automatic fan-out rather than being asked
for by name.

Everything above is public: the
[trainer](https://github.com/scattercode/tetrak-hy-trainer), the
[library](https://github.com/scattercode/tetrak-easyocr-armenian), the
[weights and their provenance](https://huggingface.co/tetrak/easyocr-armenian),
and the
[dataset](https://huggingface.co/datasets/tetrak/armenian-ocr-crops) with
the Wikisource revision of every transcript. If you are building a
recogniser for a script the big engines skipped, take all of it — and take
the gotchas above as the part we wish someone had published before us.

[^orthography]: Throughout: Eastern Armenian in reformed orthography, which
    is what the Armenian Soviet Encyclopedia is set in. Western Armenian and
    classical orthography share the alphabet, so the homoglyph and
    punctuation findings carry over; the training corpus does not yet, and
    we make no claims for them.
