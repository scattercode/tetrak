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

*Updated on 12 November 2026 with the reply to our report, and with
counts from real text.*

Implementing it, we found two sequences the list doesn't cover. *tsh*
could be `თ` then `შ`, or `ც` then `ჰ`; *dzh* could be `დ` then `ჟ`, or
`ძ` then `ჰ`. In each case the standard gives two different spellings the
same romanisation, and nothing in the Latin says which was meant.

The standard's claim is absolute. Its introduction says "the system
is entirely reversible", and of the dot it says "this avoids any
ambiguity and ensures the reversibility of the system". For these two
sequences it doesn't, so we think this is a defect in the standard, not
a matter of interpretation.

To be sure there were no others, we romanised every sequence of two and
three Georgian letters, more than 37,000 of them, and read each one back.
Every failure came down to one of those four pairs. A dot in one pair of
each two, *t·sh* or *ts·h* and *d·zh* or *dz·h*, makes every one of those
sequences read back correctly.

The foreword asks for feedback through each country's national standards
body, so in October 2026 we reported this to BSI, the UK's member of ISO,
suggesting *t·sh* and *d·zh*. The reply came in November. It agreed that
the list should have included both sequences, and said it will be
corrected when the standard is next revised. It added that the two
combinations are theoretical, so the gap should cause no trouble in the
meantime.

### How often it happens

When we first published this article we said much the same: that neither
combination is common, because `ჰ` rarely follows a consonant. That is
true of one reading of each sequence. We hadn't counted the other, and
the reply prompted us to.

*tsh* is everywhere in Georgian. The postposition `-ში`, "in", is
written as part of its noun, so any noun whose stem ends in `თ` has `თ`
then `შ`: `საათში` (*saatshi*, in an hour), `წუთში` (*ts'utshi*, in a
minute), `საფრანგეთში` (*saprangetshi*, in France). Compounds have it
too: `ხუთშაბათი`, Thursday, is *khutshabati*.

The other reading exists as well, but only in borrowed names, most of
them German, where a *z* meets an *h*: `ალცჰაიმერი` (Alzheimer),
`ერცჰერცოგი` (archduke, from *Erzherzog*), `პფორცჰაიმი` (Pforzheim).

We looked for all four pairs in the page titles of the Georgian
Wikipedia on 12 November 2026, 252,103 of them. That list includes
redirects, which are alternative titles: other names for the subject,
other word orders, and variant spellings. A redirect shows that someone
writes a form, but not that it is the accepted one, so we count them
apart from the articles:

| Romanised | Georgian | Articles | Redirects | Different words in the articles | For example |
|---|---|---|---|---|---|
| tsh | `თ` then `შ` | 864 | 85 | 72 | `საფრანგეთში`, `ხუთშაბათი` |
| tsh | `ც` then `ჰ` | 18 | 6 | 14 | `ალცჰაიმერი`, `ერცჰერცოგი` |
| dzh | `დ` then `ჟ` | 5 | 2 | 5 | `დჟარსარი` (a mountain in Armenia) |
| dzh | `ძ` then `ჰ` | 0 | 1 | 0 | none |

Of the 72 words with `თ` then `შ`, 53 are a noun with `-ში`. We would
expect ordinary prose to lean further the same way, since titles are
rich in foreign names and short on phrases with "in", but we haven't
measured that.

So *tsh* is not theoretical. It is in ordinary Georgian many times over,
and because both readings of it occur in real text, no rule for reading
an undotted *tsh* back can be right every time.

*dzh* very nearly is theoretical. The five articles with `დ` then `ჟ`
are all foreign names spelled letter by letter from another alphabet,
and Georgian usually writes that sound with the single letter `ჯ`. The
redirects show the preference: `ესმა რედჟეპოვა` leads to
`ესმა რეჯეპოვა`. The only title with `ძ` then `ჰ`, `აძჰილი`, is a
redirect too, to a village whose article is spelled `აჟილი`.

### What we do about it

Our library still writes what the standard says, with no dot in any of
the four pairs. Reading back, it has to choose, and since version 4.5.0
it chooses the reading Georgian words have: *tsh* is `თ` then `შ`, and
*dzh* is `დ` then `ჟ`. Before that it took the letter pair first, so it
read *saatshi* back as `სააცჰი`, which is not a word at all.

The cost is the borrowed names. *altshaimeri* now comes back as
`ალთშაიმერი`. Tests record both the choice and the cost, so we will
notice when a revised standard needs them to change. In the meantime the
library honours a dot typed by hand: *alts·haimeri* reads back as
`ალცჰაიმერი`.

The count also changes what we would suggest. Each sequence needs a dot
in only one of its two pairs, and the choice is which one:

| Georgian | Found in | As published | Our suggestion in October | What we would suggest now |
|---|---|---|---|---|
| `თ` then `შ` | ordinary words | tsh | t·sh | tsh |
| `ც` then `ჰ` | borrowed names | tsh | tsh | ts·h |
| `დ` then `ჟ` | a few foreign names | dzh | d·zh | dzh |
| `ძ` then `ჰ` | one redirect | dzh | dzh | dz·h |

Both columns make the standard reversible, but they are not equally
good. Under our October suggestion `საათში`, "in an hour", would be
written *saat·shi*, and so would every other noun with `-ში` after a
`თ`. Under the other, `საათში` stays *saatshi*, as the national system
writes it, and the dot goes into a couple of dozen borrowed names instead:
`ალცჰაიმერი` becomes *alts·haimeri*. Keeping ordinary text free of dots
is the point of the design, so if we were making the suggestion again,
it would be the last column.

None of this touches search. Our fold gives both readings of each
sequence the same key, so *altshaimeri* still finds `ალცჰაიმერი`.

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
