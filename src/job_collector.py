"""
Module 3/4: Job Collector.

Module 3 (single source): Adzuna only - fetch_adzuna_jobs / normalize_adzuna_job.
Module 4 (multi-source): adds Arbeitnow (Europe, no key needed) and Greenhouse
public company boards, plus five more free no-key boards - Remotive, Jobicy,
RemoteOK, Himalayas (all remote-only) and The Muse (general, fetched
pre-filtered to Software Engineering) - and merges everything into one
combined list using the same normalized job format: title, company, location,
country, date_posted, url, description, is_remote, source.

Pakistan is intentionally NOT covered here (Adzuna doesn't support it, and
Rozee.pk has no public API - decided to skip scraping it for v1).

Adzuna is queried with multiple search-phrase variations (SEARCH_QUERIES)
across every country Adzuna supports (ADZUNA_ALL_COUNTRIES), not a single
keyword/country subset - see PROJECT_SETUP.md for why, and the resulting
schedule trade-off (this multiplies API call volume substantially).
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

# Every country Adzuna's API supports (confirmed directly against their API's
# own "UNSUPPORTED_COUNTRY" error message - there is no broader worldwide
# option, this is the full list). Several countries from the target list
# (Sweden, Norway, Denmark, Finland, Ireland, UAE, Saudi Arabia, Japan, South
# Korea, Luxembourg) are NOT reachable via Adzuna at all - a real, documented
# limitation. Arbeitnow/Greenhouse aren't restricted to a country list, so
# jobs from those countries can still surface via those two sources; a
# dedicated source for the Adzuna-unreachable countries is a good future
# addition (see the analysis report for recommendations).
ADZUNA_ALL_COUNTRIES = [
    "us", "gb", "ca", "au", "nz", "de", "fr", "nl", "at", "es", "it", "pl",
    "be", "ch", "br", "in", "mx", "sg", "za",
]

# Multiple search-phrase variations instead of one - covers the different
# ways the same kind of role gets titled (e.g. Adzuna's own search wouldn't
# necessarily surface a "MERN Stack Developer" posting from a bare
# "software engineer" query). Combined with all countries above, this is a
# large number of API calls per run - see PROJECT_SETUP.md for the resulting
# schedule trade-off.
SEARCH_QUERIES = [
    "Associate Software Engineer", "Junior Software Engineer", "Software Engineer I",
    "Graduate Software Engineer", "MERN Stack Developer", "React Developer",
    "Node.js Developer", "Full Stack Developer", "Full Stack Engineer",
    "Software Developer", "Backend Developer", "Frontend Developer",
    "Web Developer", "Junior Project Manager",
]

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
GREENHOUSE_BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"

# Public Greenhouse company boards to pull from. Add/remove slugs here -
# validate a slug works by checking GREENHOUSE_BASE_URL.format(company=slug).
GREENHOUSE_COMPANIES = ["gitlab", "stripe", "airbnb"]

# Free, no-API-key job boards (all verified working live before being added).
# The four remote-only boards return exclusively remote jobs, so their
# normalizers hardcode is_remote=True - which also means every job from them
# passes the location filter, and precision comes from the role-relevance
# gate in scorer.py.
REMOTIVE_URL = "https://remotive.com/api/remote-jobs?category=software-dev"
JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs?count=50&industry=dev"
REMOTEOK_URL = "https://remoteok.com/api"
HIMALAYAS_URL = "https://himalayas.app/jobs/api?limit=100"
THEMUSE_URL = "https://www.themuse.com/api/public/jobs"
THEMUSE_PAGES = 5  # 20 jobs/page; results are roughly newest-first and the
                   # 7-day date filter prunes anything stale anyway.

# Some boards (RemoteOK notably) reject requests without a User-Agent.
REQUEST_HEADERS = {"User-Agent": "job-finder-bot (personal job search tool)"}


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


def _dedupe_by_url(jobs: list) -> list:
    seen_urls = set()
    deduped = []
    for job in jobs:
        url = job.get("url", "")
        if url and url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(job)
    return deduped


def collect_adzuna_multi(keywords, app_id: str, app_key: str, countries: list = None) -> list:
    """Queries Adzuna once per (country, keyword) combination. A single
    combination failing (rate limit, timeout, etc.) is logged and skipped -
    the rest still run. The same job commonly surfaces under more than one
    search phrase (e.g. "Software Engineer" and "Software Developer"), so
    results are deduped by URL before returning."""
    countries = countries or ADZUNA_ALL_COUNTRIES
    keywords = [keywords] if isinstance(keywords, str) else keywords
    jobs = []
    for country in countries:
        for keyword in keywords:
            try:
                jobs.extend(collect_adzuna(country, keyword, app_id, app_key))
            except requests.RequestException as e:
                print(f"[job_collector] Adzuna failed for country={country}, keyword='{keyword}': {e}")
    return _dedupe_by_url(jobs)


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


def normalize_remotive_job(raw_job: dict) -> dict:
    # candidate_required_location says where applicants must be based
    # ("Worldwide", "Europe", "USA", ...) - the most useful location data of
    # any source, kept verbatim as both location and country.
    location = raw_job.get("candidate_required_location", "") or "Worldwide"
    return {
        "title": raw_job.get("title", ""),
        "company": raw_job.get("company_name", ""),
        "location": location,
        "country": location,
        "date_posted": raw_job.get("publication_date", ""),
        "url": raw_job.get("url", ""),
        "description": _strip_html(raw_job.get("description", "")),
        "is_remote": True,  # Remotive lists remote jobs only
        "source": "remotive",
    }


def collect_remotive() -> list:
    response = requests.get(REMOTIVE_URL, timeout=20, headers=REQUEST_HEADERS)
    response.raise_for_status()
    return [normalize_remotive_job(j) for j in response.json().get("jobs", [])]


def normalize_jobicy_job(raw_job: dict) -> dict:
    location = raw_job.get("jobGeo", "") or "Anywhere"
    return {
        "title": raw_job.get("jobTitle", ""),
        "company": raw_job.get("companyName", ""),
        "location": location,
        "country": location,
        "date_posted": raw_job.get("pubDate", ""),
        "url": raw_job.get("url", ""),
        "description": _strip_html(raw_job.get("jobDescription", "")),
        "is_remote": True,  # Jobicy lists remote jobs only
        "source": "jobicy",
    }


def collect_jobicy() -> list:
    response = requests.get(JOBICY_URL, timeout=20, headers=REQUEST_HEADERS)
    response.raise_for_status()
    return [normalize_jobicy_job(j) for j in response.json().get("jobs", [])]


def normalize_remoteok_job(raw_job: dict) -> dict:
    return {
        "title": raw_job.get("position", ""),
        "company": raw_job.get("company", ""),
        "location": raw_job.get("location", "") or "Remote",
        "country": raw_job.get("location", "") or "Remote",
        "date_posted": raw_job.get("date", ""),
        "url": raw_job.get("url", ""),
        "description": _strip_html(raw_job.get("description", "")),
        "is_remote": True,  # RemoteOK lists remote jobs only
        "source": "remoteok",
    }


def collect_remoteok() -> list:
    response = requests.get(REMOTEOK_URL, timeout=20, headers=REQUEST_HEADERS)
    response.raise_for_status()
    # The first array element is RemoteOK's legal notice, not a job - it has
    # no "position" key, which is also how any future non-job items get
    # skipped safely.
    return [normalize_remoteok_job(j) for j in response.json()
            if isinstance(j, dict) and j.get("position")]


def normalize_himalayas_job(raw_job: dict) -> dict:
    restrictions = raw_job.get("locationRestrictions") or []
    location = ", ".join(restrictions) if restrictions else "Worldwide"
    pub_epoch = raw_job.get("pubDate")
    date_posted = (
        datetime.fromtimestamp(pub_epoch, tz=timezone.utc).isoformat()
        if isinstance(pub_epoch, (int, float)) else ""
    )
    return {
        "title": raw_job.get("title", ""),
        "company": raw_job.get("companyName", ""),
        "location": location,
        "country": location,
        "date_posted": date_posted,
        "url": raw_job.get("applicationLink", "") or raw_job.get("guid", ""),
        "description": _strip_html(raw_job.get("description", "")),
        "is_remote": True,  # Himalayas lists remote jobs only
        "source": "himalayas",
    }


def collect_himalayas() -> list:
    response = requests.get(HIMALAYAS_URL, timeout=20, headers=REQUEST_HEADERS)
    response.raise_for_status()
    return [normalize_himalayas_job(j) for j in response.json().get("jobs", [])]


def normalize_themuse_job(raw_job: dict) -> dict:
    locations = [loc.get("name", "") for loc in raw_job.get("locations", [])]
    location = "; ".join(locations)
    return {
        "title": raw_job.get("name", ""),
        "company": raw_job.get("company", {}).get("name", ""),
        "location": location,
        "country": location.split(",")[-1].strip() if "," in location else location,
        "date_posted": raw_job.get("publication_date", ""),
        "url": raw_job.get("refs", {}).get("landing_page", ""),
        "description": _strip_html(raw_job.get("contents", "")),
        "is_remote": _looks_remote(raw_job.get("name", ""), location),
        "source": "themuse",
    }


def collect_themuse(pages: int = THEMUSE_PAGES) -> list:
    """The Muse is the one new source that isn't remote-only - it's a
    general board with 100k+ listings, so it's fetched pre-filtered to the
    Software Engineering category, a few pages at a time (roughly
    newest-first; the 7-day date filter prunes the rest)."""
    jobs = []
    for page in range(1, pages + 1):
        try:
            response = requests.get(
                THEMUSE_URL,
                params={"category": "Software Engineering", "page": page},
                timeout=20, headers=REQUEST_HEADERS,
            )
            response.raise_for_status()
            jobs.extend(normalize_themuse_job(j) for j in response.json().get("results", []))
        except requests.RequestException as e:
            print(f"[job_collector] TheMuse failed for page={page}: {e}")
    return jobs


def collect_all(keywords, app_id: str, app_key: str) -> list:
    """Merges every source into one combined list. Each source is isolated -
    one failing entirely (e.g. bad API key) doesn't stop the others. Result
    is deduped by URL across all sources/keywords/countries."""
    jobs = []

    try:
        jobs.extend(collect_adzuna_multi(keywords, app_id, app_key))
    except requests.RequestException as e:
        print(f"[job_collector] Adzuna source failed entirely: {e}")

    keyless_sources = [
        ("Arbeitnow", collect_arbeitnow),
        ("Greenhouse", collect_greenhouse_multi),
        ("Remotive", collect_remotive),
        ("Jobicy", collect_jobicy),
        ("RemoteOK", collect_remoteok),
        ("Himalayas", collect_himalayas),
        ("TheMuse", collect_themuse),
    ]
    for source_name, collect_fn in keyless_sources:
        try:
            jobs.extend(collect_fn())
        except (requests.RequestException, ValueError) as e:
            print(f"[job_collector] {source_name} source failed entirely: {e}")

    return _dedupe_by_url(jobs)


def main():
    load_dotenv()
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise SystemExit("ADZUNA_APP_ID / ADZUNA_APP_KEY are not set in .env")

    jobs = collect_all(SEARCH_QUERIES, app_id, app_key)

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
