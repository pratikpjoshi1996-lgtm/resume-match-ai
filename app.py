"""
ResumeMatch AI -- Flask backend

Modules 6 (Ranking & Output) sits here on top of Modules 1-5 in utils/.
Endpoints:
    GET  /                    -> serves the web dashboard
    POST /api/analyze         -> upload resumes + JD, returns ranked, explainable results
    GET  /api/export/csv      -> download the last batch's shortlist as CSV
    GET  /api/export/pdf      -> download the last batch's shortlist as PDF
    GET  /api/jobs            -> list previously saved job descriptions
    DELETE /api/jobs/<id>     -> delete a saved job description
    GET  /api/history         -> list past ranking runs (summaries)
    GET  /api/history/<id>    -> full detail of one past ranking run
    DELETE /api/history/<id>  -> delete a past ranking run

Note on persistence: results are held in a simple in-memory store for the
current server process rather than a database. For a mini project's scope
(single-session use: upload -> view -> export) this avoids unnecessary
complexity; swapping in SQLite later (as listed in the software
requirements) would mean saving `LAST_RESULTS` to a table keyed by a job/run id.
"""
import io
import os
import time
import uuid

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

from utils.parser import extract_text
from utils.preprocessing import preprocess
from utils.extraction import extract_all_fields
from utils.scoring import compute_match_score, DEFAULT_WEIGHTS
from utils.job_store import list_jobs, save_job, delete_job
from utils.history_store import save_analysis, list_summaries, get_analysis, delete_analysis

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"pdf", "docx"}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB total upload cap

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# In-memory store for the most recent batch, used by the export endpoints.
LAST_RESULTS = {"rows": [], "job_title": ""}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    start_time = time.time()

    jd_text_raw = request.form.get("job_description", "").strip()
    if not jd_text_raw:
        return jsonify({"error": "Job description text is required."}), 400

    resume_files = request.files.getlist("resumes")
    if not resume_files or resume_files[0].filename == "":
        return jsonify({"error": "At least one resume file is required."}), 400

    # --- Process the job description once ---
    jd_clean, _ = preprocess(jd_text_raw)
    jd_fields = extract_all_fields(jd_text_raw, jd_clean)

    results = []
    errors = []

    for file in resume_files:
        if not allowed_file(file.filename):
            errors.append(f"{file.filename}: unsupported file type (only .pdf / .docx accepted).")
            continue

        filename = secure_filename(file.filename)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file.save(filepath)

        try:
            raw_text = extract_text(filepath)
            if not raw_text.strip():
                errors.append(f"{filename}: no extractable text found (possibly a scanned/image resume).")
                continue

            resume_clean, _ = preprocess(raw_text)
            resume_fields = extract_all_fields(raw_text, resume_clean)

            match = compute_match_score(
                resume_clean_text=resume_clean,
                jd_clean_text=jd_clean,
                candidate_skills=resume_fields["skills"],
                jd_skills=jd_fields["skills"],
                candidate_years=resume_fields["experience_years"],
                jd_required_years=jd_fields["experience_years"],
                weights=DEFAULT_WEIGHTS,
            )

            results.append({
                "candidate_name": os.path.splitext(filename)[0],
                "filename": filename,
                "final_score": match["final_score"],
                "breakdown": match["breakdown"],
                "matched_skills": match["matched_skills"],
                "missing_skills": match["missing_skills"],
                "education": resume_fields["education"],
                "experience_years": resume_fields["experience_years"],
                "organizations": resume_fields["organizations"],
            })
        except ValueError as e:
            errors.append(str(e))
        finally:
            # Clean up the uploaded file once processed.
            if os.path.exists(filepath):
                os.remove(filepath)

    # Module 6: Ranking -- sort candidates by final score, descending.
    results.sort(key=lambda r: r["final_score"], reverse=True)
    for i, r in enumerate(results, start=1):
        r["rank"] = i

    LAST_RESULTS["rows"] = results
    LAST_RESULTS["job_title"] = request.form.get("job_title", "Untitled Role")

    # Persist this job description so it can be reused later without retyping it.
    saved_job = save_job(LAST_RESULTS["job_title"], jd_text_raw)

    # Persist this whole ranking run so it can be reopened later without re-uploading resumes.
    history_record = save_analysis(
        LAST_RESULTS["job_title"], jd_text_raw, jd_fields["skills"], results, errors
    )

    elapsed = round(time.time() - start_time, 2)

    return jsonify({
        "job_title": LAST_RESULTS["job_title"],
        "jd_skills": jd_fields["skills"],
        "results": results,
        "errors": errors,
        "processing_time_seconds": elapsed,
        "weights_used": DEFAULT_WEIGHTS,
        "saved_job_id": saved_job["id"],
        "history_id": history_record["id"],
    })


@app.route("/api/jobs", methods=["GET"])
def get_saved_jobs():
    """Return every previously saved job description, most recently used first."""
    return jsonify({"jobs": list_jobs()})


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def remove_saved_job(job_id):
    """Delete a saved job description the user no longer wants to keep."""
    if not delete_job(job_id):
        return jsonify({"error": "Saved job description not found."}), 404
    return jsonify({"success": True})


@app.route("/api/history", methods=["GET"])
def get_history():
    """Return lightweight summaries of past analyses for the history dropdown."""
    return jsonify({"history": list_summaries()})


@app.route("/api/history/<analysis_id>", methods=["GET"])
def get_history_detail(analysis_id):
    """Return one full past analysis so it can be redisplayed without re-uploading resumes."""
    record = get_analysis(analysis_id)
    if not record:
        return jsonify({"error": "That saved analysis could not be found."}), 404

    # Make this the "active" result set too, so CSV/PDF export works for a
    # reopened historical shortlist just like it does for a fresh one.
    LAST_RESULTS["rows"] = record["results"]
    LAST_RESULTS["job_title"] = record["job_title"]

    return jsonify({
        "job_title": record["job_title"],
        "job_description": record["job_description"],
        "jd_skills": record["jd_skills"],
        "results": record["results"],
        "errors": record["errors"],
        "timestamp": record["timestamp"],
    })


@app.route("/api/history/<analysis_id>", methods=["DELETE"])
def remove_history(analysis_id):
    """Delete a saved past analysis the user no longer wants to keep."""
    if not delete_analysis(analysis_id):
        return jsonify({"error": "That saved analysis could not be found."}), 404
    return jsonify({"success": True})


@app.route("/api/export/csv")
def export_csv():
    rows = LAST_RESULTS["rows"]
    if not rows:
        return jsonify({"error": "No results to export yet. Run an analysis first."}), 400

    df = pd.DataFrame([{
        "Rank": r["rank"],
        "Candidate": r["candidate_name"],
        "Match Score (%)": r["final_score"],
        "Matched Skills": ", ".join(r["matched_skills"]),
        "Missing Skills": ", ".join(r["missing_skills"]),
        "Experience (yrs)": r["experience_years"] if r["experience_years"] is not None else "N/A",
        "Education": ", ".join(r["education"]) if r["education"] else "N/A",
    } for r in rows])

    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    mem = io.BytesIO(buffer.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(
        mem, mimetype="text/csv", as_attachment=True,
        download_name=f"shortlist_{LAST_RESULTS['job_title'].replace(' ', '_')}.csv",
    )


@app.route("/api/export/pdf")
def export_pdf():
    rows = LAST_RESULTS["rows"]
    if not rows:
        return jsonify({"error": "No results to export yet. Run an analysis first."}), 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(f"Shortlist Report - {LAST_RESULTS['job_title']}", styles["Title"]),
        Spacer(1, 12),
    ]

    table_data = [["Rank", "Candidate", "Score (%)", "Matched Skills", "Missing Skills", "Exp. (yrs)"]]
    for r in rows:
        table_data.append([
            r["rank"],
            r["candidate_name"],
            r["final_score"],
            ", ".join(r["matched_skills"]) or "-",
            ", ".join(r["missing_skills"]) or "-",
            r["experience_years"] if r["experience_years"] is not None else "N/A",
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f9")]),
    ]))
    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return send_file(
        buffer, mimetype="application/pdf", as_attachment=True,
        download_name=f"shortlist_{LAST_RESULTS['job_title'].replace(' ', '_')}.pdf",
    )


if __name__ == "__main__":
    # PORT is provided automatically by hosts like Render/Railway; locally it
    # just falls back to 5000, so this behaves exactly as before on your machine.
    port = int(os.environ.get("PORT", 5000))
    # Debug mode stays on by default for local development. Hosts should set
    # FLASK_DEBUG=false in their environment variables for production.
    debug_mode = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)