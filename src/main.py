"""
main.py - orchestrates the full Job Finder Bot pipeline end-to-end:
resume -> collect -> filter -> score -> dedup -> notify.

Important ordering detail: jobs are only marked "seen" in the database
AFTER the Telegram send succeeds. If sending fails (e.g. Telegram is
unreachable), the job stays "new" and will be retried on the next run
instead of being silently lost.

Resume note: this loads the already-parsed data/resume_profile.json rather
than re-parsing the raw resume PDF every run. The raw PDF lives only in your
local my-resume/ folder (gitignored - it contains real PII like passport
number/DOB/address) and is never pushed to GitHub, so GitHub Actions has no
way to read it. Whenever your resume changes, run
`python src/resume_parser.py` locally and commit the updated
resume_profile.json - that's the only file the scheduled run actually needs.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

import filters
import job_collector
import notifier
import scorer
import storage

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESUME_PROFILE_PATH = PROJECT_ROOT / "data" / "resume_profile.json"
SEARCH_KEYWORD = "software engineer"


def run() -> None:
    load_dotenv()

    adzuna_app_id = os.getenv("ADZUNA_APP_ID")
    adzuna_app_key = os.getenv("ADZUNA_APP_KEY")
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not (adzuna_app_id and adzuna_app_key):
        raise SystemExit("ADZUNA_APP_ID / ADZUNA_APP_KEY are not set in .env")
    if not (telegram_bot_token and telegram_chat_id):
        raise SystemExit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set in .env")
    if not RESUME_PROFILE_PATH.exists():
        raise SystemExit(
            f"{RESUME_PROFILE_PATH} not found - run `python src/resume_parser.py` "
            "locally first, then commit the generated file."
        )

    print("[1/6] Loading resume profile...")
    with open(RESUME_PROFILE_PATH, encoding="utf-8") as f:
        resume_profile = json.load(f)
    print(f"      {len(resume_profile['skills'])} skills, "
          f"{resume_profile['years_of_experience']} years experience")

    print("[2/6] Collecting jobs from all sources...")
    raw_jobs = job_collector.collect_all(SEARCH_KEYWORD, adzuna_app_id, adzuna_app_key)
    print(f"      Collected {len(raw_jobs)} jobs")

    print("[3/6] Filtering by date, country, and visa/relocation keywords...")
    filtered_jobs = filters.apply_filters(raw_jobs)
    print(f"      {len(filtered_jobs)} jobs survived filtering")

    print("[4/6] Scoring jobs against resume...")
    scored_jobs = scorer.score_jobs(filtered_jobs, resume_profile)

    print("[5/6] Checking for duplicates already sent...")
    conn = storage.init_db()
    try:
        new_jobs = storage.get_new_jobs(scored_jobs, conn)
        print(f"      {len(new_jobs)} new job(s) to send "
              f"({len(scored_jobs) - len(new_jobs)} already sent before)")

        print("[6/6] Sending Telegram digest...")
        if not new_jobs:
            print("      Nothing new - skipping notification.")
            return

        try:
            messages_sent = notifier.send_digest(new_jobs, telegram_bot_token, telegram_chat_id)
            print(f"      Sent {len(new_jobs)} job(s) across {messages_sent} message(s)")
        except Exception as e:
            print(f"      Telegram send failed, jobs will be retried next run: {e}")
            return

        # Only mark jobs seen once they've actually been delivered.
        storage.mark_jobs_seen(new_jobs, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
