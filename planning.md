# Provenance Guard — Planning

## Detection Signals

### Signal 1: LLM-based classification
- **What it measures:** Semantic meaning, context, tone, and overall writing style using an LLM's holistic judgment of the submitted text.
- **Why it may differ:** The LLM may recognize patterns that it associates with AI-generated writing.
- **Blind spots:** Sensitive to prompt wording and does not directly measure structural writing patterns. It may misclassify polished human writing or AI text that imitates human writing.
- **Output:** `llm_ai_likelihood`, a score between `0.0` and `1.0`, where higher values indicate more AI-like writing.

### Signal 2: Stylometric heuristics
- **What it measures:** Structural features of the text, including sentence-length variation, type-token ratio (vocabulary diversity), and punctuation density.
- **Why it may differ:** AI-generated text can sometimes be more structurally uniform, with less variation in sentence length, vocabulary, and punctuation usage. These are tendencies rather than rules.
- **Blind spots:** Cannot understand meaning or context. The measurements are affected by genre, writing style, editing, language proficiency, and text length, especially for short texts.
- **Output:** `stylometric_ai_likelihood`, a score between `0.0` and `1.0`, where higher values indicate more AI-like structural patterns.

### Combining the Signals
Both signals return AI-likelihood scores between `0` and `1` rather than binary flags. The system combines them using an equal-weighted average:
```
raw_ai_likelihood = (llm_ai_likelihood + stylometric_ai_likelihood) / 2
```
* **Why this combination makes sense:** An equal-weighted average is used because the two signals capture complementary evidence: the LLM-based classifier evaluates semantic and stylistic patterns, while the stylometric heuristics evaluate structural patterns. There is currently no validation data showing that either signal is consistently more reliable, so both signals are weighted equally. Averaging also preserves disagreement as a middle-range score that can later be treated as uncertainty rather than forcing a binary decision.

## Uncertainty Representation

The system computes a combined AI-likelihood score between `0` and `1`.

* Near `0`: evidence favors human-written content.
* Near `1`: evidence favors AI-generated content.
* Near `0.5`: evidence is mixed or uncertain.

A score of `0.60` means the evidence leans somewhat toward AI-generated content, but not strongly enough to classify the submission as likely AI-generated, so the result is labeled as uncertain.

The score is an operational confidence measure, not a statistical probability.

Raw signal outputs are mapped to a combined score as follows:
```
raw_ai_likelihood = (llm_ai_likelihood + stylometric_ai_likelihood) / 2
signal_disagreement = abs(llm_ai_likelihood - stylometric_ai_likelihood)
combined_ai_score = raw_ai_likelihood * (1 - signal_disagreement) + 0.5 * signal_disagreement
```

The disagreement term pulls conflicting results toward `0.5`, reducing confidence when the two signals disagree.

Classification thresholds:

* `combined_ai_score >= 0.80` → "Likely AI-generated"
* `combined_ai_score <= 0.30` → "Likely Human-written"
* otherwise → "Uncertain"

## Transparency Label Design

### High-Confidence AI Result
> Likely AI-generated. The system found strong patterns consistent with AI-generated writing. This is an estimate, not proof of authorship.

### High-Confidence Human Result
> Likely human-written. The system found strong patterns consistent with human-written writing. This is an estimate, not proof of authorship.

### Uncertain Result
> Uncertain. The signals were mixed or not strong enough for the system to make a reliable authorship classification.

## Appeals Workflow

* **Who may appeal:** Creators can appeal an existing classification by sending a request with `content_id` and `creator_reasoning`.
* **Appeal input:** 
```
{ 
    "content_id": "the ID returned by POST /submit", 
    "creator_reasoning": "The creator's explanation for why the classification may be incorrect." 
}
```
* **what status changes, what gets logged?:** When an appeal is received, the system finds the matching content_id, updates its status to "under_review", and logs the appeal alongside the original classification. The audit log records the content_id, appeal_reasoning, and timestamp. The system returns a confirmation response and does not automatically re-classify the content.
* **What a human reviewer should see:** For this project, exposes review-relevant records: timestamp, creator_id, content_id, attribution result, confidence score, individual signal scores, current status, and appeal_reasoning for each appealed submission.

## Anticipated Edge Cases

### Edge Case 1: A Human-Written Poem With Repetition and Simple Vocabulary

* **Scenario:** A human-written poem may intentionally repeat the same words, use short lines, and rely on simple vocabulary for rhythm or emotional effect. For example, a poem about grief may repeat one phrase at the end of every stanza.
* **Why this system may misclassify it:** The stylometric heuristics may treat the low type-token ratio and repetitive structure as AI-like. The LLM-based classifier may also interpret intentional repetition as generic or formulaic writing. This could cause human-written poetry to receive a high AI-likelihood score.
* **How the uncertainty/appeal design reduces harm:** The classification is presented as an estimate rather than proof of authorship. When the evidence is mixed or insufficient, the system should use the uncertain transparency label instead of a strong AI claim. A creator who believes the result is incorrect can submit an appeal and the appeal is recorded in the audit log.

### Edge Case 2: Highly Polished Human Professional Writing

* **Scenario:** A carefully edited human-written document, such as a scholarship essay, cover letter, press release, or formal announcement, may have high coherence, correct grammar, and structured transitions.

* **Why this system may misclassify it:** The LLM-based classifier may interpret the fluent and organized writing as AI-generated. The stylometric signal may also treat the consistent sentence structure as AI-like uniformity. This would be a false positive caused by editing quality rather than AI authorship.

* **How the uncertainty/appeal design reduces harm:** When the two signals disagree or the combined score falls in the uncertain range, the system will show an uncertain label rather than claiming the content is AI-generated. The creator can submit an appeal with reasoning, which changes the status to under_review and creates an audit-log entry for later review.

## Architecture

### Submission Flow

```
POST /submit
      │
      ▼  {"text": str, "creator_id": str}
Submitted text
      │
      ├──▶ Signal 1: llm_classify(text)
      │       │
      │       ▼  {"llm_ai_likelihood": float}
      │
      ├──▶ Signal 2: calculate_stylometric_score(text)
      │       │
      │       ▼  {"stylometric_ai_likelihood": float}
      │
      ▼
calculate_confidence(llm_ai_likelihood, stylometric_ai_likelihood)
      │
      ▼  {"raw_ai_likelihood": float,
      │     "signal_disagreement": float,
      │     "combined_ai_score": float}
      │
      ▼
select_attribution_and_label(combined_ai_score)
      │
      ▼  {"attribution": str, "label": str}
      │
      ├──▶ Audit Log
      │       ←── side effect: appends the classification record,
      │           including content_id, timestamp, both signal scores,
      │           combined_ai_score, attribution, label, and status
      │
      ▼
response
      │
      ▼  {"content_id": str, "attribution": str,
           "confidence": float, "label": str, "status": "classified"}
```

### Appeal Flow

```
POST /appeal
      │
      ▼  {"content_id": str, "creator_reasoning": str}
update_status_to_under_review(content_id)
      │
      ▼  {"status": "under_review"}
      │
      ├──▶ Audit Log
      │       ←── side effect: appends an appeal record linked by
      │           content_id, with creator_reasoning, timestamp,
      │           and status="under_review"
      │
      ▼
response
      │
      ▼  {"content_id": str, "status": "under_review",
           "message": str}
```

A submitted text is analyzed independently by the LLM-based classifier and the stylometric heuristics. Their scores are combined into `combined_ai_score`, which selects the attribution result and transparency label; the system then logs the decision and returns the result.

An appeal provides the original `content_id` and the creator's reasoning. It changes the submission status to `under_review` and adds an appeal record to the audit log, without automatically reclassifying the text.

## AI Tool Plan

### Milestone 3 — Submission Endpoint and First Signal

* **Spec sections provided to the AI tool:** The `Detection Signals` section for Signal 1, the `Submission Flow` architecture diagram, and the audit-log fields shown in the diagram.

* **What I will ask the AI tool to generate:** First, a minimal Flask app skeleton with a `POST /submit` route stub and an LLM-based `llm_classify(text)` function that returns one `llm_ai_likelihood` float from `0.0` to `1.0`. After testing that signal independently, I will ask for a structured JSONL audit-log helper and a `GET /log` route that returns recent entries as JSON.

* **What I will verify before using the output:** I will test `llm_classify(text)` directly with several texts and verify that it returns a float from `0.0` to `1.0`, not a binary flag. After wiring it into `/submit`, I will verify that the route accepts `text` and `creator_id` and returns a unique `content_id` plus the Signal 1 result. After adding logging, I will submit several texts and verify that each submission creates one structured entry containing a timestamp, `content_id`, attribution, confidence, Signal 1 score, and status, and that `GET /log` returns those entries.


### Milestone 4 — Second signal + confidence scoring


### Milestone 5 — Production layer
