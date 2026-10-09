#!/usr/bin/env bash
# ResumeMatch AI - quick start (macOS/Linux)
set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "Installing dependencies (first run only, this can take a few minutes)..."
pip install -q -r requirements.txt

python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null || python -m spacy download en_core_web_sm

echo "Starting ResumeMatch AI on http://127.0.0.1:5000"
python app.py
