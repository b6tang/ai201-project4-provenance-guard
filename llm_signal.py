"""
llm_signal.py — Signal 1: LLM-based AI-likelihood classifier.

llm_classify(text) sends the text to Groq and returns a single float
between 0.0 (human-like) and 1.0 (AI-like). That is all this file does.
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

# Load GROQ_API_KEY from .env into os.environ so Groq() can find it.
load_dotenv()


def llm_classify(text: str) -> float:
    """
    Ask a Groq-hosted LLM how AI-like the given text sounds.

    Returns a float in [0.0, 1.0].
    Raises ValueError for bad input, missing key, invalid response, or
    out-of-range score.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not found. Add it to your .env file."
        )

    client = Groq(api_key=api_key)

    # We ask the model to reason about writing style, then output strict JSON.
    prompt = f"""You are an expert writing analyst. Read the text below and
estimate how likely it is that it was written by an AI language model rather
than a human.

Respond with ONLY a JSON object in this exact format — no other text:
{{"llm_ai_likelihood": 0.0}}

The value must be a number from 0.0 (clearly human-written) to 1.0
(clearly AI-generated). Use your judgment about tone, vocabulary,
sentence structure, and writing patterns.

Text to analyze:
\"\"\"
{text}
\"\"\"
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,  # deterministic output
        response_format={"type": "json_object"},
    )

    raw_content = response.choices[0].message.content.strip()

    # Parse the JSON the model returned.
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError:
        raise ValueError(
            f"Model did not return valid JSON. Got: {raw_content!r}"
        )

    # Confirm the key exists and holds a number.
    if "llm_ai_likelihood" not in parsed:
        raise ValueError(
            f"JSON missing 'llm_ai_likelihood' key. Got: {parsed}"
        )

    score = parsed["llm_ai_likelihood"]

    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError(
            f"'llm_ai_likelihood' must be a number, got {type(score).__name__}"
        )

    score = float(score)

    if not (0.0 <= score <= 1.0):
        raise ValueError(
            f"Score {score} is outside the allowed range [0.0, 1.0]"
        )

    return score


# ---------------------------------------------------------------------------
# Quick manual test — run:  python llm_signal.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    examples = [
        "The sun set slowly over the hills as Maria watched, her coffee gone cold.",
        "In conclusion, leveraging synergistic methodologies enables robust outcomes.",
        "yo lmao i totally forgot the homework was due today bruh",
    ]

    for text in examples:
        score = llm_classify(text)
        print(f"Score: {score:.3f}  |  Text: {text[:60]!r}")
