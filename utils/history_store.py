
"""
MySQL storage for completed resume analysis runs.
Stores analysis details in analysis_history and candidate
matching results in match_results.
"""

import json
import uuid
from datetime import datetime, timezone

from database import get_connection

MAX_HISTORY = 30


def _now():
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _to_db_datetime(value):
    """Convert an ISO timestamp to MySQL DATETIME format."""
    if not value:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

    return parsed


def _to_iso(value):
    """Convert a MySQL datetime to an ISO timestamp in UTC."""
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc).isoformat()


def _decode_json(value, default=None):
    """Convert a MySQL JSON value into a Python object."""
    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")

    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default

    return value


def _encode_json(value):
    """Convert Python lists/dictionaries into JSON text."""
    return json.dumps(value if value is not None else [])


def _save_result(cursor, analysis_id, result):
    """Save one candidate's result."""
    result = result or {}
    breakdown = result.get("breakdown") or {}

    cursor.execute(
        """
        INSERT INTO match_results (
            analysis_id,
            candidate_name,
            filename,
            final_score,
            breakdown,
            matched_skills,
            missing_skills,
            education,
            experience_years,
            organizations,
            candidate_rank
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            analysis_id,
            result.get("candidate_name") or result.get("name"),
            result.get("filename"),
            result.get("final_score"),
            _encode_json(breakdown),
            _encode_json(result.get("matched_skills", [])),
            _encode_json(result.get("missing_skills", [])),
            _encode_json(result.get("education", [])),
            result.get("experience_years"),
            _encode_json(result.get("organizations", [])),
            result.get("rank"),
        ),
    )


def save_analysis(job_title, job_description, jd_skills, results, errors):
    """Save a completed analysis and return its full record."""
    analysis_id = uuid.uuid4().hex
    timestamp = _now()
    job_title = job_title or "Untitled Role"
    job_description = job_description or ""
    jd_skills = jd_skills or []
    results = results or []
    errors = errors or []

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO analysis_history (
                id, timestamp, job_title, job_description,
                jd_skills, errors, candidate_count
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                analysis_id,
                _to_db_datetime(timestamp),
                job_title,
                job_description,
                _encode_json(jd_skills),
                _encode_json(errors),
                len(results),
            ),
        )

        for result in results:
            _save_result(cursor, analysis_id, result)

        # Keep only the newest MAX_HISTORY analyses.
        cursor.execute(
            """
            SELECT id
            FROM analysis_history
            ORDER BY timestamp DESC, id DESC
            LIMIT 18446744073709551615 OFFSET %s
            """,
            (MAX_HISTORY,),
        )
        old_ids = [row[0] for row in cursor.fetchall()]

        if old_ids:
            placeholders = ", ".join(["%s"] * len(old_ids))
            cursor.execute(
                f"DELETE FROM analysis_history WHERE id IN ({placeholders})",
                tuple(old_ids),
            )

        connection.commit()

        # Return the saved record in the same shape as the JSON version.
        record = get_analysis(analysis_id)
        if record is not None:
            return record

        return {
            "id": analysis_id,
            "timestamp": timestamp,
            "job_title": job_title,
            "job_description": job_description,
            "jd_skills": jd_skills,
            "results": results,
            "errors": errors,
            "candidate_count": len(results),
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def list_summaries():
    """Return lightweight summaries for the history dropdown."""
    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, timestamp, job_title, candidate_count
            FROM analysis_history
            ORDER BY timestamp DESC, id DESC
            """
        )

        rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "timestamp": _to_iso(row["timestamp"]),
                "job_title": row["job_title"],
                "candidate_count": row["candidate_count"],
            }
            for row in rows
        ]

    finally:
        connection.close()


def get_analysis(analysis_id):
    """Retrieve one analysis with all its candidate results."""
    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, timestamp, job_title, job_description,
                   jd_skills, errors, candidate_count
            FROM analysis_history
            WHERE id = %s
            """,
            (analysis_id,),
        )

        analysis = cursor.fetchone()

        if not analysis:
            return None

        cursor.execute(
            """
            SELECT candidate_name, filename, final_score, breakdown,
                   matched_skills, missing_skills, education,
                   experience_years, organizations, candidate_rank
            FROM match_results
            WHERE analysis_id = %s
            ORDER BY candidate_rank IS NULL, candidate_rank ASC, id ASC
            """,
            (analysis_id,),
        )

        rows = cursor.fetchall()
        results = []

        for row in rows:
            results.append(
                {
                    "candidate_name": row["candidate_name"],
                    "filename": row["filename"],
                    "final_score": row["final_score"],
                    "breakdown": _decode_json(row["breakdown"], {}),
                    "matched_skills": _decode_json(row["matched_skills"], []),
                    "missing_skills": _decode_json(row["missing_skills"], []),
                    "education": _decode_json(row["education"], []),
                    "experience_years": row["experience_years"],
                    "organizations": _decode_json(row["organizations"], []),
                    "rank": row["candidate_rank"],
                }
            )

        return {
            "id": analysis["id"],
            "timestamp": _to_iso(analysis["timestamp"]),
            "job_title": analysis["job_title"],
            "job_description": analysis["job_description"],
            "jd_skills": _decode_json(analysis["jd_skills"], []),
            "results": results,
            "errors": _decode_json(analysis["errors"], []),
            "candidate_count": analysis["candidate_count"],
        }

    finally:
        connection.close()


def delete_analysis(analysis_id):
    """Delete an analysis and its results."""
    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM analysis_history WHERE id = %s",
            (analysis_id,),
        )

        deleted = cursor.rowcount > 0
        connection.commit()
        return deleted

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
