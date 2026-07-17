import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import scorer


def _job(title="Software Engineer", description="", days_old=0, is_remote=False, url="https://example.com/1"):
    from datetime import datetime, timedelta, timezone
    posted = datetime.now(timezone.utc) - timedelta(days=days_old)
    return {
        "title": title,
        "company": "Acme Corp",
        "country": "us",
        "description": description,
        "date_posted": posted.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "url": url,
        "is_remote": is_remote,
        "relocation_required": True,
    }


# --- Stage 1: role relevance gate ------------------------------------------

def test_accepts_core_target_role_titles():
    for title in [
        "Software Engineer", "Software Developer", "Full Stack Developer",
        "Full Stack Engineer", "MERN Stack Developer", "React Developer",
        "Node.js Developer", "JavaScript Developer", "Web Developer",
        "Backend Developer", "Frontend Developer",
    ]:
        result = scorer.evaluate_role_relevance(_job(title=title))
        assert result["accepted"] is True, f"expected accept for {title!r}, got: {result['reason']}"


def test_accepts_level_qualified_variations_of_software_engineer():
    """Associate/Junior/Graduate/Software Engineer I should all match the
    same underlying role as bare 'Software Engineer'."""
    for title in [
        "Associate Software Engineer", "Junior Software Engineer",
        "Software Engineer I", "Graduate Software Engineer",
        "Entry Level Software Engineer",
    ]:
        result = scorer.evaluate_role_relevance(_job(title=title))
        assert result["accepted"] is True, f"expected accept for {title!r}, got: {result['reason']}"
        assert result["is_junior_labeled"] is True


def test_rejects_excluded_industries_regardless_of_skill_overlap():
    for title in [
        "Sales Manager", "Marketing Coordinator", "Recruiter",
        "HR Business Partner", "Customer Support Specialist",
        "Accountant", "Registered Nurse", "High School Teacher",
        "Civil Engineer", "Mechanical Engineer", "Electrical Engineer",
        "Data Entry Clerk", "Call Center Agent", "Truck Driver",
    ]:
        result = scorer.evaluate_role_relevance(_job(title=title))
        assert result["accepted"] is False, f"expected reject for {title!r}"
        assert "excluded industry" in result["reason"]


def test_rejects_senior_and_leadership_titles_outright():
    for title in [
        "Senior Software Engineer", "Staff Engineer", "Principal Engineer",
        "Lead Developer", "Engineering Director", "VP of Engineering",
        "Chief Technology Officer", "Solutions Architect", "Engineering Manager",
    ]:
        result = scorer.evaluate_role_relevance(_job(title=title))
        assert result["accepted"] is False, f"expected reject for {title!r}"
        assert "excluded seniority" in result["reason"]


def test_rejects_titles_with_no_target_role_match():
    """Roles that mention overlapping tech (AWS/Docker/Git) but aren't
    actually one of the target role types (the core bug this fixes)."""
    for title in ["DevOps Engineer", "Data Engineer", "Machine Learning Engineer",
                  "QA Automation Engineer", "Site Reliability Engineer"]:
        result = scorer.evaluate_role_relevance(_job(title=title))
        assert result["accepted"] is False, f"expected reject for {title!r}"
        assert result["reason"] == "title does not match any target role"


def test_junior_project_manager_requires_software_it_context():
    with_context = scorer.evaluate_role_relevance(
        _job(title="Junior Project Manager", description="manage software delivery for our IT team")
    )
    assert with_context["accepted"] is True

    without_context = scorer.evaluate_role_relevance(
        _job(title="Junior Project Manager", description="manage construction site logistics")
    )
    assert without_context["accepted"] is False
    assert "software/IT context" in without_context["reason"]


def test_manager_excluded_unless_junior_project_manager():
    assert scorer.evaluate_role_relevance(_job(title="Engineering Manager"))["accepted"] is False
    accepted = scorer.evaluate_role_relevance(
        _job(title="Junior Project Manager", description="software team")
    )
    assert accepted["accepted"] is True


# --- Regression tests for bugs found during the 105-job live validation ----

def test_accepts_tech_developer_titles_with_a_qualifier_word_in_between():
    """Real bug: 'Node.js Trainee Developer' and 'React / Angular Developer'
    were both wrongly rejected because the original regex required the tech
    word to sit immediately next to 'developer', with no qualifier or
    second technology allowed in between."""
    result = scorer.evaluate_role_relevance(_job(title="Node.js Trainee Developer - Remote"))
    assert result["accepted"] is True
    assert result["role_group"] == "nodejs_developer"

    result = scorer.evaluate_role_relevance(_job(title="React / Angular Developer"))
    assert result["accepted"] is True
    assert result["role_group"] == "react_developer"


def test_rejects_foreign_language_seniority_qualifier_via_diacritic_normalization():
    """Real bug: a Portuguese-market posting titled '...Developer Sênior...'
    slipped past the English-only 'senior' exclude pattern. Stripping
    diacritics before matching ("Sênior" -> "senior") catches this without
    needing a per-language keyword list."""
    result = scorer.evaluate_role_relevance(_job(title="Node.js Back-End Developer Sênior | Remote"))
    assert result["accepted"] is False
    assert "excluded seniority" in result["reason"]


def test_rejects_spelled_out_vice_president_not_just_the_abbreviation():
    """Real gap found during validation: 'Vice President' spelled out wasn't
    caught by the bare '\\bvp\\b' pattern."""
    result = scorer.evaluate_role_relevance(_job(title="Vice President of Software Engineering"))
    assert result["accepted"] is False
    assert "excluded seniority" in result["reason"]


# --- Stage 2: weighted scoring -----------------------------------------------

def test_role_group_weight_ranks_specialty_match_above_generic_match():
    resume = {"skills": [], "years_of_experience": 1.0}
    mern_job = _job(title="MERN Stack Developer", url="https://x.com/1")
    generic_job = _job(title="Software Developer", url="https://x.com/2")
    ranked = scorer.score_jobs([generic_job, mern_job], resume)
    assert ranked[0]["title"] == "MERN Stack Developer"


def test_remote_bonus_outranks_relocation_bonus():
    resume = {"skills": [], "years_of_experience": 1.0}
    remote_job = _job(title="Software Engineer", is_remote=True, url="https://x.com/1")
    relocation_job = _job(title="Software Engineer",
                           description="visa sponsorship available", url="https://x.com/2")
    ranked = scorer.score_jobs([relocation_job, remote_job], resume)
    assert ranked[0]["is_remote"] is True


def test_junior_labeled_titles_score_higher_than_unlabeled_of_same_role():
    resume = {"skills": [], "years_of_experience": 1.0}
    junior_job = _job(title="Junior Software Engineer", url="https://x.com/1")
    plain_job = _job(title="Software Engineer", url="https://x.com/2")
    ranked = scorer.score_jobs([plain_job, junior_job], resume)
    assert ranked[0]["title"] == "Junior Software Engineer"


def test_skill_overlap_contributes_to_score():
    resume = {"skills": ["React.js", "Node.js", "AWS"], "years_of_experience": 1.0}
    job = _job(title="Full Stack Developer", description="React.js and Node.js and AWS experience")
    scored = scorer.score_jobs([job], resume)
    assert len(scored) == 1
    assert set(scored[0]["matched_skills"]) == {"React.js", "Node.js", "AWS"}


def test_more_recent_postings_score_higher_all_else_equal():
    resume = {"skills": [], "years_of_experience": 1.0}
    fresh_job = _job(title="Software Engineer", days_old=0, url="https://x.com/1")
    stale_job = _job(title="Software Engineer", days_old=6, url="https://x.com/2")
    ranked = scorer.score_jobs([stale_job, fresh_job], resume)
    assert ranked[0]["url"] == "https://x.com/1"


# --- Full pipeline + logging -------------------------------------------------

def test_score_jobs_only_returns_accepted_jobs():
    resume = {"skills": [], "years_of_experience": 1.0}
    jobs = [
        _job(title="Software Engineer", url="https://x.com/1"),
        _job(title="Sales Manager", url="https://x.com/2"),
        _job(title="Senior Software Engineer", url="https://x.com/3"),
    ]
    result = scorer.score_jobs(jobs, resume)
    assert len(result) == 1
    assert result[0]["title"] == "Software Engineer"


def test_score_jobs_writes_full_audit_log_including_rejected_jobs(tmp_path):
    resume = {"skills": ["React.js"], "years_of_experience": 1.0}
    jobs = [
        _job(title="Software Engineer", description="React.js required", url="https://x.com/1"),
        _job(title="Sales Manager", url="https://x.com/2"),
    ]
    log_path = tmp_path / "evaluation_log.jsonl"
    scorer.score_jobs(jobs, resume, log_path=log_path)

    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    records = [json.loads(line) for line in lines]

    accepted_record = next(r for r in records if r["title"] == "Software Engineer")
    assert accepted_record["accepted"] is True
    assert "React.js" in accepted_record["matched_skills"]
    assert accepted_record["score"] > 0

    rejected_record = next(r for r in records if r["title"] == "Sales Manager")
    assert rejected_record["accepted"] is False
    assert "excluded industry" in rejected_record["reason"]
