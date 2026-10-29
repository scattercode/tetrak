---
title: "Transliteration and cross-script search"
kicker: "Open source"
standfirst: "A small library that tells you which script a text is in, writes it in Latin letters by a named library standard, and reduces every spelling of a name to one form, so that one search finds them all."
description: "tetrak-translit: open-source detection, transliteration and search folding for Armenian, Georgian, Russian and Syriac, with ALA-LC, ISO and national romanisation schemes. MIT licensed."
---

## What it is for

A library catalogue with Armenian, Georgian, Russian or Syriac material
records the same name several ways: in its own script, and in two or five
Latin spellings depending on who catalogued it and which standard they
followed. Armenia's national poet is Tumanyan, Tumanean, Toumanyan and
Tumanian on four book covers, and all four are correct. No stock search
engine treats them as one word, so a reader who types one spelling misses
the records filed under the others.

`tetrak-translit` solves that in two directions. For readers, it writes a
name in Latin letters exactly as a library standard prescribes. For search,
it folds every spelling, Latin or script, to one key, so that an index built
with it finds a record however the name was typed.

## Who it is for

Catalogue and discovery systems that hold material in these scripts (Koha,
Solr and Elasticsearch analysis chains, aggregators); digitisation projects
that want a romanised field beside the original; and anyone who has to
convert between a script and its romanisations without guessing. It is a
dependency-free Python library with a command-line tool, so it fits into a
pipeline or a spreadsheet job as easily as into a search engine.

## What it does today

Three jobs, in plain words:

1. **Detection.** Which script a string is in, and some things about how it
   is written: for Armenian, whether it uses the classical spelling (printed
   before the 1922 reform, and still used in the diaspora) or the reformed
   one; for Russian, whether it is pre-1918 spelling; for Syriac, whether it
   carries vowel points.
2. **Transliteration**, between a script and its named Latin schemes. Each
   scheme is a tested table written from its published standard, and the
   library says which ones can be reversed exactly and refuses to guess at
   the ones that cannot.
3. **The fold.** One function that maps any spelling, in the script or in
   any scheme, to a single search key, so that the index and the query agree.
   The key is deliberately coarse and never shown to a reader.

| Script | Schemes |
|---|---|
| Armenian | ALA-LC; ISO 9985 (the 2026 edition, and the 1996 one for older data); BGN/PCGN; Hübschmann-Meillet; Western Armenian pronunciation |
| Georgian | ALA-LC; ISO 9984 (2026, and 1996); the Georgian national system |
| Russian | ALA-LC, including the pre-1918 letters; BGN/PCGN |
| Syriac | ALA-LC, rendering vowels only where the text has them |

Syriac is the newest and the most limited: the script is normally written
without vowels, so the fold works on consonants alone. The
[article on searching Syriac]({{< relref "/articles/2026/10/2026-10-28-searching-syriac.md" >}})
explains what that buys and what it costs. The current list of schemes,
with every letter of every table, is in the
[documentation](https://scattercode.github.io/tetrak-translit/schemes.html).

## What it does not do yet

- **Translate.** Transliteration is the same words in different letters.
- **Supply vowels** for unpointed Syriac. The library renders what is
  written and folds on the consonants.
- **Reverse a lossy scheme.** Where a standard maps two letters to one, the
  library says so rather than guessing.
- **Fold every popular spelling.** Spellings that came through another
  language (*Khachaturian* via Russian, *Edessa* via Greek) or that insert
  an unwritten vowel do not fold to the script. The published test sets are
  the claim: what is not in them is not promised.
- **Every script.** Four so far. Adding one is a package of tables, and the
  documentation explains how.

## Get it

```bash
pip install tetrak-translit
```

```python
import tetrak_translit as tt

tt.transliterate("Երևան", "ala_lc")       # 'Erevan'
tt.transliterate("Երևան", "bgn_pcgn")     # 'Yerevan'
tt.fold("Yerevan", script="hy") == tt.fold("Երեւան")   # True
```

| | |
|---|---|
| Code | [github.com/scattercode/tetrak-translit](https://github.com/scattercode/tetrak-translit) |
| Package | [tetrak-translit on PyPI](https://pypi.org/project/tetrak-translit/) |
| Documentation | [scattercode.github.io/tetrak-translit](https://scattercode.github.io/tetrak-translit/) |
| Licence | MIT |

## Articles about it

- [Searching Syriac, a script that leaves out its vowels]({{< relref "/articles/2026/10/2026-10-28-searching-syriac.md" >}}):
  the consonantal fold, and where we would welcome help.
- [Measuring the fold, release by release]({{< relref "/articles/2026/10/2026-10-19-measuring-the-fold.md" >}}):
  how the Armenian fold is tested against a real catalogue on every release.
- [Transliterate for display, fold for finding]({{< relref "/articles/2026/10/2026-10-12-transliterate-for-display-fold-for-finding.md" >}}):
  why a transliteration is for the reader and never for the index.
- [What changed in ISO 9984 and ISO 9985 in 2026]({{< relref "/articles/2026/10/2026-10-12-what-changed-in-iso-9984-and-iso-9985.md" >}}):
  the new editions of the standards, and the apostrophe that moved.
- [Telling classical from reformed Armenian by counting one letter]({{< relref "/articles/2026/10/2026-10-11-classical-or-reformed-armenian-by-one-letter.md" >}}):
  the orthography detector.
