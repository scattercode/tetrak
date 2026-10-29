---
title: "Searching Syriac, a script that leaves out its vowels"
date: 2026-10-28
draft: false
slug: "searching-syriac"
kicker: "Method"
standfirst: "Ephrem the Syrian is catalogued as ʾAprém, Afrem, Ephraem and ܐܦܪܝܡ, and the script itself writes no vowels at all. We have added Syriac to tetrak-translit with a fold that keys on consonants alone, and this is what that buys, what it costs, and where we would welcome the help of people who read Syriac"
author: stephen-masters
tags: [syriac, search, transliteration, unicode, project-notes]
---

Ephrem the Syrian (c. 306–373 AD) was born in Nisibis, Mesopotamia, and later moved to Edessa. He was known for his vivid poetic sermons and liturgical hymns (*madrāšê*) and is venerated as a saint across Eastern and Western Christianity. As a result, he is among the most
copied authors of the Syriac churches. He is also among the most
translated: his works reached Armenian early, and the commentary on the
Pauline epistles attributed to him is known only through its Armenian translation.
The Mekhitarist fathers printed that translation at their press on San
Lazzaro in Venice in 1836, as the third volume of his works in Armenian,
*Srboyn Epʻremi matenagrutʻiwnkʻ*. The
[Armenian Institute's library](https://arm.koha-ptfs.co.uk/cgi-bin/koha/opac-detail.pl?biblionumber=430)
in London holds a copy, and the Austrian National Library has
[digitised one](http://data.onb.ac.at/ABO/%2BZ160702405). So his
name turns up in catalogues of Syriac manuscripts and of Armenian ones,
and in a good many forms:

- **ʾAprém**, as the Library of Congress romanises the Syriac;
- **Afrem**, as the West Syriac tradition writes it (*Mor Afrem*), with
  the soft *p* pronounced as *f*;
- **Ephraem**, the Latin form, in the Library of Congress heading
  *Ephraem, Syrus, Saint, 303-373* (LC authority records disagree slightly with historians on birth date);
- **Ephrem**, as most English writing has it;
- **ܐܦܪܝܡ**, as the Syriac script writes it;
- and **Եփրեմ**, in Armenian.

Set the Armenian aside for a moment and look at what the others share.
Not the vowels: *e*, *a*, *é* and *ae* disagree about every one of them.
The Syriac spelling has five letters, `ܐ ܦ ܪ ܝ ܡ`, and only three of
them are consonants in any sense a reader of Latin would recognise: *p*,
*r* and *m*. The first, alaph, is a glottal stop that most romanisations
drop. The fourth, yod, is a consonant that is also doing the job of the
vowel *é*. Everything else a reader sees in *ʾAprém* has been supplied by
someone who knew how to pronounce the word, because the script itself is not particularly phonetic.

That is the problem Syriac poses to search, and this article is about
how we have handled it in
[tetrak-translit](https://scattercode.github.io/tetrak-translit/), our
transliteration library.

## Why Syriac, and why now

We have been thinking about Syriac OCR for a while. Syriac manuscripts
survive in large numbers, many have been photographed, and very few have
been transcribed. In late October we attended a Zoom presentation by
[Dr Ani Shahinian](https://hmml.org/about/staff/shahinian/), cataloguer
of Armenian manuscripts at the
[Hill Museum & Manuscript Library](https://hmml.org) (HMML). As she
showed HMML's online collections, we noticed what looked like a large
Syriac collection beside the Armenian. The catalogue is published
online, so we had a look at what it holds, and we saw the same thing we
had seen with Armenian: titles and names recorded twice, once in the
script and once in a romanisation, and a search that only finds a record
if you type the form its cataloguer chose.

A recogniser is a long piece of work. A transliteration library that
understands the script is a short one, and it is the part that makes the
recogniser's output, and every catalogue record, findable. So we started
there.

## What makes Syriac different

Syriac is a literary form of Aramaic, first written at Edessa, and the
language of a large body of Christian literature from late antiquity
onwards. Several things about the script matter for search.

### It is written right to left

Like Arabic and Hebrew, Syriac runs right to left, and its letters join
to their neighbours. Unicode stores the letters in the order they are
read, so in the data `ܐܦܪܝܡ` begins with alaph, and the right-to-left
display is the browser's job, governed by the Unicode Bidirectional
Algorithm. Mostly the browser gets it right. Where it goes wrong is a
line that mixes directions: a Syriac title followed by an English one,
joined with a separator, can come out with the pieces in the wrong order.
The fix is to isolate each catalogue value, with HTML's `<bdi>` element
or `dir="auto"`, so that the browser lays out each one by itself. We
found that the hard way, putting Syriac titles on a page that had only
ever shown Armenian and English.

### It has no capital letters

Each Syriac letter changes shape as it joins its neighbours, but there
is no upper and lower case. That is one less thing for a fold to do, but a library that reads romanisations back into
the script has to know not to look for capitals that do not exist.

### It is normally written without vowels

This is the big one. Syriac is an abjad: its twenty-two letters are
consonants, and three of them, alaph, waw and yod, double as long
vowels (the *matres lectionis*). The short vowels, and the quality of
the long ones, are marked, when they are marked at all, by small signs
above or below the letters, and there are two systems for doing so:

- the **West Syriac** system, attributed to Jacob of Edessa, uses small
  forms of Greek vowel letters;
- the **East Syriac** system, the older, uses dots in different
  positions.

Most text has neither. In the catalogue we looked at, almost none of the
titles written in Syriac script carried a single vowel point.

### And it has other dots too

Not every dot is a vowel. Two dots over a word, *seyāmē*, mark it as a
plural. A dot above or below one of six letters (*b g d k p t*) says
whether it is pronounced hard or soft, which is why in the West Syriac
pronunciation of *Fenqitho* (`ܦܢܩܝܬܐ`) the `ܦ` (*p*) is *f* and the `ܬ`
(*t*) is *th*. There are feminine dots and dots that tell homographs
apart. None of these is a letter, and a fold has to ignore them all.

### One encoding, three styles

Syriac is written in three main styles: Estrangela, the oldest, used in
ancient manuscripts and now for headings; Serto, the cursive West Syriac
style; and the East Syriac style. They look quite different on the page,
but they are one script and one encoding. Nothing in the text says which
style a manuscript used, so nothing in our library tries to tell them
apart.

### Not all Syriac is in Syriac

Syriac letters have also been used to write other languages, most of all
Arabic: *Garshuni*. A catalogue of Syriac manuscripts is full of it,
along with Malayalam, Turkish and other languages in Syriac script. Our
library detects all of it as Syriac script, which it is. Whether it is
Syriac language is a different question, and another question the script alone cannot
answer.

## What the Library of Congress table asks for

The romanisation used by English-language libraries is the ALA-LC
Syriac table, in its 2012 version, the only one there has been. It is a
careful table. It maps each consonant to one Latin letter (with `ʾ` and
`ʿ` for alaph and ʿē), each vowel point to a vowel, and handles the
places where yod and waw carry a vowel, so `ܝ` with the right point
becomes *í*, and a final alaph after *ā* or *e* is dropped (*zadíqā*, not
*zadíqāʾ*).

And then, for unvocalised text, it says this:

> If the text to be transliterated has no vowels, supply them, starting
> from the Syriac vowels prescribed in J. Payne Smith's Syriac English
> Dictionary.

That is an instruction to a cataloguer who reads Syriac. No table can
follow it. To supply the vowels of a word you have to know which word it
is, in which form, and in which tradition, since the table goes on to
list where East Syriac differs from the dictionary.

So our library renders exactly what is written. A pointed text is
romanised as the table says, vowel for vowel. An unpointed one is
romanised as its consonants: `ܡܠܟܐ` is *mlkʾ*, where a cataloguer would
write *malkā*. That is less pleasant to read, but it is true to the
text, and it never invents a vowel that the manuscript did not write.
Our library has the same rule for every script: a transliteration is a
display of the text, and it must not guess.

We did look at doing better. Payne Smith's dictionary is out of
copyright and has been scanned, but the available text of it is not
clean enough to build on, and a dictionary's headwords do not cover the
inflected forms a title is written in. Supplying vowels is a real
project, one we would only take on alongside a Syriac recogniser, and
one we would want to do with Syriac scholars rather than for them.

## Folding on consonants

Display is only half of what the library does. The other half is the
*fold*: a function that maps every spelling of a word to one key, so
that one search finds them all. We have written about
[folding for Armenian]({{< relref "/articles/2026/10/2026-10-12-transliterate-for-display-fold-for-finding.md" >}}),
where the key is roughly the word as a Library of Congress cataloguer
would romanise it, with the marks taken off.

That approach cannot work for Syriac, because the romanisations
disagree most about exactly the thing the script leaves out. ALA-LC
writes *Penqítā* for the book of hymns for the year's feasts; the West
Syriac tradition writes *Fenqīthō*, with *o* for *ā* and the soft
consonants spelled out; a popular spelling drops the marks, *Fenqitho*;
and the script writes `ܦܢܩܝܬܐ`. The vowels differ in every one. What
they share is the consonants, so the Syriac key is the consonants:

| Spelling | Key |
|---|---|
| ܦܢܩܝܬܐ | `pnkt` |
| Penqítā | `pnkt` |
| Fenqīthō | `pnkt` |
| Fenqitho | `pnkt` |
| ܐܦܪܝܡ, ʾAprém, Afrem, Ephraem, Ephrem | `prm` |

The rules, in order:

1. Syriac script is rendered through the ALA-LC consonants, with any
   vowel points it carries, and Garshuni's extra letters on the
   consonants they stand for.
2. Latin spellings have their two-letter consonants reduced: *sh* is
   šin, and the West Syriac soft consonants *th*, *ph*, *kh*, *gh*, *dh*
   and *bh* are their letters; *f* is *p* and *c* is *k*. Only Latin gets
   this step. The script is rendered one letter at a time, so `ܕܗ` is a
   *d* followed by an *h*, not a soft *d*.
3. *q* becomes *k*, and every vowel is dropped, with *w*, *y*, *j* and
   *v*, which are waw and yod in one spelling or another (*Jacob*,
   *David*).
4. Diacritics go, so *ṭ* meets *t*, *ṣ* meets *s* and *ḥ* meets *h*.
   Alaph and ʿē, `ʾ` and `ʿ`, go with them, as most romanisations drop
   them.

One letter needed care. Šin, `ܫ`, is *š* in ALA-LC and *sh* nearly
everywhere else. If the key wrote it *sh*, then `ܫ` would meet `ܣܚ`, *s*
followed by *ḥ*, a different pair of letters. So šin is written *c* in
the key, a letter that step 2 guarantees nothing else will leave behind.
*Šḥímā*, *Shhimo* and `ܫܚܝܡܐ` all fold to `chm`.

## What it costs

A consonantal key is coarse, and that has costs we would rather state up front.

**It over-merges.** Words that differ only in their vowels, or only in
alaph, ʿē, waw and yod, share a key. `ܥܠ` (*on*) and `ܠܐ` (*not*) both
fold to `l`. The biblical *Ephraim* folds to `prm`, the same key as
Ephrem. In a search over titles and names, most such collisions are
harmless, because a search for a two-word title needs both keys to
match, but a one-word search with a short key finds more than it should.

**It under-matches more than the Armenian fold does.** We measured the
fold against that catalogue, which records most Syriac titles both in
the script and in a romanisation or translation, by checking how often
the two forms of a title reach the same key. For Armenian, the same
measurement finds nearly every pair. For Syriac, it finds most of them,
but noticeably fewer. The pairs it misses are mostly not failures of the
fold but things a fold cannot do:

- **Names in another language.** *Edessa* is the Greek name of the city
  the Syriac calls `ܐܘܪܗܝ`, *Urhay*; *Nisibis* is `ܢܨܝܒܝܢ`. *Bar
  Hebraeus* is the Latin form of *Bar ʿEbrāyā*, with an *h* the Syriac
  does not have and a Latin ending. No spelling rule turns one into the
  other. That is a job for [a name authority]({{< relref "/services.md#catalogue-search" >}}), which knows that two names
  belong to the same place or person, not for a fold. Our test index
  already has one for people: when it is built, each creator is looked
  up in a snapshot of Wikidata's names for the region, and the person's
  names in every language are indexed beside the catalogued one. A
  search for *Abul-faraj*, or for the Armenian `Գրիգոր Բար-Հեբրեոս`,
  finds Bar Hebraeus's works, though neither form appears in the
  catalogue. The same snapshot already holds the places, with *Edessa*,
  *Urhay* and `ܐܘܪܗܝ` under one entry and *Nisibis* beside `ܢܨܝܒܝܢ`, but
  the index does not use them yet: a place in a record is not a creator,
  and joining it needs its own rule for telling one *Edessa* from
  another.
- **Translated titles.** A cataloguer's *Book of hymns* is not a
  romanisation of anything.
- **Garshuni romanised as Arabic.** Arabic romanisation writes *j* where
  Syriac has `ܓ`, *g*, so *Jirjis* and `ܓܪܓܝܣ` part company.

**And it can intrude on other scripts.** When a search index holds
Armenian and Syriac records together, every query has to be folded both
ways, because the index cannot know which script the reader had in
mind. An Armenian query folded under the Syriac rules loses its vowels
too, and can find Syriac records that happen to share its consonants.
In our test index, a search for *Avetaran*, the Armenian for the
Gospel, reaches Syriac records whose key is also `trn`. We keep the
Syriac keys only on records that are Syriac, and rank a match on them
below a match on the Armenian keys, so every Armenian Gospel book comes
first and the Syriac strays fall to the end of the list. Ranking, not
matching, keeps them in their place.

## Two scripts, one search

The reward for all of this is the search the opening promised. In our
test index over that catalogue, one search for *Ephrem* finds the Syriac
manuscripts through `ܐܦܪܝܡ` and the Armenian ones through `Եփրեմ`,
together, under the one name a reader is likely to type. The Armenian
fold and the Syriac fold never meet. Each takes its own script's
spellings to its own key, and the query is folded both ways. Where a
name authority links the two, an Armenian-script search for Եփրեմ can
reach the Syriac records too.

## What we would like help with

We are not Syriac scholars. We built the tables from the standard and
the fold from the catalogue, and a fold built that way is bound to have
mistakes that a reader of Syriac would see at once. If
you read it, we would be grateful for:

- **Romanisations we have not met.** Our test cases cover the Library of
  Congress table, the West Syriac spellings, East Syriac ones and popular
  ones, for liturgical books, authors, places and common words. There
  are certainly traditions we have missed: French and German scholarly
  spellings, the romanisations of particular churches or catalogues.
- **Places where the fold is wrong.** Two spellings of one word that do
  not reach one key, or two different words that do and should not.
- **Better ways to supply vowels.** If you know of a lexical resource
  that could, with the right permissions, support vowel suggestions for
  unpointed text, we would like to hear about it.

The test cases are published, in
[`tests/data/syr_fold_cases.tsv`](https://github.com/scattercode/tetrak-translit/blob/main/tests/data/syr_fold_cases.tsv),
and the rules are documented in the library's
[fold reference](https://scattercode.github.io/tetrak-translit/fold.html#syriac).
The easiest way to tell us is an
[issue on the library](https://github.com/scattercode/tetrak-translit/issues),
but a message to either of us on LinkedIn works too.

## Further reading

### The script and its encoding

- The Unicode Consortium, *The Unicode Standard, Version 18.0*, chapter 9,
  "West Asia-I: Modern and Liturgical Scripts", section 9.3,
  ["Syriac"](https://www.unicode.org/versions/Unicode18.0.0/core-spec/chapter-9/).
  The encoding's own account of the script: the two vowel systems, the
  three styles, Garshuni, and the requirement that implementations use
  the bidirectional algorithm.
- The Unicode Consortium,
  [Syriac code chart, U+0700–U+074F](https://www.unicode.org/charts/PDF/U0700.pdf).
  Every letter, point and mark our package handles, with its name.
- The Unicode Consortium, *Unicode Standard Annex #9: Unicode
  Bidirectional Algorithm*, revision 52, 2026,
  [unicode.org/reports/tr9](https://www.unicode.org/reports/tr9/). How
  right-to-left and left-to-right text are laid out together, and why a
  line that mixes them can come out in the wrong order.
- W3C Internationalization,
  ["Inline markup and bidirectional text in HTML"](https://www.w3.org/International/articles/inline-bidi-markup/).
  The practical advice behind isolating each catalogue value with `<bdi>`
  or `dir="auto"`.

### Romanisation and the dictionaries it relies on

- Library of Congress,
  [*ALA-LC Romanization Tables: Syriac*](https://www.loc.gov/catdir/cpso/romanization/syriac.pdf),
  2012 version. The table our `syr/ala_lc` scheme follows letter by
  letter and point by point, including the instruction to supply vowels
  from Payne Smith and its rules for East Syriac.
- J. Payne Smith (Mrs Margoliouth), *A Compendious Syriac Dictionary,
  Founded upon the Thesaurus Syriacus of R. Payne Smith*, Oxford:
  Clarendon Press, 1903, often reprinted. The dictionary the ALA-LC
  table names as the source of vowels for unpointed text.
- Michael Sokoloff, *A Syriac Lexicon: A Translation from the Latin,
  Correction, Expansion, and Update of C. Brockelmann's Lexicon
  Syriacum*, Winona Lake, IN: Eisenbrauns, and Piscataway, NJ: Gorgias
  Press, 2009. The lexicon the ALA-LC table refers cataloguers to for
  East Syriac vocalisation when in doubt.
- Beth Mardutho: The Syriac Institute,
  [SEDRA](https://sedra.bethmardutho.org/), the Syriac Electronic Data
  Research Archive. A lexical and morphological database of Syriac, and
  the kind of resource vowel suggestions for unpointed text would need.

### Syriac and its study

- Sebastian P. Brock, *An Introduction to Syriac Studies*, third
  edition, Piscataway, NJ: Gorgias Press, 2017. A short guide to the
  language, its literature and the tools for studying it, by the field's
  most widely read introducer.
- Takamitsu Muraoka, *Classical Syriac: A Basic Grammar with a
  Chrestomathy*, second, revised edition, Porta Linguarum Orientalium
  19, Wiesbaden: Harrassowitz, 2005. A grammar of the classical
  language, with the script, its vowel signs and its other dots set out
  for the learner.
- Ephrem the Syrian, *Srboyn Epʻremi matenagrutʻiwnkʻ*, four volumes,
  Venice: I tparani Srboyn Ghazaru (the Mekhitarist press, San
  Lazzaro), 1836; volume 3, *Meknutʻiwn chʻorektasan tʻghtʻotsʻn
  Pawghosi*. The Armenian collected works, whose third volume is the
  commentary on the fourteen Pauline epistles mentioned in the opening.
  A copy is in the
  [Armenian Institute's library](https://arm.koha-ptfs.co.uk/cgi-bin/koha/opac-detail.pl?biblionumber=430),
  and the Austrian National Library's copy of volume 3 is
  [digitised](http://data.onb.ac.at/ABO/%2BZ160702405) and free to read.
- Ephrem the Syrian, *S. Ephraem Syri commentarii in epistolas D. Pauli
  nunc primum ex Armenio in Latinum sermonem a patribus Mekitharistis
  translati*, Venice: Typographia Sancti Lazari, 1893. The Mekhitarists'
  Latin translation of the same commentary, for readers without
  classical Armenian; a scan of the University of Toronto's copy is on
  the [Internet Archive](https://archive.org/details/commentariiinepi00ephruoft).
- Sebastian P. Brock, "Ephrem (d. 373)", in Sebastian P. Brock, Aaron
  M. Butts, George A. Kiraz and Lucas Van Rompay (eds), *Gorgias
  Encyclopedic Dictionary of the Syriac Heritage*, Piscataway, NJ:
  Gorgias Press, 2011; [electronic edition](https://gedsh.bethmardutho.org/Ephrem).
  A survey of Ephrem's life and works that counts the commentary on
  the Pauline epistles among his genuine writings and notes that it
  survives only in Armenian.

### Our own

- [tetrak-translit](https://scattercode.github.io/tetrak-translit/), the
  library's documentation, with the
  [Syriac scheme](https://scattercode.github.io/tetrak-translit/schemes.html#syriac)
  and the [Syriac fold](https://scattercode.github.io/tetrak-translit/fold.html#syriac).
- [Transliterate for display, fold for finding]({{< relref "/articles/2026/10/2026-10-12-transliterate-for-display-fold-for-finding.md" >}}),
  on what a fold is and why it is kept apart from the romanisation a
  reader sees.
