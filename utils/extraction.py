"""
Module 3: Information Extraction
Pulls structured fields (skills, education, years of experience) out of the
cleaned resume/JD text. Corresponds to Objective 2.

Skills: matched against a synonym-aware dictionary (data/skills.json) so that
different phrasings of the same skill ("ML" vs "machine learning") resolve to
one canonical skill name. This is what keeps the dictionary step from
reintroducing the exact keyword-brittleness problem the project sets out to
fix -- known synonyms are folded together here, and anything the dictionary
still misses is caught downstream by the Sentence-BERT semantic score.

Education / experience: a lightweight regex + spaCy NER approach, appropriate
for a mini project's scope (kept simple and explainable rather than a full
information-extraction model).
"""
import json
import os
import re

import spacy

_SKILLS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "skills.json")
with open(_SKILLS_PATH, "r", encoding="utf-8") as f:
    _SKILL_DICT = json.load(f)

# Flat lookup: alias -> canonical skill name
_ALIAS_TO_CANONICAL = {}
for canonical, aliases in _SKILL_DICT.items():
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical

# Load spaCy's small English model. If it isn't installed, extraction falls
# back to regex-only education detection (still functional, just less
# thorough) instead of crashing the app.
try:
    _nlp = spacy.load("en_core_web_sm")
except OSError:
    _nlp = None

_DEGREE_PATTERNS = [
    r"\bb\.?\s?tech\b", r"\bb\.?\s?e\b", r"\bbachelor(?:'s)?\b", r"\bb\.?\s?sc\b", r"\bbca\b",
    r"\bm\.?\s?tech\b", r"\bm\.?\s?e\b", r"\bmaster(?:'s)?\b", r"\bm\.?\s?sc\b", r"\bmca\b",
    r"\bmba\b", r"\bph\.?\s?d\b", r"\bdiploma\b", r"\bassociate(?:'s)?\s+degree\b",
]

_EXPERIENCE_PATTERNS = [
    r"(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\s+(?:of\s+)?experience",
    r"experience\s+of\s+(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)",
]


def extract_skills(clean_text_str):
    """Return the set of canonical skill names found in the text."""
    found = set()
    for alias, canonical in _ALIAS_TO_CANONICAL.items():
        # word-boundary match so "r" doesn't match inside "developer", etc.
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        if re.search(pattern, clean_text_str):
            found.add(canonical)
    return found


def extract_education(raw_text):
    """Return the list of degree/qualification mentions found in the text."""
    text_lower = raw_text.lower()
    found = []
    for pattern in _DEGREE_PATTERNS:
        if re.search(pattern, text_lower):
            # store the readable pattern label rather than the raw regex
            label = pattern.strip(r"\b").replace(r"\.?\s?", ".").replace(r"\s+", " ")
            found.append(label)
    return sorted(set(found))


def extract_experience_years(raw_text):
    """Return the highest number of years of experience mentioned, or None."""
    text_lower = raw_text.lower()
    years_found = []
    for pattern in _EXPERIENCE_PATTERNS:
        for match in re.finditer(pattern, text_lower):
            try:
                years_found.append(float(match.group(1)))
            except (ValueError, IndexError):
                continue
    return max(years_found) if years_found else None


def extract_organizations(raw_text):
    """Optional: use spaCy NER to pull organization names (companies, institutes).
    Used for display in the candidate detail view, not for scoring."""
    if _nlp is None:
        return []
    doc = _nlp(raw_text[:100000])  # guard against extremely long documents
    orgs = {ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"}
    return sorted(orgs)


def extract_all_fields(raw_text, clean_text_str):
    """Convenience wrapper returning every extracted field in one dict."""
    return {
        "skills": sorted(extract_skills(clean_text_str)),
        "education": extract_education(raw_text),
        "experience_years": extract_experience_years(raw_text),
        "organizations": extract_organizations(raw_text),
    }
