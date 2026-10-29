---
title: "Armenian text recognition"
kicker: "Open source"
standfirst: "A recogniser we trained ourselves for printed Armenian, published as a small library that adds the language to EasyOCR, with the model, the word list and the training data in the open."
description: "tetrak-easyocr-armenian: an open-source Armenian OCR model for EasyOCR, trained on proofread Armenian texts, reading Eastern and Western Armenian in either orthography. Weights on Hugging Face, Apache 2.0."
---

## What it is for

Most OCR (optical character recognition) software reads Armenian badly or
not at all. The free engines either have no Armenian model, or have one
trained on so little that a page of a 1950s encyclopedia or a diaspora
newspaper comes back half wrong. A collection with Armenian books, pamphlets
and periodicals in it cannot be searched by its contents until something can
read them.

This recogniser is our answer. It reads printed Armenian well enough to make
a scanned page findable, and it is free to install, free to fork and free to
retrain.

## Who it is for

Libraries, archives and community collections with Armenian-language
holdings; anyone building a digitisation workflow that has to handle
Armenian; and researchers who want a recogniser they can measure, retrain or
extend. If you already use [EasyOCR](https://github.com/JaidedAI/EasyOCR),
it is one `pip install` away. If you use
[Tetrak OCR]({{< relref "/ocr" >}}), it is already the engine behind the
`easyocr-hy` backend.

## What it does today

- **Reads printed Armenian** across the full alphabet, the և ligature,
  Armenian punctuation, digits and the Latin letters that mixed pages carry.
  Detection, finding the lines on the page, is EasyOCR's own; reading them
  is what was missing.
- **Both the Eastern and the Western language, in either spelling.** The
  training corpus runs from the Armenian Soviet Encyclopedia to literary
  editions in both dialects, so it has seen the reformed orthography used in
  Armenia and the classical one the diaspora kept.
- **Corrects itself with a word list.** An optional list of 1.1 million
  Armenian word forms lets the model fix a word it misread by one letter,
  when the right word was its own second choice.
- **Folds look-alike letters.** The model sometimes writes a Latin letter
  for its Armenian twin; a helper puts the Armenian back without touching
  the Latin text on the same page.
- **Ships with its provenance.** Every release carries a record of the data,
  fonts, training settings and checksums that produced it, and the training
  data itself is published.

How well it reads is measured on held-out pages from eight kinds of printed
Armenian, against every other Armenian engine we can run. The numbers, and
the kinds of page it still trails on, are in the articles below and on the
[model card](https://huggingface.co/tetrak/easyocr-armenian); we do not copy
them into prose, where they would go stale.

## What it does not do yet

- **Handwriting.** It reads print. Manuscripts and handwritten letters are a
  different model, not yet trained.
- **Layout.** It reads lines; it does not reconstruct columns, tables or
  reading order. Tetrak OCR handles the ordering when the recogniser runs
  inside it.
- **Other scripts.** Georgian and Syriac recognisers are where we would like
  to go next; they do not exist yet. Our
  [transliteration library]({{< relref "/translit.md" >}}) already handles
  those scripts for search.
- **Perfect pages.** It is alpha software and some registers of print still
  defeat it. The model card says which.

## Get it

```bash
pip install tetrak-easyocr-armenian
```

```python
import tetrak_hy

reader = tetrak_hy.reader()          # an easyocr.Reader, Armenian-ready
results = reader.readtext("scan.png")
```

Inside Tetrak OCR, `pip install "tetrak[armenian]"` installs the same model
as the `easyocr-hy` backend. The weights download on first use and are
checked against the release's checksum every time they load.

| | |
|---|---|
| Code | [github.com/scattercode/tetrak-easyocr-armenian](https://github.com/scattercode/tetrak-easyocr-armenian) |
| Package | [tetrak-easyocr-armenian on PyPI](https://pypi.org/project/tetrak-easyocr-armenian/) |
| Model and word list | [tetrak/easyocr-armenian on Hugging Face](https://huggingface.co/tetrak/easyocr-armenian) |
| Training data | [tetrak/armenian-ocr-crops on Hugging Face](https://huggingface.co/datasets/tetrak/armenian-ocr-crops) |
| Trainer | [github.com/scattercode/tetrak-hy-trainer](https://github.com/scattercode/tetrak-hy-trainer), to retrain it or train a recogniser for another script |
| Licence | Apache 2.0 for the code and the model; the word list is CC BY-SA 4.0 because of its sources |

## Articles about it

The story of the model, newest first, with the measurements that go with
each step.

- [Beating the baselines, starting with our own ruler]({{< relref "/articles/2026/10/2026-10-02-beating-the-baselines.md" >}}):
  how v6 came to lead the other engines, and the metric mistake found on the
  way.
- [When your training set has read your test set]({{< relref "/articles/2026/10/2026-10-06-when-your-training-set-has-read-your-test-set.md" >}}):
  keeping the evaluation honest.
- [Telling classical from reformed Armenian by counting one letter]({{< relref "/articles/2026/10/2026-10-11-classical-or-reformed-armenian-by-one-letter.md" >}}):
  the two spellings, and how to tell them apart.
- [The engine we had left out]({{< relref "/articles/2026/09/2026-09-24-the-engine-we-had-left-out.md" >}})
  and [The comparison we had been putting off]({{< relref "/articles/2026/09/2026-09-04-the-comparison-we-had-been-putting-off.md" >}}):
  every Armenian engine we can run, measured on the same pages.
- [Built to be forked]({{< relref "/articles/2026/09/2026-09-04-built-to-be-forked.md" >}}):
  how to pick up the trainer and the library.
- [The Armenian recogniser learns both dialects]({{< relref "/articles/2026/09/2026-09-03-armenian-recogniser-both-dialects.md" >}})
  and [Shipping the Armenian recogniser]({{< relref "/articles/2026/09/2026-09-01-shipping-the-armenian-recogniser.md" >}}):
  the first versions, and what the language taught the model.
- [Armenian OCR: the engines, the numbers, and our first training run]({{< relref "/articles/2026/08/2026-08-30-armenian-ocr-measured.md" >}}):
  where it started.
