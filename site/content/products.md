---
title: "Products"
kicker: "Open source"
standfirst: "Three tools, free and open source. Each works on its own, on your own machine, without us."
description: "Tetrak's open-source tools: Tetrak OCR for turning scans into searchable text, the Armenian text recogniser, and tetrak-translit for transliteration and cross-script search."
---

Everything here is published under an open licence, with the code, the
trained models and the training data in the open. Install any of them with
`pip`, read the documentation, and use them as you like; nothing phones home
and nothing needs an account. If you would rather we did the work, that is
what [our services]({{< relref "/services.md" >}}) are for.

<div class="grid cards">

-   **[Tetrak OCR]({{< relref "/ocr" >}})**

    Turns scans of old print into searchable text. It runs several OCR
    (optical character recognition) engines over each file, keeps the best
    reading, and sets aside anything it cannot trust for a person to check.
    Local first: no material leaves your machine unless you send it.

-   **[Armenian text recognition]({{< relref "/armenian-ocr.md" >}})**

    A recogniser we trained ourselves for printed Armenian, Eastern and
    Western, in either spelling. Installs as an add-on to EasyOCR, or as
    Tetrak OCR's Armenian engine, with the model and its training data
    published alongside.

-   **[Transliteration and cross-script search]({{< relref "/translit.md" >}})**

    Detects the script, writes it in Latin letters by a named library
    standard, and folds every spelling of a name to one form for searching.
    Armenian, Georgian, Russian and Syriac so far.

</div>
