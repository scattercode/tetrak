"""Reference-free OCR quality metrics.

Two metrics are combined into a single score used to rank competing transcripts
produced by different OCR backends, and to decide whether a document should be
routed to the triage queue.

dictionary_coverage
    Fraction of word tokens that are recognised English words, using
    pyspellchecker (pure Python, ~100 KB, no model downloads).  Effective at
    catching non-word OCR noise ("tbe", "h0use", "rece1ved").

perplexity_score
    GPT-2 language model perplexity via the Hugging Face transformers library.
    Lower values mean more coherent English prose.  The GPT-2 model (~500 MB)
    is downloaded on first use and cached at ~/.cache/huggingface/.  The model
    and tokeniser are kept as module-level singletons so the cost is paid once
    per process.

combined_score
    dict_coverage × (1 / log1p(perplexity)).  Higher is better.

LowQualityError
    Raised by tetrak_ocr.auto_local when the best backend's combined_score
    falls below MIN_QUALITY_THRESHOLD.  Carries the per-backend scores and raw
    transcripts so tetrak_ocr.batch can write a useful triage manifest.

**These metrics read English, and only English.**  `dictionary_coverage`
counts `[a-zA-Z]` tokens against an English wordlist and GPT-2 is an English
language model, so a perfectly good transcript in another script scores 0.0
and lands below any threshold.  Use `scores_english_text` before applying the
gate to material that may not be English -- see `tetrak-ocr batch
--quality-gate`, which refuses rather than triaging a whole run.
"""

import importlib.util
import math
import re

MIN_QUALITY_THRESHOLD = 0.10

# Import names, not distribution names: pyspellchecker imports as `spellchecker`.
#
# torch is listed because the perplexity path imports it directly and
# transformers does not depend on it -- so a check that stopped at transformers
# would report scoring as available on a machine where it fails on the first
# file. Every caller that needs to know whether scoring can run reads this list,
# rather than keeping its own copy to drift out of step.
REQUIREMENTS = ("spellchecker", "transformers", "torch")


def is_available() -> bool:
    """True when every package the scoring path imports is installed."""
    return all(importlib.util.find_spec(m) is not None for m in REQUIREMENTS)


# Share of a transcript's letters that must be Latin before the metrics below
# are measuring anything. Half is deliberately generous: Armenian pages carry
# Latin names, numerals and abbreviations, and English pages are essentially
# all Latin, so the two land nowhere near this boundary.
MIN_LATIN_SHARE = 0.5


def scores_english_text(text: str) -> bool:
    """Whether these metrics can say anything about *text*.

    Both are English: `dictionary_coverage` counts `[a-zA-Z]` tokens against an
    English wordlist, and GPT-2 models English prose. An Armenian transcript
    therefore scores 0.0 regardless of how well it was read -- there is nothing
    in it for either metric to look at.

    That matters because 0.0 is below every threshold. Gating on it would send
    a whole run to triage while reporting each file as poor quality, which is
    the opposite of the truth and gives no clue where to look. The
    `easyocr-hy` backend made this reachable; before it, everything the
    pipeline read was English.

    A transcript with no letters at all returns True: empty and letterless
    output *is* poor, and scoring says so correctly. Only a transcript in
    another script is the case this guards.
    """
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return True
    latin = sum(1 for character in letters if character.isascii())
    return latin / len(letters) >= MIN_LATIN_SHARE


_spell = None
_gpt2_tokenizer = None
_gpt2_model = None


def _get_spell():
    global _spell
    if _spell is None:
        from spellchecker import SpellChecker

        _spell = SpellChecker()
    return _spell


def _get_gpt2():
    global _gpt2_tokenizer, _gpt2_model
    if _gpt2_model is None:
        from transformers import GPT2LMHeadModel, GPT2TokenizerFast

        _gpt2_tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
        _gpt2_model = GPT2LMHeadModel.from_pretrained("gpt2")
        _gpt2_model.eval()
    return _gpt2_tokenizer, _gpt2_model


def dictionary_coverage(text: str) -> float:
    """Return the fraction of word tokens that are recognised English words.

    Tokens shorter than 2 characters are excluded (they are too short to be
    meaningful spell-check targets and common as OCR noise).

    Args:
        text: Raw text string.

    Returns:
        A float in [0.0, 1.0].  Returns 0.0 for empty or token-free input.
    """
    tokens = [w for w in re.findall(r"[a-zA-Z]+", text) if len(w) >= 2]
    if not tokens:
        return 0.0
    spell = _get_spell()
    unknown = spell.unknown(tokens)
    known_count = len(tokens) - len(unknown)
    return known_count / len(tokens)


def perplexity_score(text: str) -> float:
    """Return the GPT-2 perplexity of the text.

    Lower values indicate more coherent, English-like prose.  Typical ranges:
      - Clean prose:      20–80
      - Moderate errors: 100–500
      - Heavy OCR noise: 500+

    Text is truncated to 1024 tokens (GPT-2 context limit).  Very short texts
    (fewer than 5 tokens) return a fixed high value (1000.0) since perplexity
    is unreliable on such short sequences.

    Args:
        text: Raw text string.

    Returns:
        A positive float.  Lower is better.
    """
    import torch

    tokenizer, model = _get_gpt2()
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=1024,
    )
    if inputs["input_ids"].shape[1] < 5:
        return 1000.0

    with torch.no_grad():
        loss = model(**inputs, labels=inputs["input_ids"]).loss
    return math.exp(loss.item())


def combined_score(text: str) -> float:
    """Return a single quality score combining dictionary coverage and perplexity.

    Score = dict_coverage × (1 / log1p(perplexity))

    Higher is better.  log1p tames the unbounded perplexity scale.
    Returns 0.0 if text is empty.

    Args:
        text: Raw text string.

    Returns:
        A non-negative float.  Higher means better quality.
    """
    if not text or not text.strip():
        return 0.0
    coverage = dictionary_coverage(text)
    perplexity = perplexity_score(text)
    return coverage * (1.0 / math.log1p(perplexity))


class LowQualityError(RuntimeError):
    """Raised when all OCR backends produce output below MIN_QUALITY_THRESHOLD.

    Attributes:
        scores:      {backend_name: combined_score} for every backend tried.
        transcripts: {backend_name: text} for every backend tried.
    """

    def __init__(
        self,
        message: str,
        scores: dict[str, float],
        transcripts: dict[str, str],
    ) -> None:
        super().__init__(message)
        self.scores = scores
        self.transcripts = transcripts
