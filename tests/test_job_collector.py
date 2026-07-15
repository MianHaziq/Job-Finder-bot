import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import job_collector as jc

load_dotenv()


def test_normalize_adzuna_job_maps_fields_correctly():
    raw_job = {
        "title": "Backend Engineer",
        "company": {"display_name": "Acme Corp"},
        "location": {"display_name": "Berlin, Germany"},
        "created": "2026-07-10T12:00:00Z",
        "redirect_url": "https://example.com/job/123",
        "description": "We need a backend engineer with visa sponsorship available.",
    }
    job = jc.normalize_adzuna_job(raw_job, country="de")

    assert job == {
        "title": "Backend Engineer",
        "company": "Acme Corp",
        "location": "Berlin, Germany",
        "country": "de",
        "date_posted": "2026-07-10T12:00:00Z",
        "url": "https://example.com/job/123",
        "description": "We need a backend engineer with visa sponsorship available.",
        "is_remote": False,
        "source": "adzuna",
    }


def test_normalize_adzuna_job_detects_remote_from_title_or_location():
    remote_in_title = jc.normalize_adzuna_job(
        {"title": "Remote Backend Engineer", "location": {"display_name": "Berlin, Germany"}}, country="de"
    )
    remote_in_location = jc.normalize_adzuna_job(
        {"title": "Backend Engineer", "location": {"display_name": "Remote, US"}}, country="us"
    )
    not_remote = jc.normalize_adzuna_job(
        {"title": "Backend Engineer", "location": {"display_name": "Berlin, Germany"}}, country="de"
    )
    assert remote_in_title["is_remote"] is True
    assert remote_in_location["is_remote"] is True
    assert not_remote["is_remote"] is False


def test_normalize_adzuna_job_handles_missing_fields():
    job = jc.normalize_adzuna_job({}, country="gb")
    assert job["title"] == ""
    assert job["company"] == ""
    assert job["source"] == "adzuna"


@pytest.mark.skipif(
    not (os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY")),
    reason="Adzuna API credentials not set in .env",
)
def test_fetch_adzuna_jobs_returns_real_results():
    jobs = jc.fetch_adzuna_jobs(
        country="gb",
        keyword="software engineer",
        app_id=os.getenv("ADZUNA_APP_ID"),
        app_key=os.getenv("ADZUNA_APP_KEY"),
        results_per_page=5,
    )
    assert len(jobs) > 0
    for job in jobs:
        assert job.get("title")
        assert job.get("redirect_url", "").startswith("http")


def test_strip_html_removes_tags_and_unescapes_entities():
    raw = "&lt;p&gt;Backend role, &amp;great team&lt;/p&gt;"
    assert jc._strip_html(raw) == "Backend role, &great team"


def test_normalize_arbeitnow_job_maps_fields_correctly():
    raw_job = {
        "title": "Backend Engineer",
        "company_name": "Acme GmbH",
        "location": "Berlin, Germany",
        "created_at": 1700000000,
        "url": "https://arbeitnow.com/jobs/acme/backend-engineer",
        "description": "<p>Visa sponsorship available.</p>",
    }
    job = jc.normalize_arbeitnow_job(raw_job)
    assert job["title"] == "Backend Engineer"
    assert job["company"] == "Acme GmbH"
    assert job["country"] == "Germany"
    assert job["description"] == "Visa sponsorship available."
    assert job["source"] == "arbeitnow"
    assert job["date_posted"].startswith("2023-11-14")
    assert job["is_remote"] is False


def test_normalize_arbeitnow_job_uses_explicit_remote_flag():
    raw_job = {"title": "Backend Engineer", "company_name": "Acme", "location": "Munich",
               "created_at": 1700000000, "url": "https://x.com", "description": "", "remote": True}
    job = jc.normalize_arbeitnow_job(raw_job)
    assert job["is_remote"] is True


def test_normalize_greenhouse_job_maps_fields_correctly():
    raw_job = {
        "title": "AI Engineer",
        "company_name": "GitLab",
        "location": {"name": "Remote, Italy"},
        "first_published": "2026-05-29T07:49:29-04:00",
        "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/123",
        "content": "&lt;p&gt;Great AI role&lt;/p&gt;",
    }
    job = jc.normalize_greenhouse_job(raw_job, company="gitlab")
    assert job["title"] == "AI Engineer"
    assert job["country"] == "Italy"
    assert job["description"] == "Great AI role"
    assert job["source"] == "greenhouse"
    assert job["is_remote"] is True


def test_normalize_greenhouse_job_detects_remote_from_messy_location_formats():
    for location_name in ["US-Remote", "Remote in the US", "Remote - USA", "Remote"]:
        job = jc.normalize_greenhouse_job(
            {"title": "Engineer", "location": {"name": location_name}}, company="acme"
        )
        assert job["is_remote"] is True, f"expected is_remote for {location_name!r}"

    not_remote = jc.normalize_greenhouse_job(
        {"title": "Engineer", "location": {"name": "Berlin, Germany"}}, company="acme"
    )
    assert not_remote["is_remote"] is False


def test_fetch_arbeitnow_jobs_returns_real_results():
    jobs = jc.fetch_arbeitnow_jobs()
    assert len(jobs) > 0
    assert jobs[0].get("title")


def test_fetch_greenhouse_jobs_returns_real_results():
    jobs = jc.fetch_greenhouse_jobs("gitlab")
    assert len(jobs) > 0
    assert jobs[0].get("title")


def test_collect_all_merges_multiple_sources():
    jobs = jc.collect_all(
        keyword="software engineer",
        app_id=os.getenv("ADZUNA_APP_ID", ""),
        app_key=os.getenv("ADZUNA_APP_KEY", ""),
    )
    sources = {job["source"] for job in jobs}
    assert len(sources) >= 2
    for job in jobs:
        assert job["title"]
        assert job["url"].startswith("http")
