"""
Module 2: Pre-processing
Cleans and normalizes raw extracted text using NLTK.
Corresponds to the "Pre-processing (clean, tokenize)" stage of the methodology.
"""
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

# Download required NLTK data on first run (no-op if already present).
for pkg in ["punkt", "punkt_tab", "stopwords", "wordnet"]:
    try:
        nltk.data.find(f"tokenizers/{pkg}" if "punkt" in pkg else f"corpora/{pkg}")
    except LookupError:
        nltk.download(pkg, quiet=True)

_lemmatizer = WordNetLemmatizer()
_stop_words = set(stopwords.words("english"))


def clean_text(text):
    """Lower-case, strip emails/URLs/special characters, collapse whitespace.
    Emails/phone numbers are stripped only for the matching pipeline's text —
    the original raw text is kept separately for display/extraction of
    contact-style fields if ever needed."""
    text = text.lower()
    text = re.sub(r"\S+@\S+", " ", text)          # emails
    text = re.sub(r"http\S+|www\S+", " ", text)   # urls
    text = re.sub(r"[^a-z0-9+.\-\s]", " ", text)  # keep + . - for skills like "c++", "node.js"
    text = re.sub(r"\s+", " ", text).strip()
    return text


def preprocess(text, remove_stopwords=True, lemmatize=True):
    """Full pre-processing pipeline: clean -> tokenize -> stop-word removal -> lemmatize.
    Returns (cleaned_full_text, list_of_tokens). The cleaned full text is what
    gets fed into TF-IDF / Sentence-BERT; the token list is used by simpler
    keyword-based steps (e.g. skill dictionary matching)."""
    cleaned = clean_text(text)
    tokens = word_tokenize(cleaned)

    if remove_stopwords:
        tokens = [t for t in tokens if t not in _stop_words]

    if lemmatize:
        tokens = [_lemmatizer.lemmatize(t) for t in tokens]

    return cleaned, tokens
