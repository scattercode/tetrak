---
title: "The engine that made it up"
date: 2026-09-24
slug: "the-engine-that-made-it-up"
kicker: "Method"
standfirst: "We measured two compact vision-language models as candidate local backends. One is in. The other produced the best score any engine has recorded on our hardest fixture, and it did it by inventing words that were never on the page"
author: stephen-masters
tags: [ocr, benchmarks, evaluation, archives, project-notes]
---

We have been looking at a new class of OCR engine: compact
vision-language models, around a billion parameters, built specifically
for reading documents and small enough to run on a laptop. Two were
worth measuring. One of them, PaddleOCR-VL, roughly doubled the best
local character similarity we have ever recorded on a dense page of
1920s newsprint, and we are building a backend for it.

This article is about the other one, and about the twenty minute experiment that
turned it from a strong candidate into something we will not ship.

## What GLM-OCR is

GLM-OCR is an open-weights document reader published by Z.ai, the lab
formerly known as Zhipu AI. It is small — about 1.3 billion parameters,
a vision encoder feeding a compact GLM language decoder — and it is
released under the MIT licence, which for us is not a detail. Several of
the strongest document and script models we have measured are CC BY-NC:
we can put them in a benchmark table but never in a shipped pipeline. An
MIT-licensed document reader that runs on a laptop is exactly the thing
we have been hoping someone would publish.

It is also genuinely popular, with well over a million downloads from
Hugging Face in the last month, and it reads eight languages. You drive
it by prompting: the model card documents modes such as `Text
Recognition:`, `Formula Recognition:` and `Table Recognition:`, and the
transcript comes back as generated text. We used the plain text mode,
because our metric scores against plain-text ground truth and a backend
returning markdown would be penalised for its own structure.

The reason it was worth the time is that this class of model reports
extraordinary numbers on the public document benchmarks — when we began
looking, GLM-OCR held the top score on OmniDocBench. We quote that as
the reason we ran the experiment, never as a result: those benchmarks
are built on modern, largely born-digital documents, and our corpus is
degraded 1920s print. Whether the scores transfer is the
question, and measuring is the only way to answer it.

One thing is worth holding on to before the next section, because it
makes what follows predictable rather than surprising. Classical OCR
engines like Tesseract *classify*: they cut the page into glyph shapes
and decide which character each shape most resembles. GLM-OCR does not
do that. It is a language model that has been given eyes, and it
*generates* — it emits the sequence of tokens most likely to follow,
conditioned on the image. Almost always, on almost any document, the
most likely sequence is the one actually printed on the page. That is
the trick, and it works remarkably well.

What no benchmark score tells you is what such a model does when the
most likely sequence and the printed one part company.

## What it did

The hardest item in our corpus is a poster for the Kar-Mi troupe, a
1910s sword-swallowing act. It is dense, ornate, wildly varied in type
size, and printed in a way that has not aged kindly. Every local engine
we have measured does badly on it. The best of them recovers under a
fifth of the character sequence.

{{< lightbox src="corpus/kar-mi-troupe-poster" alt="Vaudeville chromolithograph for the Kar-Mi troupe: hand-lettered display type arched over oval vignettes of performers swallowing swords, printed colour on colour" title="kar-mi-troupe-poster.jpg — the hardest item in the corpus. Select to view full size" >}}

You can see the problem without knowing anything about OCR. Display
lettering curves along an arc. Captions are set in a condensed hand at a
fraction of the size of the headlines. Cream text sits on orange, orange
on red. Nothing is square to anything else.

GLM-OCR scored higher on that poster than any engine we have ever run
against it. Higher than every local engine, and higher than Claude,
which is not a competitor in our tables but the ceiling reference that
generated the ground truth everything else is scored against.

Here is what it actually produced. One of the oval vignettes, at the
right of the second band, carries this caption:

{{< figure src="articles/kar-mi-sword-caption-detail.png" width="568" alt="Detail from the poster: an oval vignette of a performer drawing a curved sword from her throat, captioned in small condensed capitals 'DRAWING OUT A SWORD BENT IN THE THROAT BY MOVING THE BODY.'" caption="The caption in question, enlarged. At full-page scale this line is about 140 pixels wide." >}}

The line reads:

> DRAWING OUT A SWORD BENT IN THE THROAT BY MOVING THE BODY.

GLM-OCR transcribed it as:

> Swallows out a sword root in the trouser by moving the sword.

And then emitted the same sentence again, immediately, as the next line.

Read that substitution carefully, because the details are why this is unusable for our purposes. *Throat* became *trouser*. *Bent* became *root*. Elsewhere on
the same poster the performer Victorina became *Victoria*, and a line
set entirely in capitals came back in sentence case. The engine also
described the act using verbs that are not on the poster at all.

## Why this is not an OCR error

We are used to reading bad transcripts. A struggling OCR engine produces
recognisable wreckage: dropped characters, letters swapped for
lookalikes, words fused together, whole regions rendered as punctuation
soup. It is unpleasant to read and it is immediately, visibly wrong.

None of that is what happened here. *Trouser* is not a character-level
confusion of *throat* — they share a shape at no point. *Root* is not a
misreading of *bent*. These are lexical substitutions: real English
words, correctly spelled, grammatically placed, semantically adjacent to
a circus poster. The sentence scans. It reads like a description of the
act. It is simply not what the page says.

That is a language model doing what language models do. Faced with print
it cannot resolve, it does not emit noise or leave a gap. It generates
the most probable continuation, and on a sword-swallowing poster the
most probable continuation is a fluent sentence about swallowing swords.
The lowercasing gives the game away: a transcription engine preserves
the case it sees, and a generative one writes in its own voice.

## The part that should worry you

The fabrication scored best.

Not "scored acceptably despite being wrong" — it took first place on
that fixture, ahead of every honest transcript including the cloud
model's. Our primary accuracy metric, character similarity, actively
preferred the invented text.

Once stated, the reason is obvious. Character similarity measures how
closely one string resembles another. A fluent substitution of roughly
the right length, in roughly the right place, made of real words sharing
many letters with the real ones, resembles the reference string quite
closely. Wreckage does not. So on genuinely difficult material the
metric systematically rewards the engine that guesses well over the
engine that fails visibly — and the harder the page, the stronger that
preference gets, because that is exactly where honest engines produce
their worst-looking output.

This is the failure mode we had already written down and then filed in
the wrong drawer. When we surveyed this class of model, we ruled out a
30-billion-parameter generalist partly on the grounds that a
generalist's failure mode is paraphrase, which is self-concealing. We assumed a compact model built specifically for document
parsing would be exempt, because its whole job is transcription. It is
not exempt. And the self-concealing half is no longer a prediction: our
own instrument concealed it, and would have gone on concealing it if we
had read the scores and not the transcripts.

## Why archives in particular cannot take this

For some OCR use, a paraphrase is a tolerable error. You are
extracting a rough sense of a page, a human reads the result in context,
and a wrong word announces itself.

Archival transcription is not that. The transcript goes into a catalogue
and a search index and then, in practice, nobody looks at the scan
again. That is the entire point of digitising the thing. A garbled
transcript is self-reporting: a researcher who finds `SW0RD BENT 1N THE
THR0AT` knows exactly how much to trust it, and can go back to the
image. A researcher who finds "drawing out a sword root in the trouser"
has been handed a sentence with no signal attached. It will be quoted.
It will be indexed. It may end up in a finding aid, and from there in
somebody's footnote, and nothing in the chain will flag that a model
made it up.

The failure is worse precisely where the source is most fragile —
degraded print, damaged paper, unusual type — which is to say, exactly
the material an archive most needs help reading, and exactly the
material where nobody has the original to hand to check against.

## What we have changed

GLM-OCR is not becoming a backend. That is a decision about our corpus
and our purpose, not a verdict on the model: it is widely used, it is
strong on the modern born-digital documents it was benchmarked against,
and none of what we saw contradicts those results. Faithful
transcription of degraded historical print is a different job, and on
that job it fabricates.

PaddleOCR-VL, measured the same way on the same fixtures, did not. It
tracked the dense page from the top in correct reading order and
recovered nearly all of it. Where it could not read something it
produced fragments rather than fluent inventions. It is the one we are
building.

Two things follow that are bigger than either model.

**Our ground truth needs human eyes.** It is Claude-generated, which we
have always stated as a caveat. This gives the caveat teeth: we now have
a fixture where the metric ranks a fabrication first, and we cannot
fully separate "this engine is good" from "this engine writes like the
engine that produced the reference". Human-checked ground truth was on
the list. It has moved up it.

**Character similarity is no longer sufficient on its own.** It was a
good metric for the failure modes of classical OCR, where wrong output
looks wrong. It is a poor detector of confident invention, and every
engine arriving from here on is a language model. We do not yet know
what the right second instrument is — something that penalises fluent
text unsupported by the pixels, rather than rewarding resemblance to a
reference string. We would rather say that plainly than keep publishing
a number we now know can be gamed by a model that is simply making
things up.

The uncomfortable summary is that we nearly shipped this. The scores
looked excellent. We caught it because we read the transcript next to
the poster, which is not a process that can scale well to an archive
of thousands of images. It highlights a risk that you should be aware
of if you are using these vision-language models for OCR, and it is a
risk we are going to need to mitigate in our tools. Somehow...
