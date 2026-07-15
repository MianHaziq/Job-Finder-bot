"""
Module 7: Resume Matching & Scoring.

Scores each surviving job (from filters.py) against resume_profile.json
(from resume_parser.py) using simple keyword overlap: how many of your
resume's skills appear in the job's title/description. Jobs are sorted by
score, descending, so the best matches rise to the top.
"""
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JOBS_INPUT_PATH = PROJECT_ROOT / "data" / "jobs_filtered.json"
RESUME_PATH = PROJECT_ROOT / "data" / "resume_profile.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "jobs_scored.json"


def _skill_matches(skill: str, text: str) -> bool:
    """Whole-word/whole-token match: plain substring matching would wrongly
    match "Java" inside "JavaScript". A plain \\b regex boundary breaks on
    skills ending in punctuation (e.g. "C++"), since \\b requires one side to
    be a word character - here both sides ('+' and the following space) are
    non-word, so \\b never matches. Using explicit alphanumeric lookarounds
    instead treats any punctuation/space as a valid boundary either way.
    """
    pattern = r"(?<![a-zA-Z0-9])" + re.escape(skill.lower()) + r"(?![a-zA-Z0-9])"
    return re.search(pattern, text) is not None


def score_job(job: dict, resume_skills: list) -> tuple:
    """Returns (score 0-100, matched_skills) for one job against the resume's
    skill list. Score = % of resume skills that appear in the job text."""
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    matched = [skill for skill in resume_skills if _skill_matches(skill, text)]
    score = round(100 * len(matched) / max(len(resume_skills), 1), 1)
    return score, matched


def score_jobs(jobs: list, resume_profile: dict) -> list:
    resume_skills = resume_profile.get("skills", [])
    scored = []
    for job in jobs:
        score, matched = score_job(job, resume_skills)
        tagged = dict(job)
        tagged["score"] = score
        tagged["matched_skills"] = matched
        scored.append(tagged)
    return sorted(scored, key=lambda j: j["score"], reverse=True)


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
        print(f"[{job['score']:5.1f}] {job['title']} - {job['company']} ({job['country']}) "
              f"| matched: {', '.join(job['matched_skills']) or 'none'}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(scored_jobs, f, indent=2)
    print(f"\nSaved {len(scored_jobs)} scored jobs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
