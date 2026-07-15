import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import storage


def _job(url, title="Some Job", company="Some Co"):
    return {"url": url, "title": title, "company": company}


def test_get_new_jobs_returns_everything_on_first_run(tmp_path):
    conn = storage.init_db(tmp_path / "test.db")
    jobs = [_job("https://example.com/1"), _job("https://example.com/2")]
    new_jobs = storage.get_new_jobs(jobs, conn)
    assert len(new_jobs) == 2
    conn.close()


def test_running_pipeline_twice_sends_zero_duplicates(tmp_path):
    conn = storage.init_db(tmp_path / "test.db")
    jobs = [_job("https://example.com/1"), _job("https://example.com/2")]

    first_run = storage.get_new_jobs(jobs, conn)
    storage.mark_jobs_seen(first_run, conn)
    assert len(first_run) == 2

    second_run = storage.get_new_jobs(jobs, conn)
    assert len(second_run) == 0
    conn.close()


def test_only_genuinely_new_jobs_pass_through_on_repeat_run(tmp_path):
    conn = storage.init_db(tmp_path / "test.db")
    first_batch = [_job("https://example.com/1")]
    storage.mark_jobs_seen(storage.get_new_jobs(first_batch, conn), conn)

    second_batch = [_job("https://example.com/1"), _job("https://example.com/new")]
    new_jobs = storage.get_new_jobs(second_batch, conn)
    assert len(new_jobs) == 1
    assert new_jobs[0]["url"] == "https://example.com/new"
    conn.close()


def test_get_new_jobs_handles_empty_list(tmp_path):
    conn = storage.init_db(tmp_path / "test.db")
    assert storage.get_new_jobs([], conn) == []
    conn.close()
