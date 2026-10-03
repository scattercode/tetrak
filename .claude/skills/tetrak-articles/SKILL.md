---
name: tetrak-articles
description: Write, edit or publish an article on the Tetrak documentation site (site/content/articles/). Covers the archetype and front matter, how the URL is actually assembled, the author key, the standfirst's three jobs, tags, relref linking, and the rule that benchmark numbers never get transcribed into prose. Use this whenever writing or editing anything under site/content/articles/, adding a byline or an author, creating a tag, or asking where an article's URL comes from.
---

# Writing an article for tetrak.dev

`site/content/articles/` is the site's writing: the state of archive
digitisation and OCR, and progress notes on the pipeline and the Armenian
EasyOCR model. Reference material belongs under `site/content/reference/` and
research under `site/content/research/` — an article argues, it does not
document.

## Creating one

```bash
cd site && hugo new articles/<year>/<month>/<YYYY-MM-DD>-<slug>.md
```

Files are filed by year and month; they publish flat at
`/articles/<year>/<month>/<slug>/`.

**The date directories are deliberately not sections.** They hold no
`_index.md`, and adding one would publish a second, unstyled index of the same
articles at `/articles/<year>/`.

## Two things about the URL that are easy to get wrong

**The year and month come from `date`, not from the path.** A file misfiled by
a month still publishes correctly; only the directory listing disagrees with
the URL.

**The last segment comes from `slug`, which falls through to the *title* when
empty — not to the filename.** So a sentence-length title becomes a
sentence-length URL unless `slug` is set. The filename's own slug never
reaches the URL at all; the date prefix on the filename exists so the
directory sorts.

Set `slug` explicitly on every article.

## Front matter

`title`, `date`, `slug`, `kicker`, `standfirst`, `author`, `tags`. The
archetype at `site/archetypes/articles.md` says what each is for and is worth
reading once.

Two are load-bearing:

- **`author` is a key from `site/data/authors.toml`, not a name.** A missing
  or unknown key fails the build, so a mistyped byline cannot ship. Add the
  person to that file before crediting them.
- **`standfirst` does three jobs** — the lead paragraph on the article, the
  summary in the listing and on tag pages, and the page's meta description.
  One or two plain sentences, no markdown, no trailing full stop.

## Tags

A new tag needs no code: the term page and the tag index are generated from
the taxonomy. Tags are lowercase and hyphenated, and `capitalizeListTitles =
false` in `hugo.toml` keeps them that way on their own pages.

(This differs from scattercode.dev, where each tag needs a CSS class for its
colour dot. Do not port that habit here.)

## Linking

Link to other pages with `{{< relref "/path" >}}`, never a relative or
absolute path. An article sits four directories deep, so a relative link is
unreadable; an absolute one breaks the day the site is served from a
subdirectory; and relref resolves through the page, so a moved target **fails
the build** instead of publishing a 404.

## Numbers stay in the research pages

The research pages read their figures from `evaluation/ocr/benchmark.csv` at
build time and so cannot disagree with the harness. An article may point at a
figure and argue about what it means; it must **not** carry a transcribed copy
of one.

This is not a style preference. The slide deck carried transcribed numbers and
disagreed with the harness within a fortnight — nothing failed, and nobody
noticed until the two were read side by side. Cite and link; do not retype.

## Voice

- First person plural: "we", not "I". Tetrak is a shared project and its
  articles narrate the project's work rather than one person's — the
  `author` front matter field still credits whoever wrote the piece, but
  the prose voice is "we" throughout, including for work one person did
  alone. This is the opposite of scattercode.dev's rule, where posts are
  one author writing as "I"; don't carry that habit over here.
- British English throughout; sentence case for headings.
- `##` for top-level headings, `###` for sub-headings. Never `#` — that level
  is the page title, rendered by the template.
- Assume a competent reader. Long-form is fine; depth beats brevity.

## Before it ships

```bash
cd site && npm run build          # relref failures and unknown author keys surface here
cd site && npm run lint           # markdownlint over the content
cd site && npx playwright test    # starts its own server
```

Publishing an article also updates `/articles/index.xml`, the site's only
feed, which is advertised from the `<head>` of every page — so a broken
article breaks the feed.

Load the `tetrak-ocr-design` skill before touching layouts, styles or
shortcodes; this skill covers content only.
