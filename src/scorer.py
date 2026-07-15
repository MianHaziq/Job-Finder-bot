"""
Module 7: Resume Matching & Scoring.

Scores each surviving job (from filters.py) against resume_profile.json
(from resume_parser.py) using simple keyword overlap: how many of your
resume's skills appear in the job's title/description. Jobs are sorted by
score, descending, so the best matches rise to the top - but a role whose
title signals a seniority level well above your actual experience is always
ranked below every appropriately-leveled role, regardless of skill score.
"""
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JOBS_INPUT_PATH = PROJECT_ROOT / "data" / "jobs_filtered.json"
RESUME_PATH = PROJECT_ROOT / "data" / "resume_profile.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "jobs_scored.json"

# Job titles containing these words expect more experience than a junior/
# early-career candidate typically has.
SENIOR_TITLE_KEYWORDS = [
    "senior", "sr.", "staff", "principal", "lead", "director",
    "head of", "vp", "chief", "architect",
]
JUNIOR_EXPERIENCE_THRESHOLD_YEARS = 3.0


def _whole_word_match(term: str, text: str) -> bool:
    """Whole-word/whole-token match: plain substring matching would wrongly
    match "Java" inside "JavaScript". A plain \\b regex boundary breaks on
    terms ending in punctuation (e.g. "C++"), since \\b requires one side to
    be a word character - here both sides ('+' and the following space) are
    non-word, so \\b never matches. Using explicit alphanumeric lookarounds
    instead treats any punctuation/space as a valid boundary either way.
    """
    pattern = r"(?<![a-zA-Z0-9])" + re.escape(term.lower()) + r"(?![a-zA-Z0-9])"
    return re.search(pattern, text) is not None


def is_seniority_mismatch(job_title: str, years_of_experience: float) -> bool:
    """True if the title signals a seniority level ("Senior", "Staff", "Lead",
    etc.) that a candidate with under 3 years of experience wouldn't
    typically be considered for."""
    if years_of_experience >= JUNIOR_EXPERIENCE_THRESHOLD_YEARS:
        return False
    title_lower = (job_title or "").lower()
    return any(_whole_word_match(keyword, title_lower) for keyword in SENIOR_TITLE_KEYWORDS)


def score_job(job: dict, resume_skills: list) -> tuple:
    """Returns (matched_skill_count, matched_skills) for one job against the
    resume's skill list. Deliberately a raw count, not a percentage of total
    resume skills - a percentage shrinks every time more skills are added to
    the resume (e.g. after merging two resumes), even though the actual
    match quality hasn't changed."""
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    matched = [skill for skill in resume_skills if _whole_word_match(skill, text)]
    return len(matched), matched


def score_jobs(jobs: list, resume_profile: dict) -> list:
    resume_skills = resume_profile.get("skills", [])
    years_of_experience = resume_profile.get("years_of_experience", 0)
    scored = []
    for job in jobs:
        score, matched = score_job(job, resume_skills)
        tagged = dict(job)
        tagged["score"] = score
        tagged["matched_skills"] = matched
        tagged["seniority_mismatch"] = is_seniority_mismatch(job.get("title", ""), years_of_experience)
        scored.append(tagged)
    # Seniority-appropriate roles always rank above mismatched ones; within
    # each group, higher skill-match count ranks first.
    return sorted(scored, key=lambda j: (j["seniority_mismatch"], -j["score"]))


def main():
    if not JOBS_INPUT_PATH.exists():
        raise SystemExit(f"{JOBS_INPUT_PATH} not found - run filters.py first")
    if not RESUME_PATH.exists():
        raise SystemExit(f"{RESUME_PATH} not found - run resume_parser.py first")

    with open(JOBS_INPUT_PATH, encoding="utf-8") as f:
        jobs = json.load(f)
    with open(RESUME_PATH, encoding="utf-8") as f:
        resume_profile = json.load(f)

    scored_jobs = score_jobs(jobs, resume_profile)

    print(f"Scored {len(scored_jobs)} jobs against {len(resume_profile.get('skills', []))} resume skills.\n")
    print("--- TOP MATCHES ---")
    for job in scored_jobs[:10]:
        flag = " [SENIOR - may exceed your experience]" if job["seniority_mismatch"] else ""
        print(f"[{job['score']:2d} matched] {job['title']} - {job['company']} ({job['country']}){flag} "
              f"| matched: {', '.join(job['matched_skills']) or 'none'}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(scored_jobs, f, indent=2)
    print(f"\nSaved {len(scored_jobs)} scored jobs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
