import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import main


def _set_required_env(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")


def _fake_resume_profile_path(monkeypatch, tmp_path):
    profile_path = tmp_path / "resume_profile.json"
    profile_path.write_text(
        json.dumps({"skills": [], "years_of_experience": 0}), encoding="utf-8"
    )
    monkeypatch.setattr(main, "RESUME_PROFILE_PATH", profile_path)


@patch("main.storage")
@patch("main.notifier")
@patch("main.scorer")
@patch("main.filters")
@patch("main.job_collector")
def test_run_marks_jobs_seen_only_after_successful_send(
    mock_job_collector, mock_filters, mock_scorer,
    mock_notifier, mock_storage, monkeypatch, tmp_path,
):
    _set_required_env(monkeypatch)
    _fake_resume_profile_path(monkeypatch, tmp_path)
    mock_job_collector.collect_all.return_value = [{"title": "Job"}]
    mock_filters.apply_filters.return_value = [{"title": "Job"}]
    mock_scorer.score_jobs.return_value = [{"title": "Job", "url": "https://x.com/1", "score": 2}]
    mock_scorer.filter_by_minimum_score.return_value = [{"title": "Job", "url": "https://x.com/1", "score": 2}]
    mock_storage.init_db.return_value = MagicMock()
    mock_storage.get_new_jobs.return_value = [{"title": "Job", "url": "https://x.com/1", "score": 2}]
    mock_notifier.send_digest.return_value = 1

    main.run()

    mock_notifier.send_digest.assert_called_once()
    mock_storage.mark_jobs_seen.assert_called_once()


@patch("main.storage")
@patch("main.notifier")
@patch("main.scorer")
@patch("main.filters")
@patch("main.job_collector")
def test_run_does_not_mark_jobs_seen_when_send_fails(
    mock_job_collector, mock_filters, mock_scorer,
    mock_notifier, mock_storage, monkeypatch, tmp_path,
):
    """Critical fix: if Telegram delivery fails, jobs must NOT be marked seen,
    so they're retried on the next run instead of being lost forever."""
    _set_required_env(monkeypatch)
    _fake_resume_profile_path(monkeypatch, tmp_path)
    mock_job_collector.collect_all.return_value = [{"title": "Job"}]
    mock_filters.apply_filters.return_value = [{"title": "Job"}]
    mock_scorer.score_jobs.return_value = [{"title": "Job", "url": "https://x.com/1", "score": 2}]
    mock_scorer.filter_by_minimum_score.return_value = [{"title": "Job", "url": "https://x.com/1", "score": 2}]
    mock_storage.init_db.return_value = MagicMock()
    mock_storage.get_new_jobs.return_value = [{"title": "Job", "url": "https://x.com/1", "score": 2}]
    mock_notifier.send_digest.side_effect = Exception("network unreachable")

    main.run()  # should not raise

    mock_storage.mark_jobs_seen.assert_not_called()


@patch("main.storage")
@patch("main.notifier")
@patch("main.scorer")
@patch("main.filters")
@patch("main.job_collector")
def test_run_skips_notification_when_no_new_jobs(
    mock_job_collector, mock_filters, mock_scorer,
    mock_notifier, mock_storage, monkeypatch, tmp_path,
):
    _set_required_env(monkeypatch)
    _fake_resume_profile_path(monkeypatch, tmp_path)
    mock_job_collector.collect_all.return_value = []
    mock_filters.apply_filters.return_value = []
    mock_scorer.score_jobs.return_value = []
    mock_scorer.filter_by_minimum_score.return_value = []
    mock_storage.init_db.return_value = MagicMock()
    mock_storage.get_new_jobs.return_value = []

    main.run()

    mock_notifier.send_digest.assert_not_called()
    mock_storage.mark_jobs_seen.assert_not_called()


def test_run_raises_clear_error_when_resume_profile_missing(monkeypatch, tmp_path):
    _set_required_env(monkeypatch)
    monkeypatch.setattr(main, "RESUME_PROFILE_PATH", tmp_path / "does_not_exist.json")

    with pytest.raises(SystemExit):
        main.run()
