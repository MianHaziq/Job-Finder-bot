"""
Module 3/4: Job Collector.

Module 3 (single source): Adzuna only - fetch_adzuna_jobs / normalize_adzuna_job.
Module 4 (multi-source): adds Arbeitnow (Europe, no key needed) and Greenhouse
public company boards, and merges everything into one combined list using the
same normalized job format: title, company, location, country, date_posted,
url, description, source.

Pakistan is intentionally NOT covered here (Adzuna doesn't support it, and
Rozee.pk has no public API - decided to skip scraping it for v1).
"""
import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "jobs_raw.json"

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

# Adzuna country codes that overlap with the target regions from
# docs/1-project-goal.md (Europe, USA, Australia, Canada, New Zealand).
ADZUNA_TARGET_COUNTRIES = [
    "us", "gb", "ca", "au", "nz",           # USA, UK, Canada, Australia, New Zealand
    "de", "fr", "nl", "at", "es", "it", "pl", "be", "ch",  # Europe
]

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
GREENHOUSE_BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"

# Public Greenhouse company boards to pull from. Add/remove slugs here -
# validate a slug works by checking GREENHOUSE_BASE_URL.format(company=slug).
GREENHOUSE_COMPANIES = ["gitlab", "stripe", "airbnb"]


def _strip_html(raw_html: str) -> str:
    """Removes HTML tags and unescapes entities to get plain-text descriptions."""
    if not raw_html:
        return ""
    unescaped = html.unescape(raw_html)
    return re.sub(r"<[^>]+>", " ", unescaped).strip()


def _looks_remote(*texts: str) -> bool:
    """Heuristic remote-role check for sources with no explicit remote flag
    (Adzuna, Greenhouse) - both commonly write "Remote" into the title or
    location for fully-remote roles (e.g. Greenhouse's "Remote, Italy")."""
    return any("remote" in (text or "").lower() for text in texts)


def fetch_adzuna_jobs(country: str, keyword: str, app_id: str, app_key: str,
                       results_per_page: int = 20, page: int = 1) -> list:
    """Calls Adzuna's search endpoint and returns the raw list of job dicts."""
    url = ADZUNA_BASE_URL.format(country=country, page=page)
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results_per_page,
        "what": keyword,
        "content-type": "application/json",
    }
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    return response.json().get("results", [])


def normalize_adzuna_job(raw_job: dict, country: str) -> dict:
    title = raw_job.get("title", "")
    location = raw_job.get("location", {}).get("display_name", "")
    return {
        "title": title,
        "company": raw_job.get("company", {}).get("display_name", ""),
        "location": location,
        "country": country,
        "date_posted": raw_job.get("created", ""),
        "url": raw_job.get("redirect_url", ""),
        "description": raw_job.get("description", ""),
        "is_remote": _looks_remote(title, location),
        "source": "adzuna",
    }


def collect_adzuna(country: str, keyword: str, app_id: str, app_key: str) -> list:
    raw_jobs = fetch_adzuna_jobs(country, keyword, app_id, app_key)
    return [normalize_adzuna_job(job, country) for job in raw_jobs]


def collect_adzuna_multi(keyword: str, app_id: str, app_key: str,
                          countries: list = None) -> list:
    """Queries Adzuna once per target country. A single country failing
    (rate limit, timeout, etc.) is logged and skipped - the rest still run."""
    countries = countries or ADZUNA_TARGET_COUNTRIES
    jobs = []
    for country in countries:
        try:
            jobs.extend(collect_adzuna(country, keyword, app_id, app_key))
        except requests.RequestException as e:
            print(f"[job_collector] Adzuna failed for country={country}: {e}")
    return jobs


def fetch_arbeitnow_jobs() -> list:
    response = requests.get(ARBEITNOW_URL, timeout=20)
    response.raise_for_status()
    return response.json().get("data", [])


def normalize_arbeitnow_job(raw_job: dict) -> dict:
    location = raw_job.get("location", "") or ""
    country = location.split(",")[-1].strip() if "," in location else "Europe"
    created_at = raw_job.get("created_at")
    date_posted = (
        datetime.fromtimestamp(created_at, tz=timezone.utc).isoformat()
        if created_at else ""
    )
    return {
        "title": raw_job.get("title", ""),
        "company": raw_job.get("company_name", ""),
        "location": location,
        "country": country,
        "date_posted": date_posted,
        "url": raw_job.get("url", ""),
        "description": _strip_html(raw_job.get("description", "")),
        "is_remote": bool(raw_job.get("remote", False)),
        "source": "arbeitnow",
    }


def collect_arbeitnow() -> list:
    raw_jobs = fetch_arbeitnow_jobs()
    return [normalize_arbeitnow_job(job) for job in raw_jobs]


def fetch_greenhouse_jobs(company: str) -> list:
    url = GREENHOUSE_BASE_URL.format(company=company)
    response = requests.get(url, params={"content": "true"}, timeout=20)
    response.raise_for_status()
    return response.json().get("jobs", [])


def normalize_greenhouse_job(raw_job: dict, company: str) -> dict:
    title = raw_job.get("title", "")
    location = raw_job.get("location", {}).get("name", "") or ""
    country = location.split(",")[-1].strip() if "," in location else location
    return {
        "title": title,
        "company": raw_job.get("company_name", company),
        "location": location,
        "country": country,
        "date_posted": raw_job.get("first_published", ""),
        "url": raw_job.get("absolute_url", ""),
        "description": _strip_html(raw_job.get("content", "")),
        "is_remote": _looks_remote(title, location),
        "source": "greenhouse",
    }


def collect_greenhouse(company: str) -> list:
    raw_jobs = fetch_greenhouse_jobs(company)
    return [normalize_greenhouse_job(job, company) for job in raw_jobs]


def collect_greenhouse_multi(companies: list = None) -> list:
    companies = companies or GREENHOUSE_COMPANIES
    jobs = []
    for company in companies:
        try:
            jobs.extend(collect_greenhouse(company))
        except requests.RequestException as e:
            print(f"[job_collector] Greenhouse failed for company={company}: {e}")
    return jobs


def collect_all(keyword: str, app_id: str, app_key: str) -> list:
    """Merges every source into one combined list. Each source is isolated -
    one failing entirely (e.g. bad API key) doesn't stop the others."""
    jobs = []

    try:
        jobs.extend(collect_adzuna_multi(keyword, app_id, app_key))
    except requests.RequestException as e:
        print(f"[job_collector] Adzuna source failed entirely: {e}")

    try:
        jobs.extend(collect_arbeitnow())
    except requests.RequestException as e:
        print(f"[job_collector] Arbeitnow source failed entirely: {e}")

    try:
        jobs.extend(collect_greenhouse_multi())
    except requests.RequestException as e:
        print(f"[job_collector] Greenhouse source failed entirely: {e}")

    return jobs


def main():
    load_dotenv()
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise SystemExit("ADZUNA_APP_ID / ADZUNA_APP_KEY are not set in .env")

    keyword = "software engineer"

    jobs = collect_all(keyword, app_id, app_key)

    by_source = {}
    for job in jobs:
        by_source[job["source"]] = by_source.get(job["source"], 0) + 1
    print(f"--- COLLECTED {len(jobs)} JOBS ---")
    for source, count in by_source.items():
        print(f"  {source}: {count}")

    DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)
    print(f"\nSaved {len(jobs)} jobs to {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
