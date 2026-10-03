# Prompts for the generated diagrams

The two illustrations in this directory came from Gemini Notebook. Image models
are not deterministic and have no "change this one word" operation, so
regenerating produces a different picture rather than a corrected one. That has
bitten this project three times: a panel labelled `hospital/` after the queue
was renamed to triage, a claim that fan-out ran *concurrently* when it never
has, and a title reading "Ephemera OCR" after the product became Tetrak OCR.

**Because of that, these prompts are written to be re-run, not to reproduce.**
Detail reduces variance — composition, palette, panel count and exact strings
all constrain the model — but two runs of the same prompt will still differ.
Treat a regeneration as a new commission that has to be checked against the
code, not as an edit.

For a one-word correction, editing the existing PNG in an image editor is the
reliable route. Regenerate only when the content itself has changed.

---

## how-tetrak-ocr-works.webp

> A six-panel infographic in the style of a 1900s engineering-manual plate,
> drawn as cross-hatched pen-and-ink line art with flat colour fills. Palette
> strictly: warm cream paper `#f7f3ec` ground, deep navy `#1e3a5f` for the
> heading band and line work, muted gold `#b08d4f` for metal and highlights,
> soft grey-blue `#5d7186` for machinery. No gradients, no drop shadows, no
> photographic texture.
>
> Title band across the top, navy, reversed-out cream serif type:
> **"How Tetrak OCR Works:"** with a smaller gold subtitle beneath,
> **"A Pipeline for the Unruly Archive"**.
>
> Below it, six panels in two rows of three, each a thin gold-ruled rectangle
> containing an illustration above a bold serif numbered caption and two lines
> of smaller body text. The panels, in order:
>
> 1. **Ingestion Desk** — a Victorian writing desk stacked with loose scans and
>    floating file labels reading TIFFs, JPEGs, PNGs, PDFs, feeding a folder
>    marked `workspace/scans/`. Caption: "Historical scans are gathered into the
>    workspace/scans/ directory."
> 2. **Optical Calibration** — a brass dial gauge and a slider marked
>    CONTRAST CONFIGURATION, beside a magnifier over a pixelated page. A label
>    reads `analyse_image()`. Caption: "Pixel intensity and dark ratio set the
>    contrast and page-segmentation mode."
> 3. **Sequential Scribe Evaluation** — a CPU chip and RAM stick wired to three
>    gears turning one after another, each labelled Engine 1, Engine 2,
>    Engine 3, with a clock. Caption: "Engines run sequentially to protect CPU
>    and RAM from contention."
> 4. **Lexical Jury** — a brass twin-dial instrument panel: two round gauges
>    side by side, each needle resting in a shaded band at the upper end of its
>    arc. The left dial is lettered **"REAL WORDS"**, the right **"READS LIKE
>    LANGUAGE"**. A small engraved plate beneath the pair reads **"BOTH MUST
>    REGISTER"**. Caption: "Real words and natural word order, checked without
>    a reference transcript."
> 5. **The Triage Desk** — an archivist at a desk with a magnifier over a sheet
>    stamped `< 0.10`, beside a signpost carrying exactly two signs: the upper
>    reading MANUAL REVIEW, the lower CLAUDE API ESCALATION, and no third sign.
>    Caption: "Anything below the quality floor is held for a person to decide."
> 6. **Finished Archive** — stacked archive boxes labelled `workspace/processed/`, one
>    open with filed papers. Caption: "Clean Markdown is filed beside the
>    original scan."
>
> British English throughout. No watermark. 16:9.

**Check after every regeneration**, because these have each been wrong once:

- Panel 3 says **sequentially**, never "concurrently" or "in parallel"
- Panel 5 says **Triage**, never "hospital"
- The threshold reads **0.10**, matching `MIN_QUALITY_THRESHOLD` in `qa_score.py`
- The title reads **Tetrak OCR**
- Spelling is British: "analyse", not "analyze"
- Panel 5 carries **two** signs, not three. "Two signposts reading X and Y" was
  read as two posts plus two labels and produced a duplicated MANUAL REVIEW;
  naming the count and the position of each sign fixed it
- **Panel 4 shows no formula.** Three regenerations each produced
  "Score = Coverage x Perplexity", which is backwards — `combined_score` is
  `dict_coverage x (1 / log1p(perplexity))`, so higher perplexity *lowers* the
  score. The arithmetic belongs in prose, where it can be corrected.
- **Panel 4 is not a balance.** The earlier plate weighed a dictionary against
  a stack of perplexity blocks, which says the two signals trade off against
  each other. They do not: the score is a product, so coverage of zero gives
  zero however fluent the text reads. Two dials that must both register is the
  honest picture. What each catches is the reason there are two: dictionary
  coverage catches real letters that are not real words, and perplexity catches
  real words in an order that means nothing — which is exactly how the Vision
  backend fails on newsprint, recovering 0.88 of the words at 0.12 character
  similarity.

## custodian-of-the-forgotten.webp

> A single wide illustration in the same engraved style and palette as above.
> A navy title band reads **"Custodian of the Forgotten"**. Four claims are
> arranged around a bench of archival material — postcards, a theatre handbill,
> an open manuscript journal — with a magnifier picking one out:
>
> 1. **Historical archives are inherently unruly.** Postcards, handbills and
>    journals lack the uniform structure standard OCR engines expect.
> 2. **Routing beats picking a single engine.** Local engines run over each
>    file and their transcripts are compared, drawn as a rack of labelled
>    gears fed by branching pipes.
> 3. **Processing stays on your machine**, drawn as a server inside a shield
>    with a padlock.
> 4. **A quality gate protects the archive**, drawn as two outputs: a folder
>    marked CLEAN DATABASE and a bucket marked TRIAGE.
>
> No watermark. 16:9.

**Check after every regeneration:**

- The bucket says **TRIAGE**
- Any engine count is honest: five local backends ship, and `auto-local` fans
  out over the *eligible* ones — five at most for an image, two for a PDF
- Any privacy claim is qualified. Fan-out is local-only, but the Claude backend
  does send material off the machine. It is opt-in; `--backend` defaults to
  `tesseract`. "Never leaves your machine" is false as an unqualified claim
  about the product.

---

## custodian-of-the-forgotten.webp — Adobe Firefly

Same job as the Gemini Notebook version: a high-level introduction to what the
tool is, carrying four claims in the image itself.

Quote every string in the prompt, exactly as it should appear. An image model
given a described label invents its own wording; given a quoted one it usually
attempts that wording. Firefly renders the short labels well and the paragraphs
unreliably — see the fallback below when it garbles them.

### Settings

| Field | Value |
|---|---|
| Aspect ratio | Widescreen (16:9) |
| Content type | Art |
| Style reference | the existing `custodian-of-the-forgotten.webp`, strength ~65 |
| Effects | *Engraving*, *Vintage* |
| Exclude | `watermark, signature, logo, photorealism, 3D render, gradient background, lorem ipsum, garbled text` |

### Prompt

> A wide 19th-century engraved **infographic poster** on warm parchment
> #f7f3ec, in fine cross-hatched sepia line work, with clearly legible printed
> captions throughout, set in a classical serif face.
>
> A deep navy #1e3050 band runs across the top, with the title lettered in
> cream: **"Custodian of the Forgotten"**.
>
> Below it, four captioned stages flow left to right, joined by thin
> antique-brass #b08d4f arrows that branch and rejoin.
>
> **Stage one, far left:** a heap of unruly archival material — a stamped
> postcard, a theatre handbill, an open handwritten journal, torn newsprint —
> lit by a brass magnifier. Heading beneath: **"Historical archives are
> inherently unruly."** Caption beneath that: *"Postcards, handbills and
> journals lack the uniform structure standard OCR engines expect."*
>
> **Stage two, upper right:** a slate-blue #5d7186 machine rack of five bays,
> each holding a brass gear, labelled along the front **"Tesseract"**,
> **"EasyOCR"**, **"PaddleOCR"**, **"Marker"**, **"Vision"**. Arrows fan into
> the bays from above and converge below into one line. Heading: **"Routing
> beats picking a single engine."** Caption: *"The eligible local engines each
> read the file; the best transcript is kept."*
>
> **Stage three, lower centre:** a heraldic shield in slate-blue outline
> containing a server tower with a brass padlock. Heading: **"Processing stays
> on your machine."** Caption: *"The Claude backend is the one exception, and
> it is opt-in."*
>
> **Stage four, lower right:** the line splits a final time into two outcomes —
> a folder bearing a brass tick, labelled **"CLEAN DATABASE"**, and a metal
> bucket of crumpled question-marked sheets, labelled **"TRIAGE"**. Heading:
> **"A quality gate protects the archive."** Caption: *"Anything below the
> quality floor is held for a person to decide."*
>
> Flat 2D illustration, even diffuse light, precise and unhurried.

### Fallback when the paragraphs come out garbled

Firefly is reliable on the title, the five rack labels and CLEAN DATABASE /
TRIAGE, and unreliable on the four sentence-length captions. If they come back
as nonsense, regenerate with the captions dropped from the prompt — keep the
headings — and set the four captions as live text in Adobe Express or
Illustrator over the result. That is also the more maintainable arrangement:
these captions have been factually wrong three times, and live text is
correctable where a raster is not.

**Check after every regeneration** — the list at the top of this file, plus:

- The privacy claim is qualified. The current PNG reads "Confidential archival
  material never leaves your machine", which is false as written: the Claude
  backend sends it off. This error keeps returning.
- No engine count appears in the copy. Five local engines ship, and
  `auto-local` fans out over the *eligible* ones — five at most for an image,
  two for a PDF. Eligibility is per file and per machine: Marker needs a GPU,
  Vision is macOS-only, and neither Vision, EasyOCR nor Paddle reads a PDF. A
  bare "five" reads as "five run on every file". The rack labels are an
  inventory, not a route.
- No generator watermark. The current PNG carries a "Gemini Notebook" mark.
