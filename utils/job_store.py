"""
MySQL storage for saved job descriptions.
"""

import uuid
from datetime import datetime, timezone

from database import get_connection


def _now():
    """Return the current UTC time."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize(text):
    """Normalize text to compare titles and descriptions."""
    return " ".join((text or "").lower().split())


def list_jobs():
    """Return all saved jobs, most recently used first."""

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, title, description, created_at, updated_at
            FROM jobs
            ORDER BY updated_at DESC
        """)

        jobs = cursor.fetchall()

        # Convert datetime values to strings to preserve the old format.
        for job in jobs:
            job["created_at"] = job["created_at"].isoformat()
            job["updated_at"] = job["updated_at"].isoformat()

        return jobs

    finally:
        cursor.close()
        connection.close()


def save_job(title, description):
    """
    Save a job description.

    If an identical title and description already exist,
    update its last-used timestamp instead of inserting a duplicate.
    """

    title = (title or "Untitled Role").strip()
    description = (description or "").strip()

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, title, description, created_at, updated_at
            FROM jobs
        """)

        jobs = cursor.fetchall()

        for job in jobs:
            if (
                _normalize(job["title"]) == _normalize(title)
                and _normalize(job["description"])
                == _normalize(description)
            ):
                now = _now()

                cursor.execute("""
                    UPDATE jobs
                    SET updated_at = %s
                    WHERE id = %s
                """, (now, job["id"]))

                connection.commit()

                job["updated_at"] = now

                job["created_at"] = job["created_at"].isoformat()
                job["updated_at"] = job["updated_at"].isoformat()

                return job

        now = _now()
        job_id = uuid.uuid4().hex

        cursor.execute("""
            INSERT INTO jobs (
                id,
                title,
                description,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            job_id,
            title,
            description,
            now,
            now
        ))

        connection.commit()

        return {
            "id": job_id,
            "title": title,
            "description": description,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def delete_job(job_id):
    """Delete a saved job by ID. Return True if a job was deleted."""

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            "DELETE FROM jobs WHERE id = %s",
            (job_id,)
        )

        deleted = cursor.rowcount > 0

        connection.commit()

        return deleted

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()