---
title: "{{ replaceRE "^[0-9]{4}-[0-9]{2}-[0-9]{2}-" "" .Name | replaceRE "-" " " | humanize }}"
date: {{ .Date }}
draft: true
slug: ""
kicker: ""
standfirst: ""
author: stephen-masters
tags: []
---

<!--
  The title strips the filename's date prefix and humanises the rest. Both
  passes are replaceRE rather than replace: replace takes its input first, so
  piping into it makes the hyphen the input and the name the replacement, and
  the archetype fails on an empty title rather than producing a wrong one.

  The URL comes from `slug`, and an empty `slug` falls through to the *title*,
  not the filename -- so a long title becomes a long URL. Leave it empty when
  the title is short; set it when the title is a sentence. The filename's own
  slug never reaches the URL; it is there so the directory sorts.

  An HTML comment rather than a Go template one. An archetype is rendered when
  the file is created, so a Go template comment leaves nothing behind and none
  of this would reach the article -- and for the same reason nothing in here can
  use template syntax, because it would be executed rather than copied.

  The directory must match the date. The published URL takes its year and month
  from `date`, not from the path, so a file filed under 2026/09/ with an August
  date publishes at /articles/2026/08/ and only the directory listing disagrees.

  slug        The last URL segment. Empty means "use the title". Set it for a
              long title -- the URL is permanent and the title is not.
  kicker      The small mono label above the title: this article's beat, in a
              word or two. "Progress", "The field", "Method".
  standfirst  One or two plain sentences, no markdown. It is the lead paragraph
              here, the summary in the listing and on the tag pages, and the
              page's meta description.
  author      A key from data/authors.toml, not a name. A missing or unknown
              key fails the build.
  tags        Lowercase and hyphenated. A new tag needs no code.

  British English. Sentence case headings. Two hashes is the top level in the
  body -- one is the title, rendered by the template.

  Link to other pages with the relref shortcode rather than a path, and use the
  figure shortcode for images rather than raw markdown. Numbers belong in the
  research pages, which read them from the benchmark CSV; an article may point
  at a figure and argue about it, but must not carry a copy of one.

  CLAUDE.md, under "Adding things", has the rest. Delete this comment.
-->

Opening paragraph.

## First section

Body copy.
