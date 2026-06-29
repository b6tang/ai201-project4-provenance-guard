"""
stylometric_signal.py — Signal 2: Stylometric heuristic AI-likelihood scorer.

stylometric_classify(text) measures three structural writing features and
returns a single float between 0.0 (human-like) and 1.0 (AI-like).

No LLM, no API call, no external packages — pure Python standard library only.
"""

import re
import string

# Minimum text size required for a meaningful structural measurement.
# Fewer than 3 sentences or 20 words produces unreliable metric values.
MIN_SENTENCES = 3
MIN_WORDS = 20


# Heuristic ceiling for sentence-length variability. # A CoV of x means the standard deviation of sentence lengths is # x times the mean sentence length, indicating extremely uneven # sentence lengths. Values at or above this cap are treated as # maximally irregular for this feature. # This is a design choice, not a calibrated statistical threshold.
SENTENCE_LENGTH_COV_CAP = 0.80

# Heuristic ceiling for punctuation density. # A density of 0.x means that x% of the characters in the text are # punctuation characters. Text at or above this cap is treated as # maximally punctuation-heavy for this feature. # This is a design choice, not a calibrated statistical threshold. 
PUNCTUATION_DENSITY_CAP = 0.03


# ---------------------------------------------------------------------------
# Internal helpers — one per metric
# ---------------------------------------------------------------------------

# def _split_sentences(text: str) -> list:
#     """Split common English sentences on terminal punctuation."""
#     parts = re.split(r"(?<=[.!?…])\s+", text.strip())
#     return [s.strip() for s in parts if s.strip()]
def _split_sentences(text: str) -> list[str]:
    """Split common English sentences while preserving common abbreviations."""
    protected = text.strip()

    if not protected:
        return []

    placeholder = "<DOT>"

    # Keep decimal numbers such as 3.14 together.
    protected = re.sub(
        r"(?<=\d)\.(?=\d)",
        placeholder,
        protected,
    )

    # Keep initialisms such as U.S. or A.I. together.
    protected = re.sub(
        r"\b(?:[A-Za-z]\.){2,}",
        lambda match: match.group(0).replace(".", placeholder),
        protected,
    )

    # Keep a small set of common abbreviations together.
    abbreviations = [
        "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Sr.", "Jr.",
        "e.g.", "i.e.", "etc.", "vs.", "a.m.", "p.m.",
    ]

    for abbreviation in abbreviations:
        protected = re.sub(
            re.escape(abbreviation),
            abbreviation.replace(".", placeholder),
            protected,
            flags=re.IGNORECASE,
        )

    # Sentence-ending punctuation followed by whitespace marks a boundary.
    parts = re.split(r"(?<=[.!?…])\s+", protected)

    return [
        part.replace(placeholder, ".").strip()
        for part in parts
        if part.strip()
    ]

def _sentence_length_variation_score(sentences: list) -> float:
    """
    Low sentence-length variation → more uniform → AI-like → score close to 1.0.

    How it works:
      1. Count words in each sentence.
      2. Compute the coefficient of variation (CoV = std_dev / mean).
         CoV close to 0 means all sentences are roughly the same length.
      3. Divide CoV by SENTENCE_LENGTH_COV_CAP (a generous ceiling for very erratic text) to map
         it to [0, 1], then invert: score = 1 - normalized_CoV.

    Result: uniform text → low CoV → score near 1.0 (AI-like).
            erratic text → high CoV → score near 0.0 (human-like).
    """
    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)    

    variance = sum((ln - mean) ** 2 for ln in lengths) / len(lengths)
    std_dev = variance ** 0.5
    cov = std_dev / mean
    
    # Normalize CoV to a 0–1 irregularity scale using a heuristic cap.
    # CoV = 0.0 means all sentences have the same length.
    # CoV = SENTENCE_LENGTH_COV_CAP or higher is treated as extremely uneven.
    normalized = min(cov / SENTENCE_LENGTH_COV_CAP, 1.0)
    return 1.0 - normalized


def _type_token_ratio_score(words: list) -> float:
    """
    Lower vocabulary diversity → AI-like → score close to 1.0.

    How it works:
      1. TTR = unique_words / total_words.
      2. Lower TTR means more repeated words, so this heuristic treats it as more AI-like. The score is inverted to keep higher = more AI-like. 
      3. Thus, return 1 - TTR
    """
    if not words:
        return 0.5
    unique = len(set(words))  # already all lowercase
    ttr = unique / len(words)
    return 1.0 - ttr


def _punctuation_density_score(text: str) -> float:
    """
    Low punctuation density → less punctuation variation → AI-like → score close to 1.0.

    How it works:
      1. Count punctuation characters individually.
      2. Treat an ellipsis such as "..." as one punctuation event rather than
         three separate periods.
      3. Divide punctuation events by total text characters to calculate density.
      4. Normalize the density using PUNCTUATION_DENSITY_CAP, then invert it.

    Result: lower punctuation density → score near 1.0 (AI-like).
            higher punctuation density → score near 0.0 (human-like).
    """
    if not text:
        return 0.5

    # Treat each standard three-dot ellipsis as one punctuation event.
    # Longer runs are replaced in groups of three, so extra periods still count.
    # For example: "..." -> "…", "...." -> "….", "....." -> "…..".
    # This preserves irregular extra periods as additional punctuation evidence.
    normalized_for_counting = re.sub(r"\.{3}", "…", text)

    punctuation_chars = string.punctuation + "…“”‘’"

    punctuation_count = sum(
        1
        for character in normalized_for_counting
        if character in punctuation_chars
    )

    density = punctuation_count / len(text)
    normalized = min(density / PUNCTUATION_DENSITY_CAP, 1.0)

    return 1.0 - normalized

# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def stylometric_classify(text: str) -> float:
    """
    Compute an AI-likelihood score from structural writing features.

    Returns a float in [0.0, 1.0].
    Returns 0.5 (neutral) for text too short to measure reliably.
    Raises ValueError for non-string or blank input.

    The final score is the equal-weight average of three sub-scores:
      - sentence-length variation  (low variation → AI-like)
      - type-token ratio           (low vocabulary diversity → AI-like)
      - punctuation density        (low density → AI-like)
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")

    sentences = _split_sentences(text)
    words = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", text.lower())

    # Too little text to produce reliable structural measurements.
    if len(sentences) < MIN_SENTENCES or len(words) < MIN_WORDS:
        return 0.5

    score_sent  = _sentence_length_variation_score(sentences)
    score_ttr   = _type_token_ratio_score(words)
    score_punct = _punctuation_density_score(text)

    # Equal-weight average combines all three structural signals.
    stylometric_ai_likelihood = (score_sent + score_ttr + score_punct) / 3.0

    return stylometric_ai_likelihood


