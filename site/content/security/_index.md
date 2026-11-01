---
title: "Imaging security watch"
kicker: "Security"
standfirst: "The published security flaws in the libraries that decode images and PDFs, what each one takes to trigger, and how to protect a pipeline that opens files it did not make. Kept current from sillybos's advisory record, rebuilt weekly."
description: "A current record of security vulnerabilities (CVEs) in image and PDF libraries: Pillow, libtiff, libpng, libjpeg-turbo, poppler and others. For each: what triggers it, whether it is reached by opening a file, which are refused before decoding, and how to protect yourself."
outputs: [html, rss, json]
---

Every program that reads scans hands each file to a decoder, and decoders
have flaws. In October 2026 Pillow fixed more than thirty at once, several
of them reachable by opening a single crafted file. Anyone who runs an OCR
pipeline, a thumbnailer or an upload form has the same question each time
one is announced: *does this reach me, and what do I do?*

This page is our answer, written down. It comes from the work behind
[sillybos]({{< relref "/sillybos.md" >}}), the library that decides whether
a file may be opened before any decoder sees it: every advisory on the
libraries we watch is fetched weekly, read by a person, and recorded with
what triggers it, whether opening a file reaches it, whether a check before
decoding would have refused the file, and how to protect yourself with or
without that check. The record is [public
data](https://github.com/scattercode/sillybos/tree/main/docs/advisories/record)
in the sillybos repository; this page is built from it.

Three things it is not. It is not a vulnerability database: OSV.dev and the
GitHub Advisory Database are, and every row links to them. It is not a
claim that sillybos prevents everything: a row says **refused by default**
only where a test in the sillybos suite builds the triggering file and
proves it is refused, and many rows say plainly that nothing before the
decoder can help. And it is not advice to skip upgrading. The first line of
every "how to protect yourself" entry is the fixed version.

If you only want the general advice, read [Protecting
yourself]({{< relref "/security/protecting-yourself.md" >}}).
