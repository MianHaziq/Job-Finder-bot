"""
Module 9: Telegram Delivery.

Formats the final ranked job list (from storage.py's "new jobs" output) into
a readable digest and sends it via the Telegram Bot API.
"""
import html
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JOBS_INPUT_PATH = PROJECT_ROOT / "data" / "jobs_new.json"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

# Telegram caps messages at 4096 characters; stay comfortably under that so
# a single job's long description can never push a chunk over the limit.
MAX_MESSAGE_CHARS = 3500


def format_job(job: dict) -> str:
    if job.get("is_remote"):
        relocation_note = "Remote - no relocation needed"
    elif job.get("relocation_required"):
        relocation_note = "Relocation/visa needed"
    else:
        relocation_note = "No relocation needed (Pakistan)"
    title = html.escape(job.get("title", ""))
    company = html.escape(job.get("company", ""))
    country = html.escape(job.get("country", ""))
    url = job.get("url", "")
    matched_count = job.get("score", 0)
    seniority_note = "\n&#9888; May require more seniority than your experience" if job.get("seniority_mismatch") else ""
    return (
        f"<b>{title}</b>\n"
        f"{company} - {country}\n"
        f"{relocation_note} | Matched skills: {matched_count}"
        f"{seniority_note}\n"
        f'<a href="{url}">View &amp; Apply</a>'
    )


def build_digest_chunks(jobs: list) -> list:
    """Formats every job and packs them into chunks under MAX_MESSAGE_CHARS,
    so the digest works whether there are 1 or 50 new jobs."""
    if not jobs:
        return []

    chunks = []
    current = f"<b>Job Finder Bot - {len(jobs)} new match{'es' if len(jobs) != 1 else ''}</b>\n\n"
    for job in jobs:
        job_text = format_job(job) + "\n\n"
        if len(current) + len(job_text) > MAX_MESSAGE_CHARS:
            chunks.append(current.strip())
            current = ""
        current += job_text
    if current.strip():
        chunks.append(current.strip())
    return chunks


def send_telegram_message(text: str, bot_token: str, chat_id: str) -> dict:
    url = TELEGRAM_API_URL.format(token=bot_token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    response = requests.post(url, data=payload, timeout=20)
    response.raise_for_status()
    return response.json()


def send_digest(jobs: list, bot_token: str, chat_id: str) -> int:
    """Sends the digest, split across multiple messages if needed. Returns
    the number of Telegram messages sent (0 if there was nothing new)."""
    chunks = build_digest_chunks(jobs)
    for chunk in chunks:
        send_telegram_message(chunk, bot_token, chat_id)
    return len(chunks)


def main():
    load_dotenv()
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        raise SystemExit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set in .env")

    if not JOBS_INPUT_PATH.exists():
        raise SystemExit(f"{JOBS_INPUT_PATH} not found - run storage.py first")

    with open(JOBS_INPUT_PATH, encoding="utf-8") as f:
        jobs = json.load(f)

    if not jobs:
        print("No new jobs to send - skipping Telegram notification.")
        return

    messages_sent = send_digest(jobs, bot_token, chat_id)
    print(f"Sent {len(jobs)} job(s) across {messages_sent} Telegram message(s).")


if __name__ == "__main__":
    main()
