---
title: "The corpus"
kicker: "Reference"
aliases: ["/evaluation/ocr/corpus/", "/research/corpus/"]
---

Nine items on a single theme — **the Los Angeles stage and its picture
palaces, c. 1910–1945** — chosen to span the failure modes that matter in
archive digitisation: multi-column newsprint, ornamental display type, clean
printed captions, photographic postcards, a multi-page PDF, and archival TIFF.

Every item is in the public domain in the United States. The rights reasoning
for each is given below, so this is a record of *why* each may be
redistributed, not just where it came from. None carries an attribution
requirement, but crediting the holding institution is good practice and costs
nothing.

Click any item to see it full size — the difficulty claimed for each is much
easier to judge against the actual page than against a description of it.

<div class="grid cards">

-   {{< lightbox src="corpus/inside-facts-1930-cover" alt="Front page of Inside Facts of Stage and Screen, 31 May 1930, a dense multi-column newspaper under a heavy display masthead" title="Inside Facts of Stage and Screen, 31 May 1930 — front page" >}}

    **Inside Facts of Stage and Screen** — front page
    31 May 1930 · `inside-facts-1930-cover.jpg`

    Heavy display masthead over dense multi-column newsprint, on aged
    low-contrast paper. The hardest common case in archive digitisation.

-   {{< lightbox src="corpus/inside-facts-1930-page-six" alt="Interior page of the same newspaper issue, multi-column body text broken up by ruled advertisement boxes" title="Inside Facts of Stage and Screen, 31 May 1930 — page six" >}}

    **Inside Facts** — page six
    31 May 1930 · `inside-facts-1930-page-six.jpg`

    Multi-column body text broken up by ruled advertisement boxes. Tests
    reading order without the masthead complicating it.

-   {{< lightbox src="corpus/kar-mi-troupe-poster" alt="Vaudeville chromolithograph poster for the Victorina Troupe sword swallowing act, with hand-lettered display type arched over an illustration" title="The great Victorina Troupe — vaudeville chromolithograph, c. 1914" >}}

    **The great Victorina Troupe** — vaudeville poster
    c. 1914 · `kar-mi-troupe-poster.jpg`

    Curved and arched hand-lettered display type, colour on colour, tiny
    caption text. Nothing local reads this.

-   {{< lightbox src="corpus/carthay-circle-premiere" alt="Linen postcard showing a world premiere at the Carthay Circle Theatre, Los Angeles, with caption text reversed out of a dark night sky" title="World Premier, Carthay Circle Theatre, Los Angeles — postcard front, c. 1930–45" >}}

    **Carthay Circle Theatre premiere** — postcard front
    c. 1930–45 · `carthay-circle-premiere.jpg`

    Caption reversed out of a dark sky over a textured linen ground.

-   {{< lightbox src="corpus/carthay-circle-postcard-back" alt="Reverse of the Carthay Circle postcard, showing text rotated ninety degrees, a faded rubber stamp, handwriting and large empty areas" title="Carthay Circle Theatre — postcard reverse, c. 1930–45" >}}

    **Carthay Circle** — postcard reverse
    c. 1930–45 · `carthay-circle-postcard-back.png`

    Text rotated 90°, a faded rubber stamp, handwriting and large empty
    areas. Clean printed type, awkwardly arranged — where free tools do well.

-   {{< lightbox src="corpus/graumans-chinese-theatre" alt="Linen postcard of Grauman's Chinese Theatre, Hollywood, a colour halftone with marquee lettering at the edge of legibility" title="The Chinese Theatre, Hollywood, California — postcard, c. 1930–45" >}}

    **Grauman's Chinese Theatre** — postcard
    c. 1930–45 · `graumans-chinese-theatre.jpg`

    Colour halftone with marquee lettering right at the edge of legibility.

-   {{< lightbox src="corpus/king-of-kings-souvenir-1927" alt="First page of The King of Kings roadshow souvenir programme, 1927, showing a tinted ground and script headings" title="The King of Kings — roadshow souvenir programme, 1927 (first page)" >}}

    **The King of Kings** — souvenir programme
    1927 · `king-of-kings-souvenir-1927.pdf`

    21-page PDF: tinted grounds, script headings, drop caps. The only
    multi-page item, and the only one EasyOCR and PaddleOCR cannot read at all.

-   {{< lightbox src="corpus/hollywood-music-box-playbill-1926" alt="Playbill for the Hollywood Music Box Theatre, a tall narrow sheet of dense small type listing a Japanese touring drama company's programme" title="Hollywood Music Box Theatre — Ken-Geki playbill, week beginning 18 June 1926" >}}

    **Hollywood Music Box** — *Ken-Geki* playbill
    18 June 1926 · `hollywood-music-box-playbill-1926.tif`

    Dense small type over a full sheet: cast lists, plot synopses and ticket
    prices at footnote size. Photographed on a dark mount, as museum holdings
    usually are.

-   {{< lightbox src="corpus/kinema-theater-ad-1920" alt="Newspaper display advertisement for the Kinema Theater, with hand-lettered headlines and body text set around a large illustration" title="Kinema Theater display ad, Los Angeles Evening Express, 2 October 1920" >}}

    **Kinema Theater** — newspaper display ad
    2 October 1920 · `kinema-theater-ad-1920.tif`

    Hand-lettered headlines, a programme column in tiny type, and body text
    flowing around an illustration. Tesseract reads 95 words of the column and
    misses the masthead entirely.

</div>

The thumbnails above are generated from the corpus by
`tools/generate_corpus_thumbnails.py` and committed, so the page renders
without a build-time dependency on poppler. They are **not** what the backends
see — OCR always runs against the full-resolution originals in
`evaluation/ocr/corpus/images/`.

## Provenance and rights

| File | Source | Rights |
|---|---|---|
| `inside-facts-1930-cover.jpg` | [Internet Archive / Media History Digital Library](https://archive.org/details/insidefacts1122-1930-05-31) | US work published 1930; copyright expired 1 January 2026 |
| `inside-facts-1930-page-six.jpg` | as above | as above |
| `kar-mi-troupe-poster.jpg` | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:The_great_Victorina_Troupe_originators_and_presenters_of_the_most_marvelous_sword_swallowing_act_on_earth._LCCN2014636914.jpg), from the Library of Congress theatrical poster collection | Library of Congress: no known restrictions on publication; published pre-1929 |
| `carthay-circle-premiere.jpg` | [Digital Commonwealth / Boston Public Library](https://www.digitalcommonwealth.org/search/commonwealth:2n49tj420) | Published without copyright notice; BPL states "No known copyright restrictions" |
| `carthay-circle-postcard-back.png` | as above | as above |
| `graumans-chinese-theatre.jpg` | [Digital Commonwealth / Boston Public Library](https://www.digitalcommonwealth.org/search/commonwealth:2n49tg32b) | as above |
| `king-of-kings-souvenir-1927.pdf` | [Internet Archive](https://archive.org/details/kingofkings00unse) | US work published 1927; copyright expired 1 January 2023 |
| `hollywood-music-box-playbill-1926.tif` | Workman and Temple Family Homestead Museum Collection, via [USC Digital Library](https://digitallibrary.usc.edu/) | US work published 1926; public domain on date alone. The museum's own note is weaker — see [`SOURCES.md`](https://github.com/scattercode/tetrak/blob/main/evaluation/ocr/corpus/SOURCES.md) |
| `kinema-theater-ad-1920.tif` | *Los Angeles Evening Express*, 2 October 1920, via a newspaper-archive export | US newspaper published 1920; public domain. The scan's producer is unidentified — see [`SOURCES.md`](https://github.com/scattercode/tetrak/blob/main/evaluation/ocr/corpus/SOURCES.md) |

The full item titles and issue details are in
[`evaluation/ocr/corpus/SOURCES.md`](https://github.com/scattercode/tetrak/blob/main/evaluation/ocr/corpus/SOURCES.md).

## Modifications

- `kar-mi-troupe-poster.jpg` was downscaled from the source 4104 × 5116 to
  1123 × 1400 so that it sits in the same resolution band as the rest of the
  set. Resolution materially changes OCR scores, so fixtures are kept
  comparable. No cropping was applied — the Library of Congress colour
  calibration bar and ruler remain in frame, which is representative of real
  archive scans.
- `carthay-circle-postcard-back.png` was converted from the source JPEG so the
  set exercises the PNG path. No resampling.
- The postcards were fetched at 1400 px wide via the Digital Commonwealth IIIF
  endpoint. Everything else is unmodified from the source.

## Notes

- **1930 is a recent public-domain entry.** *Inside Facts* fell into the public
  domain on 1 January 2026 under the US 95-year term. That is the least-aged
  item in the set by a wide margin.
- **TIFF is now covered, and testing it found a real gap.** Both TIFFs read
  correctly on every backend, so the advertised support was honest for
  single-page files. It was not for multi-page ones: Pillow opens a multi-frame
  TIFF at frame 0, so a scanned pamphlet returned its cover as though it were
  the whole document. Tesseract now reads every page, as it already did for
  PDFs; the backends that cannot refuse by name rather than truncating
  silently. See [the engines](engines/#multi-page-tiff).
- **Neither TIFF is multi-page.** Both are single-frame, so the corpus proves
  the format works and does not exercise the paging path. That is covered by
  generated fixtures in `tests/test_tiff.py` instead. A real multi-page
  archival TIFF would be a worthwhile addition.

## Refetching

Internet Archive, Wikimedia Commons and Digital Commonwealth are all
scriptable — stable download URLs, JSON APIs, no bot protection. Digital
Commonwealth images come from
`https://iiif.digitalcommonwealth.org/iiif/2/commonwealth:<id>/full/1400,/0/default.jpg`.

`loc.gov` and Chronicling America sit behind Cloudflare bot protection and
return HTTP 403 to `curl` even with a browser user-agent, so anything sourced
there has to be downloaded by hand through a browser. This is why the Library
of Congress poster is taken from the Wikimedia Commons mirror rather than
directly, and why no Chronicling America newspaper page is included despite the
*Los Angeles Herald* being an obvious thematic fit.
