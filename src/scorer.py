"""
Module 7: Resume Matching & Scoring.

Two-stage relevance: first a title-based role-relevance gate (is this job
actually one of the target role types, at an appropriate seniority level,
and not an unrelated industry?), then a weighted score used purely for
ranking among jobs that already passed the gate.

Why a title gate at all: Arbeitnow and Greenhouse return every open role at
a company/board, not just engineering ones (only Adzuna's search query is
keyword-restricted). Scoring on skill-keyword overlap alone isn't a reliable
relevance signal, because generic terms shared across many disciplines
(Git, Jira, Agile, AWS, Docker) match equally well against a DevOps/Data/ML/
QA/Sales-Engineer posting as they do against an actual MERN/full-stack
developer role. The title gate checks what the job actually *is* before
skill overlap is used to rank *how good a fit* it is.
"""
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from filters import is_remote_job, mentions_visa_or_relocation

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JOBS_INPUT_PATH = PROJECT_ROOT / "data" / "jobs_filtered.json"
RESUME_PATH = PROJECT_ROOT / "data" / "resume_profile.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "jobs_scored.json"
LOG_PATH = PROJECT_ROOT / "data" / "evaluation_log.jsonl"

# --- Stage 1: title-based role relevance gate -----------------------------

# Each group is a set of regex patterns (case-insensitive, matched against
# the title only) that all mean "this is the same kind of role" - this is
# the rule-based stand-in for semantic matching: "MERN Developer" and
# "React Developer" and "Full Stack Developer" all satisfy different groups
# below, so any of them passes, without needing an LLM/embedding call.
TARGET_ROLE_PATTERNS = {
    "software_engineer": [r"software\s+engineers?\b", r"\bswe\b"],
    "software_developer": [r"software\s+developers?\b"],
    "full_stack": [r"full[\s-]?stack"],
    "mern_mean_stack": [r"\bmern\b", r"\bmean\s+stack\b"],
    "web_developer": [r"\bweb\s+develop"],
    "junior_project_manager": [r"\b(junior|associate)\s+project\s+manager\b"],
}

# A separate (tech-word, role-word) AND-pair check for the tech-specific
# groups, rather than one regex requiring the two words to sit right next to
# each other. Found via manual review of 105 real live job titles: a plain
# adjacency regex (e.g. r"node(?:\.?js)?\s+develop") missed real, clearly
# relevant postings where a qualifier word sits in between - "Node.js
# **Trainee** Developer", "React **/ Angular** Developer" - both got
# wrongly rejected as "no target role match" before this fix.
TECH_ROLE_WORD_PAIRS = {
    "backend_developer": (r"back[\s-]?end", r"develop|engineer"),
    "frontend_developer": (r"front[\s-]?end", r"develop|engineer"),
    "react_developer": (r"react(?:\.?js)?", r"develop|engineer"),
    "nodejs_developer": (r"node(?:\.?js)?", r"develop|engineer"),
    "javascript_developer": (r"javascript|\bjs\b", r"develop|engineer"),
}

# Checked first, before the positive match above - a hard reject regardless
# of any skill/keyword overlap elsewhere in the description.
EXCLUDE_INDUSTRY_PATTERNS = [
    r"\bsales\b", r"\bmarketing\b", r"\brecruiter\b", r"\brecruiting\b",
    r"\bhuman\s+resources\b", r"\bhr\s+(?:manager|specialist|coordinator|business)",
    r"\bcustomer\s+(?:support|service|success)\b", r"\baccount\s+executive\b",
    r"\baccountant\b", r"\bfinancial?\s+analyst\b", r"\bnurse\b",
    r"\bteacher\b", r"\bcivil\s+engineer", r"\bmechanical\s+engineer",
    r"\belectrical\s+engineer", r"\bdata\s+entry\b", r"\bcall\s+center\b",
    r"\btruck\s+driver\b",
]

# Hard-excluded regardless of years of experience, per explicit requirement -
# these titles are excluded outright, not just deprioritized. "manager" is
# excluded unless it's a junior/associate project manager (matched above).
# "vice president" is listed alongside the bare "vp" abbreviation - found via
# manual review that a spelled-out "Vice President" title wasn't being
# caught by "\bvp\b" at all (didn't cause a wrong call in the reviewed
# sample only because those titles also failed the positive-role match, but
# a hypothetical "Vice President of Software Engineering" would have slipped
# through).
EXCLUDE_SENIORITY_PATTERNS = [
    r"\bsenior\b", r"\bsr\.?\b", r"\bstaff\b", r"\bprincipal\b", r"\blead\b",
    r"\bdirector\b", r"\bhead\s+of\b", r"\bvp\b", r"\bvice\s+president\b",
    r"\bchief\b", r"\barchitect\b", r"\bmanager\b",
]

# Positive experience-level signal (used for ranking, not gating - an
# unlabeled title like plain "Software Engineer" is common for genuinely
# junior-friendly roles and shouldn't be penalized for not saying "junior").
JUNIOR_LEVEL_PATTERNS = [
    r"\bjunior\b", r"\bjr\.?\b", r"\bgraduate\b", r"\bentry[\s-]?level\b",
    r"\bassociate\b", r"\bintern(?:ship)?\b", r"\b0-2\s*years?\b", r"\b1-2\s*years?\b",
    r"software\s+engineer\s+i\b",
]


def _normalize_text(text: str) -> str:
    """Strips accents/diacritics (e.g. "Sênior" -> "senior") so
    seniority/industry/role matching works regardless of language variant,
    without needing a per-language keyword list. Found via manual review: a
    real posting titled "...Developer Sênior..." (Portuguese) slipped past
    the English-only "senior" exclude pattern before this fix."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _matches_any(patterns: list, text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _matched_role_group(title_lower: str):
    for role_name, patterns in TARGET_ROLE_PATTERNS.items():
        if _matches_any(patterns, title_lower):
            return role_name
    for role_name, (tech_pattern, role_pattern) in TECH_ROLE_WORD_PAIRS.items():
        if re.search(tech_pattern, title_lower, re.IGNORECASE) and re.search(role_pattern, title_lower, re.IGNORECASE):
            return role_name
    return None


def evaluate_role_relevance(job: dict) -> dict:
    """The title-relevance gate. Returns a decision record used both for
    filtering and for the per-job audit log (accepted, reason, role_group,
    is_junior_labeled)."""
    title = job.get("title", "") or ""
    title_lower = _normalize_text(title.lower())

    for pattern in EXCLUDE_INDUSTRY_PATTERNS:
        if re.search(pattern, title_lower, re.IGNORECASE):
            return {"accepted": False, "reason": f"excluded industry (matched '{pattern}')",
                    "role_group": None, "is_junior_labeled": False}

    is_junior_pm = _matches_any(TARGET_ROLE_PATTERNS["junior_project_manager"], title_lower)
    if not is_junior_pm:
        for pattern in EXCLUDE_SENIORITY_PATTERNS:
            if re.search(pattern, title_lower, re.IGNORECASE):
                return {"accepted": False, "reason": f"excluded seniority (matched '{pattern}')",
                        "role_group": None, "is_junior_labeled": False}

    role_group = _matched_role_group(title_lower)
    if role_group is None:
        return {"accepted": False, "reason": "title does not match any target role",
                "role_group": None, "is_junior_labeled": False}

    # Junior Project Manager is only in-scope with an explicit
    # software/IT qualifier - "Junior Project Manager" alone is far too
    # broad an industry-agnostic title otherwise.
    if role_group == "junior_project_manager":
        description = (job.get("description", "") or "").lower()
        has_it_context = _matches_any([r"\bsoftware\b", r"\bit\b", r"\btechnology\b"],
                                       f"{title_lower} {description}")
        if not has_it_context:
            return {"accepted": False, "reason": "junior project manager without software/IT context",
                    "role_group": None, "is_junior_labeled": False}

    is_junior_labeled = _matches_any(JUNIOR_LEVEL_PATTERNS, title_lower)
    return {"accepted": True, "reason": f"matched role group '{role_group}'",
            "role_group": role_group, "is_junior_labeled": is_junior_labeled}


# --- Stage 2: weighted ranking score ---------------------------------------

def _whole_word_match(term: str, text: str) -> bool:
    """Whole-word/whole-token match: plain substring matching would wrongly
    match "Java" inside "JavaScript". A plain \\b regex boundary breaks on
    terms ending in punctuation (e.g. "C++"), since \\b requires one side to
    be a word character - here both sides ('+' and the following space) are
    non-word, so \\b never matches. Using explicit alphanumeric lookarounds
    instead treats any punctuation/space as a valid boundary either way.
    """
    pattern = r"(?<![a-zA-Z0-9])" + re.escape(term.lower()) + r"(?![a-zA-Z0-9])"
    return re.search(pattern, text) is not None


def matched_skills_for(job: dict, resume_skills: list) -> list:
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    return [skill for skill in resume_skills if _whole_word_match(skill, text)]


def _recency_bonus(date_posted: str, max_bonus: float = 3.0, max_age_days: int = 7) -> float:
    try:
        posted = datetime.fromisoformat((date_posted or "").replace("Z", "+00:00"))
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - posted).total_seconds() / 86400
        return round(max(0.0, max_bonus * (1 - age_days / max_age_days)), 2)
    except (ValueError, TypeError):
        return 0.0


# Role groups that are an exact specialty match for a MERN/full-stack
# candidate score higher than a more generic "software developer" match -
# this is the "title similarity" weighting from the scoring requirement.
ROLE_GROUP_WEIGHTS = {
    "mern_mean_stack": 15,
    "full_stack": 14,
    "react_developer": 13,
    "nodejs_developer": 13,
    "javascript_developer": 12,
    "backend_developer": 11,
    "frontend_developer": 11,
    "web_developer": 10,
    "software_engineer": 10,
    "software_developer": 10,
    "junior_project_manager": 8,
}
SKILL_MATCH_WEIGHT = 2
JUNIOR_LABEL_BONUS = 5
REMOTE_BONUS = 8
RELOCATION_BONUS = 5


def compute_weighted_score(job: dict, role_group: str, is_junior_labeled: bool,
                            matched_skill_count: int, is_remote: bool, relocation_offered: bool) -> float:
    """Weighted relevance score. NOTE on "company reputation" (one of the
    requested factors): there is no real data source for this wired into
    the pipeline (no Glassdoor/Crunchbase/etc. integration - see the
    analysis notes), so it's intentionally not included as a scoring factor
    here rather than faking a placeholder number. Documented as a known gap
    with a recommendation to add a real source later."""
    score = ROLE_GROUP_WEIGHTS.get(role_group, 8)
    score += SKILL_MATCH_WEIGHT * matched_skill_count
    if is_junior_labeled:
        score += JUNIOR_LABEL_BONUS
    if is_remote:
        score += REMOTE_BONUS
    elif relocation_offered:
        score += RELOCATION_BONUS
    score += _recency_bonus(job.get("date_posted", ""))
    return round(score, 2)


def evaluate_job(job: dict, resume_profile: dict) -> dict:
    """Full per-job evaluation record - the single source of truth for both
    filtering/ranking and the audit log (Requirement #9). Remote/relocation
    detection and matched skills are computed regardless of accept/reject,
    so the log is useful for debugging *why* a rejected job was rejected
    even if it happened to be remote/relocation-friendly too."""
    relevance = evaluate_role_relevance(job)
    resume_skills = resume_profile.get("skills", [])

    record = {
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "country": job.get("country", ""),
        "url": job.get("url", ""),
        "accepted": relevance["accepted"],
        "reason": relevance["reason"],
        "role_group": relevance["role_group"],
        "is_junior_labeled": relevance["is_junior_labeled"],
        "matched_skills": matched_skills_for(job, resume_skills),
        "is_remote": is_remote_job(job),
        "relocation_offered": mentions_visa_or_relocation(job.get("description", "")),
        "score": 0,
    }
    if relevance["accepted"]:
        record["score"] = compute_weighted_score(
            job, relevance["role_group"], relevance["is_junior_labeled"],
            len(record["matched_skills"]), record["is_remote"], record["relocation_offered"],
        )
    return record


def score_jobs(jobs: list, resume_profile: dict, log_path: Path = None) -> list:
    """Evaluates every job, writes the full per-job audit trail to a JSONL
    log (Requirement #9 - original title, matched keywords, score,
    experience level, remote/relocation detected, accept/reject + exact
    reason), and returns only the accepted jobs, ranked best-first."""
    log_path = log_path or LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    accepted = []
    with open(log_path, "w", encoding="utf-8") as log_file:
        for job in jobs:
            record = evaluate_job(job, resume_profile)
            log_file.write(json.dumps(record) + "\n")
            if record["accepted"]:
                tagged = dict(job)
                tagged["score"] = record["score"]
                tagged["matched_skills"] = record["matched_skills"]
                tagged["is_remote"] = record["is_remote"]
                tagged["relocation_offered"] = record["relocation_offered"]
                tagged["role_group"] = record["role_group"]
                tagged["is_junior_labeled"] = record["is_junior_labeled"]
                accepted.append(tagged)

    return sorted(accepted, key=lambda j: -j["score"])


def main():
    if not JOBS_INPUT_PATH.exists():
        raise SystemExit(f"{JOBS_INPUT_PATH} not found - run filters.py first")
    if not RESUME_PATH.exists():
        raise SystemExit(f"{RESUME_PATH} not found - run resume_parser.py first")

    with open(JOBS_INPUT_PATH, encoding="utf-8") as f:
        jobs = json.load(f)
    with open(RESUME_PATH, encoding="utf-8") as f:
        resume_profile = json.load(f)

    relevant_jobs = score_jobs(jobs, resume_profile)

    print(f"Evaluated {len(jobs)} jobs -> {len(relevant_jobs)} passed the role-relevance gate "
          f"({len(jobs) - len(relevant_jobs)} rejected; see {LOG_PATH} for per-job reasons).\n")
    print("--- TOP MATCHES ---")
    for job in relevant_jobs[:10]:
        remote_tag = "[REMOTE] " if job["is_remote"] else ""
        junior_tag = "[JUNIOR-LABELED] " if job["is_junior_labeled"] else ""
        print(f"[{job['score']:5.1f}] {remote_tag}{junior_tag}{job['title']} - {job['company']} "
              f"({job['country']}) | role: {job['role_group']} | matched: {', '.join(job['matched_skills']) or 'none'}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(relevant_jobs, f, indent=2)
    print(f"\nSaved {len(relevant_jobs)} scored jobs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
