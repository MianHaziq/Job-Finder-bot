import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import resume_parser as rp

RESUME_DIR = Path(__file__).resolve().parent.parent / "my-resume"
EUROPASS_CV = RESUME_DIR / "HAZIQ_RESUME_UPDATED_V001.pdf"
SIMPLE_CV = RESUME_DIR / "Muhammad_Haziq_Nazeer_Resume_TWO.pdf"


def _assert_valid_profile(profile: dict):
    assert profile["name"] == "Muhammad Haziq Nazeer"
    assert "@" in profile["email"]
    assert len(profile["skills"]) >= 10
    assert "Python" in profile["skills"]
    assert len(profile["job_titles"]) >= 1
    assert profile["years_of_experience"] > 0
    assert len(profile["education"]) >= 1


def test_europass_cv_parses_correctly():
    profile = rp.build_profile(EUROPASS_CV)
    _assert_valid_profile(profile)


def test_simple_cv_parses_correctly():
    profile = rp.build_profile(SIMPLE_CV)
    _assert_valid_profile(profile)


def test_extract_skills_strips_stray_punctuation():
    sections = {"SKILLS": ["Databases & Storage:: PostgreSQL, MongoDB"]}
    skills = rp.extract_skills(sections)
    assert "PostgreSQL" in skills
    assert not any(s.startswith(":") for s in skills)


def test_build_combined_profile_merges_skills_from_both_resumes():
    combined = rp.build_combined_profile([EUROPASS_CV, SIMPLE_CV])
    europass_only = rp.build_profile(EUROPASS_CV)
    simple_only = rp.build_profile(SIMPLE_CV)

    # Combined skill list must contain everything from both, deduplicated.
    for skill in europass_only["skills"]:
        assert any(skill.lower() == s.lower() for s in combined["skills"])
    for skill in simple_only["skills"]:
        assert any(skill.lower() == s.lower() for s in combined["skills"])
    assert len(combined["skills"]) >= len(simple_only["skills"])
    assert len(combined["skills"]) == len(set(s.lower() for s in combined["skills"]))  # no duplicates
    assert combined["name"] == "Muhammad Haziq Nazeer"
    assert "@" in combined["email"]
    assert len(combined["job_titles"]) >= 1
    assert len(combined["education"]) >= 1
