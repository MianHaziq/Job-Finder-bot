# Project Architecture & Instructions for Claude Code

> This document is meant to be given directly to Claude Code (or read by it) at the start of the project. It defines the professional architecture of the app AND instructs Claude Code to generate a detailed `README.md` file for the project.

---

## 1. Project Overview (for Claude Code)

Build a personal job-search automation tool called **Job Finder Bot**. It is a Python-based backend system (no web framework required) that:
- Parses my resume into structured data.
- Collects job listings from multiple free/legal APIs (Adzuna, Arbeitnow, Greenhouse public boards, optionally JSearch).
- Filters jobs by recency (last 24h–7 days), country (Pakistan + Europe/USA/Australia/Canada/New Zealand), and visa/relocation keywords.
- Scores jobs against my resume for relevance.
- Stores seen jobs in a local database to avoid duplicate alerts.
- Sends me a ranked digest via Telegram.
- Runs automatically on a schedule (GitHub Actions or cron).

Do **not** build anything that logs into or scrapes LinkedIn or Indeed directly — only use official APIs or public data sources.

---

## 2. Professional Architecture

```
job-bot/
│
├── README.md                  ← Claude Code should generate this (see Section 3 below)
├── .env.example                ← template showing which environment variables are needed (no real keys)
├── .gitignore                  ← must exclude .env, __pycache__, venv, jobs.db
├── requirements.txt             ← all Python dependencies pinned to versions
│
├── data/
│   ├── resume_profile.json     ← structured resume data (output of resume parser)
│   └── jobs.db                  ← SQLite database, tracks seen jobs
│
├── src/
│   ├── resume_parser.py         ← extracts + structures resume data
│   ├── job_collector.py          ← pulls jobs from all sources, merges into one format
│   ├── filters.py                ← date filter, country filter, visa/relocation keyword filter
│   ├── scorer.py                  ← matches/scores jobs against resume_profile.json
│   ├── storage.py                  ← handles SQLite read/write, duplicate checking
│   ├── notifier.py                  ← formats and sends Telegram digest
│   └── main.py                       ← orchestrates the full pipeline end-to-end
│
├── .github/
│   └── workflows/
│       └── run_job_bot.yml       ← GitHub Actions workflow for scheduled runs
│
└── tests/
    ├── test_resume_parser.py
    ├── test_job_collector.py
    ├── test_filters.py
    ├── test_scorer.py
    └── test_storage.py
```

### Architecture Principles
- **Modular:** each file in `src/` does exactly one job. `main.py` just calls them in order.
- **Config via environment variables only** — no API keys or secrets hardcoded anywhere in the code.
- **Testable:** each module should be runnable and testable independently (matches the phased implementation plan already built for this project).
- **Idempotent runs:** running the pipeline multiple times should never send duplicate job alerts (handled by `storage.py`).
- **Fail gracefully:** if one job source API fails or times out, the pipeline should log the error and continue with the remaining sources — not crash entirely.

---

## 3. Instruction to Claude Code: Generate the README

Claude Code should create a `README.md` in the project root that explains the entire project so clearly that someone with **very little technical background** could still set it up. The README must include, in this order:

1. **Project Title & One-Line Description**
   - What this bot does, in one simple sentence.

2. **What This Project Does (Plain English)**
   - A short, non-technical explanation of the whole flow: parses resume → finds jobs → filters by country/visa/date → scores → sends Telegram message.

3. **Prerequisites — Explained Very Simply**
   - What software needs to be installed before starting (e.g. Python version, pip, git), with a one-line explanation of what each one is and a link to download it.
   - Explicitly state the required Python version and how to check it (`python --version`).

4. **Step-by-Step Setup Instructions**
   - How to download/clone the project.
   - How to create and activate a virtual environment (with exact commands for both Windows and Mac/Linux).
   - How to install dependencies (`pip install -r requirements.txt`).

5. **Environment Variables — Explained in Full Detail**
   For **each** environment variable needed, explain:
   - What it's called (exact variable name).
   - What it's for, in plain English.
   - **Exactly how to obtain it step-by-step** (e.g. "Go to https://developer.adzuna.com → click Register → verify email → copy App ID and App Key from your dashboard").
   - Where to paste it (`.env` file, matching `.env.example`).

   Variables to cover (adjust once real ones are finalized):
   - `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`
   - `RAPIDAPI_KEY` (if JSearch is used)
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   - Any LLM API key, if used for resume parsing/scoring

   Include a short "How to create a Telegram bot" walkthrough (via @BotFather) and "How to find your Telegram chat ID" since these are the least obvious steps for a non-technical person.

6. **How to Run the Bot Manually (First Test)**
   - Exact command to run the full pipeline once (e.g. `python src/main.py`).
   - What success looks like (e.g. "You should receive a Telegram message within a few seconds").

7. **How to Run Each Module Individually (For Testing)**
   - One command per module (resume parser, job collector, filters, scorer, storage, notifier), matching the phased test plan already used to build this project.

8. **How Automatic Scheduling Works**
   - Plain explanation of the GitHub Actions workflow — that it runs automatically every X hours without needing your computer on.
   - How to set repository secrets in GitHub so the workflow can access the same environment variables.

9. **Project Structure Explanation**
   - A simple table or list explaining what each folder/file does (can reuse the architecture tree from Section 2 above).

10. **Troubleshooting / FAQ**
    - Common issues (e.g. "No jobs returned," "Telegram message not arriving," "API key invalid") with simple fixes.

11. **Safety Notes**
    - Reminder that this project never logs into or scrapes LinkedIn/Indeed directly, and applications are never auto-submitted without manual review.

The README should use simple language throughout — avoid unexplained jargon, define any technical term the first time it's used, and prefer numbered steps over dense paragraphs wherever possible.
