"""
scoring.py — Combines Signal 1 and Signal 2 into a single attribution result.

combine_scores() takes both AI-likelihood floats, applies the disagreement
formula, and returns the intermediate calculations alongside the final
attribution label.
"""

import math


def _validate_signal(value: object, name: str) -> None:
    """Raise ValueError if value is not a valid signal float."""
    # bool must be checked first because bool is a subclass of int.
    if isinstance(value, bool):
        raise ValueError(f"'{name}' must be a float, not bool")
    if not isinstance(value, (int, float)):
        raise ValueError(f"'{name}' must be numeric, got {type(value).__name__}")
    if math.isnan(value):
        raise ValueError(f"'{name}' must not be NaN")
    if math.isinf(value):
        raise ValueError(f"'{name}' must not be infinite")
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"'{name}' must be in [0.0, 1.0], got {value}")


def combine_scores(
    llm_ai_likelihood: float,
    stylometric_ai_likelihood: float,
) -> dict:
    """
    Combine two signal scores into a single attribution result.

    Parameters
    ----------
    llm_ai_likelihood         : float in [0.0, 1.0] from llm_signal.py
    stylometric_ai_likelihood : float in [0.0, 1.0] from stylometric_signal.py

    Returns
    -------
    dict with keys:
        llm_ai_likelihood, stylometric_ai_likelihood,
        raw_ai_likelihood, signal_disagreement,
        combined_ai_score, attribution
    """
    _validate_signal(llm_ai_likelihood, "llm_ai_likelihood")
    _validate_signal(stylometric_ai_likelihood, "stylometric_ai_likelihood")

    # Equal-weight average of both signals.
    raw_ai_likelihood = (
        llm_ai_likelihood + stylometric_ai_likelihood
    ) / 2

    # How far apart the two signals are (0.0 = full agreement, 1.0 = opposite).
    signal_disagreement = abs(
        llm_ai_likelihood - stylometric_ai_likelihood
    )

    # Pull the combined score toward 0.5 when the signals disagree strongly.
    combined_ai_score = (
        raw_ai_likelihood * (1 - signal_disagreement) + 0.5 * signal_disagreement
    )

    # Apply classification thresholds.
    if combined_ai_score >= 0.80:
        attribution = "likely_ai"
    elif combined_ai_score <= 0.30:
        attribution = "likely_human"
    else:
        attribution = "uncertain"

    return {
        "llm_ai_likelihood": llm_ai_likelihood,
        "stylometric_ai_likelihood": stylometric_ai_likelihood,
        "raw_ai_likelihood": raw_ai_likelihood,
        "signal_disagreement": signal_disagreement,
        "combined_ai_score": combined_ai_score,
        "attribution": attribution,
    }


# ---------------------------------------------------------------------------
# Quick manual test — run:  python scoring.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_pairs = [
        (0.90, 0.90),  # expected: likely_ai
        (0.10, 0.10),  # expected: likely_human
        (0.90, 0.10),  # expected: uncertain
        (0.80, 0.60),  # expected: uncertain
    ]

    for llm, stylo in test_pairs:
        result = combine_scores(llm, stylo)
        print(f"Input: llm={llm}, stylometric={stylo}")
        print(f"Result: {result}")
        print()