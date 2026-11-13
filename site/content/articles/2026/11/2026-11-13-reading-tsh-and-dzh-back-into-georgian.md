---
title: "საათში is not სააცჰი"
date: 2026-11-13
draft: false
slug: "reading-tsh-and-dzh-back-into-georgian"
kicker: "Method"
standfirst: "The international standard for writing Georgian in Latin letters promises that the Georgian can always be recovered. For two letter sequences, tsh and dzh, it cannot, and the obvious way to read them back gets everyday words wrong. What the gap is, who it catches, and how we think software should read them"
author: stephen-masters
tags: [georgian, transliteration, standards, project-notes]
---

Georgian says "in" with a suffix, rather than a separate word. `საათი`
(*saati*) is an hour, and `საათში` (*saatshi*) is "in an hour".
`საფრანგეთი` (*saprangeti*) is France, and `საფრანგეთში`
(*saprangetshi*) is "in France". The suffix is `-ში` (*-shi*), the noun
drops its final `ი` (*i*) to take it, and so any noun whose stem ends in
`თ` (*t*) puts a `თ` directly before a `შ` (*sh*). That is a lot of
nouns: the names of many countries end in `-ეთი` (*-eti*), for a start.

The Latin spellings here, and throughout, are those of the current
international standard, ISO 9984:2026. Its introduction says that "the
system is entirely reversible": from the Latin, the Georgian can always
be recovered. Try it with *saatshi*. The letters *tsh* can be cut
as *t* and *sh*, which gives back `საათში`, or as *ts* and *h*. The
standard does not say which, and the cut a program reaches for first
gives `სააცჰი`: also *saatshi* in Latin letters, and not a word.

Anyone who can read and write Georgian will almost certainly pick the
correct Georgian word based on the context of a sentence, but for any
automated transliteration or for a cataloguer who is not fluent, this
task is not so obvious.

We described this gap, among much else, in
[our account of the 2026 standards]({{< relref "/articles/2026/10/2026-10-12-what-changed-in-iso-9984-and-iso-9985.md" >}}).
This is a more focussed story for anyone with romanised Georgian in hand,
and a need to get the correct script back.

## How the standard keeps letters apart

ISO 9984:2026 is built on the romanisation Georgia itself uses on road
signs and in passports, which spells several single Georgian letters with
two Latin ones: `შ` is *sh*, `ჟ` is *zh*, `ც` is *ts*, `ძ` is *dz*, `ხ`
is *kh* and `ღ` is *gh*.

That is comfortable to read and impossible to reverse, because the same
two Latin letters can also be two Georgian letters that happen to sit
side by side. So the standard adds one device: a middle dot (·, U+00B7)
between two letters that would otherwise be read as one.

| Georgian | Written | Without the dot it would read as |
|---|---|---|
| `ზ` then `ჰ` | z·h | zh, the letter `ჟ` |
| `თ` then `ს` | t·s | ts, the letter `ც` |
| `დ` then `ზ` | d·z | dz, the letter `ძ` |

The standard lists the pairs that take the dot, six in all, and says of
the dot that "this avoids any ambiguity and ensures the reversibility of
the system".

## The two sequences the list misses

Every pair on the list is two single letters that together look like a
two-letter spelling. The list has nothing for the case where three Latin
letters can be cut in two places:

| Latin | Cut after the first letter | Cut after the second |
|---|---|---|
| tsh | t + sh: `თ` then `შ` | ts + h: `ც` then `ჰ` |
| dzh | d + zh: `დ` then `ჟ` | dz + h: `ძ` then `ჰ` |

None of those four pairs is on the list, so none gets a dot, and *tsh*
and *dzh* each stand for two different spellings. We checked every
sequence of two and of three Georgian letters, and these are the only
ones that fail to read back.

We reported it through our national standards body. The reply agreed
that both sequences should have been on the list, and said the list will
be corrected when the standard is next revised. Until then, the standard
as published is what conforming software writes.

## Why it is not a corner case

For *dzh* it very nearly is one. For *tsh* it is not, because of that
ending.

- **`თ` then `შ`** is ordinary Georgian. Besides `საათში` and
  `საფრანგეთში` there is `წუთში`, in a minute, and it turns up inside
  compounds too: `ხუთშაბათი` is Thursday.
- **`ც` then `ჰ`** appears only in borrowed names, most of them German:
  `ალცჰაიმერი` (Alzheimer), `ერცჰერცოგი` (archduke, from *Erzherzog*),
  `პფორცჰაიმი` (Pforzheim).
- **`დ` then `ჟ`** is rare, and found in foreign names spelled out
  letter by letter from another alphabet. **`ძ` then `ჰ`** we could not
  find in use at all.

We counted all four in the titles of the Georgian Wikipedia, and
[the table is in the longer article]({{< relref "/articles/2026/10/2026-10-12-what-changed-in-iso-9984-and-iso-9985.md#a-gap-in-the-list" >}}).
Words with `თ` then `შ` outnumber words with `ც` then `ჰ` several times
over, and most of them are a noun with `-ში`.

Two kinds of reader are caught.

**Someone who does not read Georgian.** A cataloguer or researcher
holding *saprangetshi* has no way to tell which letters were meant, and
the standard they are relying on says there is nothing to decide.

**Software.** The usual way to read a romanisation back is to take the
longest spelling that matches at each position. At the *t* of *saatshi*
that rule prefers *ts* to *t*, takes `ც`, and is left with an *h*: `ჰ`.
So the obvious implementation picks the reading that only borrowed names
have, and gets the everyday word wrong every time. Ours did, until
version 4.5.0.

Looking at the neighbouring letters does not rescue it: *khutshabati*
(Thursday) and *altshaimeri* (Alzheimer) both continue *tsha*.

## What we recommend

**When writing, follow the standard as published.** Don't add dots of
your own to *tsh* or *dzh*. Your output would differ from every other
conforming implementation's, and nobody reading it could know which rule
you had applied.

**When reading back, take the reading Georgian words have.** Read *tsh*
as `თ` then `შ`, and *dzh* as `დ` then `ჟ`. Every noun with `-ში` then
comes back right. The cost is the borrowed names: *altshaimeri* comes
back as `ალთშაიმერი`, not `ალცჰაიმერი`. That is a real loss, and we think
it is the right one to accept. A wrong Alzheimer is one name in a text;
a wrong `-ში` is every other sentence.

**Let a person settle it with a dot.** A reader that skips the middle
dot wherever it stands can be told what was meant: *alts·haimeri* reads
back as `ალცჰაიმერი`. That gives an editor a way to put right the few
names that matter without changing any rule.

**Keep the Georgian if you have it.** A romanisation is for exchange and
for people who cannot read the script. Where the original spelling
exists, store it, and treat the Latin form as derived.

**For finding, none of this matters.** If you match on
[a folded key]({{< relref "/articles/2026/10/2026-10-12-transliterate-for-display-fold-for-finding.md" >}})
and not on the reconstructed script, both readings share a key, and
*altshaimeri* still finds `ალცჰაიმერი`.

This is what [tetrak-translit](https://scattercode.github.io/tetrak-translit/)
does from version 4.5.0:

```python
from tetrak_translit import to_script, transliterate

transliterate("საათში", "ka/iso_9984")       # 'saatshi'
to_script("saatshi", "ka/iso_9984")           # 'საათში'

transliterate("ალცჰაიმერი", "ka/iso_9984")   # 'altshaimeri'
to_script("altshaimeri", "ka/iso_9984")       # 'ალთშაიმერი', not the original
to_script("alts·haimeri", "ka/iso_9984")      # 'ალცჰაიმერი'
```

## When the correction comes

Each sequence needs a dot in only one of its two pairs, and the next
revision of ISO 9984 will have to choose which. We hope it dots
the borrowed names (*ts·h*, *dz·h*): ordinary text then stays exactly as
the national system writes it, and the rule above for reading back remains
correct.

If it dots the common pair instead, so that `საათში` is written
*saat·shi*, an undotted *tsh* will from then on mean `ც` then `ჰ`, and
the default has to flip. Text written under the 2026 edition will still
be ambiguous, and nothing in the text says which edition wrote it. If
you keep romanised Georgian for the long term, record the edition of the
standard it was made under, beside the data.

## Further reading

- International Organization for Standardization, *ISO 9984:2026,
  Information and documentation — Transliteration of Georgian characters
  into Latin characters*, second edition, January 2026.
  [iso.org](https://www.iso.org/standard/87131.html). The standard this
  article is about. It replaced ISO 9984:1996; the middle dot and the
  list of pairs that take it are in clause 4.2.
- UNGEGN Working Group on Romanization Systems, *Report on the Current
  Status of United Nations Romanization Systems for Geographical Names*,
  version 4.1, December 2018,
  ["Georgian"](https://arhiiv.eki.ee/wgrs/rom2_ka.htm). The history of
  the national system the 2026 edition is built on: adopted in February
  2002 by Georgia's State Department of Geodesy and Cartography and the
  Institute of Linguistics, and approved by presidential decree in 2011.
- BGN/PCGN,
  [Romanization of Georgian](https://assets.publishing.service.gov.uk/media/67990616636f8db3c2707143/ROMANIZATION_OF_GEORGIAN_Jan_25.pdf)
  (Georgia 2011 national system; BGN/PCGN 2009 Agreement). The same
  system as the UK and US geographic names boards publish it, free to
  read, with the letter pairs that the standard's dot exists to keep
  apart.
- George Hewitt, *Georgian: A Structural Reference Grammar*, London
  Oriental and African Language Library, John Benjamins, 1995.
  [doi:10.1075/loall.2](https://doi.org/10.1075/loall.2). A reference
  grammar of the language, for the postpositions that are written as
  part of their noun, `-ში` among them.
- The Unicode Consortium, *The Unicode Standard, Version 18.0*, code
  chart
  [C1 Controls and Latin-1 Supplement](https://www.unicode.org/Public/18.0.0/charts/PDF/U0080.pdf).
  U+00B7 MIDDLE DOT, the character the standard uses as its separator.
  The chart also lists it as the Georgian comma, which is worth knowing
  before searching old text for it.
- [tetrak-translit's scheme documentation](https://scattercode.github.io/tetrak-translit/schemes.html),
  which says how the library writes and reads each edition of ISO 9984,
  and what it does with *tsh* and *dzh*.
