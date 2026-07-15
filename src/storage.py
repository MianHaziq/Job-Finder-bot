"""
Module 8: Storage & Duplicate Prevention.

Tracks which jobs have already been sent to you (by URL, the natural unique
key for a job posting) in a local SQLite database, so re-running the
pipeline never sends the same job twice.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "jobs.db"
JOBS_INPUT_PATH = PROJECT_ROOT / "data" / "jobs_scored.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "jobs_new.json"


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_jobs (
            url TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            first_seen TEXT
        )
        """
    )
    conn.commit()
    return conn


def get_new_jobs(jobs: list, conn: sqlite3.Connection) -> list:
    """Returns only the jobs whose URL isn't already recorded as seen."""
    urls = [job["url"] for job in jobs]
    if not urls:
        return []
    placeholders = ",".join("?" for _ in urls)
    rows = conn.execute(
        f"SELECT url FROM seen_jobs WHERE url IN ({placeholders})", urls
    ).fetchall()
    seen_urls = {row[0] for row in rows}
    return [job for job in jobs if job["url"] not in seen_urls]


def mark_jobs_seen(jobs: list, conn: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "INSERT OR IGNORE INTO seen_jobs (url, title, company, first_seen) VALUES (?, ?, ?, ?)",
        [(job["url"], job["title"], job["company"], now) for job in jobs],
    )
    conn.commit()


def main():
    if not JOBS_INPUT_PATH.exists():
        raise SystemExit(f"{JOBS_INPUT_PATH} not found - run scorer.py first")

    with open(JOBS_INPUT_PATH, encoding="utf-8") as f:
        jobs = json.load(f)

    conn = init_db()
    try:
        new_jobs = get_new_jobs(jobs, conn)
        print(f"Scored jobs: {len(jobs)}")
        print(f"Already seen (skipped): {len(jobs) - len(new_jobs)}")
        print(f"New jobs to send: {len(new_jobs)}")

        mark_jobs_seen(new_jobs, conn)

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(new_jobs, f, indent=2)
        print(f"\nSaved {len(new_jobs)} new jobs to {OUTPUT_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
