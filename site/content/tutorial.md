---
title: "Tutorial"
kicker: "Using it"
---

A walk through the pipeline on real material: transcribing one image, batching
a folder, and seeing why the tool you pick changes the answer.

Assumes you have [installed](install/) the package and Tesseract.

## 1. Transcribe one file

The corpus ships with the repository, so there is something to point at
immediately.

```bash
tetrak-ocr ocr evaluation/ocr/corpus/images/carthay-circle-postcard-back.png
```

That is the reverse of a Tichnor linen postcard — printed caption text on a
plain ground, the case Tesseract handles well. You should get readable text
back.

Now the hard one:

```bash
tetrak-ocr ocr evaluation/ocr/corpus/images/kar-mi-troupe-poster.jpg
```

A vaudeville chromolithograph from about 1914, hand-lettered display type
arched over an illustration. You will get almost nothing — Tesseract scores
0.00 character similarity here. That is not a misconfiguration; it is the limit
of shape-matching OCR, and it is worth seeing directly before reading any
benchmark table.

Side by side, the reason is obvious. Click either to enlarge.

<div class="grid">

{{< lightbox src="corpus/carthay-circle-postcard-back" alt="Reverse of a Tichnor linen postcard: printed caption text on a plain ground, with a faded rubber stamp and handwriting" title="carthay-circle-postcard-back.png — tesseract 0.60/0.50, tesseract-auto 0.91/0.71" >}}

{{< lightbox src="corpus/kar-mi-troupe-poster" alt="Vaudeville chromolithograph with hand-lettered display type arched over an illustration, colour on colour" title="kar-mi-troupe-poster.jpg — tesseract 0.00/0.00, paddle 0.13/0.39 (the best any local backend manages)" >}}

</div>

Regular type on a plain ground on the left; on the right, letters drawn by hand,
curved along an arc, in colour over colour. Tesseract matches letter shapes
against trained forms, and the poster has no such forms to match.

## 2. Let Tesseract configure itself

Same engine, per-image auto-configuration:

```bash
tetrak-ocr ocr evaluation/ocr/corpus/images/carthay-circle-premiere.jpg --backend tesseract
tetrak-ocr ocr evaluation/ocr/corpus/images/carthay-circle-premiere.jpg --backend tesseract-auto
```

{{< lightbox src="corpus/carthay-circle-premiere" alt="Linen postcard of a world premiere at the Carthay Circle Theatre, with the caption reversed out of a dark night sky over a textured ground" title="carthay-circle-premiere.jpg — tesseract 0.00/0.00, tesseract-auto 0.49/0.86" >}}

On this fixture the first returns nothing (0.00/0.00) and the second works
(0.49/0.86). Look at what defeats the default: pale caption text reversed out
of a dark sky, over a textured linen ground. At default contrast the lettering
never separates from its background. `analyse_image()` inspects contrast and
layout density, then picks a page-segmentation mode and contrast factor to
match.

Tuning the engine you have is often worth more than switching engines: across
the twelve fixtures the current bands are fitted to, auto-configuration takes
Tesseract from 0.33 to 0.46 average character similarity.

## 3. Batch a folder

The pipeline's normal mode. It uses a `workspace/` directory in your current
working directory, holding one folder per stage:

```text
workspace/
  scans/       put files here
  processed/   transcripts and originals end up here
  triage/      anything that failed quality scoring
```

```bash
mkdir -p workspace/{scans,processed,triage}
cp evaluation/ocr/corpus/images/*.jpg workspace/scans/
tetrak-ocr batch --backend tesseract-auto
```

For each file you get `workspace/processed/<name>.md` holding the transcript,
with the original moved alongside it. `workspace/scans/` is left empty — the
pipeline is built so that "what is still in scans/" is a meaningful question.

### The triage queue

With `auto-local`, files whose best transcript still falls below the quality
floor never reach `workspace/processed/`:

```bash
cp evaluation/ocr/corpus/images/kar-mi-troupe-poster.jpg workspace/scans/
tetrak-ocr batch --backend auto-local
```

The poster lands in `workspace/triage/` with a manifest listing what each backend
produced and how it scored. That is the file to send to a vision model, or to a
person. The point is that bad transcripts do not quietly enter your archive
looking like good ones.

## 4. Let it choose the backend

```bash
tetrak-ocr batch --backend auto-local
```

`auto-local` runs every viable local backend over each file and keeps the
highest-scoring transcript, judged without a reference. It routes on file type
and available hardware — see [auto-local routing](reference/routing/) for the
decision table.

It averages 0.66/0.65 on this corpus, behind PaddleOCR-VL and Vision but ahead
of every other single backend, and it is among the slowest, because it runs
several engines per file.

## 5. Measure it yourself

Nothing above asks you to trust the published numbers.

```bash
tetrak-ocr evaluate --backend tesseract-auto
```

That scores each corpus image against its committed ground-truth transcript and
prints character similarity and word recall per fixture. To compare everything
installed:

```bash
tetrak-ocr evaluate --all --save
```

`--save` writes `evaluation/ocr/benchmark.{csv,md}` plus a dated, git-linked
snapshot under `evaluation/ocr/runs/`. Expect around 50 minutes for a full run with
every backend installed, most of it Marker.

{{< note kind="note" >}}
`--all` runs only the backends you have installed, and `--save` overwrites
the committed benchmark with whatever it managed to run. On a partial
install, keep the output rather than committing it.
{{< /note >}}

## What each fixture is for

Seven items, chosen to break OCR in different ways.

| | The item | The challenge |
|---|---|---|
| {{< lightbox src="corpus/inside-facts-1930-cover" alt="Front page, LA theatrical trade weekly, 1930" title="Inside Facts of Stage and Screen, 31 May 1930 — front page" >}} | Front page, LA theatrical trade weekly, 1930<br>`inside-facts-1930-cover.jpg` | Heavy display masthead over dense multi-column newsprint; aged low-contrast paper |
| {{< lightbox src="corpus/inside-facts-1930-page-six" alt="Interior page of the same issue" title="Inside Facts of Stage and Screen, 31 May 1930 — page six" >}} | Interior page of the same issue<br>`inside-facts-1930-page-six.jpg` | Multi-column body text broken by ruled advertisement boxes |
| {{< lightbox src="corpus/kar-mi-troupe-poster" alt="Vaudeville chromolithograph, c. 1914" title="The great Victorina Troupe — vaudeville chromolithograph, c. 1914" >}} | Vaudeville chromolithograph, c. 1914<br>`kar-mi-troupe-poster.jpg` | Curved and arched display type, colour on colour, tiny caption text |
| {{< lightbox src="corpus/carthay-circle-premiere" alt="Linen postcard, Carthay Circle premiere" title="World Premier, Carthay Circle Theatre — postcard front, c. 1930–45" >}} | Linen postcard, Carthay Circle premiere<br>`carthay-circle-premiere.jpg` | Caption reversed out of a dark sky over a textured ground |
| {{< lightbox src="corpus/carthay-circle-postcard-back" alt="Reverse of the same card" title="Carthay Circle Theatre — postcard reverse, c. 1930–45" >}} | Reverse of the same card<br>`carthay-circle-postcard-back.png` | Text rotated 90°, faded rubber stamp, handwriting, large empty areas |
| {{< lightbox src="corpus/graumans-chinese-theatre" alt="Linen postcard, Grauman's Chinese Theatre" title="The Chinese Theatre, Hollywood, California — postcard, c. 1930–45" >}} | Linen postcard, Grauman's Chinese Theatre<br>`graumans-chinese-theatre.jpg` | Colour halftone with marquee lettering at the edge of legibility |
| {{< lightbox src="corpus/king-of-kings-souvenir-1927" alt="Roadshow souvenir programme, 21 pages" title="The King of Kings — roadshow souvenir programme, 1927 (first page)" >}} | Roadshow souvenir programme, 21 pages<br>`king-of-kings-souvenir-1927.pdf` | Multi-page PDF, tinted grounds, script headings, drop caps |

Provenance and rights for each are on [the corpus page](reference/corpus/).

## Where next

- [Choosing a tool](research/in-depth/#choosing-a-tool-for-your-own-material) — which backend for which document, with the evidence
- [Results](research/in-depth/#the-results) — the full benchmark, including a retracted finding
- [Method](research/in-depth/#the-weakness-at-the-centre-of-the-method) — what the numbers do and do not establish
- [Python API](reference/api/) — driving the backends from code
