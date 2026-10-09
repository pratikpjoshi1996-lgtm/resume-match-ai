@echo off
REM ResumeMatch AI - quick start (Windows)
cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
echo Installing dependencies (first run only, this can take a few minutes)...
pip install -q -r requirements.txt

python -m spacy download en_core_web_sm

echo Starting ResumeMatch AI on http://127.0.0.1:5000
python app.py
