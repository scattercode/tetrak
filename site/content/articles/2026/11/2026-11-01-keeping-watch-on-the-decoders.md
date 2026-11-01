---
title: "Keeping watch on the decoders"
date: 2026-11-01
draft: false
slug: "keeping-watch-on-the-decoders"
kicker: "Security"
standfirst: "Eight libraries decode every scan we read, and in 2026 the flaws found in software like them more than doubled. Two people cannot read that stream by hand. This is how we turn it into a weekly issue, a bucket, a test and a published record, with a model doing the first reading, a person deciding, and nothing transcribed by hand"
author: stephen-masters
tags: [security, advisories, sillybos, automation, project-notes]
---

A digitisation pipeline rests on a short list of libraries it did not
write: Pillow, libtiff, libpng, libjpeg-turbo, zlib, OpenJPEG, FreeType and
poppler. Between them they publish a security advisory most weeks, and in
a bad month, as October 2026 was, several dozen. Each one arrives as a
paragraph of text and a severity score, and poses the same question to
everyone who runs the library: *does this reach me, and what do I do about
it?*

The stream is getting faster. The count of published vulnerabilities in
2026 more than doubled on the year before, and the finding is now partly
automated: records that credit an AI finder went from a few dozen in the
whole of 2025 to several hundred by October, and the labs doing the
finding say openly that human triage, not discovery, is what limits the
rate. We wrote about the month that made this concrete for us, and what we
built in response, in [Read the tag before you unroll the scroll]({{<
relref "/articles/2026/11/2026-11-01-read-the-tag-before-you-unroll-the-scroll.md"
>}}). This article is about the other half: how a project with two people
on it keeps up with a stream that is sized for a security team.

The usual tools do not answer it. A dependency scanner tells you that a
version you install has an advisory against it; it cannot tell you
whether the flaw is in a command-line tool you never run, a save path you
never take, or the reader a scanned page goes through every time. For a
long while our answer was to read each advisory when we noticed it, decide
in our heads, and upgrade. The decisions were not written down, so when
the next advisory in the same corner of libtiff arrived, the reading
started again from nothing.

This article is about what we built instead, in the course of building
[sillybos]({{< relref "/sillybos.md" >}}), the check that runs before any
decoder opens a file. The pieces are small. What matters is the shape:
machines fetch and file, a person decides, and every decision becomes
either a test or a sentence that says why there cannot be one.

## The stream

A job runs every Monday morning. It asks OSV, the open-source
vulnerability database, for everything published against a watchlist:
the Pillow package on PyPI, and the libtiff, libpng, libjpeg-turbo, zlib,
poppler, OpenJPEG and FreeType packages as Debian tracks them. Debian is
on the list because it is the one source that follows the C libraries
under Pillow and poppler as carefully as PyPI follows Python.

The raw stream is noisy in predictable ways, and the job cleans it. Debian
publishes its own bulletins that repeat each CVE with a release note
attached; those are dropped. Pillow's advisories arrive three times, as a
GitHub advisory, a PYSEC entry and a Debian record, and are merged into
one, keyed by the CVE. A CVE that has been reserved but has no text yet is
held as pending and checked again next week. And everything already seen
is dropped: every key in a committed baseline file, and every identifier
named in a hidden marker at the top of an existing issue.

What survives becomes one GitHub issue per advisory, from a fixed
template, with the label `advisory`. The issues are the record of what has
been seen. The job commits nothing, which keeps its permissions to reading
the repository and writing issues, and spares the main branch a bot commit
a week.

## The filters label; they never drop

Three mechanical filters look at each new advisory before a person does,
and add a second label, `likely-not-reached`, when they fire. One looks
for a path under `tools/` or `contrib/`, where libtiff keeps its
command-line programs, which no library call runs. One looks in the
headline alone for the verbs of the write path: *save*, *encode*, *write*,
*append*. One looks for the names of Pillow modules that `Image.open`
never touches: the font renderer, the drawing API, the viewer.

The rule for these filters is the one rule in the whole system we would
defend hardest: they label, and they never drop. The words filter reads
only the headline because a long write-up of a read-path flaw mentions
"writes" somewhere, and a label that nearly every advisory carries says
nothing. "Out-of-bounds write" is blanked out before the search, because
it describes a memory fault and not the save path. Even so, the filters
are wrong sometimes, in both directions, and the issue body lists what
matched so that the person reading it can overrule the label in a glance.
The point of a filter is to let the reader start with the likely-irrelevant
ones, not to let them skip anything.

## A person, and seven buckets

Someone reads each issue. The reading answers one question, *is this
reached by opening a file?*, and files the advisory in a bucket. The
buckets are the vocabulary of the whole system, so here they are.

| Bucket | Meaning | What follows |
|---|---|---|
| **A** | Already refused by an existing check: a format outside the four, a coding the policy refuses, a size over a limit | Name the check, and close |
| **B** | Preventable from a header field our readers can see: a marker, a tag, a chunk, a count, a dimension | A policy field and a hostile corpus case, then close when it ships |
| **B2** | Preventable only by a coarse policy on a PDF's contents, such as a JBIG2 stream or an embedded font | The same as B, through the PDF path, and the policy is admitted to be coarse |
| **C** | Needs decoding to detect: a flaw in the pixel data, the entropy-coded segment, the font program | Out of reach by design; say so, and close. Updating the decoder is the fix |
| **D** | Reaches `pdfinfo` itself | Check that the check still fails closed, and close |
| **N** | Not reached by opening a file: a command-line tool, a save path, a drawing API | Close |
| **U** | A reserved CVE with no text yet | Stays pending; the job re-checks it weekly |

The honest buckets are C and N, and they are the majority. Most advisories
against a decoder are in code a scan never runs, or in the decoding
itself, where nothing read from the outside can help. Writing that down
is as valuable as the refusals: the next time a flaw lands in libtiff's
PixarLog codec, the record already says that a scan never needs PixarLog
and the policy refuses it, and nobody re-reads the codec.

## Where the model comes in

Two people cannot read a hundred advisories a month with the care the
buckets demand, and we do not pretend to. The reading is done with a
model, and the way it is done matters more than the fact of it.

The triage is a written procedure, kept as a skill that Claude follows in
a session: four questions, in order, with the commands to answer each.
*Do we use it?* is answered by searching every lock file, every
`pyproject.toml` and every Dockerfile across our repositories, because a
package can hide behind an OCR engine's extras or inside a base image
that no lock file lists. *Does the flaw reach us?* is answered against a
threat model that lists every door through which something from outside
can arrive, with the file that proves a feature unused where that is the
answer. *Is there a fix?* and *where must it be fixed?* follow, with the
four places a fix can need to land: the lock file, the running images,
the laptops, the packages we publish. Urgency is expressed in our own
terms, a table whose rows are how the trigger reaches us and whose columns
are what the flaw does, so that "a harvested record can carry it and it
runs code" means *today* and "only something run by hand on a laptop, and
it crashes" means *this week*. Every answer, including "not affected", is
logged.

The model does the reading and the searching, and proposes. A person
decides. That is not modesty about the model, whose reading is usually
right; it is the rule that keeps the record honest, because a bucket is a
claim about our code, and the claim's author has to be someone who can be
asked why. When the record was started, the backfill of a hundred or so
advisories was re-read by the model in an evening, and every one of them
is marked as a proposal until a person has read it and promoted it, as
the next section describes. The design for the weekly stream is the same
shape: a model will read each new issue as it is opened and post a
*proposed* bucket and finding as a comment, for the maintainer to confirm
or overrule. It will post a comment and never file a bucket or close an
issue; it will read the advisory's text as data and not as instructions;
and nothing from private notes will go into a comment, since the issues
are public. That step is designed and not yet built, and the guide says
so rather than describing it as if it were.

This is what lets a small project be responsive. The machine fetches,
filters and files on Monday morning; the model has read and proposed by
the time a person sits down; the person's job is to confirm, overrule,
and write the test. The time that used to go into finding and reading
goes into the one part that needs a human, and the record of what was
decided is public, cited and checked by the test suite rather than kept
in anyone's head.

## A B finding becomes a test, never a quiet change

Bucket B is where the work is, and it has a rule attached. A finding that
could be prevented from a header field becomes a **policy field plus a
hostile corpus case, and never a silent change of a default**.

That means: a field on the policy object, with a default and a stricter
preset value; a command-line option; a row in the policy table that names
the advisory; a case in the test corpus that builds the triggering file
from bytes, with nothing hostile checked in; and a test that the check
refuses it with a reason an operator can act on. Where our reader must
agree with the real decoder, a further test opens a real file with Pillow
and compares.

The reason is a release rule. Every default refusal is a breaking change:
a file that passed last week and is refused this week is a change the
operator must be able to see in the changelog, name in the policy, and
turn off. A tweak to a constant gives them none of that. So a field whose
default refuses the file ships as a breaking release, and one that merely
lets the operator refuse it ships as a feature. sillybos went from 1.0 to
4.0 in its first day largely because of this rule, and we think that is
the rule working, not failing.

## The record, and the tests that enforce it

Each triaged advisory ends as one JSON file in the repository: the facts
from the advisory, how the triggering input reaches the flaw, the bucket
and the finding, which check refuses it and under which policy, the tests
that prove that, and how to protect yourself with the library and
without it. The first line of every "how to protect yourself" entry is the
fixed version. Nothing here is a substitute for upgrading.

The field that makes the record worth trusting is the list of tests. A
record in bucket A, B or B2 claims that a file is refused, and the claim
must name at least one test, by its full path, that builds the file and
proves the refusal. The test suite reads every record and checks that the
tests it names exist. A record can therefore not claim more than the code
does, and a refactor that drops a test breaks the build rather than
leaving a stale claim in a security page.

A script merges the files into one and the suite keeps that merged file
current. The [security watch]({{< relref "/security/_index.md" >}}) on
this site is built from it at build time: a row per advisory, with the
bucket, the trigger, the refusal where there is one, and links to OSV and
the advisory database for everything else. The page is rebuilt every
Monday, two hours after the fetch, through a deploy hook, so a record
promoted on a Friday is on the site the next week with nobody having
edited a page.

Nothing on that page is typed by hand. We learned that rule elsewhere: a
slide deck that carried transcribed benchmark numbers disagreed with the
harness within a fortnight, and nothing failed, and nobody noticed until
the two were read side by side. A security page that drifts from its
record would be worse than no page. So the page reads the record, the
record names the tests, and the tests run.

## The backfill, and what a proposal is

When the record was started, there were already more than six hundred
advisories on the watchlist, triaged in our heads over the preceding
months. Their buckets had been decided but never written down. We drew a
line: everything published from 2025 onwards was re-read against the
current checks and written up, a hundred or so records; the older ones
stay in the baseline file as seen but unrecorded.

The re-reading was done with help from a model, and that raised a question
we had to answer carefully: what is a record that a machine drafted and no
person has confirmed? Our answer is a *proposal*. It has the same shape as
a record, sits in its own directory, says in its notes that it is not yet
confirmed, and is read by nothing except two commands. One lists what is
waiting, by bucket, with whatever is in the way of promoting it. The other
promotes a proposal, once a person has read the advisory and the finding
and agrees, into the record, dated that day. The export never includes a
proposal, so the security watch shows only what a maintainer has stood
behind.

Listing the proposals had an effect we did not plan. Ten of them claimed
refusals the library could not yet make, and the command said so: a
ceiling on a single image dimension, a policy on embedded fonts in a PDF,
a policy on JBIG2 streams. The backlog of confirmation became a list of
the next three policies. The first shipped the same evening.

## Keeping our own readers honest

The header readers are small, and small code is auditable, but a reader
that is handed a damaged file must still answer: a header, or a refusal,
and either within a bounded time. A script in the test suite takes the
well-formed files of the hostile corpus, damages them at random, and runs
every reader on the result; any exception that is not the reader's own
refusal, and any file that takes more than a few seconds, fails. It runs
for thirty seconds on every pull request and for ten minutes every Monday,
and in its first evening, at some millions of damaged files a minute, it
found nothing, which is the result we wanted and will keep checking.

Around all of this sit the ordinary repository checks: secret scanning
over the whole history, a linter for the workflows themselves, a scanner
for the container images and configuration, and automated dependency
updates. They are the same checks across all of our repositories, so one
repository's finding is a template for the next. They catch the things the
advisory record is not for.

## What it is not

It is not a vulnerability database. OSV and the GitHub Advisory Database
are, and every row links to them. It is not an automated triage: the
filters label and the person decides, and we would rather a slow Monday
than a confident wrong bucket. And it is not a claim that the check
prevents everything: a row says *refused by default* only where a test
builds the file and proves it, and most rows say, in plain words, that
nothing before the decoder can help.

What it is, is a way of answering the Monday question once, in writing,
with a test where a test is possible, so that the next person to ask it
reads the answer instead of the advisory.

## Further reading

### Handling advisories

- Anthropic, *Coordinated vulnerability disclosure dashboard*,
  [red.anthropic.com/2026/cvd](https://red.anthropic.com/2026/cvd/),
  figures as of 2 October 2026. Where the rate described in the opening
  comes from, and the statement that human triage is the limiting step;
  the same constraint our Monday is built around.
- Murugiah Souppaya and Karen Scarfone, *Guide to Enterprise Patch
  Management Planning: Preventive Maintenance for Technology*, NIST
  Special Publication 800-40 Revision 4, National Institute of Standards
  and Technology, April 2022,
  doi:[10.6028/NIST.SP.800-40r4](https://doi.org/10.6028/NIST.SP.800-40r4).
  The case for treating patching as routine maintenance with a written
  process rather than an emergency each time; our weekly fetch and the
  bucket vocabulary are that process at the scale of one pipeline.
- ISO/IEC, *ISO/IEC 29147:2018, Information technology — Security
  techniques — Vulnerability disclosure*, second edition, and *ISO/IEC
  30111:2019, Information technology — Security techniques — Vulnerability
  handling processes*, second edition. The two standards for, respectively,
  how a vulnerability is reported and disclosed and how a vendor handles
  one internally. We are on the receiving end of the first and have
  borrowed the shape of the second.

### The data

- OpenSSF Vulnerability Disclosures Working Group, *Open Source
  Vulnerability (OSV) schema*,
  [ossf.github.io/osv-schema](https://ossf.github.io/osv-schema/). The
  format every advisory arrives in: identifiers and aliases, affected
  ranges and fixed versions, severity vectors. The merging of a CVE's
  three records into one is done on the alias field this schema defines.
- OSV, [osv.dev](https://osv.dev/), and GitHub, [GitHub Advisory
  Database](https://github.com/advisories). The two sources the fetch
  reads and the security watch links to.

### Reading files safely

- Len Sassaman, Meredith L. Patterson, Sergey Bratus and Michael E.
  Locasto, "Security Applications of Formal Language Theory", *IEEE
  Systems Journal* 7(3), 2013, pp. 489–500,
  doi:[10.1109/JSYST.2012.2222000](https://doi.org/10.1109/JSYST.2012.2222000).
  Why the bucket between "preventable from the header" and "needs
  decoding" is a real boundary: a recogniser for the header is a small,
  specifiable language, and the pixel data is not.
- Pillow, [Security](https://pillow.readthedocs.io/en/stable/handbook/security.html),
  Pillow 13 documentation. The maintainers' own guidance, which the
  "protect yourself" entries of the record repeat before anything of ours.
