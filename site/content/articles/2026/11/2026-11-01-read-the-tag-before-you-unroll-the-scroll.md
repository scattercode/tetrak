---
title: "Read the tag before you unroll the scroll"
date: 2026-11-01
draft: false
slug: "read-the-tag-before-you-unroll-the-scroll"
kicker: "The field"
standfirst: "In 2026 the number of published vulnerabilities more than doubled, and in October Pillow fixed thirty-eight security flaws in one release. A scanning pipeline cannot stop using decoders, but it can decide, from a file's first bytes and its header, whether a decoder should see it at all. We built that decision for ourselves, then made it a library, and this is why"
author: stephen-masters
tags: [security, sillybos, pillow, poppler, project-notes]
---

A library in the ancient world kept its books as rolled scrolls, and a
scroll gives nothing away from the outside. To know what one held you
unrolled it, which is slow, and wears the papyrus, and in a large
collection is no way to find anything. So a small parchment tag, a
σίλλυβος, hung from the end of each roll with the title and the author on
it. Cicero had a set made for his library. The reader checked the tag, and
only then unrolled the scroll, or did not.

An OCR pipeline is handed files it did not make, and every one of them is
a scroll. The decoders that open them, Pillow for images and poppler for
PDFs, are large and old and read formats of great complexity, and they
have flaws. This article is about the month that made us take those flaws
seriously, what we decided to do about them, and why the result is a
library anyone can use rather than a corner of our own code.

## The October storm

Something changed in 2026 in how fast security flaws are found. The
numbers are stark enough to give plainly, with their source. An analysis
of the CVE Program's full list, taken on 23 October, counted 86,292 CVEs
published since the start of the year, against 38,569 in the same window
of 2025: more than double, and already more than the whole of 2025. The
third quarter of 2026 alone held more CVEs than any full year before 2024.
September had three and a half times as many as the September before.

The analysis also counted the records that credit an AI system, or an AI
lab's research team, as the finder: 34 in the whole of 2025 and 769 by
late October 2026, with the monthly figure rising through the year from
18 in January to 199 in October with a week still to run. That is under
one per cent of the year's CVEs and the author calls it a floor, since
most vendors do not say who found their bugs. Anthropic's own disclosure
dashboard gives a sense of the volume behind the floor: as of 2 October it
had disclosed 6,157 vulnerabilities across 591 open source projects, from
nearly thirty thousand candidates, and it says in plain words that human
triage is the rate-limiting step and that there are confirmed bugs not yet
reported to maintainers for want of capacity. A dashboard like that does
not describe a spike. It describes a new rate, limited by how fast people
can read, and the reading is being automated too.

The press called it the October vulnerability storm. For a project that
reads scans, the storm had one address. On 16 October Pillow released
version 13.0.0 with thirty-eight security entries in its notes, two of
them critical, most of them reachable by opening one crafted file. Two are
worth describing, because together they show the shape of the problem.

The first was in the EPS reader. Pillow does not decode PostScript itself;
it hands the file to Ghostscript, as a separate program, with the file's
name on the command line. Nothing checked that name, so a name beginning
with a hyphen was read by Ghostscript as an option, and a researcher
showed the route from there to running a command, past Ghostscript's own
safe mode (CVE-2026-112900). The second was in the FlashPix reader, an
old Microsoft format kept in an OLE container: with the `olefile`
package installed, opening one could run code (CVE-2026-112398).

Neither of these formats has any business in a scanning pipeline. No
scanner writes PostScript or FlashPix. The reason they were reachable at
all is that Pillow, sensibly, decides what a file is from its contents and
not from its name. A PostScript file called `page.png` is a PostScript
file, and until October it went to the PostScript reader. The extension
was never a defence, and for years nobody who ran scans through Pillow had
reason to notice.

## What we decided

We read the October advisories against our own code in a sitting, and
the first conclusion was uncomfortable: the only gate in front of our
decoders was the file's extension. The second was more useful. Nearly
everything the advisories needed was visible from outside the file, before
any decoder ran.

So we decided to build a layer whose only job is to decide whether a file
may be opened, and we staged it. Stage zero was an afternoon: Pillow's
`Image.open` takes a `formats` argument, a list of the readers it may try,
and passing `["JPEG", "PNG", "TIFF"]` means a PostScript file is not a
PostScript file any more but an unrecognised one, and no reader runs on
it. That one argument, with an explicit pixel limit and a page cap on PDF
rendering, closed the October paths. Stage one was the check proper: the
format from the first bytes, the name against the contents, the header
read without decoding, the features of a PDF that a scan never has, and a
refusal that goes to the pipeline's triage queue with a reason rather than
a silent drop. Stage two is decoding in a boxed process with memory and
time limits, for the flaws nobody has announced yet. Stage three is the
same check as the front door of the platform, where files will arrive
from partner catalogues, one more step removed from anyone we know.

Stage one is where we noticed that the thing we were building was not
really about OCR. A thumbnailer needs it. An upload form needs it. A
service that converts documents needs it. Anything that runs Pillow or
poppler over files other people made has exactly our problem, and most of
the people who have it will never install an OCR tool. So the check
became a library of its own, [sillybos]({{< relref "/sillybos.md" >}}),
MIT licensed, with no dependencies at all, because a security library
that pulls in a parser adds to the attack surface it exists to reduce.
Tetrak OCR was its first user and calls it in front of every scan.

## What sillybos does

The check reads what can be read from the outside of a file, in order,
and stops at the first thing it does not like.

**The size**, from the file system, before anything reads the file.

**The format, from the first bytes.** Every format a scanner writes
announces itself in its first few bytes, and so do most of the ones it
does not: PostScript, GIF, BMP, WebP, HEIF, JPEG 2000, BigTIFF, Photoshop,
the OLE container that holds FlashPix and old Office files, zip, gzip,
icons, XML. Reading those bytes is a table lookup, not a parse, and it
lets a refusal say *what* the file was, which is the first thing the
person running the batch wants to know. Only JPEG, PNG, TIFF and PDF can
pass.

**The name against the contents.** A JPEG called `.png` would decode
perfectly well. It is refused anyway, because a file whose name lies is
not one to trust, and because the lie is the thing the operator wants
told about.

**The header, read with code of our own.** This is where it became a
library rather than a wrapper. A JPEG's dimensions, how its frame is
coded, and the size of its colour profile are in its segment headers. A
PNG's dimensions, bit depth, colour type and interlacing are in its first
chunk, and the size of every other chunk is in front of that chunk. A
TIFF's directory chain carries, for every frame, the dimensions,
compression scheme, colour model, samples and bits, tile size and
subsampling, and the position and size of every tag's data. Reading each
of these turned out to be a few dozen lines, with no decoder involved and
no dependency on one.

**For a PDF, what poppler will say without rendering.** `pdfinfo` reports
the page count, encryption, the size of every page in points and whether
the document carries JavaScript or a form; `pdfdetach` lists attached
files. Both run as separate processes with a time limit, so a file that
makes a parser loop costs one file's failure and nothing more.

**The limits**, against what the header said, from a policy set from your
own largest real files. A file is refused for being too large, for having
too many pages, for a page that would decode to more pixels than the
machine should allocate, for a side longer than any scanner writes, for a
frame coding no scanner uses, for a compression scheme that lives only in
the least-exercised corner of libtiff, for a metadata block the size of
the file, for a PDF that would make a viewer act rather than draw. Each
refusal is a sentence: *a lossless JPEG; the policy allows baseline,
extended and progressive frames*. The sentence is for the person, never a
code.

```python
from sillybos import check

verdict = check("inbox/page-012.png")
if not verdict.ok:
    quarantine(verdict.path, verdict.reasons)   # ('says PNG, is PostScript',)
```

With Pillow installed, `open_checked` runs the check and then opens the
file with Pillow's `formats` list set from the policy. That is the October
fix, packaged, with everything the header can add to it in front. There
is a command, `sillybos scans/*`, for a shell pipeline or a Dockerfile.

## The limits are the point, not the format

The format check is what stops the October flaws. The limits are what
stop the next ones, and they deserve a word, because a limit that sounds
like belt-and-braces turns out to map onto real advisories with
uncomfortable precision.

Take a pixel budget. Pillow has had one for years, the decompression-bomb
threshold, and it is a global that any library in the process can raise.
We enforce the same number ourselves, from the header, before Pillow is
asked. But a pixel budget alone lets through a page a few pixels wide and
a million tall, and an abnormally tall TIFF is exactly what one flaw in
libtiff's RGBA reader needed to write colour data to an arbitrary address
(CVE-2025-9900). So the policy also holds either side of a page, a frame
or a tile to a ceiling. No scanner writes a side longer than a few tens of
thousands of pixels; the default is three times the longest side of an A3
page at 600 dpi, and nothing we have scanned comes near it.

Or take TIFF compression. A scanner writes one of six schemes. libtiff
knows nineteen, and most of its security history lives in the other
thirteen. A scan never needs PixarLog, so the policy refuses it by name,
and the most recent PixarLog flaw (CVE-2026-12912) becomes a file that is
never opened.

Or take a multi-frame TIFF whose second frame has a different colour mode
from its first. A decoder that sized its buffers for frame one and then
reads frame two writes past them (CVE-2026-96639, one of October's two
critical entries). We walk the whole chain before the file is opened and
require every frame to agree.

In each case the check reads something the header already says, costs
microseconds, and turns a decoder's flaw into a file that was refused with
a reason. The pattern repeats often enough that we have made it a rule:
a published advisory that can be prevented from a header field becomes a
policy field, with a default, a command-line option, and a case in a
hostile corpus that builds the triggering file from bytes and proves the
check refuses it. The [security watch]({{< relref "/security/_index.md"
>}}) is the record of which advisories that has been done for, and which
it cannot be done for, and why. How two people keep that record current
against the rate described above is a story of its own, told in [Keeping
watch on the decoders]({{< relref
"/articles/2026/11/2026-11-01-keeping-watch-on-the-decoders.md" >}}).

## What it does not do

A security library carries an implied promise, so this has to be said
plainly, and the library's README says it first.

It does not protect against a flaw in the readers you *do* allow. A
crafted JPEG that exploits your JPEG decoder is a JPEG of a sensible size,
and it passes. What the check removes is every format you did not mean to
read, every file too large to be safe, every coding a scanner never
writes, and every structural lie the header can be caught in. For the
readers you keep, the advice is the old advice: update them, and decode in
a process with its own memory and time limits, which is a recipe we have
written down in the library's documentation.

It does not scan for malware, repair a file, or read any format beyond the
four a scan can be. Adding a format is adding attack surface, and we will
add one when someone shows us a scan in it.

Read the tag. Then decide whether to unroll the scroll.

## Further reading

### The storm

- Mike Carthy, "More CVEs in Q3 2026 than in any full year before 2024",
  CyberHire, 23 October 2026,
  [cyber-hire.com/blog/cve-volume-2026](https://cyber-hire.com/blog/cve-volume-2026).
  The count behind the figures above, from the CVE Program's full list
  downloaded that day: year-on-year totals, the quarter and month
  comparisons, and the rise in records crediting an AI finder, with the
  author's own caution that the data cannot prove cause.
- Anthropic, *Coordinated vulnerability disclosure dashboard*,
  [red.anthropic.com/2026/cvd](https://red.anthropic.com/2026/cvd/),
  figures as of 2 October 2026. The pipeline from candidates to
  disclosed findings to upstream patches, and the statement that human
  triage is the rate-limiting step. We cite it for the rate; our own
  triage, described in the companion article, is shaped by the same
  constraint at a much smaller scale.
- Pillow, [13.0.0 release
  notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html),
  16 October 2026. The thirty-eight security entries by severity, with
  their advisory identifiers.

### The flaws

- GitHub Advisory Database, [GHSA record for
  CVE-2026-112900](https://github.com/advisories?query=CVE-2026-112900),
  and the [Debian security tracker's
  entry](https://security-tracker.debian.org/tracker/CVE-2026-112900).
  The EPS filename flaw: affected from Pillow 2.6.0, fixed in 13.0.0.
  The two scorings disagree, GitHub's critical against the maintainers'
  moderate, because the attacker has to control the file name; a
  pipeline that opens files from outside has handed that control over.
- OSV, [osv.dev](https://osv.dev/). The vulnerability database the
  security watch is fed from, and where every row of it links.

### Reading files safely

- Len Sassaman, Meredith L. Patterson, Sergey Bratus and Michael E.
  Locasto, "Security Applications of Formal Language Theory", *IEEE
  Systems Journal* 7(3), 2013, pp. 489–500,
  doi:[10.1109/JSYST.2012.2222000](https://doi.org/10.1109/JSYST.2012.2222000).
  The case that input handling is a parsing problem and that a parser
  should accept exactly the language it claims to and nothing else. Our
  header readers are the small, fully specified recognisers this paper
  argues for; the decoders behind them are the kind of parser it warns
  about.
- Pillow, [Security](https://pillow.readthedocs.io/en/stable/handbook/security.html)
  and the [`Image.open`
  reference](https://pillow.readthedocs.io/en/stable/reference/Image.html),
  Pillow 13 documentation. The `formats` allowlist and the
  decompression-bomb threshold, with the maintainers' own advice to
  restrict formats and never disable the limit in production.

### The formats

- Adobe Systems, *TIFF Revision 6.0*, 1992. The specification our TIFF
  reader walks: the image file directory, the tag types, the strip and
  tile layouts, and the compression codes the policy names.
- W3C, *Portable Network Graphics (PNG) Specification (Third Edition)*,
  W3C Recommendation, 24 June 2025,
  [w3.org/TR/png-3/](https://www.w3.org/TR/png-3/). The chunk structure,
  the IHDR fields and, new in this edition, the animated PNG frames our
  reader counts as pages.
- ITU-T, *Recommendation T.81: Digital compression and coding of
  continuous-tone still images*, 1992 (also ISO/IEC 10918-1:1994). The
  JPEG marker segments, including the start-of-frame markers whose codes
  tell a baseline frame from a lossless or arithmetic one.
- ISO, *ISO 32000-2:2020, Document management — Portable document format
  — Part 2: PDF 2.0*, second edition. The document catalogue, actions and
  embedded files that the PDF policy refuses by default.
