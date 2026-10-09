"""
Module 5: Similarity & Match Scoring
Combines four signals into one final match score (Objective 4):
    Final Score = w1*Semantic + w2*TF-IDF + w3*SkillOverlap + w4*Experience
Also builds the explanation object every candidate is shown with
(matched skills / missing skills / per-component breakdown) -- Objective 5.
"""
from .embedding import semantic_similarity, tfidf_similarity

# Default weights (w1..w4). Sum to 1. Meant to be tuned during testing,
# e.g. via grid search against the human-reviewer ranking (Objective 6),
# rather than treated as fixed constants.
DEFAULT_WEIGHTS = {
    "semantic": 0.4,
    "tfidf": 0.2,
    "skill_overlap": 0.3,
    "experience": 0.1,
}


def skill_overlap_score(candidate_skills, required_skills):
    """Fraction of the JD's required skills that the candidate has.
    Returns (score, matched_list, missing_list)."""
    required_skills = set(required_skills)
    candidate_skills = set(candidate_skills)

    if not required_skills:
        # No skills could be extracted from the JD -- don't penalize
        # candidates for something we couldn't verify.
        return 1.0, sorted(candidate_skills), []

    matched = required_skills & candidate_skills
    missing = required_skills - candidate_skills
    score = len(matched) / len(required_skills)
    return score, sorted(matched), sorted(missing)


def experience_score(candidate_years, required_years):
    """Graded score: full credit at or above the requirement, linear credit
    below it. If either value is unknown, treat as neutral (no penalty),
    since experience is often stated informally and extraction is best-effort."""
    if required_years is None or required_years == 0:
        return 1.0
    if candidate_years is None:
        return 0.5  # unknown - don't fully penalize, don't fully credit either
    return max(0.0, min(1.0, candidate_years / required_years))


def compute_match_score(resume_clean_text, jd_clean_text,
                         candidate_skills, jd_skills,
                         candidate_years, jd_required_years,
                         weights=None):
    """Compute the full explainable match score for one resume against one JD."""
    weights = weights or DEFAULT_WEIGHTS

    semantic = semantic_similarity(resume_clean_text, jd_clean_text)
    tfidf = tfidf_similarity(resume_clean_text, jd_clean_text)
    skill_score, matched_skills, missing_skills = skill_overlap_score(candidate_skills, jd_skills)
    exp_score = experience_score(candidate_years, jd_required_years)

    final_score = (
        weights["semantic"] * semantic
        + weights["tfidf"] * tfidf
        + weights["skill_overlap"] * skill_score
        + weights["experience"] * exp_score
    )

    return {
        "final_score": round(final_score * 100, 2),        # shown as a 0-100 match %
        "breakdown": {
            "semantic": round(semantic * 100, 2),
            "tfidf": round(tfidf * 100, 2),
            "skill_overlap": round(skill_score * 100, 2),
            "experience": round(exp_score * 100, 2),
        },
        "weights_used": weights,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
    }
