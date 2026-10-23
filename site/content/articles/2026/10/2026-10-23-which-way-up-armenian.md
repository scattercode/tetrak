---
title: "Which way up is the page, when the page is Armenian?"
date: 2026-10-23
draft: false
slug: "which-way-up-armenian"
kicker: "Method"
standfirst: "Our page-orientation method leant on Latin letters carrying more ink above the line than below it. We measured whether Armenian letters do the same. They do not, and the measure that works for them does not work for English"
author: stephen-masters
tags: [archives, ocr, digitisation, armenian, project-notes]
---

The transcription notes for *Mshak*, the Tiflis Armenian newspaper whose
pages are in Tetrak's evaluation set, carry a rule about turned sorts. In
hand-set type a compositor now and then puts a letter into the stick
upside down, and on one page the second կ of կտակի prints rotated through
a half turn. The rule says to transcribe the letter the compositor meant,
because a reader does: the eye takes the intended letter and moves on
without pausing. That is worth dwelling on. If a turned Armenian letter
barely registers with a reader, then whatever tells a reader that a whole
Armenian page is upside down is not something the individual letters
shout. It is a statistic over the page, and the statistic a Latin reader
relies on may not be the one an Armenian reader does.

[Last week]({{< relref "/articles/2026/10/2026-10-16-which-way-up.md" >}})
we described how the Empire on Trial ingest works out which pages of a
microfilmed archive were filmed on their side, and which way to turn
them. Two measurements, no training data: which way the lines of text
run, and, for a page whose lines run down the image, which way is up. The
second leant on a fact about Latin script, that ascenders, capitals, dots
and bars put more ink above the body of a line than descenders put below
it. We said plainly that we had not measured whether Armenian behaves the
same way, and that for the archives Tetrak was built for this half of the
method was a thing to test before trusting. We have now tested it. This
is what we found, including two things about the method itself that the
Latin pages had hidden.

## What we measured, and on what

The pages are the ones our Armenian recogniser is evaluated on: the
held-out pages of eighteen printed works, 1840s to 1980s, Eastern and
Western Armenian, in both the classical and the reformed orthography,
from encyclopedia columns and a bilingual dictionary to literary prose and
sixty pages of *Mshak*. Every page is known to be upright. There is no
Armenian manuscript among them, because the project holds none, and that
gap stands at the end of this article as it did at the start.

Alongside them, measured identically, two controls. Eighteen pages of
Latin print from Tetrak's own corpus, so that we could see whether the
up-share, built on handwriting, survives typesetting at all. And the
Empire on Trial frames themselves, the eighteenth-century hands the method
was built on, so that any change we made to the method could be checked
against the material it already worked on.

The procedure for every page was the same. Measure it as it is. Turn it
through a half turn and measure again, recomputing everything from the
rotated image rather than rotating the answer, so that the whole chain is
tested for symmetry and not just the final number. The two readings must
mirror: if an upright page scores two thirds, its half-turned copy must
score one third. Turn it a quarter turn each way and measure the line
direction. Then look at the spread of upright pages against the spread of
turned ones, and ask whether a line can be drawn between them.

## The up-share on Armenian

It cannot. On Armenian print the share of a line's outer ink lying above
the line sits close to a half whichever way up the page is. Upright pages
lean a little above a half and half-turned pages a little below, but the
lean is a few hundredths where the Latin pages lean by a quarter, and the
two distributions overlap broadly: a good many upright pages score below
a half and a good many turned pages above it. Nor is the lean consistent.
Most presses tilt slightly above when upright; *Mshak*, the largest single
set, tilts the other way; one memoir comes out exactly level. There is no
single direction to invert the rule for, which was the one escape the
earlier article had left open.

The mirroring holds throughout, on every press, so this is not a flaw in
the measurement. The measurement is symmetric and the script gives it
nothing to measure. The one register that behaves differently confirms
it: the Armenian–English dictionary, where every page is half Latin,
scores where the Latin pages do.

The letter inventory says why, at least to the eye. Armenian lower case
has a long list of letters that descend, including several of the most
frequent (ր, ս, տ, ի, ւ, ց), and a long list that both ascend and descend
(լ, խ, ծ, կ, հ, ձ, ղ, ճ, պ, ջ, փ, ք). Set text puts about as much ink
below the body as above it, and which way the small residue leans depends
on the face and on the words. The up-share is a fact about Latin
letterforms, as the earlier article suspected, and not a fact about
writing.

## What the Latin pages had hidden

Two findings on the way concern the method rather than the script, and
they are the reason the Empire on Trial ingest has changed this week even
though its own verdicts have not.

**The line finder was reading a tenth of a typeset page.** On the
manuscript pages the method was built on, a line of writing is a single
hump in the row profile. On a typeset page it is a plateau: the x-height
body is flat for ten rows or more, and its wobble reads as two or three
local maxima a few rows apart. The finder merges maxima only when they are
very close, and then requires a dip to half the peak's height on each side
of every line, so the maxima of one line reject each other in pairs. On
one page a strip of the profile held a hundred candidate peaks and the
finder accepted two. What survived was the handful of lines that happened
to read as one hump, which is to say short lines, headings and folios,
and the up-share was being computed on those.

The uncomfortable part is that the article's safeguard did not catch it.
We had written that the upright and half-turned readings must mirror, and
on these pages they did, closely. The finder was not biased towards one
side of the line. It was biased towards a subset of the lines, and a
mirror test cannot see that. What would have caught it is a count: how
many lines the finder kept against how many it saw. The fix is one loop,
merging adjacent maxima when the profile between them never drops below
half the lower of the two, which is the same half-height criterion the
finder already applies, used to decide that two maxima belong to one
line. On the Empire on Trial reels it is harmless and slightly helpful:
the sideways document's vote tightened, and the one page that moved had
sat on exactly a half. The ingest now also refuses to trust an up-share
whose finder rejected more lines than it kept, and names the page in its
report.

**The two measurements want different resolutions.** The earlier article
settled on two thousand pixels along the long side, set by the smallest
hand in the archive. That is right for the line-direction vote and wrong
for the up-share on dense print, where the zone above and below a line's
body is a row or two at that scale and the asymmetry, where there is
one, is lost in it. One Armenian face that showed nothing at two thousand
pixels showed a clear lean at its native resolution. The reverse holds
for the line direction: at native resolution the column profile starts to
resolve individual letter strokes, the contrast between rows and columns
shrinks, and a quarter of the Armenian pages fall into the unsure band
that only one of them occupies at two thousand. Any port of the method
should run the two measurements at different scales. It does not rescue
the Armenian up-share, which was measured at native resolution for
everything above.

## The trained alternative

The earlier article set aside Tesseract's orientation and script detection
mode, `--psm 0`, because it is a classifier trained on synthetic
renderings of printed scripts and our material was handwriting on
microfilm. Armenian print is nearer what it was trained on, so it was the
obvious thing to try next, and it is fast: well under a second a page.

We ran it over every page, as it is and turned three ways, with the
Latin pages to establish which way round its answer is meant. On the
Latin print it did well, as its training would predict. On the Armenian
pages it was wrong far more often than right, and wrong in a particular
way: it called most upright pages upside down and most upside-down pages
upright, and it was more confident when wrong than when right, so a
confidence threshold makes it worse rather than better. The explanation
is in the script it reports, which is Latin, Arabic or Cyrillic and never
Armenian, because Armenian is not among the scripts the detector was
trained on. It is judging Armenian letters by how well they resemble the
letters of other scripts in each of four orientations, and an Armenian
page, it turns out, resembles Latin or Arabic print rather better on its
head. The one register it read perfectly was the bilingual dictionary,
from the English half of each page. On the Empire on Trial manuscripts,
which the earlier article had declined to trust it on, it was wrong on
almost every frame and reported the hand as Japanese.

One could invert its Armenian answer and be right about four times in
five. That would be leaning on an accident of a model trained for other
scripts, which the next revision of its training data could remove
without notice, and we would rather measure something.

## Reading the shapes instead

Aradhye's 2005 paper, which the earlier article named as where we would
start, takes a different route. Rather than asking where the ink lies, it
asks which way the open sides of the letters face, and it learns the
useful direction for each script from samples of known orientation. We
built the simplest version of that idea we could explain in a paragraph.
Take each connected blob of ink that is about the size of a letter. Within
it, find the background pixels that its own ink encloses on three sides
and leaves open on the fourth: open upward, like the bowl of a u; open
downward, like the arch of an n; open to the left or the right. Sum the
areas over the page, and take the share that is open upward against open
upward or downward. Turn the page through a half turn and up becomes down
exactly, so the two readings mirror by construction.

On Armenian print this works. Upright pages have more of their
concavities open upward, turned pages open downward, by a margin that
separates them cleanly on every press, including *Mshak*. We tested it the
way Aradhye prescribes, learning the direction from all the other presses
and testing on the one held out, and every page of text came out right
in every fold. The only pages it could not call were blank leaves and one
dark frame, where it sat on a half and the line-direction vote had
already reported nothing to measure, which is the right order to ask the
questions in.

Then we ran the same measure on the Latin pages, and it was poor. On the
Empire on Trial manuscripts it is no better than a coin, and on Latin
print the direction depends on the face: the newspapers and the playbill
lean one way and the typewritten technical report the other. Aradhye's
full method has more features than our one share and a classifier behind
them, and we make no claim about it; our paragraph-sized version is a
measure for Armenian print and not for English. The dictionary, half
Armenian and half English on every page, came out the Latin way on this
measure too, which is the failure a per-script rule has to expect from a
bilingual page.

So the picture is the mirror image of where we started. The up-share
reads Latin, in manuscript and in print, and reads nothing in Armenian.
The concavity share reads Armenian print and reads nothing reliable in
Latin. Neither is a measure of writing; each is a measure of a script.
The useful direction has to be learned per script, as Aradhye said, and
so, it turns out, does the useful measure.

## What this means for Tetrak

Three things, all of them simpler than the finding.

The line-direction vote, which does not care what the writing is, can be
ported into the OCR pipeline as it stands, at the earlier article's
scale. It answers whether an Armenian page is on its side with the same
margins it gave for English manuscript, with one bold-and-italic page in
the unsure band.

The up-share should not be ported for Armenian pages. It would be right a
little over half the time with no way to tell which half, and the
per-document vote that rescues sparse manuscript pages cannot rescue a
measure whose per-page errors are not a minority. It stays in the Empire
on Trial ingest, for Latin, with this week's two corrections.

For which way up an Armenian page is, the concavity share is the
candidate, gated behind the line-direction vote so that blank leaves are
reported rather than guessed at, and run only when the pipeline knows the
page is Armenian. Tetrak does know: the Armenian recogniser is chosen
explicitly, so the script is a fact the orientation step can be handed
rather than one it has to infer. The pages measured here, with their
half-turned copies, are the test set for it.

## Further reading

- Hrishikesh B. Aradhye, "A generic method for determining up/down
  orientation of text in Roman and non-Roman scripts", *Pattern
  Recognition* 38, 2005, pp. 2114–2131.
  [doi:10.1016/j.patcog.2004.12.011](https://doi.org/10.1016/j.patcog.2004.12.011).
  Orientation from which way the open sides of letter shapes face, with
  the useful direction learned per script from samples of known
  orientation. The concavity share above is the simplest reading of its
  central idea; the paper's own method carries more features and a
  classifier.
- Robert S. Caprari, "Algorithm for text page up/down orientation
  determination", *Pattern Recognition Letters* 21, 2000, pp. 311–317.
  [doi:10.1016/S0167-8655(99)00161-0](https://doi.org/10.1016/S0167-8655(99)00161-0).
  Up from down by the ascender and descender asymmetry of the projection
  profile: the up-share this article measured, and found to be a
  property of Latin letterforms.
- Ranjith Unnikrishnan and Ray Smith, "Combined orientation and script
  detection using the Tesseract OCR engine", *Proceedings of the
  International Workshop on Multilingual OCR (MOCR '09)*, Barcelona,
  2009, pp. 1–7.
  [doi:10.1145/1577802.1577809](https://doi.org/10.1145/1577802.1577809).
  What `--psm 0` does: a shape classifier trained on synthetic renderings
  of each script, scored over connected components in each of four
  orientations. The trained alternative tried above.
- Wolfgang Postl, "Detection of linear oblique structures and skew scan
  in digitized documents", *Proceedings of the 8th International
  Conference on Pattern Recognition*, 1986, pp. 687–689. The
  projection-profile method behind the line-direction vote, which this
  article found to be as script-agnostic as claimed.
- Tesseract documentation,
  [Improving the quality of the output](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html),
  which lists the page segmentation modes, including mode 0, orientation
  and script detection only.
