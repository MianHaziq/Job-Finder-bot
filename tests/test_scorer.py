import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import scorer


def test_score_job_returns_raw_matched_count_not_percentage():
    job = {"title": "Backend Engineer", "description": "We use Node.js and Python daily."}
    score, matched = scorer.score_job(job, ["Node.js", "Python", "Java", "C++"])
    assert set(matched) == {"Node.js", "Python"}
    assert score == 2  # raw count, not a percentage of resume_skills


def test_score_job_count_is_stable_regardless_of_resume_skill_list_size():
    """The bug this fixes: with a percentage-based score, the same match
    would score lower just because more (unrelated) skills got added to the
    resume - e.g. after merging two resumes. A raw count doesn't have this
    problem."""
    job = {"title": "Backend Engineer", "description": "We use Node.js daily."}
    small_resume_skills = ["Node.js"]
    large_resume_skills = ["Node.js"] + [f"Skill{i}" for i in range(50)]
    score_small, _ = scorer.score_job(job, small_resume_skills)
    score_large, _ = scorer.score_job(job, large_resume_skills)
    assert score_small == score_large == 1


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
    assert score == 0
    assert matched == []


def test_is_seniority_mismatch_flags_senior_titles_for_junior_candidates():
    assert scorer.is_seniority_mismatch("Senior Backend Engineer", years_of_experience=1.4) is True
    assert scorer.is_seniority_mismatch("Staff Software Engineer", years_of_experience=0.5) is True
    assert scorer.is_seniority_mismatch("Principal Architect", years_of_experience=2.0) is True


def test_is_seniority_mismatch_false_for_appropriate_titles():
    assert scorer.is_seniority_mismatch("Software Engineer", years_of_experience=1.4) is False
    assert scorer.is_seniority_mismatch("Junior Developer", years_of_experience=1.4) is False


def test_is_seniority_mismatch_false_once_experienced_enough():
    assert scorer.is_seniority_mismatch("Senior Backend Engineer", years_of_experience=5.0) is False


def test_score_jobs_ranks_seniority_appropriate_jobs_above_mismatched_ones():
    resume_profile = {"skills": ["Python", "React", "AWS"], "years_of_experience": 1.0}
    senior_high_overlap = {
        "title": "Senior Backend Engineer",
        "description": "Python, React, and AWS experience required",
    }
    junior_lower_overlap = {
        "title": "Software Engineer",
        "description": "Python experience required",
    }
    scored = scorer.score_jobs([senior_high_overlap, junior_lower_overlap], resume_profile)
    # Even though the senior role has a higher raw skill-match count, the
    # appropriately-leveled role should rank first.
    assert scored[0]["title"] == "Software Engineer"
    assert scored[0]["seniority_mismatch"] is False
    assert scored[1]["title"] == "Senior Backend Engineer"
    assert scored[1]["seniority_mismatch"] is True


def test_score_jobs_sorts_descending_by_score_within_same_seniority_group():
    resume_profile = {"skills": ["Python", "React", "AWS"], "years_of_experience": 5.0}
    jobs = [
        {"title": "Sales Manager", "description": "no overlap here"},
        {"title": "Full Stack Dev", "description": "Python, React, and AWS experience required"},
        {"title": "Backend Dev", "description": "Python experience required"},
    ]
    scored = scorer.score_jobs(jobs, resume_profile)
    scores = [j["score"] for j in scored]
    assert scores == sorted(scores, reverse=True)
    assert scored[0]["title"] == "Full Stack Dev"
    assert scored[-1]["title"] == "Sales Manager"
