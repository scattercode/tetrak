# Corpus expansion candidates

Draft findings for expanding the OCR test corpus beyond the current nine
items, still on the theme of **the Los Angeles stage and its picture
palaces, c. 1910–1945**. Sourced from the same four places already used
(Internet Archive/MHDL, Digital Commonwealth/BPL, Wikimedia Commons/Library
of Congress, USC Digital Library), plus a look at Chronicling America, which
`SOURCES.md` had already flagged as a gap.

None of these have been downloaded or added yet — this is a shortlist for
you to review and pick from. Two caveats apply across the board:

- Where a candidate's rights are marked "CC BY 3.0" rather than a bare
  public-domain-by-date claim, that's a real difference: it needs an
  attribution line, unlike the plain PD items already in the corpus.
- A few items (marked below) were confirmed to exist and matched on rights
  and metadata, but the image itself couldn't be loaded from this session —
  worth a quick look before committing to one.

## Status, 21 August 2026

Nine of these are now in the corpus; `SOURCES.md` is the catalogue of record
for them and carries the rights reasoning and every modification. Rows below
are marked **[in corpus]** or **[not fetched]** with the reason.

| Outcome | Items |
|---|---|
| **Fetched** | *Camera!*, *The Film Mercury*, *The Film Spectator*, all four Tichnor postcards, all four Library of Congress posters |
| **Blocked** | The *Los Angeles Herald* page — `loc.gov` still answers 403 to anything scripted, so it needs the by-hand browser download `SOURCES.md` already describes |
| **Not scriptable** | Everything at USC. `digitallibrary.usc.edu` is a JS-rendered CONTENTdm instance and the Calisphere mirror exposes only a thumbnail host, which is far too small to OCR |
| **Left deliberately** | The minstrelsy poster, which is your call and not one to make by default; and *Camera!* Vol. 3, which duplicates the volume already held |

**On what to look for next.** This shortlist was scoped to the Los Angeles
theatre theme, because that is what the *published* walkthrough set holds to.
The wider corpus is not bounded that way — see the opening of `SOURCES.md`.
That gap — the plainest material imaginable, black text on white in one column
— was closed on 21 August 2026, outside this list: a Dickens page, a 1952 NACA
technical note and a 1924 small-town newspaper, all from the Internet Archive
and all recorded in `SOURCES.md`. A future search should not be thematic.

The four USC photographs carry a second reason to pause: they are **CC BY 3.0**,
so they would need an attribution line. Every item in the corpus today is public
domain with no attribution requirement, and `SOURCES.md` says so in its opening
paragraph. Adding them changes that sentence.

## Priority: fills a documented gap

The existing `SOURCES.md` notes two open gaps: no genuine multi-page
archival TIFF, and no Chronicling America item despite the *Los Angeles
Herald* being an obvious fit. These two candidates target those directly.

| Item | Date | Source | Rights | Why it fills the gap |
|---|---|---|---|---|
| **[not fetched — USC not scriptable]** Lambardi Pacific Coast Grand Opera Company — tickets and programmes (a pair of pamphlets plus a partially-used ticket book, for a run at LA's Auditorium Theatre) | Dec 1912 – Jan 1913 | Workman and Temple Family Homestead Museum Collection, via USC Digital Library / Calisphere: `calisphere.org/item/7d16978d2fccf2f56220890468ca3b75` | Pre-1931 US publication — public domain on date alone, same reasoning as the existing playbill | Genuinely multi-item, multi-page ephemera (two pamphlets + a ticket booklet with unused stubs) — the corpus's two TIFFs are both single-frame, so this is the strongest lead for closing that gap. Not yet visually confirmed — the USC/Calisphere page wouldn't render in this session; worth checking directly before use. |
| **[not fetched — loc.gov 403]** *Los Angeles Herald*, 25 July 1910, page 4 | 25 Jul 1910 | Chronicling America (Library of Congress): `chroniclingamerica.loc.gov/lccn/sn85042462/1910-07-25/ed-1/seq-4/` | US newspaper published 1910 — clearly public domain | Matched repeatedly across independent theatre/vaudeville keyword searches against this specific page, suggesting real content there. Same bot-protection wall as before: cannot be fetched programmatically, needs a manual download through a browser, exactly as `SOURCES.md` already describes for the Kinema ad. |

Two fallback dates if the July 1910 page doesn't pan out on inspection —
same paper, same LCCN, both hit repeatedly on theatre-keyword searches, but
sit just before the 1910–1945 window: 13 June 1908 p.5
(`.../1908-06-13/ed-1/seq-11/`) and 24 June 1908 p.6
(`.../1908-06-24/ed-1/seq-12/`). Note also: this title's Chronicling America
run stops in November 1911 (it merges into the *Evening Herald* after
that), so nothing later is available under this masthead.

## Internet Archive / Media History Digital Library

Three more LA/Hollywood trade papers, each with a visually distinct
masthead and layout from *Inside Facts* (already in the corpus) and from
each other, so they'd add variety to the multi-column-newsprint failure
mode rather than duplicating it:

| Item | Date | Source | Rights |
|---|---|---|---|
| **[in corpus]** `camera-1919.pdf` — *Camera!* — "the digest of the motion picture industry" | 1919–1920 | `archive.org/details/camera1919losa` (Vol. 2); alternate Vol. 3 (Apr 1920) at `archive.org/details/camera03unse` | Published 1919–1920 — expired |
| **[in corpus]** `film-mercury-1928.pdf` — *The Film Mercury*, Hollywood | 1928–1929 | `archive.org/details/filmmercury1928100merc` | Published 1928–1929 — within the pre-1931 safe-harbour reasoning already used for *Inside Facts* |
| **[in corpus]** `film-spectator-1927.pdf` — *The Film Spectator*, Hollywood (Welford Beaton's film-criticism journal — running prose rather than classified-style layout) | 1927–1928 | `archive.org/details/filmspectator19200film` | Published 1927–1928 — expired |

No genuine multi-page TIFF turned up on archive.org for this theme — MHDL
periodicals are all delivered as single-page JP2/PDF stacks, never a native
multi-frame TIFF, so that gap has to come from elsewhere (see the Lambardi
item above).

Checked and set aside: a 1923 *Ten Commandments* souvenir programme (public
domain, but no confirmed LA/Grauman's tie, and it's the same genre as the
*King of Kings* item already in the corpus); *Variety* issues around the
May 1927 Grauman's Chinese opening (loads fine, but a full-text check found
no actual mention of Grauman's or the Chinese Theatre, and *Variety* is
NY-published/national rather than LA-specific).

## Digital Commonwealth / Boston Public Library (Tichnor postcards)

A direct-name search for other well-known LA venues — Pantages, Egyptian,
Warner Hollywood, El Capitan, Million Dollar, the Los Angeles Theatre,
Orpheum, Loew's State — turned up nothing in BPL's holdings; their Tichnor
collection just doesn't cover those. What it does have:

| Item | Date | Source | Rights | Note |
|---|---|---|---|---|
| **[in corpus]** `chinese-theatre-triptych-postcard.jpg` — Triptych postcard: The White House / Lincoln Memorial / **The Chinese Theatre, Hollywood** (three landmarks, one card) | c. 1930–45 | `digitalcommonwealth.org/search/commonwealth:8g84n2077` | "No known copyright restrictions" | Three separate caption lines under three sub-images — a different layout challenge from the single-caption postcards already in the corpus |
| **[in corpus]** `hollywood-boulevard-east.jpg` — "Looking east on Hollywood Boulevard" (1 of 2) | c. 1930–45 | `commonwealth:2n49tg34w` | as above | Street scene through the theatre district — small/distant signage rather than one dominant marquee |
| **[in corpus]** `hollywood-boulevard-west.jpg` — "Looking west on Hollywood Boulevard" (2 of 2) | c. 1930–45 | `commonwealth:2n49tg30s` | as above | Companion angle to the above |
| **[in corpus]** `greek-theatre-night.jpg` — Night scene, Greek Theatre, Griffith Park | c. 1930–45 | `commonwealth:2n49tg487` | as above | Marginal fit — this is the open-air amphitheatre, not a picture palace, and it's a low-light/high-contrast scene, which is the main reason to consider it |

None of these image files could be loaded from this session (network
policy blocked the IIIF and BPL blob-storage hosts), so treat the
marquee/caption legibility as unconfirmed until you've had an actual look.

## Wikimedia Commons / Library of Congress theatrical poster collection

No confirmed Commons item ties directly to an LA venue by name (searched
Orpheum, Pantages, and the Federal Theatre Project's LA unit — the one WPA
LA item that turned up lives on archives.gov, not Commons). These four are
generic vaudeville/theatrical-era posters, on the same basis as the
Victorina Troupe poster already in the corpus:

| Item | Date | Source | Rights | OCR interest |
|---|---|---|---|---|
| **[in corpus]** `bancroft-magician-poster.jpg` — *Frederick Bancroft, prince of magicians — the magician's castle* | 1895 | LOC LCCN 2014636879, via Wikimedia Commons | PD Mark 1.0 / no known restrictions | Portrait-centred composition with banner text — different layout from the existing poster's arched act-name lettering |
| **[in corpus]** `thurston-magician-poster.jpg` — *Thurston the Great Magician* (Strobridge Litho. Co.) | 1910 | LOC LCCN 2014636950, via Wikimedia Commons | PD Mark 1.0 | Dense ornamented lettering crowded by illustration — a harder text/illustration segmentation test |
| **[in corpus]** `parlor-match-poster.jpg` — *Evans and Hoey's evergreen success — A parlor match, enough said!* | 1898 | LOC LCCN 2014636358, via Wikimedia Commons | PD Mark 1.0 | Large title plus a distinct small-caption line — the small-caption-text case the existing item lacks |
| **[in corpus]** `over-the-fence-poster.jpg` — *Over the fence*, by Owen Davis | 1899 | LOC LCCN 2014636511, via Wikimedia Commons | PD Mark 1.0 | Different colour palette and a separate caption line |

None of these Commons pages could be loaded directly from this session
either (proxy policy again) — corroborated instead via search snippets and
an independent PICRYL mirror carrying the same LCCN and rights statement.
Worth a manual check before committing to one.

**Flagged, not recommended:** *William H. West's Big Minstrel Jubilee*
(LCCN 2014637057) is public domain and has the ornamental lettering this
search was looking for, but depicts blackface minstrelsy caricature.
Public-domain status doesn't settle whether it belongs in a published test
corpus — that's a call for you to make deliberately rather than one worth
making by simply not mentioning it.

## USC Digital Library

Beyond the Lambardi opera set above (priority section), four more Homestead
Museum / California Historical Society photographs, all interior or
premiere-night views rather than printed ephemera — useful if you want the
corpus to include photo-with-caption material, less useful if you want more
printed-text failure modes:

| Item | Date | Source | Rights |
|---|---|---|---|
| **[not fetched — CC BY, not scriptable]** Grauman's Chinese Theatre, premiere of *Hell's Angels* | c. 1929 | `digitallibrary.usc.edu/asset-management/2A3BF1BDCZD` (Calisphere mirror: `calisphere.org/item/80e50f3086aab1c570a36f3de2fc5d45`) | CC BY 3.0 — needs attribution, weaker than a bare PD claim |
| **[not fetched — CC BY, not scriptable]** Interior, Grauman's Egyptian Theatre | undated, est. 1920s–30s | `digitallibrary.usc.edu/asset-management/2A3BF1G3JNM` | CC BY 3.0 |
| **[not fetched — CC BY, not scriptable]** Interior, Hollywood Pantages Theater auditorium | undated, est. early 1930s | `digitallibrary.usc.edu/asset-management/2A3BF1GGPP6` | CC BY 3.0 |
| **[not fetched — CC BY, not scriptable]** Interior, Hollywood Pantages Theater lobby | undated, est. early 1930s | `digitallibrary.usc.edu/asset-management/2A3BF1GG22Z` | CC BY 3.0 |

digitallibrary.usc.edu is a JS-rendered site that wouldn't load directly in
this session; the above were confirmed via the parallel Calisphere records
for the same digitised objects, which did render.

A Homestead Museum blog post mentions a Boyle Heights Spanish-language
theatre broadside (Teatro Hidalgo/Zendejas) among the museum's holdings,
which would be a nice addition for language diversity, but no digitised
USC record could be found for it — may not be online yet.

## Suggested next step

If you want to move on any of these, the ones with a clean paper trail and
no network blocker are the three Internet Archive trade papers and the
Lambardi opera set — those can most likely be fetched the same scriptable
way as the existing MHDL and USC items. The Digital Commonwealth and
Wikimedia candidates are solid on paper but need a manual look at the
actual image before you commit. The Chronicling America page needs the
same by-hand browser download the Kinema ad already required.
