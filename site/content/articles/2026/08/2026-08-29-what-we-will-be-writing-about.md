---
title: "What we will be writing about"
date: 2026-08-29
kicker: "Writing"
standfirst: "Opening this section with the two things it is for: the state of OCR for real archival material, and the working notes from building a tool for it."
author: stephen-masters
tags: [archives, ocr, project-notes]
---

The documentation on this site answers the questions a person has once they
have decided to try Tetrak. What it installs, what the flags do, what the
engines are, what the benchmark measured. It is deliberately static: the
[research pages]({{< relref "/research" >}}) are regenerated from the harness,
so the figures on them cannot drift away from the data, and the reference
pages describe a surface that only changes when the code does.

None of that is a good home for an argument, or for a note about something that
did not work. This section is.

## The field

Most published writing about OCR is benchmarked against clean, modern,
single-column print. That is a reasonable place to start and a poor guide to
what happens next, because the material that actually sits in an archive does
not look like that. It is a linen postcard with a caption printed over a
photograph. It is a 1920s trade weekly in six columns of small type on paper
that has browned unevenly. It is a hand-lettered vaudeville bill where the
lettering *is* the design.

Engines behave very differently on that material, and the difference is not
captured by a single accuracy number. Some fail politely and return nothing.
Some return confident nonsense, which is considerably worse, because a
transcript that looks plausible gets ingested and then has to be found again
years later. Some read the first page of a multi-page TIFF and quietly ignore
the rest.

Articles under this heading are about that gap: what the current generation of
engines does with awkward material, where the published benchmarks stop being
predictive, and how the people running digitisation programmes are working
around it today.

## The project

The second thread is a record of building the thing. Changes to how routing
picks engines and what that did to the corpus. What the quality gate is
catching now that it was not catching before, and — more usefully — what it is
still letting through. Progress on the Armenian EasyOCR model, which is a
long-running piece of work with a lot of interesting failure in it.

These will include the ones where the number went the wrong way. A progress
report that only ever reports progress is marketing, and it is also much less
useful to read: the interesting part of a regression is usually the reason for
it.

{{< note kind="note" title="Where the figures live" >}}
Numbers stay in the research pages, which read them from the benchmark CSV at
build time. An article may point at a figure and argue about what it means, but
it will not carry a transcribed copy of one — a number typed into prose starts
disagreeing with the harness within a fortnight, and we have the scars.
{{< /note >}}

## Cadence

Regularly, rather than on a schedule. Something worth reading when there is
something worth reading, which in practice means when a piece of work finishes
or a question turns out to be more interesting than expected.

There is a feed linked from the [articles index]({{< relref "/articles" >}}),
if you would rather not keep checking.
