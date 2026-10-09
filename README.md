# ResumeMatch AI

An AI-based resume screening and job-matching system. Upload a batch of
resumes (PDF/DOCX) and a job description; get back a ranked, explainable
shortlist showing exactly which required skills each candidate matched or
is missing.

## How this maps to the project's methodology

| Pipeline stage (report)            | Code                          |
|-------------------------------------|-------------------------------|
| Web Interface                       | `templates/index.html`, `static/` |
| Text Extraction & Pre-processing    | `utils/parser.py`, `utils/preprocessing.py` |
| Information Extraction              | `utils/extraction.py`        |
| Embedding Generation (S-BERT + TF-IDF) | `utils/embedding.py`      |
| Similarity & Match Scoring          | `utils/scoring.py`            |
| Ranking, Dashboard, Report Export   | `app.py` (Flask routes)       |

## Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Download the spaCy English model (used for organization/education-adjacent
   NER; the app runs fine without it, just with lighter extraction):
   ```bash
   python -m spacy download en_core_web_sm
   ```

3. NLTK data (stopwords, tokenizer, lemmatizer) downloads automatically the
   first time you run the app. If your machine has no internet access at
   runtime, pre-download once with:
   ```bash
   python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords'); nltk.download('wordnet')"
   ```

4. Run the app:
   ```bash
   python app.py
   ```
   Then open **http://127.0.0.1:5000** in your browser.

## Notes on design decisions (for your report)

- **No database.** Results are held in memory for the current server
  session; this matches a single-session "upload -> view -> export"
  workflow and avoids unnecessary complexity for a mini project. Swapping
  in SQLite (already listed in the software requirements) would mean
  persisting `LAST_RESULTS` to a table keyed by a run/job id, so recruiters
  could revisit past shortlists later -- a natural extension, not a rebuild.
- **Weights are configurable, not hard-coded philosophy.** `DEFAULT_WEIGHTS`
  in `utils/scoring.py` is a plain dictionary. Tuning them against a
  human-reviewer ranking (Objective 6) is a matter of trying different
  values and comparing rank agreement (e.g. Spearman correlation) --
  no code changes needed elsewhere.
- **First request will be slow.** The Sentence-BERT model
  (`all-MiniLM-L6-v2`) loads lazily on the first `/api/analyze` call and is
  cached afterward (`utils/embedding.py`). Expect the very first analysis
  in a session to take longer than the ~10 second target; subsequent runs
  in the same session should be much faster. If this matters for your
  evaluation, consider "warming up" the model on app startup instead of on
  first request.
- **Scanned/image-based resumes are out of scope**, per your report -- if
  `pdfplumber` extracts no text from a PDF, that file is skipped with a
  reported error rather than silently producing a zero score.
