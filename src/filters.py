"""
Module 5/6: Date, Location & Visa/Relocation Filter.

Filters the combined job list (from job_collector.py) down to:
- Posted within the last 7 days.
- Location handling is worldwide by design (no country allow-list): a job
  is kept if it's in Pakistan (no relocation needed), OR is genuinely
  remote, OR explicitly mentions visa sponsorship / relocation assistance.
  Everything else (an onsite job, anywhere in the world, with no
  remote/relocation signal at all) is dropped, since it's not something a
  Pakistan-based applicant could actually take without sponsorship.

Earlier versions of this filter used a hardcoded allow-list of ~15
countries (Europe/USA/Australia/Canada/NZ) and dropped anything else - that
silently excluded genuinely good remote/relocation-sponsored jobs in the
UAE, Singapore, Sweden, Japan, etc. purely because their country string
wasn't on the list. Removed in favor of the remote/relocation-signal gate
below, which works regardless of country.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "jobs_raw.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "jobs_filtered.json"

MAX_AGE_DAYS = 7

PAKISTAN_TOKENS = {"pk", "pakistan"}

# Explicit remote-status phrases beyond the bare word "remote" (which
# job_collector.py's _looks_remote already checks against title/location).
# These are checked against the full description text too.
REMOTE_PHRASES = [
    "remote", "work from home", "fully remote", "remote worldwide",
    "remote-first", "remote first",
]

VISA_KEYWORDS = [
    "visa sponsorship", "visa sponsor", "sponsor visa", "sponsors visa",
    "sponsorship available", "will sponsor", "provide sponsorship",
    "relocation assistance", "relocation package", "relocation support",
    "relocation provided", "provide relocation", "open to relocation",
    "relocation offered", "work permit", "visa support",
    "immigration support", "eligible for visa sponsorship", "visa agency",
    "international applicants welcome",
]

# If one of these phrases appears shortly before a keyword match, the match
# is a negation (e.g. "not eligible for relocation support") and is ignored.
NEGATION_TRIGGERS = [
    "not eligible", "not offer", "does not", "doesn't offer", "no longer",
    "unable to", "without", "not provide", "cannot provide", "isn't eligible",
]
NEGATION_WINDOW_CHARS = 60


def parse_date(date_str: str):
    """Parses the ISO 8601 date strings used across all our sources
    (Adzuna: ...Z, Arbeitnow/Greenhouse: ...+00:00 / -04:00). Returns an
    aware UTC datetime, or None if the string can't be parsed."""
    if not date_str:
        return None
    try:
        normalized = date_str.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def is_recent(job: dict, max_age_days: int = MAX_AGE_DAYS) -> bool:
    posted = parse_date(job.get("date_posted", ""))
    if posted is None:
        return False
    age = datetime.now(timezone.utc) - posted
    return timedelta(0) <= age <= timedelta(days=max_age_days)


def _contains_token(token: str, text: str) -> bool:
    pattern = r"(?<![a-zA-Z0-9])" + re.escape(token) + r"(?![a-zA-Z0-9])"
    return re.search(pattern, text) is not None


def is_pakistan(country: str) -> bool:
    text = (country or "").strip().lower()
    return any(_contains_token(token, text) for token in PAKISTAN_TOKENS)


def is_remote_job(job: dict) -> bool:
    """True if the job is remote, from its own is_remote flag (set in
    job_collector.py from title/location) or from any of the wider remote
    phrases appearing in the full description."""
    if job.get("is_remote"):
        return True
    text = f"{job.get('title', '')} {job.get('location', '')} {job.get('description', '')}".lower()
    return any(phrase in text for phrase in REMOTE_PHRASES)


def mentions_visa_or_relocation(description: str) -> bool:
    """True if description genuinely mentions visa sponsorship/relocation
    support - i.e. a keyword match that isn't immediately negated
    ("not eligible for relocation support")."""
    lowered = (description or "").lower()
    for keyword in VISA_KEYWORDS:
        start = 0
        while True:
            idx = lowered.find(keyword, start)
            if idx == -1:
                break
            window = lowered[max(0, idx - NEGATION_WINDOW_CHARS):idx]
            if not any(neg in window for neg in NEGATION_TRIGGERS):
                return True
            start = idx + 1
    return False


def filter_by_date(jobs: list, max_age_days: int = MAX_AGE_DAYS) -> list:
    return [job for job in jobs if is_recent(job, max_age_days)]


def filter_by_location(jobs: list) -> list:
    """Worldwide by design: keeps a job if it's in Pakistan (no relocation
    needed), genuinely remote, or explicitly offers visa/relocation support -
    regardless of which country it's listed under. Tags each surviving job
    with relocation_required (False for Pakistan) and is_remote."""
    kept = []
    for job in jobs:
        pakistan = is_pakistan(job.get("country", ""))
        remote = is_remote_job(job)
        relocation_offered = mentions_visa_or_relocation(job.get("description", ""))

        if not (pakistan or remote or relocation_offered):
            continue

        tagged = dict(job)
        tagged["relocation_required"] = not pakistan
        tagged["is_remote"] = remote
        tagged["relocation_offered"] = relocation_offered
        kept.append(tagged)
    return kept


def apply_filters(jobs: list, max_age_days: int = MAX_AGE_DAYS) -> list:
    return filter_by_location(filter_by_date(jobs, max_age_days))


def main():
    if not INPUT_PATH.exists():
        raise SystemExit(f"{INPUT_PATH} not found - run job_collector.py first")

    with open(INPUT_PATH, encoding="utf-8") as f:
        jobs = json.load(f)

    after_date = filter_by_date(jobs)
    after_location = filter_by_location(after_date)

    print(f"Collected: {len(jobs)}")
    print(f"After date filter (<= {MAX_AGE_DAYS} days): {len(after_date)}")
    print(f"After location filter (Pakistan / remote / relocation-sponsored, worldwide): {len(after_location)}")

    pakistan_count = sum(1 for j in after_location if not j["relocation_required"])
    remote_count = sum(1 for j in after_location if j["is_remote"])
    relocation_count = sum(1 for j in after_location if j["relocation_offered"] and not j["is_remote"])
    print(f"  Pakistan (no relocation needed): {pakistan_count}")
    print(f"  Remote (any country): {remote_count}")
    print(f"  Onsite/hybrid with relocation sponsorship: {relocation_count}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(after_location, f, indent=2)
    print(f"\nSaved {len(after_location)} jobs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
