---
title: "Protecting yourself"
kicker: "Security"
standfirst: "What a pipeline that opens images and PDFs it did not make can do about the flaws in its decoders, in order of how much each step buys. None of it replaces upgrading; all of it helps when the next flaw has no fix yet."
description: "How to protect an OCR pipeline, thumbnailer or upload handler from vulnerabilities in image and PDF libraries: pin and scan, allow-list formats, set limits, check before decoding, decode in a boxed process, and keep a routine for the next advisory."
weight: 1
---

Every row in the [watch]({{< relref "/security/_index.md" >}}) ends with
advice specific to that flaw. This page is the advice that applies to all
of them. It is written for someone who runs a pipeline rather than someone
who writes decoders: the steps are things you can do this week.

## Upgrade, and know what you have

The fixed version is the first line of every row for a reason: a flaw with
a fix is closed by installing the fix, and nothing below is as good. The
part people miss is knowing what to upgrade. An image library is several
libraries: Pillow carries libjpeg-turbo, libpng, libtiff, OpenJPEG and
zlib inside its wheels, and a Docker image carries the operating system's
copies of the same underneath. Pin exact versions in a lock file, scan the
lock file *and* the built image for published flaws (Trivy does both, for
free), and let a tool propose the updates so that you only have to read
them.

## Allow-list the formats you mean to read

A scan is a JPEG, a PNG, a TIFF or a PDF. A decoder that will also read
PostScript, FlashPix, Photoshop, SPIDER, XBM and forty other formats is
forty readers' worth of flaws you never needed, and in October 2026 two of
the three flaws that ran code on the computer were in readers of that
kind. Decoders choose the reader from the file's *contents*, so an
extension check does nothing; the allow-list has to be given to the
decoder. In Pillow that is one argument:

```python
Image.open(path, formats=["JPEG", "PNG", "TIFF"])
```

It costs nothing and removes most of the attack surface at a stroke.

## Set limits from your own files

A decompression bomb is a tiny file whose header claims a vast image; the
decoder allocates what the header says before it has read a pixel. The
limit to set is not a guess: take the largest real file you have, and the
longest, and allow two or three times that. Pixels per image, bytes per
file, pages per PDF, frames per TIFF, and the size of any block of
metadata (a scan carries kilobytes of it, not megabytes). Pillow's
`MAX_IMAGE_PIXELS` is a start, but it is a global another library can
raise, and it is checked on the first frame only.

## Decide before decoding

The three steps above are what [sillybos]({{< relref "/sillybos.md" >}})
packages: it names the format from the first bytes, reads the header with
code of its own, applies your limits, and refuses with a sentence before
any decoder runs. It also refuses the rare codings a scanner never writes
(a lossless JPEG, a PixarLog TIFF, an interlaced PNG) that turn out to be
where decoders' least-exercised code lives. What it cannot do is protect
the readers you keep from a flaw in their own pixel decoding; the watch
says which rows those are.

## Decode in a box

For a flaw nobody has announced yet, the only defence is to make a crash
or a hang cost one file rather than the whole run. Decode in a separate
process with a memory limit and a time limit and no network: on Linux,
`subprocess` with `resource` limits, or `systemd-run`; a container is too
slow per file but fine per batch. Catch the failure, set the file aside
with a note, and carry on. Tetrak OCR's triage queue is this idea at the
pipeline level: a file the pipeline cannot trust goes to a folder with a
reason, for a person.

## Never hand back what you decoded

Several of the October flaws read past a buffer and copied what they found
into the pixels of the image returned. A service that returns thumbnails
of uploads returns fragments of its own memory. If you must return pixels
from an untrusted file, re-encode them, and never return the decoder's
buffer as it came.

## Have a routine for the next one

A flaw is announced on a Tuesday; the question is what you do on
Wednesday. Ours is four questions, in order, written down each time: *do
we use it* (search the lock files, the images and the extras, not just
the obvious package); *does the trigger reach us* (an opened file, or only
a save path or a drawing call); *is there a fix*; *where must it be
applied* (the lock file, the running image, the laptops, and any package
you publish that others install). The watch is that routine, done in
public, for the libraries we depend on.

## What this page does not say

It does not say which of these to skip. A pipeline that only does the
first step is in a much better place than one that does none, and a
pipeline that does all six still has decoders in it. The order above is
the order of return on effort; the first two are an afternoon.
