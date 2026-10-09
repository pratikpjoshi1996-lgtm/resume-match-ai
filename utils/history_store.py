"""
Lightweight JSON-file storage for completed analyses (ranking runs).

Every time /api/analyze successfully ranks a batch of resumes, the job
description and the full ranked result list are saved here, so a past
shortlist can be reopened later without re-uploading the same resumes.

Kept intentionally simple for a mini project's scope: a single JSON file at
data/analysis_history.json, capped to the most recent MAX_HISTORY runs so it
can't grow without bound over time.
"""
import json
import os
import uuid
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_PATH = os.path.join(BASE_DIR, "data", "analysis_history.json")
MAX_HISTORY = 30


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load():
    if not os.path.exists(STORE_PATH):
        return []
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _persist(history):
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def save_analysis(job_title, job_description, jd_skills, results, errors):
    """Save a completed ranking run and return the full saved record."""
    history = _load()
    record = {
        "id": uuid.uuid4().hex,
        "timestamp": _now(),
        "job_title": job_title or "Untitled Role",
        "job_description": job_description or "",
        "jd_skills": jd_skills or [],
        "results": results or [],
        "errors": errors or [],
        "candidate_count": len(results or []),
    }
    history.append(record)
    # Keep only the most recent MAX_HISTORY runs so the file can't grow unbounded.
    history = sorted(history, key=lambda h: h["timestamp"], reverse=True)[:MAX_HISTORY]
    _persist(history)
    return record


def list_summaries():
    """Lightweight list for a history dropdown -- no full JD text or result rows."""
    history = sorted(_load(), key=lambda h: h["timestamp"], reverse=True)
    return [
        {
            "id": h["id"],
            "timestamp": h["timestamp"],
            "job_title": h["job_title"],
            "candidate_count": h["candidate_count"],
        }
        for h in history
    ]


def get_analysis(analysis_id):
    for h in _load():
        if h["id"] == analysis_id:
            return h
    return None


def delete_analysis(analysis_id):
    history = _load()
    remaining = [h for h in history if h["id"] != analysis_id]
    if len(remaining) == len(history):
        return False
    _persist(remaining)
    return True
