import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import scorer


def test_score_job_counts_matched_skills_as_percentage():
    job = {"title": "Backend Engineer", "description": "We use Node.js and Python daily."}
    score, matched = scorer.score_job(job, ["Node.js", "Python", "Java", "C++"])
    assert set(matched) == {"Node.js", "Python"}
    assert score == 50.0


def test_score_job_does_not_match_java_inside_javascript():
    job = {"title": "Frontend Developer", "description": "We use JavaScript and TypeScript extensively."}
    score, matched = scorer.score_job(job, ["Java", "JavaScript", "C++"])
    assert matched == ["JavaScript"]


def test_score_job_handles_punctuation_heavy_skills_like_cpp():
    job = {"title": "Systems Engineer", "description": "Strong knowledge of C++ and Java required."}
    score, matched = scorer.score_job(job, ["Java", "C++"])
    assert set(matched) == {"Java", "C++"}


def test_score_job_with_no_overlap_scores_zero():
    job = {"title": "Sales Manager", "description": "Manage client relationships and quotas."}
    score, matched = scorer.score_job(job, ["Python", "React", "AWS"])
    assert score == 0.0
    assert matched == []


def test_score_jobs_sorts_descending_by_score():
    resume_skills = ["Python", "React", "AWS"]
    jobs = [
        {"title": "Sales Manager", "description": "no overlap here"},
        {"title": "Full Stack Dev", "description": "Python, React, and AWS experience required"},
        {"title": "Backend Dev", "description": "Python experience required"},
    ]
    scored = scorer.score_jobs(jobs, {"skills": resume_skills})
    scores = [j["score"] for j in scored]
    assert scores == sorted(scores, reverse=True)
    assert scored[0]["title"] == "Full Stack Dev"
    assert scored[-1]["title"] == "Sales Manager"
