import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import filters


def _job(days_old=0, country="us", description="", is_remote=False, date_style="z"):
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
        "description": description,
        "is_remote": is_remote,
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


def test_is_pakistan_recognizes_codes_and_names():
    assert filters.is_pakistan("pk") is True
    assert filters.is_pakistan("Pakistan") is True
    assert filters.is_pakistan("us") is False
    assert filters.is_pakistan("") is False


def test_filter_by_date_drops_stale_jobs():
    jobs = [_job(days_old=1), _job(days_old=10)]
    result = filters.filter_by_date(jobs)
    assert len(result) == 1


def test_mentions_visa_or_relocation_matches_genuine_phrasing():
    assert filters.mentions_visa_or_relocation("We offer visa sponsorship for this role.") is True
    assert filters.mentions_visa_or_relocation("Relocation package included for international hires.") is True
    assert filters.mentions_visa_or_relocation("We're open to relocation and providing support with our visa agency.") is True
    assert filters.mentions_visa_or_relocation("International applicants welcome to apply.") is True


def test_mentions_visa_or_relocation_rejects_negated_phrasing():
    assert filters.mentions_visa_or_relocation("This role is not eligible for relocation support.") is False
    assert filters.mentions_visa_or_relocation("We are unable to provide visa sponsorship for this position.") is False


def test_mentions_visa_or_relocation_rejects_unrelated_text():
    assert filters.mentions_visa_or_relocation("We are looking for a great team player.") is False
    assert filters.mentions_visa_or_relocation("") is False


def test_is_remote_job_widened_phrases_beyond_bare_remote():
    assert filters.is_remote_job({"is_remote": False, "title": "", "location": "",
                                   "description": "This is a fully remote position."}) is True
    assert filters.is_remote_job({"is_remote": False, "title": "", "location": "",
                                   "description": "Work from home opportunity."}) is True
    assert filters.is_remote_job({"is_remote": False, "title": "", "location": "",
                                   "description": "Remote worldwide, any timezone."}) is True
    assert filters.is_remote_job({"is_remote": False, "title": "", "location": "",
                                   "description": "Standard office role."}) is False
    assert filters.is_remote_job({"is_remote": True, "title": "", "location": "", "description": ""}) is True


def test_filter_by_location_keeps_pakistan_jobs_with_no_signal_needed():
    jobs = [_job(country="pk", description="no mention of anything special")]
    result = filters.filter_by_location(jobs)
    assert len(result) == 1
    assert result[0]["relocation_required"] is False


def test_filter_by_location_keeps_remote_jobs_from_any_country_no_signal_needed():
    """Worldwide by design: a genuinely remote job needs no visa/relocation
    mention at all, and is kept regardless of which country it's listed
    under (e.g. UAE, Japan - not on any old allow-list)."""
    jobs = [_job(country="United Arab Emirates", is_remote=True, description="no visa mention here")]
    result = filters.filter_by_location(jobs)
    assert len(result) == 1
    assert result[0]["is_remote"] is True


def test_filter_by_location_keeps_onsite_jobs_anywhere_if_relocation_offered():
    """The old version required the country to be on a fixed allow-list -
    this confirms that requirement is gone: Sweden/Japan/UAE etc. all work
    now as long as relocation/visa is genuinely offered."""
    for country in ["Sweden", "Japan", "United Arab Emirates", "South Korea"]:
        jobs = [_job(country=country, description="Visa sponsorship available for this role.")]
        result = filters.filter_by_location(jobs)
        assert len(result) == 1, f"expected {country} job to survive with visa sponsorship mentioned"


def test_filter_by_location_drops_onsite_jobs_anywhere_with_no_signal():
    jobs = [_job(country="us", description="Standard office role, no relocation mentioned.")]
    result = filters.filter_by_location(jobs)
    assert len(result) == 0


def test_apply_filters_combines_date_and_location():
    keep = _job(days_old=1, country="us", description="visa sponsorship offered")
    stale = _job(days_old=10, country="us", description="visa sponsorship offered")
    no_signal = _job(days_old=1, country="us", description="no mention of relocation")
    remote_ok = _job(days_old=1, country="Sweden", is_remote=True, description="")

    result = filters.apply_filters([keep, stale, no_signal, remote_ok])
    assert len(result) == 2
