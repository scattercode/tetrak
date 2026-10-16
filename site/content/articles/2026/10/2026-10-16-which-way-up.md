---
title: "Which way up is the page?"
date: 2026-10-16
draft: false
slug: "which-way-up"
kicker: "Method"
standfirst: "A reel of eighteenth-century court papers came off the scanner with many of its pages on their side. We developed an algorithm to work out which were sideways and to rotate them to their correct orientation"
author: stephen-masters
tags: [archives, ocr, digitisation, project-notes]
---

The [Armenian Institute](https://www.armenianinstitute.org.uk/)'s
[Empire on Trial](https://www.armenianinstitute.org.uk/empire-on-trial-rafael-x-verelest)
project is transcribing the papers of *Rafael v. Verelst*, the suits that
Armenian merchants of Bengal brought in London against Harry Verelst, the
East India Company's Governor of Bengal, in the 1770s. The papers are in
the India Office Records at the British Library, and the project works
from the Library's page images: six documents, some four hundred and fifty
frames, microfilmed in 1995 and scanned from the film. We built the
project a reading site, each frame beside its transcript, and the first
build looked wrong. Most of one document, the brief and proofs assembled
for Verelst's defence, was lying on its side.

Not all of it. Sixty-five frames, and twenty-one of them stood upright.
Those twenty-one carried an EXIF orientation tag, the one that tells a
viewer to turn the image a quarter turn clockwise before showing it, and
our pipeline honoured it. The other forty-four carried no tag at all.
Someone on the team had evidently gone through the folder fixing pages
one at a time, and stopped a third of the way in. Nothing in the files
recorded which way the rest should go.

We knew why it had happened. Everything about a microfilm reel is a
choice the camera operator made in 1995: what fits in the frame, which
way the page lies under the lens. ISO 6199, the standard for microfilming
documents, has a clause for the orientation of images on the film,
because the film does not care and a page can go either way. A reader at
a microfilm viewer turns the knob. A scanner does not: it hands you the
frame as filmed, and the frame as filmed is what we had. The other five
documents on the same shelf had been filmed upright. This one had not.

So we had a folder of images, one orientation per reel, no record of
which reel was which, and a project team whose Word files keep changing
and whose images we cannot touch. The fix had to run inside our own
ingest, every time, and give the same answer every time. This is how we
did it, and what we got wrong first.

## Why not just turn the landscape ones

The obvious rule is that a page is taller than it is wide, so any frame
wider than it is tall is on its side. It fails on the first spread. Most
of this archive is bound volumes filmed open, two pages to a frame, and
every one of those is landscape and correct. The sideways reel had
spreads too, filmed sideways. Aspect ratio tells you the shape of the
frame and nothing about the writing on it.

In 2026 the next obvious route is to ask a model. Send each frame to
Claude, or any of the vision models that can now read a page, with the
question "which way up is this?", and it would very likely answer
correctly; Tetrak uses Claude as one of its OCR engines and we know what
it can do. We decided against it for this job, for two reasons that are
really one. A call per frame costs money and takes seconds, which is
fine for four hundred frames and not fine for a collection of forty
thousand, and this is the kind of tool that will be pointed at the next
collection. And a model's answer is not reproducible: the same frame can
come back differently on a different day, which means the step cannot be
tested, only sampled. We wanted something fast and cheap enough to run on
every frame on every ingest, and deterministic enough that a test could
assert what it does.

The nearer alternative is a classifier built for the job. Tesseract has
an orientation and script detection mode, `--psm 0`, that returns a
rotation and a confidence without reading a word. PaddleOCR ships a text
line orientation classifier. We use both engines in Tetrak and think
well of them. But both are trained models too: Tesseract's was trained
on synthetic renderings of printed scripts, and these pages are
eighteenth-century law hand on microfilm, grey on grey. We would have
been trusting a model on material it had never seen, with no way to say
why it answered as it did. What we wanted was a measurement: something
we could explain in a paragraph, that reads the ink and nothing else,
and that fails loudly rather than guessing.

That is two questions. Which way do the lines of text run? And, once we
know the lines run down the image, which way is up?

## Which way do the lines run

A page of text has structure in one direction and not the other. Sum the
darkness along each row of the image and the result rises and falls with
every line of writing: a peak at each line, a trough at each gap. Sum
along each column and the result is comparatively flat, because every
column crosses every line. Turn the page on its side and the two swap.
Document analysis has used this since Postl's 1986 paper on skew, where
the projection profile's variance is greatest at the angle of the text
lines. We only need two angles.

A word on tools before the code. The ingest is a Python program, and
for its images it uses [Pillow](https://pillow.readthedocs.io/), the
standard Python library for working with image files: it opens a JPEG,
converts it to greyscale, resizes, crops, blurs and filters it, and hands
the pixel values back as plain numbers. It is the maintained successor
of the original Python Imaging Library, which is why its import is still
`PIL`, and it was already in the ingest to make the site's three image
sizes. Everything that follows is written with Pillow and the standard
library's `statistics` and `math`, and nothing else. There is no NumPy,
OpenCV or scikit-image in it, which is deliberate: the whole method fits
in one small module with no new dependency to explain. In these snippets `ink`
is a Pillow image in greyscale mode, the same size as the frame being
analysed, in which each pixel's value says how much ink is there, 0 for
bare paper up to 255 for a solid stroke. How we make it is described
below, under what fooled the first version.

Pillow gives us the profiles for nothing. Resizing an image to one pixel
wide with a box filter averages every row; resizing to one pixel tall
averages every column.

```python
import math
import statistics

from PIL import Image


def profile(ink, axis):
    """Mean ink per row (axis 0) or per column (axis 1), 0 to 1."""
    w, h = ink.size
    strip = ink.resize((1, h) if axis == 0 else (w, 1), Image.Resampling.BOX)
    return [v / 255 for v in strip.getdata()]
```

Compare the variance of the two, take the logarithm of the ratio, and a
positive number means the lines run across the image and a negative one
means they run down it. On a clean page this works at once. We ran it
over the whole archive and it flagged half the upright spreads as
sideways.

### What fooled it

The failures were all the same failure. A projection profile sums
everything in the row, and a page has more on it than writing. The black
border of the film frame, the shadow in the gutter of a bound volume, the
edge of a leaf lying on the one beneath: each is a long straight dark
line, and a vertical line of that kind puts a spike into the column
profile that outweighs forty lines of handwriting. Two-page spreads have
a gutter down the middle and a page edge on either side, so the column
profile of an upright spread was peakier than its row profile, and the
whole document voted the wrong way.

Three changes fixed it. What they have in common is that each stops a
straight edge, which is not writing, from being counted as if it were.

**Measure ink against the local background, not the page.** Our first
ink image was simply darkness below the page's median brightness. That
counts the gutter's shadow as ink, a wide soft band of it. Subtracting a
blurred copy of the image from itself, so that each pixel is scored
against its own neighbourhood, makes the shadow vanish: it is dark, but
no darker than the pixels around it. Pen strokes are a few pixels wide
and stand out from their neighbourhood by design. This is the idea behind
Sauvola and Pietikäinen's local thresholding, used here as a soft score
rather than a binary one.

**Fill the large dark regions with paper first.** The film border is not
a shadow, it is black, and at its edge the local background changes
abruptly, which the subtraction above turns into a thick false stroke.
So before measuring anything we find the regions that are dark over a
large area, which no handwriting is, and paint them the colour of the
paper. The frame edge then has nothing to contrast with.

**Measure many small pieces of the page, not the page.** So far the
whole image has produced one pair of profiles and one number, and one
straight edge anywhere on the page can swing that number. The fix is to
stop asking the page and ask its parts. We cut the image into a twelve
by twelve grid and compute the same number, the log of the row variance
over the column variance, for each block on its own. A block of
handwriting gives a positive number if its lines run across and a
negative one if they run down, and it does so regardless of what is
happening elsewhere on the page. That is the sense in which each block
votes: it answers the question for its own patch of paper.

Two kinds of block are not asked. A block with almost no ink is bare
paper and has nothing to say. A block whose ink is a single spike, one
row or one column many times darker than the block's mean, holds an
edge rather than writing, because text is texture and texture has no
such spike. The page's answer is the median of the votes that remain:
sort them and take the middle one. A median cannot be dragged by a
minority, however loud. A gutter can still fool the blocks it passes
through, but it passes through a dozen, a page has well over a hundred,
and the middle vote belongs to a block of handwriting.

```python
def line_direction(ink, grid=12):
    w, h = ink.size
    bw, bh = w // grid, h // grid
    votes = []
    for j in range(grid):
        for i in range(grid):
            block = ink.crop((i * bw, j * bh, (i + 1) * bw, (j + 1) * bh))
            rows, cols = profile(block, 0), profile(block, 1)
            mean = sum(rows) / len(rows)
            if not 0.005 <= mean <= 0.5:
                continue  # bare paper, or a solid
            if max(rows) > 8 * mean or max(cols) > 8 * mean:
                continue  # an edge, not texture
            vr, vc = statistics.pvariance(rows), statistics.pvariance(cols)
            votes.append(math.log((vr + 1e-9) / (vc + 1e-9)))
    return statistics.median(votes), len(votes)
```

With those three in place every sideways page in the archive scored
below minus 1.7, the upright pages sat around 2 the other way with a
handful of sparse ones dipping towards 1, and nothing that was not
writing came near either. What sat in the middle, close to zero, was
blank leaves, the title cards at the head of each reel, and one wrinkled
sheet. We set the threshold at 1 and treat the middle as a third answer:
not *across*, not *down*, but *cannot tell*.

One more thing hid in the resolution. Our first pass analysed each frame
at a thousand pixels on the long side, which was plenty for a single
page. One document is an album of small mounted sheets, two to a spread,
each a few hundred pixels wide at that scale with lines of writing five
pixels apart, and five pixels is not enough for a line and a gap to show
as a peak and a trough. At two thousand pixels they are ten apart, and
they do. The lines you
are measuring have to be resolvable, and the smallest hand in the
collection sets the scale.

## Which way is up

A quarter turn either way makes the lines run down the image, so knowing
they run down leaves a coin to toss: turn clockwise or anticlockwise?
This is the harder question, and it is where our first three ideas were
wrong.

The first was the margin. Lines of English start at a straight left edge
and end ragged on the right, so, we reasoned, find the lines, find where
each begins and ends, and the straighter side is the left. On these pages
it is the other way round. They are fair copies, written for the court by
clerks who filled each line to the right-hand edge, and the left margin
is where the clerk put the dates, the paragraph marks and the notes. The
straight edge was the right one. A rule that is true of a printed novel
is not true of a legal manuscript, and it was lucky we had enough
upright pages to test it on before trusting it.

The second was the slant. English round hand leans forward, so the
dominant stroke direction in an upright page runs up and to the right.
But a stroke is a line, not an arrow. Rotate the page a quarter turn
clockwise and the slant runs down and to the right; rotate it
anticlockwise and it runs up and to the left, which is the same line.
Slant distinguishes upright from sideways, which we already knew, and
nothing more.

The third was the right idea done carelessly. Latin script carries more
ink above the body of a line than below it: ascenders, capitals, the
dots on *i* and the bars on *t*, against descenders alone. Caprari's 2000
paper determines up from down by exactly this asymmetry in the
projection profile, and it is a measurement, not a learned rule. So find
each line in the row profile, find its peak, and compare the ink above
the peak with the ink below. We did, and on upright pages it came out
right about half the time, which is to say it was not measuring
anything.

Two things were wrong with it. The ink immediately above and below a
line's peak is mostly the body of the line itself, the x-height, which
is symmetric by construction, so the asymmetry was drowned. And our line
finder had a bias we had not noticed. To bound a line we looked for the
lowest point of the profile on each side of its peak, and between two
lines of handwriting the profile is often flat at zero for a stretch.
Python's `min()` returns the first of equal values, and we searched
upwards on one side and downwards on the other, so the upper bound
landed at the far end of the gap and the lower bound at the near end.
Every line was measured with a longer reach above than below, and the
measure leaned above before it had looked at a single ascender. We
caught it only by running the same measurement on a page and on the same
page turned through a half turn, which must give mirror answers and did
not.

The version that works does three things differently. The valley between
two lines is the middle of the flat stretch, so neither side is
favoured. The body of the line is excluded: we take the ink beyond half
the peak's height on each side, which is the zone where only ascenders
and descenders reach. And we measure in narrow vertical strips rather
than across the page, so that on a spread the lines of the left page and
the right page, which do not align, are not summed into one blurred
profile.

```python
def share_above(ink, strips=8):
    # find_lines() is the line finder described above: given a row
    # profile, it returns each line as (upper valley, peak, lower valley)
    # and the lightly smoothed profile it found them in.
    """Across all lines found, the median share of outer ink (beyond half
    the line's peak height) that lies above the line rather than below."""
    w, h = ink.size
    sw = w // strips
    shares = []
    for s in range(strips):
        lines, sm = find_lines(profile(ink.crop((s * sw, 0, (s + 1) * sw, h)), 0))
        for a, p, b in lines:  # upper valley, peak, lower valley
            half = sm[p] * 0.5
            ha = next((y for y in range(p, a - 1, -1) if sm[y] < half), a)
            hb = next((y for y in range(p, b + 1) if sm[y] < half), b)
            above, below = sum(sm[a:ha]), sum(sm[hb + 1 : b + 1])
            if above + below > 0:
                shares.append(above / (above + below))
    return statistics.median(shares) if len(shares) >= 5 else None
```

On the archive's upright pages the share above now sits around two
thirds, and on the same pages turned through a half turn around one
third. Put a sideways page through a clockwise quarter turn and measure
it, and the answer says whether that was the right turn.

## Settling it per reel

Clear on most pages is not clear on all of them. A page with a few lines
of writing in one corner gives the up-share a few lines to work with,
and on one such page it answered confidently and wrongly. What rescues it is
the thing we knew at the start: a reel was filmed one way. The camera
operator did not turn the book between frames. So the decision is not
per page but per document: every page whose lines run down casts a vote
for clockwise or anticlockwise, and the majority turns them all. On the
sideways reel the vote was thirty-seven to two.

That leaves the pages that could not be read, and here the method's job
is to say so rather than to guess. The ingest prints a report after every
run: what was turned, which way, how many pages agreed, and the numbers
of the pages it is unsure of. Three came up on the first run, and all
three were worth a human eye. Two were spreads filmed upright whose
right-hand leaf carried a docket written along the sheet, so one page of
the spread was sideways and the other was not. The third was a spread
whose left leaf was blank but showed the lines of the page beneath it
bleeding through, at right angles to the writing on the right. None of
them should turn. The editorial file that names and describes each
document gained a small table, a page number and a rotation in degrees,
and those three are pinned at zero. The report falls silent about a
pinned page, and the pin is in the repository, with a comment saying why.

That is the whole mechanism: two measurements, a majority, a report, and
a place to write down what the measurements cannot know. It is the same
shape as the auto-configuration in Tetrak's own
[Tesseract backend]({{< relref "/reference/engines.md#tesseract-and-auto-configuration" >}}),
which picks a contrast factor and a page segmentation mode from two
statistics of the image, with thresholds fitted on data and checked by a
test. A rule you can read is a rule you can check.

## Making it cheap enough to run every time

The ingest reads the raw folder every time it runs, because the team's
Word files keep changing, so the orientation pass had to be fast enough
not to be noticed. The first version took over a minute on the archive,
most of it in a single call: the morphological filter that grows the dark
regions before they are painted over. Pillow's `MaxFilter` sorts a
neighbourhood for every pixel, and at two thousand pixels across, with a
fifteen-pixel window, that is nearly a second a frame. But the regions
we are looking for are large by definition, so the mask can be found at
a quarter of the scale and scaled back up with no loss. That took the
pass to nine seconds across the archive.

Two other things keep it cheap. Pillow's `draft()` method asks the JPEG
decoder for a reduced-size image while loading, at a half, a quarter or
an eighth of the original, so the full-size frames, thirty megapixels
and more, are never decoded at full size for analysis. And each derivative we write carries
the rotation it was made with in its JPEG comment, a field Pillow reads
and writes directly, so that a changed decision, a new pin, say, remakes
the three sizes of that one page and nothing else.

## What it does not do

It assumes the writing runs across the page. The obvious counterexample
is Chinese or Japanese set the traditional way, in columns read from top
to bottom and ordered right to left, and Mongolian script, which is
vertical too. On such a page the first measurement would report, quite
correctly, that the lines run down the image, and the rule as written
would then turn an upright page on its side. The measurement is not
wrong, the rule that acts on it is, and for a vertically written
collection the rule simply inverts: *down* is upright. What the method
cannot do is tell the two cases apart on its own, so a collection that
mixes vertical and horizontal setting, as modern Japanese print does,
would need the writing direction known per document before the
orientation could be read from it.

It also assumes Latin script for the second measurement. The
line-direction measure does not care what the writing is, but the
up-share leans on ascenders outnumbering descenders, which is a fact
about Latin letterforms and the eighteenth-century English hand in
particular. Chinese characters sit in a square and have no ascenders at
all, so the up-share would have nothing to measure. Armenian has ascenders
and descenders of its own, and we have not measured whether the
asymmetry holds, so for the archives Tetrak was built for this half of
the method is a thing to test before trusting. Aradhye's 2005 paper, which
takes a different route through the open sides of letter shapes and
learns the useful direction for a script from samples, is where we would
start.

It does not look for pages that are upside down. A half turn leaves the
lines running across, so the first measurement passes it, and we never
act on the second for a page that already reads across. A microfilm
camera does not film a book upside down by accident, and we have not
seen one, but the measurement is there if a collection needs it.

And it is a rule, not a model, with everything that implies. It will not
get better with more data. It knows nothing about the shapes of letters.
What it knows is where the ink is, which is enough for this question, and
it will give the same answer tomorrow.

## Further reading

### Page orientation and skew

- Wolfgang Postl, "Detection of linear oblique structures and skew scan
  in digitized documents", *Proceedings of the 8th International
  Conference on Pattern Recognition*, 1986, pp. 687–689. The
  projection-profile method: sum the image along lines at a candidate
  angle and take the angle at which the profile's variance is greatest.
  Our first measurement is this with two candidate angles.
- Henry S. Baird, "The skew angle of printed documents", *Proceedings of
  the SPSE Symposium on Hybrid Imaging Systems*, Rochester, NY, 1987,
  pp. 21–24. The other classic skew estimator, working from the
  alignment of connected components rather than from profiles.
- Jonathan J. Hull, "Document image skew detection: survey and annotated
  bibliography", in *Document Analysis Systems II*, World Scientific,
  1998, pp. 40–64.
  [doi:10.1142/9789812797704_0003](https://doi.org/10.1142/9789812797704_0003).
  The survey of the field as it stood: projection profiles, Hough
  transforms, nearest-neighbour clustering, and their failure modes.
- Robert S. Caprari, "Algorithm for text page up/down orientation
  determination", *Pattern Recognition Letters* 21, 2000, pp. 311–317.
  [doi:10.1016/S0167-8655(99)00161-0](https://doi.org/10.1016/S0167-8655(99)00161-0).
  Up from down by the ascender and descender asymmetry of the projection
  profile. The second measurement is Caprari's idea; the care needed in
  bounding each line is ours.
- Hrishikesh B. Aradhye, "A generic method for determining up/down
  orientation of text in Roman and non-Roman scripts", *Pattern
  Recognition* 38, 2005, pp. 2114–2131.
  [doi:10.1016/j.patcog.2004.12.011](https://doi.org/10.1016/j.patcog.2004.12.011).
  Orientation from which way the open sides of letter shapes face, with
  the useful direction learned per script from samples with known
  orientation. The route to take for Armenian.
- Joost van Beusekom, Faisal Shafait and Thomas M. Breuel, "Combined
  orientation and skew detection using geometric text-line modeling",
  *International Journal on Document Analysis and Recognition* 13,
  2010, pp. 79–92.
  [doi:10.1007/s10032-009-0109-5](https://doi.org/10.1007/s10032-009-0109-5).
  Fits a geometric model of each text line and reads orientation and
  skew from the fit; a more principled relative of the ascender measure,
  with a review of the methods before it.
- Ranjith Unnikrishnan and Ray Smith, "Combined orientation and script
  detection using the Tesseract OCR engine", *Proceedings of the
  International Workshop on Multilingual OCR (MOCR '09)*, Barcelona,
  2009, pp. 1–7.
  [doi:10.1145/1577802.1577809](https://doi.org/10.1145/1577802.1577809).
  What `--psm 0` does: a shape classifier trained on synthetic renderings
  of each script, scored over connected components in each of four
  orientations. The learned alternative to what we built.

### Separating ink from paper

- Jaakko Sauvola and Matti Pietikäinen, "Adaptive document image
  binarization", *Pattern Recognition* 33, 2000, pp. 225–236.
  [doi:10.1016/S0031-3203(99)00055-2](https://doi.org/10.1016/S0031-3203(99)00055-2).
  Thresholding each pixel against its own neighbourhood rather than the
  page, which is what lets shading and gutters drop out. Our ink score is
  the same idea kept continuous.

### Standards, formats and tools

- International Organization for Standardization, *ISO 6199:2005,
  Micrographics — Microfilming of documents on 16 mm and 35 mm
  silver-gelatin type microfilm — Operating procedures*, second edition.
  [iso.org](https://www.iso.org/standard/27582.html). The operating
  standard for the cameras that made these reels, including the
  orientation of images on the film.
- Camera & Imaging Products Association, *CIPA DC-008-2026, Exchangeable
  image file format for digital still cameras: Exif Version 3.1*, 2026.
  [cipa.jp](https://www.cipa.jp/e/std/std-sec.html). The Exif standard,
  including the Orientation tag that twenty-one of our frames carried
  and the rest did not.
- Pillow documentation:
  [`ImageOps.exif_transpose`](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose),
  which applies that tag and removes it;
  [`Image.draft`](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.draft),
  which loads a JPEG at a half, quarter or eighth of its size; and the
  [JPEG format notes](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg),
  which cover the `comment` save option and the `info["comment"]` field
  we use to stamp each derivative with its rotation.
- Tesseract documentation,
  [Improving the quality of the output](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html),
  which lists the page segmentation modes, including mode 0, orientation
  and script detection only.
- PaddleOCR documentation,
  [Text line orientation classification](https://www.paddleocr.ai/main/en/version3.x/module_usage/textline_orientation_classification.html),
  the trained classifier that PaddleOCR 3 runs on each detected line.
