---
title: "Telling classical from reformed Armenian by counting one letter"
date: 2026-10-11
draft: false
slug: "classical-or-reformed-armenian-by-one-letter"
kicker: "Method"
standfirst: "Armenian is printed in two orthographies with the same alphabet, and a book's title is no guide to which one its pages use. One letter is: the reform left ւ only one place to stand, so counting it anywhere else tells the two apart, on a page or in a single name"
author: stephen-masters
tags: [armenian, orthography, unicode, training, project-notes]
---

For most of its history Armenian had one spelling. The alphabet Mesrop
Mashtots devised at the start of the fifth century was made for the
classical language, Grabar, and its spelling stayed put while the spoken
language moved on. By the nineteenth century there were two modern
literary standards, both a long way from Grabar: Eastern Armenian, centred
on Tiflis in the Russian Empire and spoken across Persia, and Western
Armenian, centred on Constantinople in the Ottoman Empire. They differed in
grammar and pronunciation, but both were written in the same classical
spelling, including letters that had stopped being pronounced.

Soviet Armenia changed that. A reform drafted largely by the linguist Manuk
Abeghyan and adopted in 1922, then partly revised in 1940, respelled the
language closer to how Eastern Armenian was spoken. It was part of the
literacy campaign: fewer silent letters, fewer spellings to memorise. It
applied wherever Soviet power did, and independent Armenia kept it after
1991.

Most of the Armenian world was outside Soviet power, and most of it never
adopted the reform. The Western Armenian communities scattered by the
genocide of 1915 rebuilt their schools and presses in Beirut, Aleppo,
Paris and the Americas, in classical spelling. Iran's Armenians speak
Eastern Armenian, and they kept the classical spelling too. So did the
Eastern Armenian politicians and writers of the short-lived First Republic
who went into exile after 1920. For many of these communities, keeping the
old spelling was also a way of not accepting a Soviet decision about their
language. The newer diaspora, people who left Soviet and post-Soviet
Armenia, mostly brought the reformed spelling with them.

The result is that dialect and spelling don't line up. Eastern Armenian is
printed in both orthographies, depending on where and when. Western
Armenian is almost always classical, except where Soviet publishers reset
Western authors in reformed spelling. A collection like the Armenian
Institute's, gathered from across the diaspora over a century, holds all
of these on the same shelves.

A goal of the next version of our Armenian model is to read the books the
current one has never seen: everything printed in classical spelling,
before the reform and outside Soviet Armenia since, in either dialect. To
train and test on that material we first had to find it, among several
hundred Armenian works on Wikisource. The obvious approach was to read the
index titles. The titles turned out to be no help.

They mislead in both directions. Kajaznuni's *Ազգ և հայրենիք* is in
classical spelling throughout, but its title carries the reformed ligature
`և`, because whoever typed it in typed it that way. The Soviet Yerevan
editions of Western Armenian authors (Zohrab, Varoujan, Terian, Metsarents)
were reset in reformed spelling, whatever the authors wrote. A title is a
piece of metadata somebody typed. The page is what the printer set. So we
stopped reading titles and read the pages instead, looking for a test that
anyone could run on a page of text.

That test turned out to be one letter.

## What the reform changed, and what it did not

The reform added no letters and removed none. Classical and reformed
Armenian share an alphabet and, in Unicode, a code block. What changed is
where the letters go:

| Classical | Reformed | Meaning | What moved |
|---|---|---|---|
| `նաւ` | `նավ` | ship | `ւ` for *v* became `վ` |
| `հաւատք` | `հավատք` | faith | the same |
| `իւր` | `իր` | his, her | `իւ` simplified |
| `եւ` | `և` | and | the two letters became the ligature |
| `Երեւան` | `Երևան` | Yerevan | the same, inside a word |
| `կէս` | `կես` | half | `է` inside a word became `ե` |
| `-ութիւն` | `-ություն` | the abstract-noun suffix | `իւ` became `յու` |
| `Պօղոսեան` | `Պողոսյան` | Boghosian, Poghosyan | `օ` became `ո`; `եա` became `յա` |
| `ծառայ` | `ծառա` | servant | the silent final `յ` was dropped |

A classifier therefore can't look for a letter that only one orthography
has. It has to look at *distribution*, and the question is which
distribution separates the two cleanly enough to trust.

## Four candidates, one winner

We measured four markers on pages we already knew the answer for. That
meant every reformed harvest we had, plus a handful of sampled pages from
works we knew were classical. Each marker was counted per thousand Armenian
letters, so that long and short pages compare.

**The two-letter `եւ` against the ligature `և`.** This was the marker we
expected to work, and the one that failed outright. It is a habit of the
press, not of the orthography. *Հայկական տպագրութիւն*, a history of
Armenian printing set in impeccable classical spelling, uses the ligature
almost everywhere. Across the classical works the census eventually found,
some presses prefer the two letters and some the ligature, and the split
is close to even. We still record it, because it matters for scoring (we
now treat the two forms as one when measuring accuracy), but it can't
decide anything.

**`է` inside a word**, where reformed spelling writes `ե`. **A silent final
`յ` after a vowel.** Both move in the right direction, and both overlap at
the edges. A word-final `յ` is also perfectly reformed in `հայ` and `թեյ`.
Once the fourth marker has been counted, neither adds anything.

**`ւ` outside the `ու` digraph.** This one separates the two with room to
spare, and the reason is structural rather than statistical. In classical
spelling `ւ` (U+0582, *yiwn*) does several jobs: half of the digraph `ու`
for *u*, the *v* in `աւ` and `եւ`, and the glide in `իւ`. The reform gave
each of the other jobs to another letter, and left `ւ` exactly one place
to stand: the second half of `ու`. The ligature `և` is a separate code
point (U+0587) and doesn't contain a U+0582 at all. So in properly reformed
text, a `ւ` that doesn't follow an `ո` isn't rare. It shouldn't exist.

A rule rather than a tendency is what you want to build a classifier on. On
the reformed harvests the free `ւ` barely registers, and the little there
is comes from quotation and apparatus. On classical pages it is everywhere,
because the commonest abstract-noun suffix, `-ութիւն`, carries one, and so
does "and" wherever the press writes it as two letters. Between the
two groups there was a wide empty band with no work in it.

## The classifier

The test fits in a regular expression with a lookbehind:

```python
import re

ARMENIAN_LETTER = re.compile(r"[Ա-Ֆա-և]")
FREE_YIWN = re.compile(r"(?<![ոՈ])ւ")   # ւ that is not the second half of ու

def free_yiwn_per_thousand(text: str) -> float:
    letters = len(ARMENIAN_LETTER.findall(text))
    return 1000 * len(FREE_YIWN.findall(text)) / letters if letters else 0.0
```

The trainer's
[`orthography` module](https://github.com/scattercode/tetrak-hy-trainer/blob/2acd9a0c212493a2f6e72adf0629341451bf7f72/src/tetrak_hy_trainer/orthography.py)
adds three verdicts and a floor. At 8 or more per thousand, the text is
classical. At 2 or fewer, it's reformed. Anything between is *mixed*.
Below 500 Armenian letters it declines to answer, because a short sample
says nothing about a rate. The thresholds sit well inside the empty band,
so a page has to be genuinely unusual to land near one.

The census that uses it samples four body pages from every work with
enough proofread pages. It spreads them through the book and skips the
first tenth, where title pages and prefaces live. It cleans each page with
the same code the harvester uses, so the classifier sees exactly the text
the trainer would. It caches the verdicts, so that adding a work doesn't
mean re-reading the rest.

## What the census found

It found far more classical material than the titles had suggested,
including two full-resolution sources we hadn't known were classical.
Before it could, it exposed a bug: every poetry index on Wikisource had
been harvesting as empty. hy.wikisource wraps a verse page in a template,
our cleaner strips templates whole, and the poem went with the wrapper.
The census couldn't classify a page with no letters on it. That made the
gap visible for the first time, and the fix brought several thousand
proofread pages of verse back into every harvest.

The verdicts also explained themselves in the places they were awkward.

**The mixed band is reformed print with something old inside it.** Soviet
editions that quote Grabar at length.
Collected works whose apparatus is in classical spelling. A few pages of
facsimile. Nothing in the mixed band turned out to be a classical source,
which is the outcome you want from a band labelled "don't use this for
either".

**Grabar trips the marker, correctly.** The seventeenth- and
eighteenth-century song collections in modern critical editions came back
classical, and they are classical orthography. They just aren't the modern
Armenian in classical spelling that we're trying to teach the model, so
they're left out of the harvest. The classifier answers the question it
was asked, about spelling, not the one we sometimes meant, about the
language.

**The Western authors' Soviet editions are reformed**, as feared. Classical
spelling on Wikisource means diaspora and émigré printing, in both
dialects. On the Western side there are Toranian's books from Aleppo,
Yesayan, Shushanian, and Baronian's *Ազգային Ջոջեր* in its original
spelling. On the Eastern side there are Khatisian, Kajaznuni and Aghbalyan,
First Republic figures who went on writing in classical spelling in exile.

**A handful of works sit just over the classical line.** Each is probably a
reformed edition quoting classical text at length, or a collection
containing both. We treat them as mixed: text supply for the language
model, not image crops for the recogniser, until a page-level pass says
otherwise.

## The same question about a single name

A rate needs a page. A library catalogue often has only a title or a
name, and the question still matters there. A reader searching for
*Boghosian* should find both `Պօղոսեան` and `Պողոսյան`, and knowing which
orthography a record is in tells a search system how to fold it. So the
same idea went into [tetrak-translit](https://scattercode.github.io/tetrak-translit/),
our transliteration library, rebuilt for strings too short to have a rate.

Its [detector](https://github.com/scattercode/tetrak-translit/blob/main/src/tetrak_translit/hy/orthography.py)
works on *presence* rather than rate, and adds tells that only make sense
for a short string:

- **Classical** if there is any free `ւ`, any `եա` or `եօ` digraph (which
  reformed spelling writes `յա`, `յո`), or any `է` inside a word. On a
  page, inner `է` adds nothing once `ւ` has been counted. On a single name
  like `Գէորգ` it may be the only tell there is.
- **Reformed** if there is none of those, but there is a `յ` between a
  consonant and a vowel (the reformed `-յան` of `Պողոսյան`) or the ligature
  `և`.
- **Indeterminate** if there is nothing at all. `Արմեն` is spelled the same
  way under both, and the honest answer is that the string doesn't say.

```python
from tetrak_translit import detect

detect("Պօղոսեան").orthography   # 'classical'
detect("Պողոսյան").orthography   # 'reformed'
detect("Գէորգ").orthography      # 'classical'
detect("Արմեն").orthography      # 'indeterminate'
```

Three answers rather than two is the important part. A classifier that
must always pick a side will pick one for `Արմեն`, and whatever relies on
it downstream will treat a guess as a fact.

## Where it goes wrong

The test reads how a text was *spelled*. That isn't always how it was
*printed*, and three cases fall in the gap.

**Reformed text typed with two letters.** The reformed "and" is the
ligature `և`. A lot of reformed Armenian typed on keyboards that make the
ligature awkward to enter is written `եւ` instead. Every one of those
contains a free `ւ`. On a page, the trainer's rate absorbs a few of them,
but text that uses `եւ` every time can drift into the mixed band. On a
single string, tetrak-translit calls it classical. Wikisource's
proofreaders set what the page prints, so the census never met the
problem. A catalogue typed by hand will. For now we treat that as a known
gap rather than guess.

**Quotation.** A reformed book that quotes Grabar contains classical
spelling, and the classifier reports it. That's correct about the text and
unhelpful about the book. The mixed verdict is how the page-level version
copes. The string-level version has no rate to fall back on, and a quoted
classical title in a reformed record is called classical.

**The ligature in a classical title.** The case we started with: a
title-only string like `Ազգ և հայրենիք` has no classical tell and one
reformed one, so the detector calls it reformed. The book is classical. A
detector working on a title can only be as right as the title, which is
where this began.

## If you are doing the same for another script

Armenian isn't the only script printed in two spellings. Russian before
and after 1918 sets the same problem with different details, and so does
any language whose spelling was reformed while its old books stayed on the
shelves. The lessons carry over:

- **Read the text, not the metadata.** Titles and catalogue records are
  typed by people at a later date. The page is the evidence.
- **Look for a rule, not a frequency.** The marker worth having is a
  character the reform made impossible in one context, not one it made
  less common. Impossible gives you an empty band to put thresholds in.
- **Have a third answer.** *Mixed* on a page and *indeterminate* on a
  string. They aren't failures of the classifier. They're the cases where
  the honest answer is that the text doesn't say.
- **Measure the markers you expected to work, and write down why they
  didn't.** The `եւ`/`և` habit looked like the obvious test. Both of our
  modules keep a note in their docstrings saying why it isn't, so nobody
  spends an afternoon rediscovering that.
