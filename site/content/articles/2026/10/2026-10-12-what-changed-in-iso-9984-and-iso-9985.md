---
title: "What changed in ISO 9984 and ISO 9985 in 2026"
date: 2026-10-12
draft: false
slug: "what-changed-in-iso-9984-and-iso-9985"
kicker: "The field"
standfirst: "In January 2026 ISO replaced its thirty-year-old standards for romanising Georgian and Armenian. The Georgian one now puts the apostrophe on the other letter of each pair, so text romanised under the old edition reads back wrongly under the new one, and nothing warns you"
author: stephen-masters
tags: [georgian, armenian, transliteration, standards, project-notes]
---

ISO publishes one standard for writing Georgian in Latin letters,
ISO 9984, and one for Armenian, ISO 9985. Both first appeared in 1996, and
both were replaced in January 2026 by second editions. We found out by
accident, while checking the references for
[an article about search]({{< relref "/articles/2026/10/2026-10-12-transliterate-for-display-fold-for-finding.md" >}}):
the citation we had for ISO 9985:1996 led to a page marking it withdrawn.

We haven't found anyone describing what changed. ISO's own pages list the
new editions, standards bodies' shops sell them, and that's all. At the
time of writing, Wikipedia's page on romanising Georgian still describes
the 1996 edition as current. So this article describes the changes, from
the published standards, for anyone who keeps romanised Georgian or
Armenian in a catalogue, a database, or a gazetteer.

The short version: the Armenian standard changed four letters, for a
reason that makes sense once you see the pattern. The Georgian standard is
a completely different system from the one it replaced, and some of its
letters now mean the opposite of what they meant before.

We implemented both editions in
[tetrak-translit](https://scattercode.github.io/tetrak-translit/), our
transliteration library, so the examples below are its output. The tables
themselves are ISO's to publish, so we describe the changes rather than
reproduce them; [ISO 9984:2026](https://www.iso.org/standard/87131.html)
and [ISO 9985:2026](https://www.iso.org/standard/87132.html) are on
ISO's site.

## Georgian: the apostrophe changes sides

### Two traditions for one set of sounds

Georgian has five pairs of consonants that differ in the same way: an
aspirated one, said with a puff of breath, and an ejective one, said with
a catch in the throat. `თ` and `ტ` are both a kind of *t*; `ფ` and `პ` are
both a kind of *p*; and so on for `ქ`/`კ`, `ჩ`/`ჭ` and `ც`/`წ`. Latin has
one letter for each sound, so every romanisation has to mark one member of
each pair, and there are two traditions for which one.

The library tradition marks the **aspirate**. The Library of Congress
table writes `თბილისი` as *Tʻbilisi*, and ISO 9984:1996 wrote it
*T'bilisi*. Georgia's national system, devised in 2002 and the one it
uses for its own place names, marks the **ejective** instead and leaves
the aspirate plain, which is why the capital is *Tbilisi* in English and
*Ts'ereteli* has its apostrophe where it does. The UK and US geographic
names boards switched to the national system in 2009, from a 1981 system
of their own that marked the aspirate.

Until this year ISO 9984 sat with the library tradition, as the Library
of Congress table still does. The 2026 edition moves it to the other side:
it is based on the national system, "with modifications
incorporated to ensure reversibility", in the words of its foreword.

### What that means letter by letter

The 1996 edition was built from single letters with diacritics. The 2026
edition uses the national system's letter pairs:

| Georgian | 1996 edition | 2026 edition |
|---|---|---|
| `თ` `ფ` `ქ` (aspirated) | t' p' k' | t p k |
| `ტ` `პ` `კ` (ejective) | t p k | t' p' k' |
| `ჩ` / `ჭ` | č' / č | ch / ch' |
| `ც` / `წ` | c' / c | ts / ts' |
| `ყ` | q | q' |
| `ჟ` `შ` | ž š | zh sh |
| `ღ` | ḡ | gh |
| `ხ` | x | kh |
| `ძ` | j | dz |
| `ჯ` | ǰ | j |

The other letters are unchanged. For most words the new edition gives
exactly the national spelling:

| Georgian | 1996 edition | 2026 edition |
|---|---|---|
| თბილისი | t'bilisi | tbilisi |
| ქუთაისი | k'ut'aisi | kutaisi |
| წერეთელი | ceret'eli | ts'ereteli |
| მცხეთა | mc'xet'a | mtskheta |
| ჭავჭავაძე | čavčavaje | ch'avch'avadze |
| ჯავახიშვილი | ǰavaxišvili | javakhishvili |

The new edition also keeps the six historical letters the old one had,
adds eight more historical and phonetic letters, and drops the old edition's
table of punctuation, since Georgian now uses the same punctuation as
Latin-script languages.

### Old text reads back to Georgian letters ... just the wrong ones

Look at three letters in that first table. The apostrophe now marks the
other member of each pair. `j` was `ძ` and is now `ჯ`. And `t`, `p` and `k`
on their own were the ejectives and are now the aspirates. A string
written under the 1996 edition, read back with the 2026 table, gives
real Georgian letters, just the wrong ones:

| 1996 romanisation | Read with the 2026 table | Should be |
|---|---|---|
| t'bilisi | ტბილისი | თბილისი |
| k'ut'aisi | კუტაისი | ქუთაისი |
| jveli | ჯველი | ძველი |

Nothing fails. There's no stray character or error message to notice,
only a word that is wrong, and which only someone reading the Georgian
will spot. The reverse is just as bad: a 2026 string read with the old
table makes the same swaps the other way.

The national system, and so the new edition, is better for readers. Most
English-language writing already uses its spellings, so moving the
international standard to match them is a sensible change. But it means
"ISO 9984" no longer names one system, and anything that stores a
romanisation needs to know which edition made it.

### How a system of letter pairs stays reversible

ISO's transliteration standards promise reversibility: from the Latin you
can get back exactly the original script. The 1996 edition kept that
promise easily, because every Georgian letter had its own Latin letter,
with a diacritic where the plain alphabet ran out. Letter pairs break it.
*zh* is `ჟ`, but it could also be `ზ` followed by `ჰ`; *ts* is `ც`, but it
could be `თ` followed by `ს`.

The 2026 edition's fix is a middle dot (U+00B7). When two letters would
otherwise read as a pair, a dot goes between them:

| Georgian | 2026 edition |
|---|---|
| `ჟ` | zh |
| `ზ` then `ჰ` | z·h |
| `ც` | ts |
| `თ` then `ს` | t·s |
| `ძ` | dz |
| `დ` then `ზ` | d·z |

The standard lists where the dot goes: between `გ`, `ზ`, `ს` or `ქ` and a
following `ჰ`, between `თ` and `ს`, and between `დ` and `ზ`. Reading back,
the dot is simply skipped. It's an elegant solution, because the dot
appears only in those rare places, and the ordinary text you see
everywhere else is the familiar national spelling.

### A gap in the list

Implementing it, we found two sequences the list doesn't cover. *dzh*
could be `ძ` then `ჰ`, or `დ` then `ჟ`; *tsh* could be `ც` then `ჰ`, or
`თ` then `შ`. In each case the standard gives two different spellings the
same romanisation, and nothing in the Latin says which was meant.

Neither combination is common, because `ჰ` rarely follows a consonant.
But the standard's claim is absolute. Its introduction says "the system
is entirely reversible", and of the dot it says "this avoids any
ambiguity and ensures the reversibility of the system". For these two
sequences it doesn't, so we think this is a defect in the standard, not
a matter of interpretation.

To be sure there were no others, we romanised every sequence of two and
three Georgian letters, more than 37,000 of them, and read each one back.
Every failure came down to `დჟ` or `თშ`. Adding those two pairs to the
list, so that they are written *d·zh* and *t·sh*, makes every one of
those sequences read back correctly.

The foreword asks for feedback through each country's national standards
body, so in October 2026 we reported this to BSI, the UK's member of ISO,
with the two extra pairs as a suggested fix. Until the standard
changes, our library follows it as published: it reads *dzh* and *tsh*
back as `ძ`+`ჰ` and `ც`+`ჰ`, and a test records that, so we will notice
when an amendment needs it to change.

## Armenian: four letters, one pattern

ISO 9985's change is smaller, and it makes the standard more consistent.

Armenian has the same kind of pairs as Georgian, though here it is
plain against aspirated. The 1996 edition marked them in two different
ways. For *p*, *t* and *k* it used a plain letter and the same letter
with an apostrophe: `պ`/`փ` were *p*/*p'*. For the two affricate pairs it
used different letters instead, so `ծ`/`ց` were *ç*/*c'*, and `ճ`/`չ`
were *č̣*/*č*, with a dot below to tell the first from the second.

The 2026 edition, in its foreword's words, shows these pairs "visually
consistently": a plain letter for the unaspirated one and an apostrophe
for the aspirated one, for all five pairs. Together with one change to a
vowel, that moves four letters:

| Armenian | 1996 edition | 2026 edition |
|---|---|---|
| `ծ` | ç | c |
| `ճ` | č̣ | č |
| `չ` | č | č' |
| `օ` | ò | ō |

The foreword also specifies the apostrophe itself: the plain, neutral
apostrophe (U+0027) rather than the typographic one (U+2019). Everything
else, including *ow* for `ու` and *ew* for `և`, is as it was.

There is one trap here, smaller than Georgian's. *č* has changed meaning.
In 1996 it was `չ`; in 2026 it is `ճ`. So the poet Charents, `Չարենց`,
romanised *Čarenc'* under the old edition, reads back under the new one
as `Ճարենց`, which is not his name. Under the new edition he is
*Č'arenc'*.

The 2026 edition also has a table for punctuation. Its marks are
converted where they stand, including the stress marks Armenian sets
over the stressed vowel in the middle of a word, so `կարդացե՞լ`
(*have you read?*) becomes *kardac'e?l*. We haven't seen the 1996
edition's text on punctuation, so we can't say whether this part is new.

## A quieter change at the Library of Congress

While checking these, we found that the Library of Congress table for
Armenian, the ALA-LC table that library catalogues use, now carries the
line "2022 version", with earlier versions in 2011 and 1997. Our library had been written from the
2011 table, and the 2022 version includes rules we didn't have, though
we can't tell which are new in 2022 and which we had missed:

- **A soft sign**, the prime `ʹ`, between letters that would otherwise
  read as a pair: *patʹsparan* for `պատսպարան`. It is a similar idea
  to ISO 9984's middle dot.
- **Rules for classical spelling only**, the orthography used across most
  of the diaspora: a word-initial `յ` becomes `ḥ`, so `Յակոբ` is *Ḥakob*.
- **Punctuation that moves.** The question and exclamation marks that
  Armenian sets over a vowel go to the end of the sentence, the way
  English writes them: `Դու կարդացե՞լ ես այս գիրքը` is
  *Du kardatsʻel es ays girkʻě?*.

The Georgian ALA-LC table is still the 2011 version.

## If you keep romanised data

None of this is a reason to rewrite existing records. A catalogue
romanised under ISO 9984:1996 is correct under that edition; the new
edition is the one to use for new work. What matters is keeping the two
apart.

- **Record which edition made each romanisation.** "ISO 9984" is no
  longer enough to say what an apostrophe means. tetrak-translit keeps
  both editions under separate names, `iso_9984` for 2026 and
  `iso_9984_1996` for 1996 (and the same for ISO 9985), and each table
  carries its own version number.
- **Read old data back with the old table.** Reading back is where the
  quiet errors come from.
- **Check the version line on Library of Congress tables.** They change
  without much notice.
- **For search, don't convert at all.** A search key that ignores the
  differences between systems finds records made under either edition.
  That is what our [fold]({{< relref "/articles/2026/10/2026-10-12-transliterate-for-display-fold-for-finding.md" >}})
  is for, and both editions fold to the same key:

```python
import tetrak_translit as tt

{tt.fold(s, script="ka") for s in
 ["თბილისი", "t'bilisi", "Tbilisi", "Tʻbilisi"]}
# {'tbilisi'}
```

## Sources

The standards, from ISO:

- [ISO 9984:2026](https://www.iso.org/standard/87131.html),
  *Information and documentation — Transliteration of Georgian characters
  into Latin characters*, second edition. It replaced ISO 9984:1996.
- [ISO 9985:2026](https://www.iso.org/standard/87132.html),
  *Information and documentation — Transliteration of Armenian characters
  into Latin characters*, second edition. It replaced ISO 9985:1996.

In the UK, ISO standards are sold through BSI, as BS ISO 9984:2026 and
BS ISO 9985:2026.

Free to read: the national system the new Georgian edition draws on, and
the Library of Congress tables.

- BGN/PCGN,
  [Romanization of Georgian](https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/1057659/ROMANIZATION__GEORGIAN_Feb22_53_.pdf):
  the Georgian national system of 2002, as the UK and US geographic names
  boards adopted it in 2009.
- Library of Congress,
  [ALA-LC Romanization Tables: Armenian](https://www.loc.gov/catdir/cpso/romanization/armenian.pdf)
  (2022 version) and
  [Georgian](https://www.loc.gov/catdir/cpso/romanization/georgian.pdf)
  (2011 version).

And [tetrak-translit's scheme documentation](https://scattercode.github.io/tetrak-translit/schemes.html),
which describes how each edition is implemented.
