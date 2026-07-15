# Global Job Finder Bot — Stack & Build Plan

## 1. Recommended Stack: Python

Python is the best fit because this project is mostly **background scripts + text parsing + matching**, not a real-time web app. Node.js would work too, but Python's libraries are stronger for this exact use case.

| Layer | Tool | Why |
|---|---|---|
| Core language | **Python 3** | Best libraries for resume parsing, NLP, and scheduled scripts |
| Resume parsing | `pdfplumber` (PDF) / `python-docx` (Word) | Extracts raw text from your resume file |
| Text understanding | OpenAI/Claude API or `spaCy` | Turns raw resume text into structured skills/experience data |
| Job data fetching | `requests` / `httpx` | Simple HTTP calls to job APIs (Adzuna, JSearch, Arbeitnow, Greenhouse, etc.) |
| Matching/scoring | `sentence-transformers` (embeddings) or simple keyword overlap | Scores each job against your resume |
| Storage | **SQLite** (simplest) or free **Supabase/Postgres** | Tracks jobs already seen, avoids duplicate alerts |
| Scheduling | **cron** (Linux/Mac) or **GitHub Actions** (free, cloud-based) | Runs the script every few hours automatically |
| Notifications | **Telegram Bot API** (easiest) or SMTP email | Sends you the ranked job digest |
| Dashboard (optional, later) | **Next.js** | Only if you want a web page to browse results instead of Telegram messages |

**Bottom line:** No web framework is needed to get a fully working bot. It's a Python script + cron + Telegram — the dashboard is an optional add-on once the core works.

## 2. Complete Bot — What It's Made Of

Think of the whole system as 5 small pieces that plug together:

### Piece 1: Resume Parser
- Input: your resume (PDF or Word).
- Extracts: skills, job titles, years of experience, education, key achievements.
- Output: a structured JSON file (e.g. `resume_profile.json`) — this becomes your bot's "reference profile."
- Only needs to run once, or again whenever you update your resume.

### Piece 2: Job Collector
- Connects to job data sources:
  - **Adzuna API** — UK/Europe/US/Australia/Canada/NZ
  - **JSearch (RapidAPI)** — aggregates Indeed/LinkedIn/Glassdoor legally
  - **Arbeitnow** — Europe, many visa-sponsor tags
  - **Greenhouse/Lever public job boards** — direct company listings
  - **Rozee.pk** or similar — Pakistan-specific jobs
- Pulls jobs posted in the **last 24 hours to 7 days**.
- Saves raw results temporarily for the next step.

### Piece 3: Filter Layer
- Splits jobs into two buckets:
  - **Pakistan jobs** → no relocation filter needed, keep all relevant matches.
  - **Europe/US/Australia/Canada/NZ jobs** → keep only ones mentioning "visa sponsorship," "relocation assistance," "work permit provided," etc.
- Removes jobs already seen before (checked against the database).

### Piece 4: Matching & Scoring
- Compares each remaining job description against your resume profile (Piece 1).
- Produces a relevance score (e.g. 0–100) so the best-fit jobs rise to the top.
- Only top-scoring jobs get sent to you — avoids spamming you with irrelevant listings.

### Piece 5: Delivery
- Sends a digest via **Telegram bot message** (simplest, instant, free) or email.
- Format: job title, company, country, relocation/visa note, score, and direct application link.
- Runs on a schedule (e.g. every 6–12 hours) via cron or GitHub Actions — fully automatic, no manual triggering needed.

## 3. Build Order (Step by Step)

1. **Set up the resume parser** — get your resume turned into structured JSON.
2. **Connect to 2–3 job APIs** (start with Adzuna + JSearch) and confirm you can pull live job data.
3. **Add date filtering** (last 24h–7 days) and country filtering (Pakistan + your 5 target regions).
4. **Add the visa/relocation keyword filter** for non-Pakistan jobs.
5. **Add scoring** — match job text against your resume profile.
6. **Add storage** (SQLite) to avoid duplicate alerts across runs.
7. **Add delivery** — Telegram bot digest is the fastest to set up and test.
8. **Add scheduling** — cron job or GitHub Actions to run it automatically every few hours.
9. *(Optional, later)* Add a Next.js dashboard for a nicer way to browse/search past matches.
10. *(Optional, later)* Add semi-automated application filling (Playwright) — bot pre-fills forms, you review and click submit.

## 4. What This Avoids (On Purpose)
- No direct LinkedIn/Indeed login automation or scraping — protects your account from bans.
- No full auto-apply without review — keeps applications high quality and avoids looking spammy to employers.
- No heavyweight infrastructure — everything above can run on a free tier or even your own laptop with cron.
