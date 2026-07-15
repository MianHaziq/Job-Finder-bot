import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import filters


def _job(days_old=0, country="us", date_style="z"):
    posted = datetime.now(timezone.utc) - timedelta(days=days_old)
    if date_style == "z":
        date_str = posted.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        date_str = posted.isoformat()
    return {
        "title": "Test Job",
        "company": "Test Co",
        "location": "Somewhere",
        "country": country,
        "date_posted": date_str,
        "url": "https://example.com/job/1",
        "description": "desc",
        "source": "test",
    }


def test_parse_date_handles_z_and_offset_formats():
    assert filters.parse_date("2026-07-14T13:07:31Z") is not None
    assert filters.parse_date("2026-07-14T13:07:31+00:00") is not None
    assert filters.parse_date("2026-04-17T05:58:03-04:00") is not None
    assert filters.parse_date("") is None
    assert filters.parse_date("not-a-date") is None


def test_is_recent_keeps_jobs_within_seven_days_and_drops_older():
    assert filters.is_recent(_job(days_old=1)) is True
    assert filters.is_recent(_job(days_old=6)) is True
    assert filters.is_recent(_job(days_old=8)) is False


def test_classify_country_recognizes_codes_and_names():
    assert filters.classify_country("pk") == "pakistan"
    assert filters.classify_country("Pakistan") == "pakistan"
    assert filters.classify_country("us") == "target"
    assert filters.classify_country("United States") == "target"
    assert filters.classify_country("Germany ") == "target"
    assert filters.classify_country("Brazil") == "other"


def test_filter_by_date_drops_stale_jobs():
    jobs = [_job(days_old=1), _job(days_old=10)]
    result = filters.filter_by_date(jobs)
    assert len(result) == 1


def test_filter_by_country_tags_relocation_required():
    jobs = [_job(country="pk"), _job(country="us"), _job(country="brazil")]
    result = filters.filter_by_country(jobs)
    assert len(result) == 2  # brazil dropped
    by_country = {j["country"]: j["relocation_required"] for j in result}
    assert by_country["pk"] is False
    assert by_country["us"] is True


def test_apply_filters_combines_date_country_and_visa_keywords():
    keep = _job(days_old=1, country="us")
    keep["description"] = "We offer visa sponsorship for this role."
    stale = _job(days_old=10, country="us")
    stale["description"] = "We offer visa sponsorship for this role."
    wrong_country = _job(days_old=1, country="brazil")
    wrong_country["description"] = "We offer visa sponsorship for this role."
    no_keyword = _job(days_old=1, country="us")
    no_keyword["description"] = "Great team, no mention of relocation."

    result = filters.apply_filters([keep, stale, wrong_country, no_keyword])
    assert len(result) == 1
    assert result[0]["country"] == "us"


def test_mentions_visa_or_relocation_matches_genuine_phrasing():
    assert filters.mentions_visa_or_relocation("We offer visa sponsorship for this role.") is True
    assert filters.mentions_visa_or_relocation("Relocation package included for international hires.") is True
    assert filters.mentions_visa_or_relocation("We're open to relocation and providing support with our visa agency.") is True


def test_mentions_visa_or_relocation_rejects_negated_phrasing():
    assert filters.mentions_visa_or_relocation("This role is not eligible for relocation support.") is False
    assert filters.mentions_visa_or_relocation("We are unable to provide visa sponsorship for this position.") is False


def test_mentions_visa_or_relocation_rejects_unrelated_text():
    assert filters.mentions_visa_or_relocation("We are looking for a great team player.") is False
    assert filters.mentions_visa_or_relocation("") is False


def test_filter_by_visa_keywords_pakistan_jobs_skip_the_filter():
    jobs = [_job(country="pk")]
    jobs[0]["relocation_required"] = False
    jobs[0]["description"] = "No mention of visa at all."
    result = filters.filter_by_visa_keywords(jobs)
    assert len(result) == 1


def test_filter_by_visa_keywords_drops_target_jobs_without_keywords():
    job_with_keyword = _job(country="us")
    job_with_keyword["relocation_required"] = True
    job_with_keyword["description"] = "Visa sponsorship available for the right candidate."

    job_without_keyword = _job(country="us")
    job_without_keyword["relocation_required"] = True
    job_without_keyword["description"] = "Great team, no mention of relocation."

    result = filters.filter_by_visa_keywords([job_with_keyword, job_without_keyword])
    assert len(result) == 1
    assert "sponsorship" in result[0]["description"].lower()
