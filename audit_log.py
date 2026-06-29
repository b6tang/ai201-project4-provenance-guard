"""
audit_log.py — Append-only audit log using JSON Lines format.

Each call to log_event() writes one JSON object to audit_log.jsonl.
Each call to read_log() returns the most recent entries from that file.
"""

import json
import os
from datetime import datetime, timezone

LOG_FILE = "audit_log.jsonl"


def log_event(entry: dict) -> None:
    """
    Append one record to audit_log.jsonl.

    Adds a UTC timestamp to a copy of entry, then writes it as one JSON line.
    The caller's original dict is not modified.
    """
    record = entry.copy()
    record["timestamp"] = datetime.now(timezone.utc).isoformat()

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def find_classification(content_id: str) -> dict | None:
    """
    Scan the full audit_log.jsonl for the first classification record matching
    content_id.

    Returns the record dict, or None if not found.
    Does not use read_log() — that function only returns the latest 20 lines,
    which would silently miss older submissions.
    """
    if not os.path.exists(LOG_FILE):
        return None

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                record.get("content_id") == content_id
                and record.get("status") == "classified"
            ):
                return record

    return None


def read_all_events() -> list[dict]:
    """
    Read all valid JSONL entries from audit_log.jsonl.

    Returns an empty list if the file does not exist or has no valid lines.
    Skips any line that cannot be parsed as JSON.
    Unlike read_log(), this returns every entry, not just the most recent 20.
    """
    if not os.path.exists(LOG_FILE):
        return []

    entries = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    return entries


def get_analytics() -> dict:
    """
    Calculate analytics metrics from all classification events.

    Returns:
        {
            "total_classifications": int,
            "verdict_counts": {
                "likely_ai": int,
                "likely_human": int,
                "uncertain": int,
            },
            "appeal_rate": float (0.0 to 1.0, or 0.0 if no classifications),
            "average_confidence": float or None,
        }
    """
    events = read_all_events()

    # Filter to classification records only.
    classifications = [
        e for e in events if e.get("status") == "classified"
    ]

    if not classifications:
        return {
            "total_classifications": 0,
            "verdict_counts": {"likely_ai": 0, "likely_human": 0, "uncertain": 0},
            "appeal_rate": 0.0,
            "average_confidence": None,
        }

    # Count verdicts by attribution.
    verdicts = {"likely_ai": 0, "likely_human": 0, "uncertain": 0}
    for c in classifications:
        attribution = c.get("attribution", "uncertain")
        if attribution in verdicts:
            verdicts[attribution] += 1

    # Count appeals: unique content_ids with at least one appeal event.
    appealed_ids = set()
    for e in events:
        if e.get("event_type") == "appeal":
            appealed_ids.add(e.get("content_id"))

    classified_ids = set(c.get("content_id") for c in classifications)
    appeal_rate = len(appealed_ids & classified_ids) / len(classifications)

    # Average confidence across all classifications.
    confidences = [
        c.get("confidence") for c in classifications
        if isinstance(c.get("confidence"), (int, float))
    ]
    avg_conf = sum(confidences) / len(confidences) if confidences else None

    return {
        "total_classifications": len(classifications),
        "verdict_counts": verdicts,
        "appeal_rate": appeal_rate,
        "average_confidence": avg_conf,
    }


def read_log(limit: int = 20) -> list[dict]:
    """
    Return the most recent entries from audit_log.jsonl, up to `limit`.

    Returns an empty list if the file does not exist or has no valid lines.
    Skips any line that cannot be parsed as JSON.
    """
    if not os.path.exists(LOG_FILE):
        return []

    entries = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # skip corrupted lines

    return entries[-limit:]


