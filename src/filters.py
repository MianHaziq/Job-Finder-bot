"""
Module 5: Date & Country Filter.

Filters the combined job list (from job_collector.py) down to:
- Posted within the last 7 days.
- Country = Pakistan, OR one of the target international regions
  (Europe, USA, Australia, Canada, New Zealand).

Each surviving job is tagged "relocation_required": False for Pakistan,
True for everything else (used by filters.py's next stage, the visa
keyword filter, and by the Telegram digest).
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "jobs_raw.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "jobs_filtered.json"

MAX_AGE_DAYS = 7

# Lowercased country codes/names that count as "Pakistan" or a target
# international region. Job sources are inconsistent about whether they give
# a 2-letter code ("de") or a full name ("Germany"), so both are listed.
PAKISTAN_TOKENS = {"pk", "pakistan"}

TARGET_COUNTRY_TOKENS = {
    # USA / UK / Canada / Australia / New Zealand
    "us", "usa", "united states", "united states of america",
    "gb", "uk", "united kingdom",
    "ca", "canada",
    "au", "australia",
    "nz", "new zealand",
    # Europe
    "de", "germany", "deutschland",
    "fr", "france",
    "nl", "netherlands", "the netherlands",
    "at", "austria",
    "es", "spain",
    "it", "italy",
    "pl", "poland",
    "be", "belgium",
    "ch", "switzerland",
    "europe",  # Arbeitnow's fallback when no specific country is given
}

# Module 6: Visa/Relocation Keyword Filter (kept in this file per the
# architecture doc, which groups date/country/visa filtering together).
VISA_KEYWORDS = [
    "visa sponsorship", "visa sponsor", "sponsor visa", "sponsors visa",
    "sponsorship available", "will sponsor", "provide sponsorship",
    "relocation assistance", "relocation package", "relocation support",
    "relocation provided", "provide relocation", "open to relocation",
    "relocation offered", "work permit", "visa support",
    "immigration support", "eligible for visa sponsorship", "visa agency",
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


def classify_country(country: str) -> str:
    """Returns "pakistan", "target", or "other" for a raw country string."""
    token = (country or "").strip().lower()
    if token in PAKISTAN_TOKENS:
        return "pakistan"
    if token in TARGET_COUNTRY_TOKENS:
        return "target"
    return "other"


def filter_by_date(jobs: list, max_age_days: int = MAX_AGE_DAYS) -> list:
    return [job for job in jobs if is_recent(job, max_age_days)]


def filter_by_country(jobs: list) -> list:
    """Keeps only Pakistan/target-region jobs, tagging each with
    relocation_required (False for Pakistan, True otherwise)."""
    kept = []
    for job in jobs:
        classification = classify_country(job.get("country", ""))
        if classification == "other":
            continue
        tagged = dict(job)
        tagged["relocation_required"] = classification != "pakistan"
        kept.append(tagged)
    return kept


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


def filter_by_visa_keywords(jobs: list) -> list:
    """Pakistan jobs (relocation_required=False) skip this filter entirely.
    Everything else is only kept if it genuinely mentions visa/relocation
    support in its description."""
    kept = []
    for job in jobs:
        if not job.get("relocation_required", True):
            kept.append(job)
            continue
        if mentions_visa_or_relocation(job.get("description", "")):
            kept.append(job)
    return kept


def apply_filters(jobs: list, max_age_days: int = MAX_AGE_DAYS) -> list:
    date_filtered = filter_by_date(jobs, max_age_days)
    country_filtered = filter_by_country(date_filtered)
    return filter_by_visa_keywords(country_filtered)


def main():
    if not INPUT_PATH.exists():
        raise SystemExit(f"{INPUT_PATH} not found - run job_collector.py first")

    with open(INPUT_PATH, encoding="utf-8") as f:
        jobs = json.load(f)

    after_date = filter_by_date(jobs)
    after_country = filter_by_country(after_date)
    after_visa = filter_by_visa_keywords(after_country)

    print(f"Collected: {len(jobs)}")
    print(f"After date filter (<= {MAX_AGE_DAYS} days): {len(after_date)}")
    print(f"After country filter (Pakistan + target regions): {len(after_country)}")
    print(f"After visa/relocation keyword filter: {len(after_visa)}")

    pakistan_count = sum(1 for j in after_visa if not j["relocation_required"])
    target_count = len(after_visa) - pakistan_count
    print(f"  Pakistan (no relocation needed): {pakistan_count}")
    print(f"  Target regions (visa/relocation confirmed): {target_count}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(after_visa, f, indent=2)
    print(f"\nSaved {len(after_visa)} jobs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
