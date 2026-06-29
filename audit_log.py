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


# ---------------------------------------------------------------------------
# Quick manual test — run:  python audit_log.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample = {
        "content_id": "test-content-001",
        "creator_id": "test-user-1",
        "attribution": "likely_ai",
        "confidence": 0.8,
        "llm_ai_likelihood": 0.8,
        "status": "classified",
    }

    print("Writing sample record to audit_log.jsonl...")
    log_event(sample)

    print("Reading log back (most recent 20 entries):")
    entries = read_log()
    for entry in entries:
        print(entry)

    print(f"\nTotal entries visible: {len(entries)}")
