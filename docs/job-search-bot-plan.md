# Global Job Finder Bot — Project Plan

## 1. Goal
Build a personal automation tool that:
- Scans job boards worldwide for new openings (posted in the last 24 hours to 1 week).
- Matches jobs against my resume/skills.
- Prioritizes roles in **Europe, USA, Australia, Canada, and New Zealand** that offer **visa sponsorship / relocation assistance**.
- Also includes **local Pakistan jobs** (no relocation needed since I'm already here).
- Sends me a ranked, filtered list (not just a dump of every job) so I can apply quickly to the best matches.
- Does **NOT** get my LinkedIn account banned. This is a hard requirement — no scraping or automating LinkedIn directly with my login.

## 2. Requirements

### 2.1 Functional
- Pull new job postings from multiple countries/regions.
- Filter by posting date (last 24h / last 7 days).
- Filter/flag jobs that mention relocation, visa sponsorship, work permit assistance.
- Parse my resume into structured data (skills, experience, job titles, years of experience).
- Score/rank each job against my resume.
- Deliver results as a daily or twice-daily digest (email, Telegram, or simple dashboard).
- Keep a history/database so I don't get the same job twice.

### 2.2 Non-Functional / Constraints
- **No LinkedIn scraping.** LinkedIn actively detects and bans scraper bots and automated logins — this account is my professional identity, so it's not worth the risk.
- **No Indeed scraping directly either** — same reasoning, Indeed also blocks bots and can flag/ban accounts or IPs.
- Instead, use **official APIs or licensed aggregators** that legally re-share LinkedIn/Indeed/other listings without needing my personal login.
- Should be low-cost or free to run (most of these APIs have generous free tiers for personal use).
- Should be simple enough to maintain solo (no huge infrastructure).

## 3. How This Will Work (Safe Approach)

Instead of "scraping LinkedIn," the plan is to pull the **same jobs** from sources that are either:
- Public APIs meant for this exact purpose, or
- Company career pages that expose open, public data feeds (fully legal, no ToS issue).

### 3.1 Data Sources
| Source | What it covers | Why it's safe |
|---|---|---|
| **Adzuna API** | UK, US, Europe, Australia, Canada, NZ jobs | Free tier, official API, built for this |
| **JSearch (via RapidAPI)** | Aggregates Indeed, LinkedIn, Glassdoor, ZipRecruiter | Licensed re-share, no scraping needed |
| **Arbeitnow API** | Europe-focused, many visa-sponsor tags | Free, public, remote-friendly |
| **RemoteOK / WeWorkRemotely** | Remote roles, many open to any country | Public feeds/RSS, allowed |
| **Greenhouse / Lever / Workday public job boards** | Direct company listings (e.g. `boards-api.greenhouse.io/v1/boards/{company}/jobs`) | Public JSON endpoints, no login needed |
| **USAJobs API** | US government roles, some sponsor relocation | Official US government API |
| **Rozee.pk / Indeed Pakistan (public listings)** | Local Pakistan jobs | Lower risk region-specific board, can check ToS or use official feed if available |

This gives near-total overlap with what you'd see manually on LinkedIn/Indeed, without ever touching those platforms' bot-detection systems.

### 3.2 Pipeline Steps
1. **Resume Parser**
   - Extract skills, job titles, years of experience, education into structured JSON (done once, or whenever resume updates).
2. **Job Collector**
   - Scheduled script (e.g. runs every few hours) queries each API above.
   - Filters: posted date (24h–7 days), target countries, keyword match on relocation/visa terms.
3. **Relocation/Visa Filter**
   - Text-search job descriptions for phrases like "visa sponsorship," "relocation assistance," "work permit provided," "sponsorship available."
   - Pakistan jobs skip this filter entirely (no relocation needed).
4. **Matching & Scoring**
   - Compare job description to resume data (keyword overlap or embedding similarity) to produce a relevance score.
5. **Digest & Delivery**
   - Store results in a simple database (avoids duplicate alerts).
   - Send a ranked daily/twice-daily summary via email or Telegram bot.
6. **Application Step (semi-automated, not full auto)**
   - Because every company uses a different application system (Workday, Greenhouse, Lever, etc.), full auto-submission is unreliable and can look spammy to employers.
   - Better: bot pre-fills your details in a browser (via Playwright) for review, and you click "Submit" yourself — keeps quality high and avoids looking like bot-spam applications.

## 4. What I Will NOT Do
- Log into LinkedIn/Indeed with automation scripts or browser bots.
- Mass auto-apply without human review (hurts response rate + looks bot-generated).
- Scrape at high frequency/volume that could trip rate limits or ToS violations on any platform.

## 5. Next Steps (Build Order)
1. Build resume parser (turn resume → structured JSON).
2. Build job collector script hitting Adzuna + JSearch + Arbeitnow (start with 2–3 sources).
3. Add date + relocation/visa filtering.
4. Add scoring against resume.
5. Add delivery (start simple: email digest).
6. Later: add browser-assisted semi-auto application filling.
