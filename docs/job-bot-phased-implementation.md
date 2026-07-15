# Global Job Finder Bot — Phased Implementation Guide

**Rule for every phase: build it → test it → confirm it works → only then move to the next phase.**
Do not stack phases on top of each other before testing. Each module should work standalone before you connect it to the next one.

---

## Module 1: Stack Setup (Foundation)

### What to install/set up
- Python 3.10+ installed
- A project folder, e.g. `job-bot/`
- Virtual environment: `python -m venv venv`
- Core libraries:
  ```
  pip install requests python-dotenv pdfplumber python-docx
  ```
- A `.env` file to hold API keys later (never hardcode keys in scripts)
- Accounts/keys to create now (all free tier):
  - Adzuna API (app_id + app_key)
  - RapidAPI account (for JSearch, optional)
  - Telegram Bot (message @BotFather on Telegram to create one, get bot token + your chat ID)

### ✅ Test for Module 1
- Run a "hello world" Python script to confirm your environment works:
  ```python
  print("Environment ready")
  ```
- Confirm `.env` loads correctly using `python-dotenv`:
  ```python
  from dotenv import load_dotenv
  import os
  load_dotenv()
  print(os.getenv("ADZUNA_APP_ID"))
  ```
- **Pass condition:** script runs with no errors, and your test API key prints correctly.

---

## Module 2: Resume Parser

### What it does
Reads your resume file (PDF or Word) and extracts raw text, then structures it into JSON (skills, job titles, experience, education).

### Steps
1. Write a script `resume_parser.py` that:
   - Loads your resume file from a local path
   - Extracts raw text (`pdfplumber` for PDF, `python-docx` for Word)
   - Outputs the raw text to console first (sanity check)
2. Once raw text extraction works, structure it:
   - Either use simple rule-based parsing (look for "Skills," "Experience," "Education" headers)
   - Or send the raw text to an LLM API with a prompt like "extract skills, job titles, years of experience, education as JSON"
3. Save the result to `resume_profile.json`

### ✅ Test for Module 2
- Run the script against your real resume file.
- **Pass condition:**
  - Raw text extraction shows readable, non-garbled text matching your resume.
  - `resume_profile.json` is created and contains your actual skills/job titles/experience — manually check 3-4 fields for accuracy.

---

## Module 3: Job Collector (Single Source First)

### What it does
Pulls live job listings from **one** API first (start with Adzuna) before adding more sources — easier to debug.

### Steps
1. Write `job_collector.py` that:
   - Calls Adzuna API for one country (e.g. `gb` for UK) and one keyword (e.g. your main job title)
   - Prints the raw JSON response
2. Confirm the response structure, then extract just: job title, company, location, date posted, description, URL
3. Save results to a local file (`jobs_raw.json`) for now

### ✅ Test for Module 3
- Run the script and confirm real, current job listings are returned (check 2-3 job titles/links manually — do they look real and clickable?).
- **Pass condition:** you get a list of real jobs with working URLs, correct country, and posting dates.

---

## Module 4: Multi-Source Expansion

### What it does
Adds more job sources once Module 3 is proven to work.

### Steps
1. Add Arbeitnow API call (Europe-focused)
2. Add Greenhouse public job board pulls for 2-3 companies you're interested in
3. Add JSearch (optional, if you want Indeed/LinkedIn-sourced listings)
4. Add Pakistan-specific source (e.g. Rozee.pk, if a usable public feed exists)
5. Merge all sources into one combined list with a consistent format:
   ```json
   {
     "title": "...",
     "company": "...",
     "location": "...",
     "country": "...",
     "date_posted": "...",
     "url": "...",
     "description": "...",
     "source": "adzuna / arbeitnow / greenhouse / etc."
   }
   ```

### ✅ Test for Module 4
- Run the combined collector.
- **Pass condition:** you see jobs from at least 2 different sources in one unified list, each with all fields filled in correctly (no blank/broken entries).

---

## Module 5: Date & Country Filter

### What it does
Filters the combined job list down to:
- Posted in the last 24 hours to 7 days
- Country = Pakistan, OR country in [target list: Europe countries, USA, Australia, Canada, New Zealand]

### Steps
1. Write a filter function that parses each job's `date_posted` and discards anything older than 7 days
2. Write a country filter that keeps only your target countries
3. Tag each job as `"relocation_required": true/false` based on country (Pakistan = false, others = true)

### ✅ Test for Module 5
- Run filter on Module 4's output.
- **Pass condition:** every remaining job is within the date range, and every job is tagged correctly as Pakistan (no relocation) or target-country (relocation required).

---

## Module 6: Visa/Relocation Keyword Filter

### What it does
For non-Pakistan jobs, keeps only ones that actually mention visa sponsorship or relocation support.

### Steps
1. Build a keyword list: `"visa sponsorship"`, `"relocation assistance"`, `"work permit"`, `"sponsor visa"`, `"relocation package"`, etc.
2. Search each non-Pakistan job's description for these phrases (case-insensitive)
3. Drop non-Pakistan jobs that don't match any keyword
4. Keep all Pakistan jobs (no filter needed there)

### ✅ Test for Module 6
- Run on Module 5's output.
- **Pass condition:** manually open 3-5 of the surviving non-Pakistan job listings and confirm they genuinely mention visa/relocation support in the real posting.

---

## Module 7: Resume Matching & Scoring

### What it does
Scores each surviving job against your resume profile (Module 2) so best matches rise to the top.

### Steps
1. Start simple: keyword overlap score (how many resume skills/keywords appear in the job description)
2. Sort jobs by score, descending
3. *(Optional upgrade later)*: use sentence-embedding similarity for smarter matching

### ✅ Test for Module 7
- Run scoring on Module 6's output.
- **Pass condition:** the top 5 scored jobs are ones you'd genuinely consider applying to; a job with almost no overlap to your skills should score low and sit near the bottom.

---

## Module 8: Storage & Duplicate Prevention

### What it does
Saves seen jobs so you don't get repeat alerts every run.

### Steps
1. Set up SQLite database (`jobs.db`) with a table storing job URL (as unique key) + date first seen
2. Before sending any digest, check each job against the database — skip if already recorded
3. Insert new jobs into the database after sending

### ✅ Test for Module 8
- Run the full pipeline twice in a row.
- **Pass condition:** the second run sends zero (or only genuinely new) jobs — no duplicates from the first run.

---

## Module 9: Telegram Delivery

### What it does
Sends you the final ranked job list as a Telegram message.

### Steps
1. Use your Telegram bot token + chat ID from Module 1
2. Format message: job title, company, country, relocation note, score, link
3. Send via Telegram Bot API (`sendMessage` endpoint)

### ✅ Test for Module 9
- Run the pipeline end-to-end.
- **Pass condition:** you receive a real Telegram message with correctly formatted, clickable job links matching what Module 7/8 produced.

---

## Module 10: Scheduling (Full Automation)

### What it does
Runs everything automatically without you triggering it manually.

### Steps
1. Set up a GitHub Actions workflow (or local cron job) to run the full script every 6-12 hours
2. Store your API keys as GitHub Secrets (not in code)
3. Confirm logs show successful runs

### ✅ Test for Module 10
- Wait for 2 scheduled runs to happen automatically (no manual trigger).
- **Pass condition:** you receive Telegram messages at the scheduled times with no manual intervention, and no errors in the run logs.

---

## Module 11 (Optional, Later): Semi-Auto Application Filling

### What it does
Pre-fills application forms using Playwright browser automation; you review and click submit yourself.

### Steps
1. Pick 1-2 target company application forms to start with
2. Write a Playwright script that opens the form and fills in name/email/resume/work history from your profile
3. Leave the final "submit" click to you

### ✅ Test for Module 11
- Run on a real job you intend to apply to.
- **Pass condition:** the form is filled correctly with no wrong/missing fields before you click submit — you personally verify accuracy every time before submitting.

---

## Summary Table

| Module | Purpose | Must Pass Before Next Step |
|---|---|---|
| 1 | Stack setup | Environment + keys work |
| 2 | Resume parser | Accurate resume_profile.json |
| 3 | Job collector (1 source) | Real jobs returned |
| 4 | Multi-source expansion | Combined list from 2+ sources |
| 5 | Date & country filter | Correct date/country tagging |
| 6 | Visa/relocation filter | Only real visa-friendly jobs remain |
| 7 | Resume matching/scoring | Top jobs are genuinely relevant |
| 8 | Storage/dedup | No duplicate alerts on repeat runs |
| 9 | Telegram delivery | Real message received with correct data |
| 10 | Scheduling | Automatic runs succeed with no manual trigger |
| 11 | Semi-auto apply (optional) | Forms filled correctly, human confirms before submit |
