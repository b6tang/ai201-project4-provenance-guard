# Provenance Guard

## Overview

Provenance Guard is a Flask API for text-based creative platforms. A creator submits text and the API returns an attribution result, confidence value, and plain-language transparency label.

The system is not meant to prove authorship. It gives readers context, records how a decision was made, and allows creators to appeal a result.

## Architecture

```text
POST /submit {text, creator_id} 
    -> llm_classify(text) 
        evaluates semantic meaning, context, tone, and overall writing style 
    -> stylometric_classify(text) 
        measures sentence-length variation, vocabulary diversity, and punctuation density 
    -> combine_scores(...) 
        calculates raw_ai_likelihood, signal_disagreement, and combined_ai_score 
    -> get_label(attribution) 
        selects the matching transparency-label text 
    -> log_event(...) 
        appends the classification record to audit_log.jsonl 
    -> JSON response 
        returns content_id, attribution, confidence, label, and status

POST /appeal {content_id, creator_reasoning} 
    -> find the original classification 
    -> append an appeal event with status="under_review" 
    -> JSON response 

GET /log -> returns recent structured audit-log entries as JSON
```

## Detection Signals and Confidence

### LLM-Based Classification

The first signal sends the text to an LLM and asks it to evaluate overall meaning, tone, coherence, and writing style. I used this because some AI-like patterns are difficult to represent with simple text statistics alone.

Its output is `llm_ai_likelihood`, a value from `0.0` to `1.0`. Higher values mean the text appears more AI-like to the LLM.

This signal can be wrong. Polished human writing may look AI-like, and AI-written text can imitate human writing.

### Stylometric Heuristics

The second signal uses pure Python text statistics:

* sentence-length variation
* type-token ratio for vocabulary diversity
* punctuation density

I used this signal because it measures something different from the LLM. It does not judge meaning. It looks at structure and variation in the writing.

Its output is `stylometric_ai_likelihood`, also from `0.0` to `1.0`.

This signal is limited by genre, editing, language proficiency, and text length. Short text provides less reliable structural information.

### Combining Scores

The system first averages both scores:

```python
raw_ai_likelihood = (
    llm_ai_likelihood + stylometric_ai_likelihood
) / 2
```

It then measures disagreement between the signals:

```python
signal_disagreement = abs(
    llm_ai_likelihood - stylometric_ai_likelihood
)
```

When the signals disagree, the result is pulled toward `0.5`:

```python
combined_ai_score = (
    raw_ai_likelihood * (1 - signal_disagreement)
    + 0.5 * signal_disagreement
)
```

I chose this approach because disagreement should reduce confidence instead of allowing one signal to make a strong decision by itself.

| Combined AI score | Attribution    |
| ----------------- | -------------- |
| `>= 0.80`         | `likely_ai`    |
| `<= 0.30`         | `likely_human` |
| otherwise         | `uncertain`    |

Near 0, evidence favors human-written content. Near 1, evidence favors AI-generated content. Near 0.5, evidence is mixed or uncertain. For example, a combined score of 0.60 leans somewhat toward AI, but it remains uncertain because it is below the 0.80 threshold.

## Transparency Labels

### Likely AI-Generated

> Likely AI-generated. The system found strong patterns consistent with AI-generated writing. This is an estimate, not proof of authorship.

### Likely Human-Written

> Likely human-written. The system found strong patterns consistent with human-written writing. This is an estimate, not proof of authorship.

### Uncertain

> Uncertain. The signals were mixed or not strong enough for the system to make a reliable authorship classification.

## Appeals, Rate Limiting, and Audit Log

Creators can submit an appeal with a content_id and creator_reasoning. The endpoint finds the original classification, appends a linked appeal event, and returns status: "under_review".

The project uses an append-only JSONL audit log. The original classification is not overwritten. Instead, the appeal is stored as a second event with the same content_id. This preserves the original decision and creates a review history.

`POST /submit` is rate limited per client IP:

```text
10 submissions per minute
100 submissions per day
```

The API returns HTTP `429 Too Many Requests` after the limit is reached.

## Validation Results

I ran five M4 test cases after resetting the local audit log.

| Test case                 | Content ID                             | Attribution    | Confidence |
| ------------------------- | -------------------------------------- | -------------- | ---------: |
| `m4-test-clear-ai`        | `5a87fb69-efdb-4e93-b097-97a889521c14` | `uncertain`    |   `0.5488` |
| `m4-test-clear-human`     | `540e24aa-bfbc-4fae-b299-edd5937911a8` | `likely_human` |   `0.7502` |
| `m4-test-formal-human`    | `f92e587c-7112-457f-893f-c8a88a226a2e` | `uncertain`    |   `0.6050` |
| `m4-test-edited-ai`       | `a7bb2954-fe0e-40d5-889e-5d65941fccf5` | `likely_human` |   `0.7460` |
| `m4-test-high-ai-control` | `78c56448-9897-4894-8038-de7d5011f88f` | `likely_ai`    |   `0.8495` |

These results show that the system produced all three possible attribution outcomes. They also show that the result is not proof of authorship: the clear-AI example remained uncertain, while the edited-AI example was classified as likely human-written.

## Audit-Log Evidence

The committed `audit_log.jsonl` file is an append-only structured JSONL log. Each classification record includes:

* `timestamp`
* `content_id`
* `creator_id`
* `attribution`
* `confidence`
* `llm_ai_likelihood`
* `stylometric_ai_likelihood`
* `combined_ai_score`
* `label`
* `status`

The five classification records listed above are stored in the log with these fields.

I also submitted an appeal for the high-AI classification:

```text
content_id: 78c56448-9897-4894-8038-de7d5011f88f
message: Appeal submitted and queued for review.
status: under_review
```

The appeal is stored as a separate JSONL event with the same `content_id`, `event_type: "appeal"`, `creator_reasoning`, and `status: "under_review"`. This keeps the original classification and later appeal linked without overwriting the original decision.

### Audit-Log Sample

The following excerpt is from an actual test in `audit_log.jsonl`. The original classification and its appeal share the same `content_id`.


```
{"content_id": "5a87fb69-efdb-4e93-b097-97a889521c14", "creator_id": "m4-test-clear-ai", "attribution": "uncertain", "confidence": 0.5488285362982145, "llm_ai_likelihood": 0.8, "stylometric_ai_likelihood": 0.3710216605488538, "raw_ai_likelihood": 0.585510830274427, "signal_disagreement": 0.4289783394511462, "combined_ai_score": 0.5488285362982145, "label": "Uncertain. The signals were mixed or not strong enough for the system to make a reliable authorship classification.", "status": "classified", "timestamp": "2026-06-29T17:58:37.148462+00:00"}
{"content_id": "540e24aa-bfbc-4fae-b299-edd5937911a8", "creator_id": "m4-test-clear-human", "attribution": "likely_human", "confidence": 0.7652456741258724, "llm_ai_likelihood": 0.1, "stylometric_ai_likelihood": 0.26481883304062737, "raw_ai_likelihood": 0.18240941652031367, "signal_disagreement": 0.16481883304062736, "combined_ai_score": 0.23475432587412753, "label": "Likely human-written. The system found strong patterns consistent with human-written writing. This is an estimate, not proofof authorship.", "status": "classified", "timestamp": "2026-06-29T17:58:39.904308+00:00"}
{"content_id": "78c56448-9897-4894-8038-de7d5011f88f", "creator_id": "m4-test-high-ai-control", "attribution": "likely_ai","confidence": 0.849505182820703, "llm_ai_likelihood": 0.99, "stylometric_ai_likelihood": 0.8361281992860939, "raw_ai_likelihood": 0.913064099643047, "signal_disagreement": 0.15387180071390605, "combined_ai_score": 0.849505182820703, "label": "Likely AI-generated. The system found strong patterns consistent with AI-generated writing. This is an estimate, not proof of authorship.", "status": "classified", "timestamp": "2026-06-29T17:58:47.986868+00:00"}
{"event_type": "appeal", "content_id": "78c56448-9897-4894-8038-de7d5011f88f", "creator_id": "m4-test-high-ai-control", "creator_reasoning": "I wrote this content myself and would like the classification to be reviewed.", "status": "under_review","timestamp": "2026-06-29T18:03:35.549171+00:00"}
```

## Known Limitation

Highly polished human writing is a major limitation. For example, scholarship essays, press releases, cover letters, or formal announcements may have strong grammar, organized transitions, and consistent sentence structure.

The LLM may interpret these traits as AI-like. The stylometric signal may also interpret very consistent structure as unusually uniform.

Poetry is another difficult case because intentional repetition, simple vocabulary, and short lines can affect stylometric measurements.

## Spec Reflection

The planning document helped guide the implementation by requiring decisions about the two signals, thresholds, labels, audit-log fields, and appeal behavior before coding.

My planning document described updating a submission status to under_review after an appeal. The final implementation diverged by keeping an append-only JSONL log: it adds a separate appeal event with the same content_id and status: "under_review" instead of overwriting the original classification record.

I chose this design because it preserves the original decision and creates a clearer history of later actions. A future review system could determine the latest review state from the newest event linked to that content ID.

## AI Usage Transparency

### Transparency Labels

I gave Claude my `planning.md`, `app.py`, and `scoring.py`, then asked it to create a separate label function using my exact three label variants.

Claude added `get_label(attribution)` and replaced the hard-coded label logic in `app.py`. I kept the existing scoring formula and thresholds unchanged because the existing `confidence` value alone could not distinguish likely AI from likely human results. I tested all three labels directly and through `POST /submit`.

### Appeals Workflow

I gave Claude the appeals section of my planning document, `app.py`, and `audit_log.py`. I asked it to add `POST /appeal` without rewriting the existing classification system.

Claude added a helper to find the original classification and added an append-only appeal event. I kept the append-only design instead of modifying the original JSONL record. I tested the endpoint and confirmed that the log showed both the original classification and the appeal event.

### Rate Limiting

I chose these limits because a normal creator may submit or revise a few drafts in a short period, while repeated automated requests could consume LLM API capacity, create unnecessary cost, and flood the audit log.

I tested 12 rapid requests. The first 10 returned `200`, and requests 11 and 12 returned `429`.

```
Request 1 : HTTP 200
Request 2 : HTTP 200
Request 3 : HTTP 200
Request 4 : HTTP 200
Request 5 : HTTP 200
Request 6 : HTTP 200
Request 7 : HTTP 200
Request 8 : HTTP 200
Request 9 : HTTP 200
Request 10 : HTTP 200
Request 11 : HTTP 429
Request 12 : HTTP 429
```


## Walkthrough Video

[Add video link here.]


### Stretch Features