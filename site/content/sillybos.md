---
title: "sillybos"
kicker: "Open source"
standfirst: "A small library that decides, before any image library or PDF renderer opens a file, whether it is one of the formats you meant to read, within the limits you expect, and if not, why. Read the tag; don't unroll the scroll."
description: "sillybos: a dependency-free Python library and command that checks a JPEG, PNG, TIFF or PDF before any decoder opens it: format from the first bytes, header limits, rare codings refused, a plain reason for each refusal. MIT licensed."
---

## What it is for

A σίλλυβος (*sillybos*, say it *SIL-lee-boss*; Latin *sittybus*) was the
little parchment tag that hung from a rolled scroll in an ancient library,
carrying its title and author, so that a reader could tell what a scroll
was without unrolling it. Cicero had them made for his books. This library
is that tag for the files a scanning or OCR pipeline is handed: it reads
the tag, and says whether the scroll should be unrolled at all.

Every program that reads scans hands each file to a decoder: Pillow for
images, poppler for PDFs, then an OCR engine. Decoders are large, old
programs that read complicated formats, and they have flaws. In October
2026 Pillow fixed more than thirty at once; one of them ran commands on the
computer when an EPS file was opened, and a file's extension was no
protection, because Pillow decides what a file is from its contents, so a
PostScript file named `page.png` went straight to the PostScript reader.

## Who it is for

Anyone who runs Pillow or poppler over files they did not make: an OCR
pipeline, a digitisation workflow, a thumbnailer, an upload handler, a
service that converts documents. It came out of [Tetrak OCR]({{< relref
"/ocr" >}}), where it sits in front of every scan, and is a library of its
own because most of the people who need it will never install an OCR tool.
It has no dependencies, so it adds nothing to the attack surface it exists
to reduce.

## What it does

1. **Size**, from the file system, before anything reads the file.
2. **Format, from the first bytes.** JPEG, PNG, TIFF and PDF can pass. It
   also recognises PostScript, GIF, BMP, WebP, HEIF, JPEG 2000, BigTIFF,
   Photoshop, OLE (FlashPix, old Office), zip, gzip, icons and XML, so a
   refusal can say *what* the file is. Everything else is "an unknown
   format". Refused by name; no reader runs on it.
3. **Name against contents.** "Says PNG, is JPEG."
4. **The header, read with code of its own**, never a decoder's: the
   dimensions, frame coding and colour profile size of a JPEG and every
   picture of a multi-picture one; a PNG's whole header, its frame count,
   and the size of every chunk; every directory of a TIFF, with its
   compression, layout and colour model, all required to match from frame
   to frame, and every tag's data checked to lie inside the file. For a
   PDF, poppler's `pdfinfo` in a separate process with a time limit reports
   the page count, encryption and every page's size.
5. **The limits**, against what the header said, from a policy you set from
   your own largest real files.

```python
>>> from sillybos import check
>>> verdict = check("scans/page-012.png")
>>> verdict.ok
False
>>> verdict.reasons
('says PNG, is PostScript',)
```

The refusals are sentences for the person running the batch, never codes.
With Pillow installed, `open_checked()` runs the check and then opens the
file with Pillow's own `formats=` list set from the policy, which is the
one-line fix for the October flaws, packaged.

## What it does not do

A security library carries an implied promise, so the README says this
first and so does this page.

- **It does not protect against a flaw in the readers you do allow.** A
  crafted JPEG that exploits your JPEG decoder is a JPEG of a sensible
  size and passes. What it removes is every format you did not mean to
  read, every file too big to be safe, and the rare codings a scanner
  never writes. For the readers you keep: update them, and decode in a
  boxed process.
- **It does not scan for malware**, repair or "sanitise" a file, validate
  uploads, or read formats beyond the four.

The [security watch]({{< relref "/security/_index.md" >}}) keeps the
record of which published flaws it would have refused, which it would not,
and why, each claim tied to a test.

## Get it

```bash
pip install sillybos            # the check; no dependencies
pip install 'sillybos[pillow]'  # plus open_checked()
sillybos scans/*                # the command
```

| | |
|---|---|
| Code | [github.com/scattercode/sillybos](https://github.com/scattercode/sillybos) |
| Package | [sillybos on PyPI](https://pypi.org/project/sillybos/) |
| Documentation | [scattercode.github.io/sillybos](https://scattercode.github.io/sillybos/) |
| Licence | MIT |
