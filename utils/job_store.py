"""
Lightweight JSON-file storage for saved job descriptions.

Kept intentionally simple for a mini project's scope: a single JSON file at
data/saved_jobs.json holds a list of records. If this ever needs to grow into
something bigger (multi-user, concurrent writes, etc.), only this module
would need to change to swap in SQLite -- nothing in app.py or the frontend
depends on the storage mechanism.
"""
import json
import os
import uuid
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_PATH = os.path.join(BASE_DIR, "data", "saved_jobs.json")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _normalize(text):
    return " ".join((text or "").lower().split())


def _load():
    if not os.path.exists(STORE_PATH):
        return []
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _persist(jobs):
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)


def list_jobs():
    """Return all saved job descriptions, most recently used first."""
    return sorted(_load(), key=lambda j: j["updated_at"], reverse=True)


def save_job(title, description):
    """
    Save a job description. If an identical one (same title + description,
    ignoring case/extra whitespace) is already saved, its "last used" time is
    refreshed instead of creating a duplicate entry.
    """
    title = (title or "Untitled Role").strip()
    description = (description or "").strip()
    jobs = _load()
    now = _now()

    for job in jobs:
        if _normalize(job["title"]) == _normalize(title) and _normalize(job["description"]) == _normalize(description):
            job["updated_at"] = now
            _persist(jobs)
            return job

    record = {
        "id": uuid.uuid4().hex,
        "title": title,
        "description": description,
        "created_at": now,
        "updated_at": now,
    }
    jobs.append(record)
    _persist(jobs)
    return record


def delete_job(job_id):
    jobs = _load()
    remaining = [j for j in jobs if j["id"] != job_id]
    if len(remaining) == len(jobs):
        return False
    _persist(remaining)
    return True
