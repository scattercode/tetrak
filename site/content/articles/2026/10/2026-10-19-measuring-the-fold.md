---
title: "Measuring the fold, release by release"
date: 2026-10-19
draft: false
slug: "measuring-the-fold-release-by-release"
kicker: "Method"
standfirst: "A search fold is a claim about which spelling differences do not matter, and a library catalogue is where that claim gets tested. We run our Armenian fold against a real catalogue on every release, chart its whole history, and let a continuous integration check fail on the loss of a single record"
author: stephen-masters
tags: [armenian, search, transliteration, evaluation, project-notes]
---

> Count what is countable, measure what is measurable, and what is not
> measurable, make measurable.
>
> — Galileo's method, in the words of Thomas-Henri Martin (1868)

A few minutes after midnight on Monday 19 October we released
tetrak-translit 3.5.0, and one of its changes was a correction we had
implemented based on a detailed review of the code. Armenian's 1922
spelling reform turned a
word-initial `յ` before a vowel into `հ`, so classical `յեղափոխական`
(*revolutionary*) became reformed `հեղափոխական`, and our fold had been
keeping the two apart. From 3.5.0 they folded to the same key. The change
came with test cases, the published fold set passed, and the gap it
left was written into the documentation: a Latin *ye* at the start of a
word might be classical `յե` or a plain `ե`, as in *Yerevan*. We shipped
it and went to bed.

We have a job that runs in GitHub Actions that measures the
effectiveness of the fold against a catalog of titles. As it does
against every release, it ran and on this occasion, found that two
titles had been lost. The catalogue's own ALA-LC rendering of
`յեղափոխական`, *Yeghapʻokhakani*,
folded to a key beginning *e*, as the *Yerevan* rule says it
should, while the Armenian script itself now folded to one beginning
*he*. The **[tetrak-translit](https://github.com/scattercode/tetrak-translit)** library's tests were right about what the rule
did. The catalogue was the test the library did not have, and it
showed the cost of the declared gap: two titles in every scheme,
out of five hundred. We filed the
issue before nine and released 4.0.0 before ten, a breaking change that
puts initial `հե`, `յե` and `ե` on one key and declares the over-merge
that is our compromise. The measure ran again, and the two titles were
back.

That morning is what this article is about. In
[*Transliterate for display, fold for finding*]({{< relref "/articles/2026/10/2026-10-12-transliterate-for-display-fold-for-finding.md" >}})
we explained what a fold is and why a search needs one. It left open
how you know a fold is any good, and how you keep it good as it
changes. Our answer has three parts: a measure that asks a real
catalogue, a history that runs the measure through every release the
library has ever had, and a continuous integration check that refuses
a change which loses a single record.

## Ask the catalogue

The fold's job is to make a search typed one way find a record written
another. So the measure asks exactly that, of a real catalogue.

The catalogue is the [Armenian Institute](https://armenianinstitute.org.uk/)'s, a Koha catalogue we work
with, and a thousand of its records are in the measure. Like most
catalogues of Armenian material it records many works twice: romanised
under ALA-LC in the main fields, and in Armenian script in a linked
MARC 880 field. Every record with a script creator or a script title is
a target: the name cut to its Armenian words, or the title proper, four
words at most, as a reader would type it.

From each script value the measure makes the queries a reader might
type: the script itself; its rendering in each of the five Armenian
schemes the library carries (ALA-LC, ISO 9985, BGN/PCGN,
Hübschmann-Meillet and the Western pronunciation spelling); and a sixth
we call *plain*, which is ALA-LC with its diacritics and apostrophes
stripped, because that is what ALA-LC looks like typed on an ordinary
keyboard. Seven queries per target, over nine hundred targets.

Each query then runs four ways:

- **Stock.** The query against the text fields alone, with Solr's
  standard analysis. This is a catalogue without a fold, and the
  baseline for everything else.
- **Fold.** The search as our prototype runs it: the reader's text
  against the text fields, the folded query against the fold fields,
  and a fold match ranked higher. This is what the fold is worth to a
  reader.
- **Fuzzy.** The fold search with a third clause that allows each
  folded word an edit or two. It is there to catch a near miss, and it
  is not the subject here.
- **Key.** No index at all. Does the query fold to exactly the key of
  the script value it was rendered from?

A search finds its target if the record is in the first hundred
results. Rank is reported too, because a wider search can find more
and rank it worse, and presence alone would hide that.

### Why the fourth

The first three are what a reader experiences. The fourth isolates the
fold, and it exists because of how the catalogue was made.

The cataloguers romanised most works under ALA-LC, so an ALA-LC query
can find its record by matching the cataloguer's own romanisation even
when the fold has failed to link it to the script. The search-level
figures flatter the fold on this catalogue, and they say nothing about
a source that holds the script alone, which some of the archives we
care about do. The key measure takes the cataloguer's romanisation out
of the picture. It asks only whether the fold brings romanisation and
script to the same place, and that is something a fold release
can change – deliberately or accidentally.

The stock figures say why any of this matters. On this catalogue, a
title typed in the Western spelling most of the diaspora uses for its
own names finds its record about twice in a hundred without the fold.
ISO 9985 and Hübschmann-Meillet, with their diacritics, do little
better. ALA-LC does best, because it is what the cataloguers typed, and
it still misses whenever an apostrophe or a diacritic differs. With the
fold, every scheme finds the record ninety-nine or a hundred times in a
hundred, and a name query returns a median of three records rather than
one.

## A history of tetrak-translit releases

The key measure needs no index. It is a pure function of the library,
so it can be taken for any release of the library without re-indexing
anything. We wrote a script that does exactly that: the same
targets, the same queries, and every release of tetrak-translit that
PyPI has ever carried, folding the lot with each one in turn. Each
release gets an environment of its own, built by uv, and a worker that
prints counts and nothing else. Once the packages are cached, the whole
history takes a few seconds.

{{< figure-themed src="articles/fold-key-agreement" alt="A line chart of the share of romanised queries that fold to the key of the Armenian-script value they were rendered from, for creators and for titles, at each tetrak-translit release from 0.1.0 to 4.0.0. Creators start at ninety-six per cent and reach a hundred at 3.3.0. Titles start at eighty-two per cent, rise in steps at 3.0.2, 3.1.0, 3.2.0, 3.3.0 and 3.4.0, dip at 3.5.0 and finish just short of a hundred at 4.0.0." caption="Mean key agreement over the six romanisations, for creators and for titles, by release. Every step is a round of defects the measure sent back to the library, and 3.5.0 is the first release to fall." >}}

Two things about how the chart is made matter for reading it.

**The queries are fixed and the library varies.** The queries are
rendered once, by the installed release, and every release folds the
same renderings, so what moves between releases is the fold alone.
Rendering each release's queries with its own tables would mix two
kinds of change: the fold improving, and the transliteration tables
following new editions of the standards. Two major versions did the
latter and nothing else. Version 2.0.0 followed ISO 9985:2026, which
[replaced the 1996 edition in January]({{< relref "/articles/2026/10/2026-10-12-what-changed-in-iso-9984-and-iso-9985.md" >}}),
and 3.0.0 followed ALA-LC's 2022 table. Both sit flat on the chart,
which is exactly what the display-and-finding split intends: a
transliteration table may follow its standard, and a fold key must not
move as a result of that table changing.

**An earlier row can move when a later rendering changes.** The 3.3.0
row's ISO 9985 figure is one title lower than 3.3.0 measured on its own
day, because 3.4.0 changed how a question mark set inside the `ու`
digraph is rendered, and 3.3.0's fold does not take the new form. That
is a known cost of fixing the queries, and a small one. Otherwise the
reconstruction agrees with the figures we wrote down by hand at the
time.

### Reading the steps

Each step on the chart is a release, and each release is a round of
defects the measure found and sent back to the library with its cases.
Creators were high before any fix, because names rarely carry the
letters the early defects concerned; titles carry all of them.

| Release | What the measure had found | What the fold learned |
|---|---|---|
| 3.0.2 | Classical `իւ` romanised `iw` missed the script | Latin `iw` folds as the script's `իւ` does |
| 3.1.0 | ISO 9985 and Hübschmann-Meillet write `ձ` as `j`, which ALA-LC uses for `ջ` | `j` read as `ձ` when a mark elsewhere in the word shows the scheme |
| 3.2.0 | BGN/PCGN writes `ը` as `y`, which every other scheme reads as a glide | A `y` in that position folds with the other schemes' vowel |
| 3.3.0 | `hay` inside a compound, the `Ḥ.` of an initial, and the Western `ivo` glide | Three rules, and every creator in every scheme now reaches its key |
| 3.4.0 | `ye` after a cataloguer's bracket, the article after classical `իւ`, and intonation marks set inside a word | Three narrow rules, one of them undoing a loss 3.3.0 had caused |
| 3.5.0 | Nothing: a review release | Classical `յե` read as `հե`; two titles lost |
| 4.0.0 | The two titles | A Latin initial `he` read as that `յե` |

Two of these show the measure doing more than just counting.

**3.1.0 is a fix a fold can only make with evidence in hand.** ISO 9985
and Hübschmann-Meillet use `j` for `ձ`; ALA-LC and BGN/PCGN use it for
`ջ`. The letter alone cannot tell you which, but the rest of the word
can: if it carries a mark that only ISO 9985 or Hübschmann-Meillet
writes, the `j` is theirs. A lone *Jayn*, with no such mark, still
folds the ALA-LC way, and that residue is a declared gap with a test
asserting it still misses. The measure says what it costs: two or three
titles in those two schemes, and nothing anywhere else.

**3.3.0 shows the measure pricing an over-merge.** Western Armenian
writes the glide it says in *-իոս* names: *Virkilivos* for
`Վիրգիլիոս`. Reading *ivo* as *io* catches that, and it also drops a
real *v* from *Livorno* and from its Armenian spelling `Լիվոռնո`, so
the port's key would take in anything else that folds the same way.
We document that as a declared over-merge, with the measure's
answer beside it: the rule freed a scheme that had been stuck for a
week, and the catalogue has no second *liorno* for it to confuse. A
fold is a claim about what does not matter, and this is what pricing
such a claim looks like.

The same release also lost a title, through a rule for the silent `յ`
of classical *hay* that happened to catch BGN/PCGN's *y* for `ը` in a
shape no test case had: *tʻiwy* for `թիւը`. No test in the library saw
it. The measure saw it the same evening, and 3.4.0 restored it with a
rule narrow enough to catch nothing else.

## Two kinds of test

It would be easy to read all this as the library having weak tests and
the catalogue making up for them. That is not what is going on.

The library's tests are its documented claims. The largest is a
published file of fold cases, nearly three hundred now, in groups:
every spelling in a group must fold to one key, in both scripts, both
orthographies and every scheme, and the first spelling of every group
must fold to a different key from every other group's, because a fold
that mapped everything to one key would otherwise pass. Every script
form in the file is rendered through every scheme and the rendering
folded back, to check it reaches the key the script does. The declared
gaps are tests asserting that a spelling does *not* fold with its name,
so that a change which closes one is noticed; the declared over-merges
assert that two different words *do* share a key, for the same reason
in reverse. And since 3.5.0 every example in the documentation is a
doctest.

Every one of those tests passed on 3.5.0, and 3.5.0 lost two titles.
The gap that lost them was documented, with a test. What the tests
could not say was what the gap cost, because a test case is a spelling
somebody thought of, and the two titles were spellings a cataloguer had
typed. A unit test says what a rule does, but to determine the true
value of a rule requires measuring against a real catalogue.
The library's tests say the fold does what we claim;
the measure says whether what we claim is enough, and it is the measure
that decides whether a declared gap should stay.

That division of labour also settles where the cases come from. Almost
every group added to the library's file since its first release arrived
from the measure: a defect found on the catalogue, reduced to the
spellings that show it, filed against the library with those spellings
as the test, and fixed by the smallest rule that passes them. The file
tripled that way in nine days, and it is the better for having been
written from a catalogue rather than from our assumptions.

## The floor beneath the merge

A measure run by hand after each release catches a regression the next
morning. We wanted one that catches it before the merge. That is a
different problem, because the measure needs a running Solr and a
harvest of the catalogue, and a continuous integration job has neither.

So the job builds a small index of its own. A few dozen of the
catalogue's records are committed as raw MARC, with the Institute's
permission, alongside a hundred records from a public aggregator to
compete with them. The real mappers map them, the real indexer loads
them into a Solr the job starts, and the real measure runs over them.
The fold and key counts are compared with a baseline file in the
repository, and if any count falls below it by one record, the job
fails. A rise is printed as an improvement, and the baseline is
rewritten only on purpose, with a flag. If the number of targets
changes, the job refuses to compare at all and asks for a new baseline.

The job runs on every push and every pull request, and one kind of pull
request is the reason it exists. Dependabot opens one each week for
every dependency with a new release, tetrak-translit among them, and
the findability job runs on it like any other. A fold release that
loses a record on the committed sample cannot be merged without
somebody looking at why.

We should be honest about what it catches. The sample is a couple of
dozen targets, and the two titles 3.5.0 lost were not in it: the
baseline was regenerated on the upgrade with no count moved, and the
loss was found by the full measure over the whole catalogue. The check
is not a substitute for that measure. It is the floor under it: no
change to the index, the mappers, the query or the library can take
away anything the sample finds today without a failing check saying so.
The full measure is the ceiling, run after every release of the library
and every change to the search. One leaves a green tick; the other
leaves a dated row in the history.

## Keys are data

One more thing the measure made plain, and it is a rule about releases
rather than about tests.

A fold key is stored. It sits in the index beside the record, and in
anything else built by folding: [our name authority]({{< relref "/services.md#catalogue-search" >}}), a snapshot of
Wikidata keyed by the same fold, stores every name's key beside the
name. When a release changes a key, every stored copy is wrong until it
is rebuilt. So the library treats a moved key as a change to a public
interface, and the version number says what kind. A rule that only
changes keys for spellings the published cases did not cover is a
minor release, and its notes say an index built with an earlier
version must be rebuilt. A rule that moves the key of an existing
case is a major release. 1.0.0 was the day *Hovhannes* lost its
initial *h* in the key, so that the Russian-mediated *Ovanes* could
find it; 4.0.0 was the morning above,
when every key beginning *he* moved. Dependants pin the major version
and rebuild when they take a new one, and the name authority records
the fold's version in its snapshot so that our indexer can refuse one
keyed by another release. The measure makes a key change visible as it
happens; the versioning makes it safe to ship.

## What we would tell another project

Little of this is specific to Armenian, or to transliteration.

- **Measure how you use it; on real data.** Unit tests tell us what a
  fold does; only a catalogue tells us what that is worth. Write the
  measure early, because every later decision will benefit from it.
- **Have a measure that isolates the component.** Search-level numbers
  are what a reader experiences and the ones to publish, but a
  catalogue with its own romanisations flatters the fold. The key
  measure, with no index, is the one a release can change, and the one
  you can take for any release.
- **Fix the queries and vary the library.** That is what lets a history
  stay relevant. Render once with the current release; fold with every
  release; give each release its own interpreter.
- **Send defects back as cases, not patches.** The library's test file
  is better for having been written from the catalogue, and the next
  catalogue gets the fix.
- **Declare what you do not do, and price it.** A documented gap with a
  test is a claim; the measure says whether the claim is affordable.
  3.5.0's was not.
- **Put a floor in continuous integration, and say where it is.** A
  small committed sample held to a baseline that fails on one record
  catches the breakage a dependency bump would otherwise merge. It will
  not catch everything, so say what it covers and keep running the full
  measure.
- **Treat a moved key as an interface change.** Keys live in indexes
  you do not control. Version accordingly, and have dependants check
  the version they were built with.

## Further reading

### Evaluating retrieval

- Christopher D. Manning, Prabhakar Raghavan and Hinrich Schütze,
  *Introduction to Information Retrieval*, Cambridge University Press,
  2008, chapter 8,
  ["Evaluation in information retrieval"](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-in-information-retrieval-1.html).
  The textbook account of test collections, relevance judgements, and
  the measures this article uses, including the mean reciprocal rank.
- Mark Sanderson, "Test Collection Based Evaluation of Information
  Retrieval Systems", *Foundations and Trends in Information Retrieval*
  4(4), 2010, pp. 247–375.
  [doi:10.1561/1500000009](https://doi.org/10.1561/1500000009). A
  survey of the test-collection method from Cranfield on: how
  collections are built, what they can and cannot show, and how stable
  their conclusions are. Our measure is a small test collection whose
  relevance judgements come free, since each query is made from the
  record it must find.
- Ellen M. Voorhees, "The Philosophy of Information Retrieval
  Evaluation", in *Evaluation of Cross-Language Information Retrieval
  Systems*, Lecture Notes in Computer Science 2406, Springer, 2002,
  pp. 355–370.
  [doi:10.1007/3-540-45691-0_34](https://doi.org/10.1007/3-540-45691-0_34).
  Why comparative evaluation on a fixed collection is sound even when
  absolute figures are not, which is the footing the release-by-release
  chart stands on.
- Chris Buckley and Ellen M. Voorhees, "Evaluating evaluation measure
  stability", *Proceedings of the 23rd Annual International ACM SIGIR
  Conference*, 2000, pp. 33–40.
  [doi:10.1145/345508.345543](https://doi.org/10.1145/345508.345543).
  How many queries a collection needs before a small difference between
  two systems can be trusted. The reason our continuous integration
  sample is a floor and not a measure.
- Cyril Cleverdon, "The Cranfield tests on index language devices",
  *Aslib Proceedings* 19(6), 1967, pp. 173–194.
  [doi:10.1108/eb050097](https://doi.org/10.1108/eb050097). The
  experiments that established evaluation by test collection, and a
  reminder that the question of which equivalences an index should
  make is as old as indexing.

### Regression testing and versioning

- Michael C. Feathers, *Working Effectively with Legacy Code*, Prentice
  Hall, 2004, chapter 13. The source of the *characterisation test*: a
  test that records what the code does today so that a change which
  alters it is noticed, which is what the findability baseline is.
- Tom Preston-Werner, [*Semantic Versioning 2.0.0*](https://semver.org/spec/v2.0.0.html).
  The convention under which a moved fold key is a breaking change and
  gets a major version.

### The pieces

- Library of Congress, [*MARC 21 Format for Bibliographic Data*, field 880](https://www.loc.gov/marc/bibliographic/bd880.html),
  "Alternate Graphic Representation". Where the Armenian script sits in
  a catalogue that romanises its main fields, and therefore where the
  measure's targets come from.
- Apache Solr, *Solr Reference Guide*,
  [The Extended DisMax Query Parser](https://solr.apache.org/guide/solr/latest/query-guide/edismax-query-parser.html)
  and [The Standard Query Parser](https://solr.apache.org/guide/solr/latest/query-guide/standard-query-parser.html).
  The `qf` and `mm` parameters the fold and text clauses are built
  with, and the fuzzy search the near-miss clause uses.
- Astral, *uv* documentation,
  [Running scripts](https://docs.astral.sh/uv/guides/scripts/). The
  `--with` option that gives each release of the library an environment
  of its own in the history script.
- Python Software Foundation, [`doctest`](https://docs.python.org/3/library/doctest.html).
  How the library's documentation examples became tests.
