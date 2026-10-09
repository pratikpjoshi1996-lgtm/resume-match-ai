"""
Module 4: Embedding Generation
Produces two representations for each document:
  - a Sentence-BERT vector, capturing semantic meaning (Reimers & Gurevych, 2019)
  - a TF-IDF vector, capturing exact keyword weight
Corresponds to Objective 3.
"""
from functools import lru_cache

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# all-MiniLM-L6-v2 is a small, fast Sentence-BERT model well suited to a
# CPU-only mini-project deployment while still giving strong semantic
# similarity performance.
_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model():
    """Load the Sentence-BERT model once and cache it for the app's lifetime."""
    return SentenceTransformer(_MODEL_NAME)


def get_semantic_embedding(text):
    """Return a single Sentence-BERT vector for the given text."""
    model = _get_model()
    return model.encode(text, convert_to_numpy=True)


def semantic_similarity(text_a, text_b):
    """Cosine similarity between the Sentence-BERT embeddings of two texts,
    scaled to [0, 1]."""
    model = _get_model()
    vecs = model.encode([text_a, text_b], convert_to_numpy=True)
    sim = cosine_similarity([vecs[0]], [vecs[1]])[0][0]
    return float(max(0.0, min(1.0, sim)))


def tfidf_similarity(text_a, text_b):
    """Cosine similarity between TF-IDF vectors fit jointly on the two texts.
    Captures exact keyword overlap, complementing the semantic score."""
    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        tfidf_matrix = vectorizer.fit_transform([text_a, text_b])
    except ValueError:
        # happens if both texts are empty after cleaning
        return 0.0
    sim = cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])[0][0]
    return float(max(0.0, min(1.0, sim)))
