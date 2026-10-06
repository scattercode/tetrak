---
title: "When your training set has read your test set"
date: 2026-10-06
draft: false
slug: "training-set-has-read-your-test-set"
kicker: "Method"
standfirst: "Our held-out registry knew every evaluation page and refused to train on any of them. It knew nothing about the other pages that print the same text: a commentary quoting the passage it annotates, a variant in another volume, an encyclopedia quoting a chronicle. An eight-word shingle check found 25 of them in the harvest, and nothing had failed"
author: stephen-masters
tags: [armenian, ocr, evaluation, training, project-notes]
---

Before anything trained on a work, we reserved pages of it. We [wrote about
that]({{< relref "/articles/2026/09/2026-09-03-armenian-recogniser-both-dialects.md" >}})
with some satisfaction: the whole of volume 2 of the Armenian Soviet
Encyclopedia and a fixed set of pages from each of seven other works,
registered in a module whose only job is to refuse. The harvester checks every
harvest's manifest against it, so a copied or renamed directory cannot get
past it. The crop cutter checks it. The synthetic sampler checks it. The
word-list builder checks it. The pages the evaluator downloads are, by
construction, exactly the pages the training code will not touch.

It had a hole we did not see for a month, and the hole was in the definition.
The registry held out *pages*. The model learns *text*. Those are the same
thing only if no passage appears on more than one page, and in the books we
train on that is false in at least four different ways.

## Where the same text turns up twice

Our registers are mostly scholarly editions: collected works with an apparatus
at the back, a chronicle with an editor's introduction, encyclopedias. That
kind of book repeats itself by design.

**The commentary quotes the text it annotates.** One of our evaluation pages
from volume 10 of Baronian's collected works is in the editorial commentary at
the back. It quotes a satire from page 107 of the same volume at length, and
follows the quotation with "see page 107". Page 107 is not an evaluation page.
It was harvested, cut into crops and rendered as synthetic text, and so was
page 205, which another evaluation page of the commentary quotes for forty
eight-word runs. The 1968 edition of Faustus of Byzantium does the same thing
from the other end: one of its evaluation pages falls in the editor's
introduction, which retells the scene of King Arshak at the Persian court in
words close enough to the translation on page 215 that thirteen eight-word
runs survive the paraphrase.

**The same text in another volume.** Volume 10 of Tumanyan's academic edition
carries an article of his about folk tales. The apparatus in volume 5, where
one of our evaluation pages sits, quotes a 25-word run from it. A registry
keyed by volume cannot see this. One keyed by work could see it only by
holding out every volume, which is most of the training data.

**Another work quotes it.** The encyclopedia's entry on Arshak II quotes
Faustus's account of him, a 23-word speech, verbatim from the same 1968
edition we harvest, and cites that edition in its bibliography. So a page of a
1968 translation of a fifth-century chronicle carries the text of an
evaluation page from a twentieth-century encyclopedia. No per-work registry crosses that line,
because nobody writing one imagines it needs to.

**Formulaic apparatus.** Baronian's notes open every entry the same way:
first published in such a periodical, unsigned, in such a year; a second time
in the 1936 complete works. The formula repeats across the notes pages with
only the dates changed, and nine of them share between five and twelve
eight-word runs with evaluation page 749 on that basis alone. A page of
encyclopedia volume 9 shares a bibliography citation with a page of volume 2.
These are not reprints. They are boilerplate, and the check cannot tell the
difference. It does not need to.

**And one we have not explained.** Two pages of the Tumanyan volume 5
apparatus, four leaves apart, both compare the Armenian tale of the handless
girl with the versions in Afanasyev and Grimm. At the word level they are four
fifths identical: 203 shared eight-word runs, the longest of them 53 words.
Whether the edition prints the comparison twice or a Wikisource transcriber
attached one page's text to the other, we have not yet checked against the
scan. For the purpose here it does not matter. That text was in v5's
synthetic set, and v5 was scored on reading it.

## Why nothing failed

A harvest is used three ways, and the leak reaches all of them.

Real crops are the obvious one: a line image and its transcript. The guard
caught those correctly, for the pages it knew about.

The synthetic set is where a text leak does the most work. We render the
harvested transcripts in a set of Armenian faces to teach the recogniser
what Armenian text looks like before it sees a real scan. A recogniser reads a
line at a time and has no language model, so what it absorbs from a thousand
renderings of a passage is the character sequences in it. Render an
evaluation page's sentences often enough and the model arrives at that page
already knowing what the next letter is likely to be. It never saw the scan.
It did not need to.

The word list is the third. Our lexicon decoder corrects a reading that is not
in the list to the most probable listed word within a small edit distance. A
word that occurs only on an evaluation page, and on the commentary page that
quotes it, is in the list by leakage, and the decoder will helpfully correct
towards it.

No test fails in any of this. Every guard checked exactly what it was told to
check. The numbers just improve for the wrong reason, and a leak does not
announce its size. We cannot tell you how many points of word recall those 25
pages were worth to v5, which is precisely the problem.

## Finding it with shingles

The check is the oldest trick in near-duplicate detection, the w-shingling
that Andrei Broder [defined in
1997](https://doi.org/10.1109/SEQUEN.1997.666900) and used, with colleagues
at Digital's research lab, to [find near-duplicate pages across the whole
web](https://doi.org/10.1016/S0169-7552(97)00031-7). Split the text into
words, take every run of *w* consecutive words as a shingle, and compare the
sets. The papers are listed at the end for anyone who wants the originals.

```python
SHINGLE = 8

def shingles(text: str) -> set[tuple[str, ...]]:
    words = wikisource.normalise_transcript(text).lower().split()
    return {tuple(words[i : i + SHINGLE]) for i in range(len(words) - SHINGLE + 1)}
```

Every harvested page that is not itself an evaluation page is compared with
every evaluation transcript. Five or more shared shingles flags the pair. That
is the whole method, and over our 75 evaluation pages and a few thousand
harvested ones it finishes quickly enough on a laptop not to be worth
optimising, as set intersections do.

Three choices in it are worth explaining, because they are the ones a reader
would change.

**Eight words.** Shorter shingles flag every proverb, every stock phrase of
the apparatus and every bibliographic formula. Longer ones miss a quotation in
which the editor has changed one word, which editors do. Eight catches the
Faustus paraphrase and the Baronian boilerplate alike, and we would rather
have the boilerplate than miss the paraphrase.

**Five shared runs.** One shared run is a quotation of a sentence, and a
commentary that quotes one sentence of an evaluation page has given the model
very little. Five means the pages are telling the same story. The threshold is
a flag, and the flag is cheap: what it costs us is one page of training text
out of thousands. Excluding a page we did not need to exclude is a rounding
error. Keeping one we should have excluded is an unknown quantity in every
published figure. So the threshold is set for recall, and the boilerplate
pages go too.

**The same normalisation on both sides.** Our training pipeline folds
transcriber habits onto what the page prints: the ASCII colon typed for the
Armenian full stop, straight quotes for guillemets, and so on. The check runs
the harvested page and the evaluation transcript through exactly that fold,
then lower-cases both, before shingling. It deliberately does *not* apply the
one per-source exception in that fold, because the point is that both sides
are treated identically. A reprint must not hide behind a different quotation
mark.

We did not reach for anything cleverer. MinHash and locality-sensitive hashing
exist for when the sets are too large to intersect, and embeddings for when
the duplicate is a translation or a close paraphrase rather than a quotation.
Neither is our situation. A few thousand pages against 75 fit in memory, and
what we are hunting is text an editor copied out, which exact shingles of
normalised words find without fuss.

## What we did with the list

The 25 pages went into a second table in the held-out module,
[`OVERLAPPING_PAGES`](https://github.com/scattercode/tetrak-hy-trainer/blob/main/src/tetrak_hy_trainer/heldout.py),
beside the evaluation pages. The same predicate the samplers already call now
reports both, so every consumer of a harvest excluded them without changing a
line. They are not evaluation pages: we do not score anything on them, they
are simply gone from training.

Two details of the table were deliberate. Entries are keyed by *volume*, not
by work. Page 691 of Tumanyan volume 5 is a leaking page; page 691 of volume
10 is not, and a table keyed by the work's name would have thrown it away. The
tests say so explicitly. And the comment above the table names the check that
produced it and the condition under which to re-run it, because a list like
this rots the moment a work with evaluation pages gains a volume.

The check itself became a
[script](https://github.com/scattercode/tetrak-hy-trainer/blob/main/scripts/check_eval_overlap.py)
and a gate. It reports every flagged page as listed or not listed, and exits
non-zero when it finds one that is not. It also exits non-zero, with a
different code, when it finds no evaluation transcripts at all. That second
exit is the more important one. The natural failure of a leak check is to
compare against an empty set and pass, and we would rather it refused. The
trainer's [training
guide](https://github.com/scattercode/tetrak-hy-trainer/blob/main/.claude/skills/tetrak-hy-training/SKILL.md)
now says: run it after harvesting any volume of a work with evaluation pages,
before training on it, and add what it reports.

## What it does not undo

v5 was trained before the list existed, with those 25 pages in its synthetic
text. v6, the model we [released this
month]({{< relref "/articles/2026/10/2026-10-02-beating-the-baselines.md" >}}),
is fine-tuned from v5's weights and reuses v5's synthetic crops, relabelled
rather than re-rendered, because re-rendering a third of a million crops was
not what that brief was for. The guard keeps the pages out of every piece of
new data v6 saw: its real crops, its all-caps set and its word list. It cannot
take them back out of the starting weights.

So the exposure is inherited, and the honest statement is that v6's figures
on the four registers concerned, Tumanyan, Baronian, Faustus and the
encyclopedia, may be flattered by an amount we cannot measure. That sentence
is in the model's provenance record on Hugging Face as a known defect, next to
the other things we know are wrong with it, where anyone comparing against our
numbers will read it. Removing it means re-rendering the synthetic set without
those pages and pre-training from scratch. That is on the list. It is not
free, and we would rather say so than quietly carry a number we cannot stand
behind.

## If you are building your own

Everything above is specific to Armenian books on Wikisource, and none of the
lessons are.

- **Hold out text, not pages.** Whatever your unit of exclusion is, a file, a
  page, a document ID, ask what else in the corpus contains the same text.
  In scholarly material the answer is always something.
- **Check across the whole corpus, not within each source.** The encyclopedia
  quoted the chronicle. A per-source check would never have found it.
- **Normalise both sides identically, with the training pipeline's own
  code.** Any difference between how the check reads a transcript and how
  the sampler reads it is a place for a duplicate to hide.
- **Set the threshold for recall and pay in pages.** Training data is cheap
  and an evaluation set is not. A false positive costs one page. A false
  negative costs the credibility of every figure you publish.
- **Make it a gate, and make it fail when it has nothing to compare.** A
  check that passes on an empty evaluation set is worse than no check,
  because it looks like one.
- **Write down the leak you cannot remove.** In the model card, in the
  provenance, wherever the numbers are. The next person to compare against
  them deserves to know.

The registry still holds out pages, because pages are what a harvester
fetches. It now also knows that a page is not the only place its text lives.

## Further reading

The method is thirty years old and well documented. These are the originals,
and two later papers that take the same idea to the two places a reader of
this article is most likely to want it next.

- Andrei Z. Broder, "On the resemblance and containment of documents",
  *Compression and Complexity of Sequences*, IEEE, 1997.
  [doi:10.1109/SEQUEN.1997.666900](https://doi.org/10.1109/SEQUEN.1997.666900).
  The paper that defines shingles, resemblance and containment, and
  introduces the min-wise sketch that became MinHash.
- Andrei Z. Broder, Steven C. Glassman, Mark S. Manasse and Geoffrey Zweig,
  "Syntactic clustering of the Web", *Computer Networks and ISDN Systems*
  29(8–13), 1997.
  [doi:10.1016/S0169-7552(97)00031-7](https://doi.org/10.1016/S0169-7552(97)00031-7).
  Shingling applied to a crawl of thirty million pages, which is where the
  technique earned its reputation.
- Udi Manber, "Finding similar files in a large file system", *USENIX Winter
  Technical Conference*, 1994.
  [usenix.org](https://www.usenix.org/legacy/publications/library/proceedings/sf94/full_papers/manber.finding).
  The precursor: fingerprints of substrings, anchored to the content rather
  than to positions, to find files that share text.
- Andrei Z. Broder, Moses Charikar, Alan M. Frieze and Michael Mitzenmacher,
  "Min-wise independent permutations", *Journal of Computer and System
  Sciences* 60(3), 2000.
  [doi:10.1006/jcss.1999.1690](https://doi.org/10.1006/jcss.1999.1690).
  The theory behind MinHash, for when the sets are too large to intersect
  directly.
- Jure Leskovec, Anand Rajaraman and Jeffrey D. Ullman, *Mining of Massive
  Datasets*, chapter 3, "Finding similar items".
  [mmds.org](http://www.mmds.org/). The textbook treatment of shingling,
  MinHash and locality-sensitive hashing together, free to read.
- Tom B. Brown and others, "Language models are few-shot learners", 2020,
  appendix C. [arXiv:2005.14165](https://arxiv.org/abs/2005.14165). The same
  n-gram overlap check, at thirteen words, used to find evaluation benchmarks
  that had leaked into a language model's training crawl. The problem this
  article describes is not peculiar to OCR.
