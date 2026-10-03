---
title: "Beating the baselines, starting with our own ruler"
date: 2026-10-02
draft: false
slug: "beating-the-baselines"
kicker: "Benchmark"
standfirst: "We set out to lead every Armenian OCR engine we can measure on every register. Before training anything, we found that most of the gap we were chasing was in our own metric. The rest came down to reading order, a word list and a second fine-tune: v6 now leads both means and most registers outright"
author: stephen-masters
tags: [armenian, ocr, benchmarks, evaluation, project-notes]
---

At the end of September, the [comparison with every external
engine]({{< relref "/articles/2026/09/2026-09-24-the-engine-we-had-left-out.md" >}})
left us level on word recall and well behind on character similarity. Calfa's
Tesseract model led the order-sensitive metric on almost every register. We
wrote that what survived reading order was a recognition-sharpness gap, and
that it was the next thing to train against.

That turned out to be mostly wrong, and the way it was wrong is the more
useful half of this article.

## The ruler was bent

Our character similarity is `difflib.SequenceMatcher(...).ratio()`.
`SequenceMatcher` has a parameter, `autojunk`, that is on by default. On any
string longer than 200 characters, it treats every character making up more
than one per cent of the text as junk and stops matching on it. A page of
Armenian is a few thousand characters, and almost the whole alphabet, plus the
space, clears one per cent. So the metric was matching on a handful of rare
characters, and its score depended on where those few blocks happened to fall,
not on how much of the page had been read.

The effect was not small. Single-column literary pages that we were reading
almost perfectly had been scored as though about a quarter of the text were
wrong. The trainer's own alignment code had turned the flag off long ago, for
exactly this reason. The metric module never had.

Fixing it meant re-running every external engine on every page, because we
had kept their scores but not their output. They now save their raw readings,
so the next correction to the metric is a re-score that takes seconds.

Three smaller corrections followed, each of the same kind: a transcription
habit the metric was charging to whichever engine did not share it.

- **The Armenian full stop.** Transcribers type an ASCII colon for `։`
  throughout the medical encyclopedia. We now score the two as one character
  for every engine. We still train the model to emit `։`, because that is
  what the page prints.
- **The abbreviation dot.** `․` and `.` are scored as one character for the
  same reason. This one cost us a lead: our model had learnt `․` from the
  encyclopedia's transcripts, and the other engines emit `.`.
- **Punctuation-only tokens.** A lone `-` is no longer counted as a word in
  word recall.

None of these changed which engine led which register on its own. Together
with `autojunk`, they changed what the gap was.

## What the gap actually was

With the metric fixed, the single-column registers were close: a hair behind
the leader on both metrics, where they were behind at all. Two things were not.

**Reading order on the encyclopedia.** The Armenian Soviet Encyclopedia is set
in three columns, closer together than EasyOCR pads its text boxes. No vertical
line on the page was free of boxes. Our XY-cut found a gutter, but treated
every box that overhung it as a full-width divider, such as a running head. It
peeled the page apart a line at a time until its recursion limit gave up and
read the rest straight across. The fix:

- Trim each box by a quarter of a line height before looking for a gutter.
- Try candidate gutters in turn.
- Count a crossing box as a divider only if it stands alone and off the
  column's line grid.

Without touching the weights, the encyclopedia went from our worst register on
character similarity to one where we lead every engine we measure.

**Recognition on three registers.** Faustus of Byzantium, Tumanyan's academic
edition and the encyclopedia still trailed on word recall, by a little.

## Closing it

Three changes, in order of what each was worth.

**A word list.** The recognition head has no language model, so a word it
misreads by one letter comes out as written, even when the right word was its
own second choice. We built a list of Armenian words from proofread Wikisource
transcripts and the [Nayiri Armenian
Lexicon](http://www.nayiri.com/nayiri-armenian-lexicon), with the evaluation
pages excluded. For each word whose reading is not in that list, a small beam
search over the recogniser's own probabilities looks for a listed reading
nearly as probable. We chose the threshold on training crops held out from the
fine-tune, not on the evaluation pages. On those pages it fixed many times
more words than it broke, and those it broke are proper nouns, classical
spellings and edition spellings: the words any lexicon breaks.

**A second fine-tune.** v6 is v5 trained on twice as many real crops, cut from
more volumes of the editions we were losing on. Two things went into the
training data deliberately: the Armenian full stop in place of the transcribers'
colon, and lines set in capitals for the encyclopedia's headwords. Before
training, a check of every harvested page against every evaluation page found
25 pages that print an evaluation page's text: variants and reprints in an
academic edition. One of them shared two hundred eight-word runs with the
evaluation page it reprints. Those pages had been in v5's training text. They
are excluded from everything new in v6, but v6 starts from v5's weights and
reuses v5's synthetic crops, so the exposure is inherited, not removed: the
model card records it as a known defect on the four registers concerned
(Tumanyan, Baronian, Faustus and the encyclopedia). Removing it takes a
pre-train from scratch.

**A digit fold.** The Faustus index is set in a bold italic in which the model
reads the digit 2 as the Armenian letters `Չ` or `շ`. Inside a number, neither
letter can be meant, so the script fold now reads them as the digit.

{{< registers >}}

{{< registers metric="chr" >}}

## Where we still lose, and why

We lead both means, and both metrics on most registers. Each register we do
not lead outright has a named cause.

- **Faustus of Byzantium.** We lead on its text pages and lose in the back
  matter, where page numbers are set in a bold italic whose digits the model
  confuses with each other. A fine-tune on synthetic index lines in the bold
  and italic faces we can render made Faustus worse, not better, so the faces
  evidently do not match. Real crops from bold-italic index pages are the next
  thing to try.
- **Tumanyan's academic edition, on character similarity.** The apparatus
  quotes Russian, and the model has no Cyrillic. On the edition's Armenian
  pages we are level with the leaders. Adding Cyrillic is a new charset, and so
  a new model; it belongs with the classical and Western Armenian work that
  comes next.
- **The medical encyclopedia, on character similarity.** Its index prints an
  en dash between each term and its page number. EasyOCR's detector draws no
  box around an isolated dash at any setting we tried, so no recogniser behind
  it ever sees one. Recognising the inked gaps between boxes recovers the
  dashes, but the transcripts type a hyphen where the page prints the dash, and
  on ordinary pages the same step reads stray marks as text. Neither is clean
  enough to ship.

The two Calfa models that still lead somewhere are both CC BY-NC 4.0: we can
measure them, but nobody can ship them in a commercial pipeline. Ours can be:
the code and weights are Apache 2.0, and the word list is CC BY-SA 4.0, as
the sources it is counted from require.

## What we would tell ourselves a month ago

Read the metric before reading the model. We spent a brief planning to train
our way out of a character-similarity gap that a one-word flag had largely
created, and nearly built a dictionary harvest for a register whose losses
turned out to be its index pages' dashes. Each of these was found by looking at
one page's output beside its transcript, not by looking at another number.
