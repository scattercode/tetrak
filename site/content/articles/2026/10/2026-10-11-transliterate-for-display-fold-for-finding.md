---
title: "Transliterate for display, fold for finding"
date: 2026-10-11
draft: false
slug: "transliterate-for-display-fold-for-finding"
kicker: "Method"
standfirst: "A fold maps many spellings onto one key, so that things that differ in ways that don't matter compare as equal. Tetrak already folds in three places, and the fourth, search across scripts, explains why a transliteration is for the reader and never for the index"
author: stephen-masters
tags: [armenian, search, transliteration, unicode, project-notes]
---

The word *fold* turns up all over Tetrak. The recogniser's output goes
through a script fold. The accuracy metric folds before it compares. The
trainer folds transcribers' habits out of its ground truth. And
[tetrak-translit](https://scattercode.github.io/tetrak-translit/), our
transliteration library, has a function called `fold()` that most of the
library exists to support. These are the same idea four times. It's worth
explaining once, slowly, because the fourth use only makes sense once the
first three do. It also answers a question that comes up as soon as you look at the
library: if you have five perfectly good romanisation schemes, why do you
need anything else to search with?

## What a fold is

A fold is a function that maps many inputs onto one output, on purpose,
so that things which differ in ways you don't care about compare as
equal.

You have almost certainly used one. Case folding is the familiar example:
`"Straße".casefold()` in Python gives `"strasse"`, so a comparison of
folded strings ignores case, including the cases where upper and lower
case don't map one to one. Search engines fold accents: Elasticsearch's
`asciifolding` filter and Solr's equivalent turn *café* into *cafe*, so a
reader without an *é* on their keyboard still finds the café. Unicode
defines case folding formally, in a table of its own, because "make these
compare equal" turns out to need more care than "make these lowercase".

Three properties make something a fold rather than just a transformation:

- **It throws information away, deliberately.** *Café* and *cafe* go in,
  one key comes out, and nothing can tell you afterwards which one it
  was. That's the point.
- **You compare folded forms. You don't show them.** The folded key is a
  tool for matching. The text a reader sees is the original.
- **Every fold is a claim about what doesn't matter.** Folding case
  claims that case doesn't matter *for this purpose*. The same two
  strings might be equal for one purpose and different for another, so a
  fold always belongs to a job, never to the text.

The third property is the one that causes the trouble, and it runs
through everything below.

## Three folds Tetrak already runs

### On the way out of the recogniser

Some Armenian letters have Latin twins: `հ` and `h`, the Armenian full
stop `։` and the colon. At the level of ink on paper there is nothing to
tell them apart, and our recogniser reads one character at a time, with
no language model to say that a Latin letter is unlikely in the middle of
an Armenian word. So sometimes it emits the twin.

The script fold, `fold_script()` in the model's package, fixes that.
Inside any word that already contains an Armenian letter, it folds each
Latin twin back to its Armenian form. A wholly Latin word, such as a name
or a citation, is left alone. This fold is unusual in that its output *is*
what the reader sees, because inside an Armenian word the Latin twin is
never right. The claim it makes ("inside an Armenian word, `h` means `հ`")
is true every time.

The fold's first draft made a second claim that wasn't true. It also
folded the en dash onto the hyphen, which looked like a free correction.
It turned out to be grammar: Armenian joins case endings to numerals and
abbreviations with a dash, and the transcribers use an en dash for many
of those. The fold broke more words than it fixed, and we took it out. We
[wrote that up]({{< relref "/articles/2026/09/2026-09-01-shipping-the-armenian-recogniser.md" >}})
at the time, and it's the first lesson about folds: **a difference that
looks like noise can be a meaning you haven't met yet.**

### Inside the accuracy metric

When we score an engine's reading against a reference transcript, both
sides are folded first. The fold lowercases, collapses whitespace, and
equates two Armenian marks with the ASCII characters they print
identically to: the full stop `։` with the colon, and the abbreviation
dot `․` with the full stop. Since tetrak 5.15.0 it also equates the
two-letter `եւ` with the ligature `և`.

Each of those is a claim that the difference doesn't matter *for
scoring*. Transcribers type the colon because it's on every keyboard.
Classical presses split on whether to print `եւ` or `և`, as we found
[when we told the two orthographies apart]({{< relref "/articles/2026/10/2026-10-11-classical-or-reformed-armenian-by-one-letter.md" >}}).
An engine that outputs one form where the transcript has the other hasn't
misread anything, and a metric that marked it wrong would be ranking
engines on which habits they share with a transcriber.

Note where the fold lives. The reference transcripts still say exactly
what the page prints, and we train on them as printed, so the model
learns to read both forms. The fold only exists inside the comparison.
That's the second lesson: **fold at the point of comparison, and keep
the original everywhere else.**

### On both sides of a check

The trainer cleans every harvested transcript before using it: it folds
transcribers' stand-ins (a typographic apostrophe for the Armenian
apostrophe `՚`, a backtick for the Armenian comma `՝`) onto the characters
the page prints. When we built the check that stops evaluation text from
leaking into training data, it had to read the harvest through *exactly*
that fold, with the training pipeline's own code, because any difference
between how the check reads a page and how the trainer reads it is a
place for a duplicate to hide. We
[wrote about that check]({{< relref "/articles/2026/10/2026-10-06-when-your-training-set-has-read-your-test-set.md" >}})
last week. The third lesson: **two things being compared must go through
the same fold**, or the comparison is measuring the folds.

## Transliteration is for display

Now the fourth fold, which needs a detour first.

A transliteration renders a script in another script for a reader. For
Armenian there are several standards, and they disagree, because each
serves a different reader. Here is what tetrak-translit's five Armenian
schemes make of three names:

| Armenian | ALA-LC | ISO 9985 | BGN/PCGN | Hübschmann-Meillet | Western |
|---|---|---|---|---|---|
| Երևան | Erevan | Erewan | Yerevan | Erewan | Yerevan |
| Պողոսյան | Poghosyan | Poġosyan | Poghosyan | Połosyan | Boghosyan |
| Հակոբ | Hakob | Hakob | Hakob | Hakob | Hagop |

None of these is wrong:

- **ALA-LC** is what library catalogues use: the Library of Congress,
  WorldCat, a Koha catalogue. A librarian writing *Erevan* is following
  the table exactly.
- **ISO 9985** and **Hübschmann-Meillet** give every letter a distinct
  form, using diacritics where plain letters run out, so they can be read
  back into Armenian without loss. That matters for data exchange and for
  linguists.
- **BGN/PCGN** is the system behind English place names, which is why the
  map says *Yerevan*.
- **The Western pronunciation spelling** isn't a standard at all. It's
  how most of the diaspora writes its own names: *Hagop*, *Boghosian*,
  *Kevork*. Western Armenian pronounces the classical letters with the
  voiced and voiceless consonants swapped relative to Eastern, so the
  same letters that give Eastern *Hakob* give Western *Hagop*.

A transliteration should therefore be faithful to its standard and keep
every distinction its reader expects. A catalogue record romanised under
ALA-LC should look like ALA-LC. That's exactly why a transliteration is
the wrong tool for finding things.

## Why you can't search with a transliteration

Picture a catalogue built up over decades. Some records are in Armenian
script, in classical spelling or reformed. Some were romanised by
librarians under ALA-LC, and older ones under whatever the library used
before. Records harvested from elsewhere use other schemes. Then a reader
arrives and types *Boghosian*, because that's how their grandmother
spelled it.

Exact matching finds almost nothing. The obvious fix, picking one scheme
and converting everything into it, doesn't work either:

- **The reader's spelling isn't in any scheme.** *Boghosian*, with its
  *-ian*, is a popular spelling. No table produces it, so no table can
  read it back.
- **Most schemes can't be reversed.** ALA-LC's *ts* could be `ծ`, or `տ`
  followed by `ս`. Converting *into* Armenian means guessing.
- **Schemes disagree on purpose.** The whole point of the table above is
  that the same name has several right answers. Converting them all to
  one would erase the distinctions each reader relies on.

What search needs isn't a better transliteration. It needs a fold: a key
coarse enough that *Boghosian*, *Poghosyan*, `Պողոսյան` and the classical
`Պօղոսեան` all land in the same place.

## How the Armenian fold works

tetrak-translit's `fold()` maps any spelling of an Armenian word, in
either script, onto one lowercase Latin skeleton. It works in two stages.

**Armenian text is first normalised across the spelling reform**, towards
the reformed spelling: `եւ` becomes `և`, `է` becomes `ե`, the classical
digraphs `եա` and `իւ` become `յա` and `յու`, and a silent final `յ` is
dropped. The result is then rendered through ALA-LC, so that Armenian
input and catalogue Latin arrive at the next stage by the same road.

**Latin is then reduced to a skeleton.** Diacritics and aspiration marks
are stripped. Each sound's competing spellings are collapsed onto one
(`ž` and `zh`; `x` and `kh`; `ł`, `ġ` and `gh`; `ow`, `ou` and `u`; `w`
and `v`). The voiced and voiceless pairs are merged (`b` with `p`, `d`
with `t`, `g` with `k`), because that's exactly where Eastern and
Western spellings disagree. The glides are regularised, so *Yerevan* and
*Erevan* meet, and so do *-yan*, *-ean* and *-ian*. Doubled letters are
collapsed, and anything that isn't a letter or a digit goes.

```python
import tetrak_translit as tt

{tt.fold(s, script="hy") for s in
 ["Երևան", "Երեւան", "Erevan", "Erewan", "Yerevan"]}
# {'erevan'}

{tt.fold(s, script="hy") for s in
 ["Պողոսյան", "Պօղոսեան", "Poghosyan", "Boghosian"]}
# {'poghosian'}

{tt.fold(s, script="hy") for s in
 ["Հակոբ", "Յակոբ", "Hakob", "Yakob", "Hagop"]}
# {'hakop'}
```

Look at the keys: *poghosian*, *hakop*. Nobody spells the names that way,
and nobody is meant to read them. They're the coarse middle point that
every spelling folds down to, and the merges that get there would be
errors in a transliteration. Merging *b* with *p* would be wrong in a
catalogue record. In a search key, it's how *Bedros* finds *Petros*.

### Index time and query time

A fold is used twice, and both uses must be the same function. At index
time, every record's name and title fields are folded and the keys stored
next to the originals. At query time, the reader's search is folded the
same way and matched against the keys. The reader sees the record as it
was catalogued, in whatever script and scheme it was written. The key
never appears on screen. This is the same shape as accent folding in
Elasticsearch or Solr, and `fold()` is meant to be called from that kind
of analysis chain.

### Each script makes its own claims

Because every fold is a claim about what doesn't matter, a fold can't be
shared between scripts that disagree about what matters. Our Georgian
fold also strips apostrophes, merging the aspirated and ejective
consonants however each system marked them. But it must never merge *b*
with *p*. In Georgian, `ბ` and `პ` are different letters that don't swap
the way Armenian's do. *Batumi* folded under Armenian rules would never
find `ბათუმი`.

So a Latin string can't be folded until you say which script it's meant
to be in:

```python
tt.fold("Tbilisi")
# ScriptRequiredError: fold() needs to know which script's rules to
# apply to Latin text: pass script='hy' (Armenian) or script='ka' (Georgian)

tt.fold("Tbilisi", script="ka") == tt.fold("თბილისი", script="ka")
# True
```

Text already in Armenian or Georgian script says which rules apply by
itself. Latin text doesn't, and the library refuses to guess rather than
default to one.

## What a fold should not do

A coarser fold finds more, and it also merges more names that aren't the
same. There's no setting that is simply correct, so the fold's claims are
written down as tests. One published file lists groups of spellings that
must fold together: cities, surnames, saints and poets, in both scripts,
both orthographies and every scheme. A second test checks that different
names stay different. If a proposed rule would merge two names that a
reader would want kept apart, the second test is where we find out.

The fold also doesn't claim to be complete, and its gaps are tests too,
asserted as failing:

- `Մկրտիչ` is *Mkrtich* in every scheme, but *Megerdich* on many a
  gravestone, with vowels the Armenian doesn't write. The two don't fold
  together.
- *Khachaturian* came to English through Russian, which gave it a *u*
  that `Խաչատրյան` doesn't have.
- Classical `աւր` and reformed `օր` (*day*) are the same word, but the
  fold reads `ւ` as *v* and can't know this one changed differently.

If a change to the rules closes one of these, its test moves into the
published set. The right way to extend a fold is to add the cases first
and then find the rule that passes them, which is the habit we built when
the dash fold went wrong.

## The pattern

Four folds, one idea. Put together, the lessons are short:

- **A fold is a claim about what doesn't matter, for one job.** Write the
  claim down, and decide which job it serves.
- **Measure it on real data.** A difference that looks like noise can be
  grammar.
- **Fold at the point of comparison.** Keep the original for training,
  for storage and for the reader.
- **Use the same fold on both sides** of every comparison: reference and
  reading, harvest and evaluation set, index and query.
- **Never show a fold key to a reader.** Transliterate for display, fold
  for finding.
