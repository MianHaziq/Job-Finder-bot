# Project Setup Log — Job Finder Bot

This file is a running diary of exactly how this project was built: what was
installed, why, and how, in the order it happened. It is updated after every
module so you (or anyone else) can understand the project's history without
having to reverse-engineer it from the code. It is separate from the final
`README.md` (which will be a polished, end-user-facing setup guide, generated
once the whole pipeline works — see `docs/2-architecture-and-readme-instructions.md`).

The plan documents that this whole project is based on live in `docs/`:
- `docs/1-project-goal.md` — the "why", written from the user's perspective.
- `docs/2-architecture-and-readme-instructions.md` — folder structure + README spec.
- `docs/job-bot-phased-implementation.md` — the 11-module build order (source of truth for what "Module N" means below).
- `docs/job-bot-stack-and-build-plan.md` / `docs/job-search-bot-plan.md` — stack choice and data-source research.

---

## Module 1 — Stack Setup

### What this module is for
Get a working Python environment with the right libraries installed, before
writing any real logic. Nothing here is job-bot-specific yet — it's just
making sure the tools exist and work.

### What we installed, and why

| Tool | Why we need it |
|---|---|
| **Python 3.14** (already installed on this machine) | The language the whole bot is written in. Checked with `python --version`. |
| **venv** (`python -m venv venv`) | A virtual environment — an isolated folder with its own copy of Python packages, so this project's dependencies don't clash with anything else on the machine. Everything installed below goes *inside* `venv/`, not system-wide. |
| `requests` | Makes HTTP calls to job APIs (Adzuna, etc.) and the Telegram Bot API. |
| `python-dotenv` | Reads the `.env` file and loads its values (API keys, tokens) as environment variables, so no secret ever has to be typed directly into the code. |
| `pdfplumber` | Extracts raw text out of PDF resumes. |
| `python-docx` | Extracts raw text out of Word (`.docx`) resumes, in case a resume is ever supplied in that format. |
| `pytest` | Runs the automated tests in `tests/` so we can confirm each module still works, automatically, instead of manually re-checking by eye every time. |

### How we installed it
```bash
python -m venv venv                       # create the virtual environment
./venv/Scripts/pip.exe install -r requirements.txt   # install everything listed above
```
Exact versions are pinned in `requirements.txt` so a future `pip install` always
installs the same thing that was tested here.

### Files created
- `requirements.txt` — the pinned dependency list above.
- `.env.example` — a template listing every environment variable the project needs, with blank values. Safe to commit to git (no real secrets in it).
- `.env` — your actual real copy of those variables. **Never committed** (see `.gitignore`).
- `.gitignore` — tells git to never track `.env` (secrets) or `venv/`/`__pycache__/`/`.pytest_cache/` (machine-specific junk that shouldn't be shared).
- Folders: `data/` (structured output + database), `src/` (all the bot's code), `tests/` (automated checks), `.github/workflows/` (future scheduling config).

### Environment variables in `.env` so far
| Variable | What it's for | Status |
|---|---|---|
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Credentials for the Adzuna job-listings API (Module 3+). | ✅ filled in (real keys) |
| `RAPIDAPI_KEY` | Credentials for JSearch, an optional extra job source (Module 4). | empty — not needed yet |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Lets the bot send you messages (Module 9). | empty — not needed yet |
| `RESUME_FILE_PATH` | Which resume file `resume_parser.py` should read. | ✅ set to `my-resume/HAZIQ_RESUME_UPDATED_V001.pdf` |

### Test & result
Ran a hello-world script and confirmed `.env` loads correctly via `python-dotenv`:
```
Environment ready
test_placeholder_123        # printed value of a test ADZUNA_APP_ID
```
**Pass condition met** — no errors, test value printed correctly. ✅

---

## Module 2 — Resume Parser

### What this module is for
Turn your resume (a PDF) into structured data (`data/resume_profile.json`) —
skills, past job titles, years of experience, education — so later modules
can score job postings against it, instead of comparing raw PDF text.

Per your decision, this uses **rule-based parsing only** (no LLM/AI API call) —
free, no extra API key, and works fine given how clean your resumes' section
structure is.

### Input
You provided two real resume files in `my-resume/`:
- `HAZIQ_RESUME_UPDATED_V001.pdf` — Europass-format CV.
- `Muhammad_Haziq_Nazeer_Resume_TWO.pdf` — a simpler, single-column CV.

These two files use noticeably different layouts (different section names,
different ways of writing job entries and dates), so the parser was written
and tested against **both**, not just one, to make sure it isn't overfit to a
single resume format.

### How it works (`src/resume_parser.py`)
1. **Extract raw text** — `pdfplumber` for PDFs, `python-docx` for Word docs.
2. **Split into sections** — scans line by line for known section header text
   (`SUMMARY`, `EXPERIENCE`, `EDUCATION`, `SKILLS`, `PROGRAMMING SKILLS`, etc.,
   matched case-insensitively) and groups the lines under each header.
3. **Extract skills** — from the `SKILLS` / `PROGRAMMING SKILLS` section,
   splitting on commas, pipes (`|`), and `Category:` prefixes, then
   de-duplicating.
4. **Extract job titles + years of experience** — scans the experience section
   for lines that contain both a date (e.g. `12/2025`) and a role keyword
   (`Engineer`, `Developer`, `Intern`, etc.); the earliest date found becomes
   the "career start," compared against today's date to compute total years.
5. **Extract education** — looks for lines mentioning `university`, `college`,
   `board of`, `bachelor`, or `institute`, and pulls the attached date range
   whether it's on the same line or the line above (both formats appear
   across your two resumes).
6. **Extract contact info** — name (first line), email (regex), phone (regex),
   location (from an `Address:` field or the header line).
7. Saves everything to `data/resume_profile.json`.

### Bugs found and fixed during testing
Three issues turned up only because we tested against real, messy resume
text rather than a clean hypothetical example:
- A bare subheader word ("Languages") with no delimiter was being pulled in
  as if it were a skill — fixed by requiring skill lines to actually contain
  a comma, pipe, or colon.
- The phone number regex dropped the opening `(` in `(+92) 0311...`.
- A resume line describing coursework ("...studied during this degree
  are:") was wrongly matched as an education entry because it contained the
  word "degree" — fixed by tightening the keyword list and skipping lines
  that end in `:`.
- (Also fixed) a resume typo (`Storage::` with a double colon) was leaking a
  stray `:` onto the front of the next skill — fixed by stripping colons off
  extracted skill tokens.

### Test & result
Automated tests added at `tests/test_resume_parser.py`, run via:
```bash
./venv/Scripts/python.exe -m pytest tests/test_resume_parser.py -v
```
All 3 pass: both real resumes parse into valid profiles (name, email, 10+
skills, at least one job title, years of experience > 0, at least one
education entry), and the punctuation-stripping fix is covered directly.

Sample output (from the Europass CV):
```json
{
  "name": "Muhammad Haziq Nazeer",
  "email": "haziqnazeer@gmail.com",
  "phone": "(+92) 03110645820",
  "skills": ["HTML", "CSS", "Javascript", "Typescript", "React.js", "Next.js", "Node.js", "Express.js", "NestJs", "C++", "Java", "Python", "PHP"],
  "job_titles": ["ASSOCIATE SOFTWARE ENGINEER", "SOFTWARE ENGINEER INTERN"],
  "years_of_experience": 1.4,
  "education": [{"line": "BS SOFTWARE ENGINEERING University of Central Punjab", "dates": "18/10/2021 – 22/07/2025 Lahore, Pakistan"}, ...]
}
```
**Pass condition met** — real skills/titles/experience extracted accurately from your actual resume. ✅

### How to run this module yourself
```bash
./venv/Scripts/python.exe src/resume_parser.py
```
Prints the raw extracted text (sanity check), then the structured JSON, then
saves it to `data/resume_profile.json`.

---

## Module 3 — Job Collector (Single Source: Adzuna)

### What this module is for
Prove that we can pull real, live job listings from one API before adding
more sources. Per the phased plan, this is Adzuna only — multi-source
comes in Module 4.

### What we installed, and why
Nothing new — this module only needed `requests` (already installed in
Module 1) to make HTTP calls to Adzuna's REST API.

### How it works (`src/job_collector.py`)
1. `fetch_adzuna_jobs(country, keyword, app_id, app_key)` — calls
   `https://api.adzuna.com/v1/api/jobs/{country}/search/1` with your
   `ADZUNA_APP_ID`/`ADZUNA_APP_KEY` from `.env`, `results_per_page=20`, and a
   keyword to search for.
2. `normalize_adzuna_job(raw_job, country)` — converts Adzuna's raw JSON shape
   (nested `company.display_name`, `location.display_name`, etc.) into the
   flat, source-agnostic job format the whole pipeline will use going
   forward:
   ```json
   {
     "title": "...", "company": "...", "location": "...", "country": "...",
     "date_posted": "...", "url": "...", "description": "...", "source": "adzuna"
   }
   ```
   This exact shape is what doc `job-bot-phased-implementation.md` specifies
   for the *combined* multi-source list in Module 4 — building it now means
   Module 4 just adds more functions that produce the same shape, no rework.
3. `main()` runs a real query (`country="gb"`, `keyword="software engineer"`),
   prints the raw API response, prints the normalized list, and saves it to
   `data/jobs_raw.json`.

### Test & result
Ran the collector live against Adzuna's production API:
```bash
./venv/Scripts/python.exe src/job_collector.py
```
Returned 20 real, current UK job listings (Capital One, Hudson Shribman,
Saftronics, etc.) with working `adzuna.co.uk` URLs and 2026 posting dates.
**Pass condition met** — real jobs, correct country, correct dates, working
links. ✅

Automated tests in `tests/test_job_collector.py`:
- Two pure unit tests for `normalize_adzuna_job` (field mapping, missing-field
  handling) — no network needed.
- One live integration test that calls the real Adzuna API and checks every
  returned job has a title and a valid `http` URL. It auto-skips if
  `ADZUNA_APP_ID`/`ADZUNA_APP_KEY` aren't set (e.g. on a machine without your
  `.env`), so the test suite never fails just because of missing local
  secrets.

```bash
./venv/Scripts/python.exe -m pytest tests/test_job_collector.py -v
```
All 3 pass. ✅

### How to run this module yourself
```bash
./venv/Scripts/python.exe src/job_collector.py
```

---

## Module 4 — Multi-Source Expansion

### What this module is for
Add more job sources on top of Adzuna, so the bot isn't dependent on a single
API, and merge everything into one combined list in the shared job format.

### Decisions made along the way
While building this, two real gaps turned up that needed a decision rather
than a default:
- **JSearch (RapidAPI) doesn't work with the provided key** — every path
  (`/search`, `/v1/search`, etc.) returns `404 Endpoint does not exist`,
  which is what RapidAPI's gateway returns when a key isn't subscribed to
  that specific API. This needs to be re-checked on the RapidAPI dashboard;
  JSearch is skipped for now and the pipeline works fine without it.
- **Pakistan isn't covered by Adzuna** (confirmed directly against their API -
  it only supports `at, au, be, br, ca, ch, de, es, fr, gb, in, it, mx, nl,
  nz, pl, sg, us, za`) **and Rozee.pk has no public API**. You chose to
  **skip Pakistan for v1** and add it as its own module later, rather than
  scrape Rozee.pk's public pages now. So this version of the bot only
  surfaces international (Europe/USA/Australia/Canada/NZ) jobs — Pakistan
  support is a known gap, not an oversight.

### What we added to `src/job_collector.py`
1. **Adzuna, multiple countries** — `collect_adzuna_multi()` loops over every
   Adzuna country code that overlaps your target regions (`us, gb, ca, au,
   nz` + 9 European codes) instead of just `gb`. If one country's request
   fails, it's logged and skipped — the rest still run (matches the "fail
   gracefully" principle from the architecture doc).
2. **Arbeitnow** (`fetch_arbeitnow_jobs` / `normalize_arbeitnow_job`) — a free,
   public, no-API-key-needed job board API, Europe-focused. Its raw
   description field is real HTML, so a small `_strip_html()` helper (using
   Python's built-in `html.unescape` + a regex to drop tags) turns it into
   plain text — no extra HTML-parsing library needed.
3. **Greenhouse public company boards** (`fetch_greenhouse_jobs` /
   `normalize_greenhouse_job`) — public JSON endpoints companies expose for
   their own career pages (`boards-api.greenhouse.io/v1/boards/{company}/jobs`),
   no login or API key needed. Tested several well-known slugs; three came
   back valid with real listings and were kept as the default set:
   `gitlab`, `stripe`, `airbnb`. Greenhouse's description field turned out to
   be *double*-escaped HTML (e.g. literal text `&lt;div&gt;`), so the same
   `_strip_html()` helper handles that correctly too (it unescapes first,
   then strips tags).
4. **`collect_all()`** — runs all three sources and merges them into one
   list. Each source is wrapped in its own `try/except`, so if (say) Adzuna's
   API key gets revoked, Arbeitnow and Greenhouse still run and you still get
   a digest instead of the whole pipeline crashing.

### Test & result
```bash
./venv/Scripts/python.exe src/job_collector.py
```
```
--- COLLECTED 1272 JOBS ---
  adzuna: 280
  arbeitnow: 100
  greenhouse: 892
```
Checked every job for blank/broken fields: only 4 out of 1272 (0.3%) were
missing a field, and in every case it was Adzuna's own data missing a
`company` name (a recruiting agency listing that hides the client's name) -
not a bug in our code. **Pass condition met** — 2+ sources represented, fields
correctly filled in. ✅

Automated tests in `tests/test_job_collector.py` (9 total, all passing):
pure unit tests for each source's field-mapping/HTML-cleaning logic, plus
live smoke tests confirming each real API still returns usable jobs, plus one
test confirming `collect_all()` actually merges 2+ distinct sources.

### How to run this module yourself
```bash
./venv/Scripts/python.exe src/job_collector.py
./venv/Scripts/python.exe -m pytest tests/test_job_collector.py -v
```

---

## Module 5 — Date & Country Filter

### What this module is for
Narrow the ~1,270 collected jobs down to only the ones that are actually
recent (posted in the last 7 days) and in a country you actually care about
(Pakistan, or one of your target international regions), tagging each with
whether relocation/visa sponsorship applies.

### How it works (`src/filters.py`)
1. **`parse_date()`** — all three sources format dates slightly differently
   (Adzuna: `...Z`, Arbeitnow/Greenhouse: `...+00:00` / `...-04:00`).
   Normalizes all of them into one comparable, timezone-aware UTC datetime.
2. **`filter_by_date()`** — drops anything older than 7 days.
3. **`classify_country()`** — job sources are inconsistent about whether
   `country` is a 2-letter code (`"us"`) or a full name (`"United States"`,
   with occasional stray whitespace) so this checks a lowercased lookup table
   covering both forms for Pakistan and every target region (Europe
   countries, USA, UK, Canada, Australia, New Zealand). Anything not in
   either list (e.g. Brazil) is dropped.
4. **`filter_by_country()`** — keeps only Pakistan/target-region jobs and
   tags each with `"relocation_required": false` (Pakistan) or `true`
   (everywhere else).
5. **`apply_filters()`** — runs both filters together; this is what later
   modules will call.

### Test & result
```bash
./venv/Scripts/python.exe src/filters.py
```
```
Collected: 1272
After date filter (<= 7 days): 259
After country filter (Pakistan + target regions): 193
  Pakistan (no relocation needed): 0
  Target regions (relocation required): 193
```
(Pakistan is 0 because Module 4 intentionally doesn't collect Pakistan jobs
yet - see the Module 4 notes above.) Manually verified: zero surviving jobs
are older than 7 days, and the country tagging correctly handles both codes
and full names (`"us"`, `"United States"`, `"United States "` with a trailing
space, `"Germany"`, etc. all correctly classified). **Pass condition met.** ✅

6 automated tests added in `tests/test_filters.py`, all passing - covering
date parsing across all 3 source formats, the 7-day boundary, country
classification (including the Pakistan/target/other split), and the combined
`apply_filters()`.

### How to run this module yourself
```bash
./venv/Scripts/python.exe src/filters.py
./venv/Scripts/python.exe -m pytest tests/test_filters.py -v
```

---

## Module 6 — Visa/Relocation Keyword Filter

### What this module is for
Of the 193 jobs that survived Module 5 (recent + in a target country), most
international job postings never actually say whether they sponsor visas.
This module keeps only the ones that explicitly do — Pakistan jobs skip this
filter entirely since no relocation is needed there. Lives in the same
`filters.py` file as Modules 5/6, per the architecture doc's grouping.

### A real bug found while testing (not hypothetical)
Running this against the live 193 jobs surfaced two problems immediately:
- **A false positive from negation**: one Airbnb posting said *"is **not**
  eligible for relocation support"* — naive substring matching on
  `"relocation support"` flagged it as a genuine match, which is the exact
  opposite of what you want (a job that explicitly does *not* help with
  relocation). Fixed by checking the ~60 characters immediately before every
  keyword match for negation phrases (`"not eligible"`, `"does not"`,
  `"unable to"`, etc.) and rejecting the match if one is found.
- **A false negative from too-rigid phrasing**: a real, genuine match ("We're
  open to relocation and providing support with our visa agency") didn't
  contain any of the exact 2-3 word phrases from the original keyword list
  (the words were split across the sentence). Fixed by adding a few more
  real-world phrasings (`"open to relocation"`, `"visa agency"`,
  `"immigration support"`, etc.) to the keyword list.

### How it works (`src/filters.py`, added to Module 5's file)
- `VISA_KEYWORDS` — curated list of phrases (not single words like bare
  "visa", which would false-positive on sentences like "candidate must
  already hold a visa").
- `mentions_visa_or_relocation(description)` — finds each keyword match, then
  checks the text immediately before it for a negation phrase before
  accepting it as genuine.
- `filter_by_visa_keywords(jobs)` — Pakistan jobs (`relocation_required:
  false`) pass through untouched; everything else is dropped unless
  `mentions_visa_or_relocation()` is true.
- `apply_filters()` now chains all three: date -> country -> visa keywords.

### Test & result
```bash
./venv/Scripts/python.exe src/filters.py
```
```
Collected: 1272
After date filter (<= 7 days): 259
After country filter (Pakistan + target regions): 193
After visa/relocation keyword filter: 1
  Pakistan (no relocation needed): 0
  Target regions (visa/relocation confirmed): 1
```
Only 1 of 193 target-region postings explicitly confirms visa/relocation
support - which matches reality (most job ads simply don't mention it either
way). Manually confirmed the one surviving job (Urban Sports Club, Germany)
genuinely does say so in its real description, and confirmed the earlier
false-positive (Airbnb, "not eligible for relocation") is correctly excluded.
**Pass condition met.** ✅

5 new automated tests added (11 total in `tests/test_filters.py`), covering
genuine matches, negated matches, unrelated text, Pakistan jobs skipping the
filter, and the full three-stage `apply_filters()` pipeline.

### How to run this module yourself
```bash
./venv/Scripts/python.exe src/filters.py
./venv/Scripts/python.exe -m pytest tests/test_filters.py -v
```

---

## Module 7 — Resume Matching & Scoring

### What this module is for
Rank surviving jobs so the ones that best match your actual skills rise to
the top, using simple keyword overlap (per your earlier choice to keep
everything rule-based, no LLM/embeddings) between `resume_profile.json`'s
skill list and each job's title + description.

### A real bug found while testing (not hypothetical)
The very first test run flagged a "PHP" match on a Golang backend role -
worth double-checking. Turned out to be genuine (the posting literally says
"experience with PHP is a nice-to-have"). But checking the underlying logic
exposed a real, general bug: naive substring matching means the skill
**"Java" matches inside the word "JavaScript"** - so a job that only wants
JavaScript would incorrectly get credit for "Java experience" too, inflating
its score. Confirmed with a direct test before fixing it.

The fix isn't as simple as switching to a `\b` word-boundary regex, though -
that breaks for skills ending in punctuation like **"C++"**, because `\b`
requires one side of the boundary to be a word character, and neither `+`
nor a following space qualifies, so `\b` never fires right after "C++".
Instead, `_skill_matches()` uses explicit lookarounds
(`(?<![a-zA-Z0-9])...(?![a-zA-Z0-9])`) that treat *any* non-alphanumeric
character (space, punctuation, start/end of string) as a valid boundary on
either side - this correctly rejects "Java" inside "JavaScript" while still
correctly matching "C++" and "Node.js".

### How it works (`src/scorer.py`)
1. `score_job(job, resume_skills)` — checks how many resume skills appear as
   a whole token in the job's title + description; score = `(matched / total
   resume skills) * 100`.
2. `score_jobs(jobs, resume_profile)` — scores every job and sorts descending
   by score. Each job gets two new fields: `score` and `matched_skills` (the
   latter isn't strictly required by the plan doc, but it's cheap to add and
   makes it possible to see *why* a job ranked where it did, both for testing
   and later in the Telegram digest).

### Test & result
Because Module 6's real output is only 1 job right now (see Module 6's
notes - most real postings simply don't mention visa sponsorship this week),
that's too thin a sample to judge ranking quality on its own. As an extra
quality check (not part of the permanent pipeline), scoring was also run
against the broader 193-job Module-5 output to see real ranking behavior:
```
[ 30.8] Software Engineer - Mindbox Sp. z o.o.        | matched: Javascript, Typescript, Node.js, Java
[ 30.8] Senior DevOps Engineer - Contensi Software     | matched: Typescript, Node.js, Java, Python
[ 23.1] Senior ML Engineer, Query Intelligence - Airbnb | matched: C++, Java, Python
...
[  0.0] Senior Market Manager, Experiences - Airbnb    | matched: (none)
[  0.0] Senior Regulatory Operations Lead - Airbnb     | matched: (none)
```
Top matches are genuinely relevant full-stack/JS/Node/Python engineering
roles; the bottom-ranked jobs are non-engineering roles (Market Manager,
Regulatory Operations) that leaked in because Greenhouse's public API
returns a company's *entire* job board, not just engineering roles - and
they correctly scored 0. **Pass condition met** — relevant jobs rank highest,
irrelevant ones score lowest. ✅

5 automated tests added in `tests/test_scorer.py`: percentage scoring, the
Java/JavaScript false-positive fix, the C++ punctuation-boundary fix, a
zero-overlap case, and descending sort order.

### How to run this module yourself
```bash
./venv/Scripts/python.exe src/scorer.py
./venv/Scripts/python.exe -m pytest tests/test_scorer.py -v
```

---

## Module 8 — Storage & Duplicate Prevention

### What this module is for
Remember which jobs you've already been sent, using a local SQLite database
(`data/jobs.db`), so re-running the pipeline never re-sends the same job.
A job's URL is used as its unique key (two different job postings never
share a URL).

### How it works (`src/storage.py`)
1. `init_db()` — creates `data/jobs.db` (if it doesn't already exist) with
   one table, `seen_jobs (url PRIMARY KEY, title, company, first_seen)`.
2. `get_new_jobs(jobs, conn)` — checks every scored job's URL against the
   table in a single query and returns only the ones not already recorded.
3. `mark_jobs_seen(jobs, conn)` — inserts the jobs that are about to be sent
   (`INSERT OR IGNORE`, so re-inserting an already-seen URL is a harmless
   no-op rather than an error).
4. `main()` — loads `jobs_scored.json`, filters out already-seen jobs, saves
   the genuinely-new ones to `data/jobs_new.json` (this is what Module 9's
   Telegram delivery will actually send), and marks them seen.

Remember from Module 1: `data/jobs.db` is deliberately **not** in
`.gitignore` - once scheduling (Module 10) runs this on GitHub Actions,
the workflow will commit this file back to the repo after every run so the
"already seen" history survives between runs on the ephemeral runner.

### Test & result
Ran the exact test the phased plan specifies - run the whole thing twice in
a row:
```bash
./venv/Scripts/python.exe src/storage.py   # 1st run
./venv/Scripts/python.exe src/storage.py   # 2nd run, same input
```
```
1st run -> Scored jobs: 1 | Already seen (skipped): 0 | New jobs to send: 1
2nd run -> Scored jobs: 1 | Already seen (skipped): 1 | New jobs to send: 0
```
**Pass condition met exactly** — the second run sends zero duplicate jobs. ✅

4 automated tests added in `tests/test_storage.py` (using a temporary
throwaway database per test, via pytest's `tmp_path` fixture, so tests never
touch your real `data/jobs.db`): first-run behavior, the exact
run-twice-get-zero-duplicates scenario, a mixed batch where only the
genuinely new job passes through, and an empty-list edge case.

### How to run this module yourself
```bash
./venv/Scripts/python.exe src/storage.py
./venv/Scripts/python.exe -m pytest tests/test_storage.py -v
```

---

## Module 9 — Telegram Delivery

### What this module is for
Format the final ranked, deduplicated job list (`data/jobs_new.json` from
Module 8) into a readable message and send it to you via the Telegram Bot
API - the last step before scheduling (Module 10).

### ⚠️ Could not verify live delivery from this environment
Every attempt to reach `api.telegram.org` from here timed out on connect,
while Adzuna, Arbeitnow, Greenhouse, and RapidAPI all connected fine in
earlier modules. That points to `api.telegram.org` specifically being
blocked at the network level in this environment - Telegram access has been
intermittently restricted in Pakistan by the PTA in the past, so this may
also affect your own machine/network depending on when/where you run this.
**You'll need to verify the real send yourself**, e.g. by running:
```bash
./venv/Scripts/python.exe src/notifier.py
```
If it also times out for you, a VPN (or a network where Telegram isn't
blocked, e.g. once this runs on GitHub Actions' cloud runners in Module 10)
should work, since the code itself is a plain, correct call to Telegram's
public Bot API.

### How it works (`src/notifier.py`)
1. `format_job(job)` — one job -> an HTML-formatted block (title, company,
   country, a relocation note, score, and a clickable "View & Apply" link).
   Uses Telegram's HTML `parse_mode`, escaping any special characters in the
   title/company (via `html.escape`) so a job title containing `<` or `&`
   can't break the message formatting.
2. `build_digest_chunks(jobs)` — packs formatted jobs into one or more
   messages, staying under `MAX_MESSAGE_CHARS` (3500, safely below
   Telegram's real 4096-character limit) so the digest still works
   correctly whether there's 1 new job or 50.
3. `send_telegram_message(text, bot_token, chat_id)` — a single POST to
   Telegram's `sendMessage` endpoint.
4. `send_digest(jobs, bot_token, chat_id)` — sends one Telegram message per
   chunk; returns 0 (and sends nothing) if there are no new jobs, so runs
   with nothing new don't spam you with an empty message.

### Test & result
Since live delivery couldn't be confirmed here, all 8 tests in
`tests/test_notifier.py` mock the network call (`unittest.mock.patch` on
`requests.post` / `send_telegram_message`) and verify the logic that
*doesn't* depend on network access actually working:
- message formatting includes every required field (title, company,
  country, relocation note, score, link),
- Pakistan jobs get the correct "no relocation needed" note,
- HTML special characters in a job title are escaped correctly,
- a 50-job batch correctly splits across multiple messages, each under the
  character limit,
- `send_telegram_message` posts to the exact right URL with the right
  payload fields (`chat_id`, `text`, `parse_mode: HTML`),
- `send_digest` sends exactly one Telegram message per chunk, and sends
  nothing at all when there are no new jobs.

All 8 pass. ✅ **Still outstanding: run `src/notifier.py` yourself once (with
a job in `data/jobs_new.json`) to confirm you actually receive the message.**

### How to run this module yourself
```bash
./venv/Scripts/python.exe src/notifier.py
./venv/Scripts/python.exe -m pytest tests/test_notifier.py -v
```

---

## `src/main.py` — Full Pipeline Orchestrator

### What this is for
Wire Modules 2-9 together into the single end-to-end run described in the
architecture doc ("main.py just calls them in order"): parse resume -> collect
jobs -> filter -> score -> dedup -> send Telegram digest. This is what
Module 10's scheduled GitHub Actions run will actually execute
(`python src/main.py`).

### A real ordering bug this caught
Building this exposed exactly the risk flagged in Module 9's notes: my
`storage.py` test run had marked a job "seen" immediately, before it was
ever actually sent (because the Telegram send failed on this environment's
network). Re-reading the phased plan's own Module 8 spec confirms this was
wrong: *"Insert new jobs into the database after sending"* — sending comes
first. `main.py`'s `run()` now enforces that ordering explicitly:
`storage.mark_jobs_seen()` is only called **after** `notifier.send_digest()`
succeeds; if the send raises an exception (e.g. Telegram unreachable), the
error is logged and the function returns *without* marking anything seen -
so the job is correctly retried on the next scheduled run instead of being
silently lost. Also cleaned up the actual `data/jobs.db` afterwards, since an
earlier Module 8 test run had already wrongly marked the one real live job
as "seen" before this fix existed.

### Test & result
Ran the real end-to-end pipeline live:
```bash
./venv/Scripts/python.exe src/main.py
```
```
[1/6] Parsing resume...        13 skills, 1.4 years experience
[2/6] Collecting jobs...       1271 jobs
[3/6] Filtering...             1 job survived
[4/6] Scoring...
[5/6] Checking duplicates...   1 new job (0 already sent)
[6/6] Sending Telegram digest...
      Telegram send failed, jobs will be retried next run: ConnectTimeout ...
```
Confirmed directly against `data/jobs.db` that the job was correctly **not**
marked as seen after the failed send (0 rows in `seen_jobs`) - exactly the
intended behavior. **Telegram delivery itself is still unverified** (see
Module 9's note - it's blocked in Pakistan; you'll confirm this once
deployed).

3 automated tests added in `tests/test_main.py`, all with every dependency
mocked (no real network/API calls): a successful run marks jobs seen exactly
once after sending; a failed send does **not** mark anything seen (the
critical fix, verified directly); and a run with zero new jobs skips
notification entirely without erroring.

Full test suite (all 9 modules): **43/43 passing.**

### How to run this module yourself
```bash
./venv/Scripts/python.exe src/main.py
./venv/Scripts/python.exe -m pytest tests/ -v
```

---

## Module 10 — Scheduling (GitHub Actions) + a PII fix that changed `main.py`

### What this module is for
Run the whole pipeline automatically, on a schedule, with no computer of
yours needing to stay on.

### A privacy problem found while preparing to push to GitHub
Your Europass CV (`my-resume/HAZIQ_RESUME_UPDATED_V001.pdf`) contains real
PII - passport number, date of birth, home address. You decided (correctly)
to keep `my-resume/` out of git entirely rather than risk it ending up in a
public repo's history forever. But `main.py` was calling
`resume_parser.build_profile()` on that raw file on every run - which would
have broken the second the workflow ran on GitHub Actions, since the actual
PDF would never exist in the cloned repo.

The real fix (which the architecture doc already hinted at - "resume parser
only needs to run once, or whenever you update your resume") was to change
`main.py` to load the already-parsed `data/resume_profile.json` directly
instead of re-parsing the PDF every run. That file **is** committed to the
repo (it's already de-identified - no passport/DOB/address, per Module 2)
and is the only resume-related thing the scheduled run actually needs.
Workflow: whenever you update your resume, run
`python src/resume_parser.py` locally and commit the refreshed
`resume_profile.json` - the automated runs never touch the raw PDF at all.

### What's excluded from git, and why
- `my-resume/` — raw resume PDFs with PII (decision above).
- `.claude/` — my own tool's local settings, irrelevant to this project.
- `data/jobs_raw.json`, `jobs_filtered.json`, `jobs_scored.json`,
  `jobs_new.json` — regenerated fresh every run, no reason to track them.
- `.env`, `venv/`, `__pycache__/`, `.pytest_cache/` — secrets/machine-local
  junk, as set up back in Module 1.
- **Tracked**: `data/jobs.db` (needs to persist across runs for dedup) and
  `data/resume_profile.json` (needed by every scheduled run, see above).

### How it works (`.github/workflows/run_job_bot.yml`)
1. Triggers every 4 hours (`cron: "0 */4 * * *"`) plus a manual
   "Run workflow" button (`workflow_dispatch`) for on-demand testing. Changed
   from every 12 hours since the repo is public - GitHub Actions minutes are
   free and unlimited for public repos, so there's no cost to running more
   often.
2. Checks out the repo, installs Python 3.12 + `requirements.txt`.
3. Runs `python src/main.py` with your 4 secrets
   (`ADZUNA_APP_ID`/`ADZUNA_APP_KEY`/`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`)
   injected as environment variables from GitHub's encrypted repo secrets -
   never hardcoded in the workflow file.
4. Commits `data/jobs.db` back to the repo if it changed, so the next
   scheduled run (on a brand-new, empty runner) still remembers what's
   already been sent.

### What you still need to do to actually deploy this
1. On GitHub: **Settings -> Secrets and variables -> Actions -> New
   repository secret**, add all 4: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`,
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
2. Push this repo (already done for you at
   `https://github.com/MianHaziq/Job-Finder-bot`).
3. Go to the repo's **Actions** tab and click **Run workflow** once
   manually to confirm it works before waiting for the schedule.

### Test & result
Couldn't run the actual GitHub Actions workflow from here (that only runs
on GitHub's own servers once pushed), but verified everything it depends on:
- `requirements.txt` installs cleanly (already proven in Module 1).
- `main.py` runs correctly end-to-end locally with real credentials
  (Modules 1-9's tests + the live run above).
- `data/resume_profile.json` is committed and loadable without the raw PDF.
- The workflow YAML was written directly against GitHub Actions' documented
  syntax (`schedule`/`workflow_dispatch` triggers, `secrets.*` context,
  `permissions: contents: write` for the commit-back step).

**You'll confirm the real scheduled run + Telegram delivery once deployed**,
since Telegram itself is unreachable from this environment (see Module 9).

---

## Follow-up — Merging Both Resumes

### Why this changed
After deployment, it became clear the Europass CV alone (the one
`RESUME_FILE_PATH` pointed to) only yields **13 skills** - it lists
programming languages but not frameworks/tools/cloud services. Your simpler
CV (`Muhammad_Haziq_Nazeer_Resume_TWO.pdf`) yields **41 skills** (React,
Next.js, AWS, Docker, MongoDB, Stripe, WebSockets, etc.) because its SKILLS
section is organized by explicit categories. Since `scorer.py` only ever
matches against whatever's in `resume_profile.json`, using just the
Europass CV meant jobs were being scored against a much narrower picture of
your actual skills than you really have.

### What changed (`src/resume_parser.py`)
- `RESUME_FILE_PATH` in `.env`/`.env.example` now accepts **comma-separated
  paths** - currently set to both PDFs.
- `build_combined_profile(file_paths)` — parses every listed file
  independently, then merges them: skills/job-titles/education are unioned
  and deduplicated (case-insensitive), `years_of_experience` takes the max
  across files (both describe the same jobs, so they should roughly agree),
  and `name`/`email`/`phone`/`location`/`summary` take the first non-empty
  or longest value found.
- `main()` now splits `RESUME_FILE_PATH` on commas; a single path still
  works exactly as before (uses `build_profile()` directly), multiple paths
  trigger the merge.

### Test & result
```bash
./venv/Scripts/python.exe src/resume_parser.py
```
Merged profile now has **48 unique skills** (13 + 41, minus overlaps),
still correctly identifies name/email, 1.4 years of experience, and 4
education entries (2 from each CV - degree + intermediate + matriculation
from Europass, the single combined line from the simple CV). 1 new
automated test added (`test_build_combined_profile_merges_skills_from_both_resumes`,
4 total in `tests/test_resume_parser.py`) verifying every skill from both
individual resumes appears in the merged result with no duplicates.

Full suite re-run after this change: **45/45 passing.**

### How this actually works day-to-day
- Your raw PDFs never leave your computer (not in git - see Module 10's PII
  notes) and the bot on GitHub Actions never touches them.
- Locally, whenever either resume changes, re-run
  `python src/resume_parser.py` (it reads both paths from `.env`
  automatically) and push the refreshed `data/resume_profile.json` - that's
  the only file the scheduled bot actually reads.

---

## Follow-up — First Real Digest Feedback: Bad Score + Wrong Seniority + Missing Remote Jobs

### What happened
The first real GitHub Actions run succeeded and delivered a real Telegram
message - end-to-end confirmed working. But it surfaced 3 real problems
worth fixing rather than living with:

**1. Score formula was flawed.** The one job you got scored "2.1" - looked
broken. It wasn't a bug in the match itself: `score = (matched skills /
*total* resume skills) * 100`. Before merging resumes you had 13 skills, so
1 match = 7.7%. After merging to 48 skills, that *same* 1 match became
2.1% - the score shrinks every time the resume profile grows, even though
nothing about the actual job match changed. **Fix:** `score_job()` now
returns a raw matched-skill *count* instead of a percentage - stable
regardless of how many total skills are in your profile (verified with a
test that scores the same job against a 1-skill vs. 51-skill resume and
confirms the count doesn't change).

**2. No seniority awareness at all.** The job was "Senior Backend Engineer"
despite you having ~1.4 years of experience - `scorer.py` only ever checked
skill-keyword overlap, never title seniority. **Fix:** added
`is_seniority_mismatch(title, years_of_experience)` in `scorer.py` - flags
titles containing "senior"/"staff"/"principal"/"lead"/"director"/etc. when
experience is under 3 years. `score_jobs()` now sorts on
`(seniority_mismatch, -score)` - every appropriately-leveled job ranks above
every mismatched one, regardless of skill score. `notifier.py` shows a
"⚠ May require more seniority than your experience" line when flagged.

**3. Good remote jobs were being silently dropped - a real bug, not just a
missing feature.** You asked to make sure remote jobs are included, which
led to finding this: Greenhouse's Stripe/Airbnb boards format remote roles
as `"US-Remote"`, `"Remote in the US"`, `"Remote - USA"` etc. (no clean
"City, Country" format), and the country filter required an *exact* match
against the whole string - so all of these were being classified as
`"other"` and dropped entirely. Confirmed at scale: 38 Stripe + 28 Airbnb
US-remote roles were being thrown away every single run.
**Fix:** `classify_country()` in `filters.py` now searches for any known
country token as a *whole word anywhere* in the string, not just an exact
match (e.g. `"US-Remote"` now correctly matches "us"). Also added an
`is_remote` field (from Arbeitnow's explicit `remote` boolean, or a
"remote" keyword heuristic on title/location for Adzuna/Greenhouse) that
lets a job skip the visa/relocation keyword filter entirely - a genuinely
remote role doesn't need visa sponsorship or physical relocation, regardless
of which country it's listed under, same as a Pakistan job.

### Result
Re-ran the full pipeline after all three fixes:
```
Collected 1271 jobs -> 260 after date filter -> 206 after country filter
(46 of which are remote) -> 47 after visa/remote filter -> 46 new
(1 already sent previously)
```
Up from just 1 surviving job before these fixes - the remote-job country
classification bug alone was responsible for most of that.

13 new/updated automated tests added across `test_scorer.py`,
`test_filters.py`, `test_job_collector.py`, and `test_notifier.py` covering:
score stability across resume sizes, seniority-mismatch detection and
sort-order, the exact messy-location-string formats that were being
dropped, remote-flag detection from all 3 sources, remote jobs bypassing
the visa filter, and the corrected "Remote - no relocation needed" digest
note. Full suite: **58/58 passing.**

---

## Follow-up — Irrelevant Non-Engineering Jobs Slipping Into the Digest

### What happened
Asked which countries/job types the bot targets, which led to checking the
real data: **22 of the 47 surviving jobs had zero skill overlap with your
resume** - Recruiter, Performance Marketing Manager, Account Executive,
FP&A Manager, Engineering Manager (non-technical), etc. Root cause: only
Adzuna is keyword-restricted to `"software engineer"` - Arbeitnow and the 3
Greenhouse company boards (GitLab/Stripe/Airbnb) return *every* open role,
relying entirely on scoring to rank relevant ones up top. But `main.py` was
sending every job that survived filtering regardless of score, so these
completely unrelated roles (which only got through because they were
remote + recent + in a target country) would have reached your Telegram
digest.

### Fix (`src/scorer.py` + `src/main.py`)
- `filter_by_minimum_score(jobs, min_score=1)` — drops any job with zero
  matched skills. You chose the "require at least 1 matched skill" option
  (vs. a stricter 2+ threshold, since with only 1.4 years of experience a
  stricter cutoff risked losing genuinely good junior-friendly roles too).
- `main.py`'s step 4 now calls this right after scoring, before the
  duplicate-check/send steps, and logs how many were dropped.

### Test & result
```
[4/6] Scoring jobs against resume...
      25 jobs have at least one matched skill (22 dropped as irrelevant)
[5/6] Checking for duplicates already sent...
      24 new job(s) to send (1 already sent before)
```
2 new automated tests in `test_scorer.py`: confirms zero-overlap jobs
(e.g. "Recruiter") are dropped while any-overlap jobs are kept, and that a
custom threshold works. Full suite: **60/60 passing.**

---

## Follow-up — Workflow's Commit Step Wasn't Resilient to a Moved Remote

### What happened
A GitHub Actions run's "Run the job bot" step succeeded fine (the bot
worked correctly), but the final "Commit updated seen-jobs database" step
failed with a plain `git push` rejection - the remote had moved ahead
(code commits were being pushed from this session around the same time).
Caused mainly by unusually frequent manual re-runs/pushes during today's
testing, but the underlying risk is real: any two runs (or a run + a manual
code push) close together in time can hit the same race.

### Fix (`.github/workflows/run_job_bot.yml`)
The commit step now retries up to 3 times: if `git push` is rejected, it
fetches the latest remote state and rebases the jobs.db commit on top of
it, resolving any conflict on that file with `-X ours` (safe here since the
commit touches only `data/jobs.db`, and "ours" already contains everything
from when the run started plus its own new entries).

### Result
Couldn't fully simulate GitHub's runner locally, but traced through the
script logic step by step (bash `-e` semantics, conditional vs.
unconditional command failures) to confirm it retries correctly and still
surfaces a real failure clearly if all 3 attempts fail. Pushed; will be
exercised for real on the next scheduled/manual run.

---

## Major Rework — Relevance Overhaul (Title Matching, Worldwide Location, Multi-Query Search)

You reported the bot was returning too many unrelated jobs - wrong roles,
wrong industries, wrong seniority - and asked for a full analysis, fixes,
comprehensive tests, and an empirical precision/recall validation against
100+ real live jobs. This section documents all of it.

### Root cause analysis (what was actually wrong, and why)

**1. There was no title/role-type matching anywhere in the pipeline - the
primary cause.** `scorer.py` only ever checked whether your 48 *skill*
keywords (React.js, Node.js, AWS, Docker, Git, Jira, Agile, CI/CD...)
appeared anywhere in a job's title+description. Nothing checked whether the
job's *title* was actually a Software/Full-Stack/MERN/Backend/Frontend
role. Since Arbeitnow and Greenhouse (`job_collector.py`) pull **every open
role** with zero keyword restriction, a "DevOps Engineer," "Data Engineer,"
"Machine Learning Engineer," "QA Automation Engineer," or "Site Reliability
Engineer" posting mentioning AWS/Docker/Git scored just as well as an
actual MERN developer role, because generic terms like "Git"/"Jira"/"Agile"
carry almost no discriminating signal but counted identically to a specific
one like "React.js."

**2. Non-tech industries were only excluded incidentally.** No title-based
exclude list existed at all (Sales/Marketing/HR/Nurse/Teacher/Civil-
Mechanical-Electrical Engineer/etc.) - they were only dropped because they
happened to score 0 on skill overlap, which is fragile, not a guarantee.

**3. Seniority was only "soft-deprioritized," never excluded.** The old
`is_seniority_mismatch()` pushed Senior/Staff/Lead/Principal/Director/
Architect titles to the *bottom* of the ranked list, but `main.py` still
sent every job in the list regardless of rank - nothing was actually
removed. This is exactly why you received a "Senior" role earlier.

**4. Country handling was a hard allow-list, contradicting "search
worldwide."** The old `classify_country()`/`TARGET_COUNTRY_TOKENS` dropped
any job whose country wasn't one of ~15 hardcoded names/codes - UAE, Saudi
Arabia, Singapore, Sweden, Norway, Denmark, Finland, Ireland, Japan, South
Korea, Luxembourg were all silently thrown away, even if remote or visa-
sponsored.

**5. Only one search phrase was ever used, and only for Adzuna.** Arbeitnow/
Greenhouse got no keyword filtering at all, simultaneously under-searching
the one filtered source and completely flooding the pipeline from the other
two.

**6. Remote/relocation phrase list was narrower than requested** (missing
"work from home," "fully remote," "remote worldwide," "international
applicants welcome" as explicit signals).

**7. No per-job structured logging** - only aggregate counts were printed.

### An engineering trade-off you decided on before implementation

Searching 14 title variations across every Adzuna-supported country, every
4 hours, works out to ~1,500+ Adzuna calls/day - likely to exceed a free-
tier quota (Adzuna doesn't expose its limit in responses, so this couldn't
be confirmed directly, only estimated). You chose to **keep all 14 literal
query variations** but **drop the schedule back to every 12 hours**
(from the 4-hour schedule set earlier) to manage the ~14x volume increase
safely. See `.github/workflows/run_job_bot.yml`.

### Fix 1 — Title-based role-relevance gate (`src/scorer.py`)

Two-stage relevance model, replacing pure skill-overlap scoring:

**Stage 1 (gate, hard accept/reject):**
- `EXCLUDE_INDUSTRY_PATTERNS` - hard rejects Sales/Marketing/Recruiter/HR/
  Customer Support/Account Executive/Accountant/Financial Analyst/Nurse/
  Teacher/Civil-Mechanical-Electrical Engineer/Data Entry/Call Center/Truck
  Driver, checked first, regardless of any skill overlap.
- `EXCLUDE_SENIORITY_PATTERNS` - hard rejects Senior/Sr./Staff/Principal/
  Lead/Director/Head of/VP (+ spelled-out "Vice President")/Chief/Architect/
  Manager (Manager is exempted only for Junior/Associate Project Manager).
  This is now a **hard exclude**, not a soft deprioritization.
- `TARGET_ROLE_PATTERNS` + `TECH_ROLE_WORD_PAIRS` - a job must positively
  match one of: Software Engineer, Software Developer, Full Stack (Developer/
  Engineer), MERN/MEAN Stack, Backend/Frontend/React/Node.js/JavaScript
  Developer (any qualifier word in between allowed, see Fix 2 below), Web
  Developer, or Junior/Associate Project Manager (only with an explicit
  software/IT context - "Junior Project Manager" alone is far too broad an
  industry-agnostic title otherwise). This positive-match requirement is
  what naturally excludes DevOps/Data/ML/QA/SRE/Architect-type roles
  *without* needing to enumerate every possible non-target discipline by
  name - this is the rule-based stand-in for semantic matching ("MERN
  Developer" ~ "React Developer" ~ "Full Stack Developer" ~ "Software
  Engineer (JavaScript)" all satisfy different groups, so any of them
  passes, with no LLM/embedding call needed).

**Stage 2 (weighted ranking score, only among jobs that passed Stage 1):**
`compute_weighted_score()` combines: role-group weight (an exact specialty
match like MERN/full-stack/React/Node scores higher than a generic
"Software Developer" match - the "title similarity" factor), skill overlap
(`+2` per matched resume skill), a junior-label bonus (`+5` if the title
itself says Junior/Graduate/Entry-Level/Associate/Intern - explicit
experience-level match), a remote bonus (`+8`, highest per your stated
priority order), a relocation-sponsored bonus (`+5`, only if not remote),
and a recency bonus (up to `+3`, decaying linearly to 0 at 7 days old).
**"Company reputation" is one of the requested scoring factors but is
intentionally *not* implemented** - there's no real data source wired into
this pipeline (no Glassdoor/Crunchbase/etc. integration), and faking a
placeholder number would be worse than being explicit about the gap. See
Recommendations below.

### Fix 2 — Worldwide location, no country allow-list (`src/filters.py`)

`classify_country()`/`filter_by_country()` were replaced with
`filter_by_location()`: a job is kept if it's in **Pakistan** (no
relocation needed), **genuinely remote** (any country), or **explicitly
offers visa/relocation sponsorship** (any country) - the hardcoded ~15-
country allow-list is gone entirely. This is worldwide by construction: a
job in the UAE, Sweden, or Japan is now evaluated on the same remote/
relocation signal as one in the US or UK, not on whether its country
happened to be on a fixed list.

**Known limitation, not fixed (a real constraint, not an oversight):**
Adzuna itself only supports querying 19 specific countries (`at, au, be, br,
ca, ch, de, es, fr, gb, in, it, mx, nl, nz, pl, sg, us, za` - confirmed
directly against Adzuna's own API error message). **Sweden, Norway,
Denmark, Finland, Ireland, UAE, Saudi Arabia, Japan, South Korea, and
Luxembourg cannot be queried via Adzuna at all**, regardless of
configuration - there is no "worldwide" option on their end. Jobs from
those countries can still surface via Arbeitnow/Greenhouse (which aren't
restricted to a country list), but there's no dedicated *search* of those
countries. See Recommendations.

### Fix 3 — Multi-query search generation (`src/job_collector.py`)

`SEARCH_QUERIES` now holds all 14 requested title variations (Associate/
Junior/Graduate Software Engineer, Software Engineer I, MERN Stack
Developer, React/Node.js Developer, Full Stack Developer/Engineer,
Software Developer, Backend/Frontend/Web Developer, Junior Project
Manager), each searched against all 19 Adzuna-supported countries
(`ADZUNA_ALL_COUNTRIES`) - 266 Adzuna calls per run. Results are deduped by
URL (`_dedupe_by_url()`), since the same posting commonly surfaces under
multiple search phrases.

### Fix 4 — Structured per-job audit logging (`src/scorer.py`)

`score_jobs()` now writes a full JSONL audit trail to
`data/evaluation_log.jsonl` on every run - one line per job processed,
whether accepted or rejected: title, company, country, matched skills,
score, remote/relocation detected, junior-labeled, accepted (true/false),
and the *exact* rejection reason (e.g. `"excluded seniority (matched
'\bsenior\b')"`, `"title does not match any target role"`). This is what
made the validation below possible - every decision is traceable.

### Edge cases handled
- **Missing/ambiguous experience level**: an unlabeled title like plain
  "Software Engineer" is *not* penalized for not saying "junior" - it's
  accepted by default (junior-labeling only adds a ranking bonus, it's
  never required to pass the gate).
- **Ambiguous remote status**: widened phrase detection ("work from home,"
  "fully remote," "remote worldwide," "remote-first") checked against the
  full description, not just title/location.
- **Vague/foreign-language titles**: see the diacritic-normalization fix
  below.
- **Relocation implied but not stated**: intentionally *not* inferred -
  requiring an explicit mention (with negation-checking, from the earlier
  Module 6 work) avoids false confidence; this is a deliberate precision-
  over-recall choice, called out as a trade-off, not silently guessed at.

### Validation methodology and results (the empirical part)

**Important methodological caveat, stated upfront:** "ground truth" here is
my own careful manual review of each real job title against your literal
stated criteria - not independent third-party/human-labeled data. That's a
real limitation for a fully rigorous study, and worth knowing before trusting
the numbers below at face value. It is, however, the most rigorous check
achievable without a human labeling service, and it *did* catch concrete,
real bugs (evidence it wasn't just circular).

**Sample**: collected a live batch across all 3 sources (Adzuna with 4
query variations x 5 countries, plus full-volume Arbeitnow + Greenhouse) -
2,363 raw jobs, filtered to **105 jobs** surviving the date + worldwide
location filter (multiple sources: 20 Adzuna, 8 Arbeitnow, 77 Greenhouse).
Every one of the 105 titles was read and independently judged against your
literal criteria, then compared against the pipeline's actual decision.

**Findings from the first pass (before fixes) - 3 real, concrete bugs:**

| # | Job title (real, from live data) | Bug | Type |
|---|---|---|---|
| 1 | "Node.js Back-End Developer **Sênior** \| Remote" | Portuguese "Sênior" not caught by the English/ASCII-only seniority exclude list | False positive |
| 2 | "Node.js **Trainee** Developer - Remote" | Regex required the tech word immediately next to "Developer"; the qualifier word "Trainee" in between broke the match | False negative |
| 3 | "React **/ Angular** Developer" | Same adjacency bug - a second technology name in between broke the match | False negative |

Also found (didn't cause a wrong call in this sample, but would have on a
different title): **"Vice President" spelled out wasn't caught** by the
bare `\bvp\b` pattern - both "Area Vice President" titles in the sample
happened to also fail the positive role-match anyway, but a hypothetical
"Vice President of Software Engineering" would have slipped through
undetected before the fix.

**All 3 were fixed** (see Fix 1's `TECH_ROLE_WORD_PAIRS` design and the new
`_normalize_text()` diacritic-stripping, plus adding `\bvice\s+president\b`
to the exclude list) and **re-validated against the same 105-job sample**:

| Metric | Before fixes | After fixes |
|---|---|---|
| Accepted | 25 | 27 |
| Confirmed false positives | 1 | **0** |
| Confirmed false negatives | 2 | **0** |
| Precision (clear-cut cases) | 96% (24/25) | **100%** |
| Recall (clear-cut cases) | 92.3% (24/26) | **100%** |

**3 remaining genuine judgment calls** (not counted as errors either way -
flagged transparently for you to decide, not swept under the rug):
- "Intermediate Backend Engineer - Analytics Instrumentation" and
  "Intermediate Fullstack Engineer - Data Products" - "Intermediate" wasn't
  in your explicit exclude list (Senior/Lead/Staff/Principal/Manager/
  Director/Architect) nor your explicit include list (0-2/1-2 years), so it
  defaults to accepted. If you want strictly 0-2 years only, add
  `r"\bintermediate\b"` and `r"\bmid[\s-]?level\b"` to
  `EXCLUDE_SENIORITY_PATTERNS` in `src/scorer.py`.
- "React Native Developer (Wallet team)" - now accepted as a side effect of
  fixing the adjacency bug (Fix 2 above): it genuinely contains both "react"
  and "developer" as separate words. React Native is mobile development
  using React - adjacent to, but not identical to, the "React Developer"
  (web) role you listed. Your resume doesn't show explicit React Native/
  mobile experience. If you don't want mobile roles, add a
  `r"react\s+native"` check to `EXCLUDE_INDUSTRY_PATTERNS` (or a new
  exclude group) to filter it back out.

All 78 rejected jobs in the sample were manually confirmed correct
(Sales/Marketing/HR/Account Executive/Customer Success postings, Senior/
Staff/Lead/Director/Manager/VP titles, and non-target disciplines like
DevOps/Data/ML/Security/QA/SRE Engineer, Paralegal, Analyst roles).

### Tests

25 new/rewritten tests added across `tests/test_scorer.py` (role-gate
acceptance/rejection for every category, the 3 validation-driven regression
tests, weighted-score ordering, full-pipeline + audit-log correctness),
`tests/test_filters.py` (worldwide location filtering, widened remote
phrases, messy remote-location-string formats), `tests/test_job_collector.py`
(multi-keyword search + cross-source dedup), and `tests/test_notifier.py`/
`tests/test_main.py` updated for the new job schema and pipeline shape.
**Full suite: 67/67 passing.** A full real end-to-end `main.py` run (all 14
queries x 19 countries) was also executed to confirm the production
configuration works, not just the unit tests.

### Recommendations for further improvement

1. **Adzuna-unreachable countries** (Sweden, Norway, Denmark, Finland,
   Ireland, UAE, Saudi Arabia, Japan, South Korea, Luxembourg) have no
   dedicated search coverage - consider adding a region-specific source
   (e.g. a Gulf-region job board, a Nordic job board) if these countries
   matter enough to justify the integration work.
2. **Company reputation** isn't scored at all (no real data source
   available). A Glassdoor/LinkedIn-follower-count/Crunchbase API
   integration could fill this in later, but it's a genuinely new
   integration, not a quick addition.
3. **Multi-language support is currently just diacritic-stripping**, which
   fixed the one real case found ("Sênior") but wouldn't catch a fully
   different-language word for "senior" (e.g. German "erfahren"). True
   multi-language semantic matching would benefit from an LLM/translation
   step - a bigger change than a rule-based fix, and one that would revisit
   the earlier "no LLM" decision.
4. **"Intermediate"/"mid-level" and "React Native" are currently accepted**
   by default (see the two judgment calls above) - decide if you want them
   excluded and I can add that in a follow-up.
5. **Monitor Adzuna's actual rate limit** once this runs on the new 266-
   call/run, 12-hour schedule for real - if it starts failing/rate-limiting
   in practice, the per-country try/except already logs and skips
   gracefully, but the schedule or query count may need tightening further.
