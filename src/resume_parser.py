"""
Module 2: Resume Parser.

Reads a resume file (PDF or Word), extracts raw text, and structures it into
resume_profile.json (skills, job titles, years of experience, education).
Rule-based only (no LLM) — looks for known section headers and known patterns.
"""
import json
import os
import re
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "resume_profile.json"

# Section headers we recognize, matched case-insensitively against a whole
# (stripped) line. Order doesn't matter; the splitter finds whichever header
# appears next in the document.
SECTION_HEADERS = {
    "SUMMARY", "ABOUT ME",
    "EXPERIENCE", "WORK EXPERIENCE",
    "EDUCATION", "EDUCATION AND TRAINING",
    "SKILLS", "PROGRAMMING SKILLS", "LANGUAGE SKILLS",
    "PROJECTS",
    "CERTIFICATIONS",
    "VOLUNTEER EXPERIENCE",
    "FINAL YEAR PROJECT",
}

SKILL_SECTION_NAMES = {"SKILLS", "PROGRAMMING SKILLS"}
EXPERIENCE_SECTION_NAMES = {"EXPERIENCE", "WORK EXPERIENCE"}
EDUCATION_SECTION_NAMES = {"EDUCATION", "EDUCATION AND TRAINING"}

ROLE_KEYWORDS = [
    "Engineer", "Developer", "Intern", "Manager", "Analyst", "Lead",
    "Designer", "Architect", "Consultant", "Scientist", "Director",
]

DATE_PATTERN = re.compile(r"\b(\d{1,2}/)?(\d{1,2})/(\d{4})\b")
DATE_RANGE_PATTERN = re.compile(
    r"(\d{1,2}/(?:\d{1,2}/)?\d{4})\s*[–-]\s*(Present|Current|\d{1,2}/(?:\d{1,2}/)?\d{4})",
    re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_PATTERN = re.compile(r"(\(?\+?\d[\d ()-]{7,}\d)")


def extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    if suffix == ".docx":
        import docx
        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError(f"Unsupported resume file type: {suffix}")


def split_sections(text: str) -> dict:
    """Split raw text into {header: [lines]} using SECTION_HEADERS as markers.
    Lines before the first recognized header are kept under "HEADER" (contact info)."""
    sections = {"HEADER": []}
    current = "HEADER"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper() in SECTION_HEADERS:
            current = stripped.upper()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def extract_contact_info(text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    name = lines[0] if lines else ""

    email_match = EMAIL_PATTERN.search(text)
    email = email_match.group(0) if email_match else ""

    phone_match = PHONE_PATTERN.search(text)
    phone = phone_match.group(0).strip() if phone_match else ""

    location = ""
    address_match = re.search(r"Address:\s*(.+)", text)
    if address_match:
        location = address_match.group(1).strip()
    else:
        # simple-CV style header line: "email | phone | City, Region, Country | LinkedIn | Github"
        for line in lines[:5]:
            if "|" in line and email in line:
                parts = [p.strip() for p in line.split("|")]
                for part in parts:
                    if "," in part and "@" not in part and not PHONE_PATTERN.fullmatch(part):
                        location = part
                        break
    return {"name": name, "email": email, "phone": phone, "location": location}


def extract_skills(sections: dict) -> list:
    skills = []
    for header in SKILL_SECTION_NAMES:
        for line in sections.get(header, []):
            line = line.strip()
            # Bare subheader labels like "Languages" or "Projects" carry no
            # delimiter and aren't actual skill lists - skip them.
            if not line or not any(d in line for d in (",", "|", ":")):
                continue
            # "Category: item, item, item" -> keep only the part after the colon
            if ":" in line:
                line = line.split(":", 1)[1]
            # Split on both delimiters used across the two resume formats
            tokens = re.split(r"[,|]", line)
            for token in tokens:
                token = token.strip(" .:")
                if token and len(token) <= 40:
                    skills.append(token)
    # de-duplicate, case-insensitive, preserve first-seen casing
    seen = set()
    deduped = []
    for skill in skills:
        key = skill.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(skill)
    return deduped


def extract_job_titles_and_years(sections: dict) -> tuple:
    lines = []
    for header in EXPERIENCE_SECTION_NAMES:
        lines.extend(sections.get(header, []))

    titles = []
    earliest_year, earliest_month = None, None
    today = date.today()

    for line in lines:
        if not DATE_PATTERN.search(line):
            continue
        if not any(keyword.lower() in line.lower() for keyword in ROLE_KEYWORDS):
            continue

        # Isolate a title: split on common separators and keep the segment(s)
        # containing a role keyword, stripped of dates/locations.
        segment_candidates = re.split(r"[–\-|]", line)
        for segment in segment_candidates:
            segment = DATE_PATTERN.sub("", segment).strip(" ,.-")
            if segment and any(k.lower() in segment.lower() for k in ROLE_KEYWORDS):
                if segment not in titles:
                    titles.append(segment)

        for match in DATE_PATTERN.finditer(line):
            month, year = int(match.group(2)), int(match.group(3))
            if earliest_year is None or (year, month) < (earliest_year, earliest_month):
                earliest_year, earliest_month = year, month

    years_of_experience = 0.0
    if earliest_year is not None:
        months = (today.year - earliest_year) * 12 + (today.month - earliest_month)
        years_of_experience = round(max(months, 0) / 12, 1)

    return titles, years_of_experience


def extract_education(sections: dict) -> list:
    entries = []
    keywords = ["bachelor", "university", "college", "board of", "institute"]
    for header in EDUCATION_SECTION_NAMES:
        current_dates = ""
        for line in sections.get(header, []):
            stripped = line.strip()
            # Skip blank lines and descriptive lead-ins (e.g. "...studied are:")
            if not stripped or stripped.endswith(":"):
                continue

            has_keyword = any(k in stripped.lower() for k in keywords)
            if has_keyword:
                # Some formats put the date range on the same line as the
                # degree (simple CV); others put it on its own line above
                # (Europass). Handle both.
                range_match = DATE_RANGE_PATTERN.search(stripped)
                if range_match:
                    dates = range_match.group(0)
                    degree_line = DATE_RANGE_PATTERN.sub("", stripped).strip(" ,")
                else:
                    dates = current_dates
                    degree_line = stripped
                entries.append({"line": degree_line, "dates": dates})
            elif DATE_PATTERN.search(stripped) and len(stripped) < 60:
                current_dates = stripped
    return entries


def build_profile(file_path: Path) -> dict:
    text = extract_text(file_path)
    sections = split_sections(text)

    contact = extract_contact_info(text)
    skills = extract_skills(sections)
    job_titles, years_of_experience = extract_job_titles_and_years(sections)
    education = extract_education(sections)
    summary = " ".join(l.strip() for l in sections.get("SUMMARY", sections.get("ABOUT ME", [])) if l.strip())

    return {
        "source_file": str(file_path),
        "name": contact["name"],
        "email": contact["email"],
        "phone": contact["phone"],
        "location": contact["location"],
        "summary": summary,
        "skills": skills,
        "job_titles": job_titles,
        "years_of_experience": years_of_experience,
        "education": education,
    }


def _merge_skills(skill_lists: list) -> list:
    seen = set()
    merged = []
    for skills in skill_lists:
        for skill in skills:
            key = skill.lower()
            if key not in seen:
                seen.add(key)
                merged.append(skill)
    return merged


def _merge_job_titles(title_lists: list) -> list:
    seen = set()
    merged = []
    for titles in title_lists:
        for title in titles:
            key = title.lower()
            if key not in seen:
                seen.add(key)
                merged.append(title)
    return merged


def _merge_education(education_lists: list) -> list:
    seen = set()
    merged = []
    for entries in education_lists:
        for entry in entries:
            key = entry["line"].lower()
            if key not in seen:
                seen.add(key)
                merged.append(entry)
    return merged


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""


def build_combined_profile(file_paths: list) -> dict:
    """Merges multiple resume files (e.g. a Europass CV + a simpler CV) into
    one profile. Different resume formats often surface different skills
    (e.g. one lists frameworks/tools explicitly, another only languages) -
    merging gives the fullest possible picture for scoring."""
    profiles = [build_profile(path) for path in file_paths]

    longest_summary = max((p["summary"] for p in profiles), key=len, default="")
    longest_location = max((p["location"] for p in profiles), key=len, default="")

    return {
        "source_files": [str(p) for p in file_paths],
        "name": _first_non_empty(*(p["name"] for p in profiles)),
        "email": _first_non_empty(*(p["email"] for p in profiles)),
        "phone": _first_non_empty(*(p["phone"] for p in profiles)),
        "location": longest_location,
        "summary": longest_summary,
        "skills": _merge_skills(p["skills"] for p in profiles),
        "job_titles": _merge_job_titles(p["job_titles"] for p in profiles),
        "years_of_experience": max((p["years_of_experience"] for p in profiles), default=0.0),
        "education": _merge_education(p["education"] for p in profiles),
    }


def main():
    load_dotenv()
    resume_path_str = os.getenv("RESUME_FILE_PATH")
    if not resume_path_str:
        raise SystemExit("RESUME_FILE_PATH is not set in .env")

    # Supports one path, or multiple comma-separated paths to merge
    # (e.g. a Europass CV + a simpler CV, combining their skill lists).
    resume_paths = [PROJECT_ROOT / p.strip() for p in resume_path_str.split(",") if p.strip()]
    for path in resume_paths:
        if not path.exists():
            raise SystemExit(f"Resume file not found: {path}")

    for path in resume_paths:
        print(f"--- RAW TEXT ({path.name}, sanity check) ---")
        print(extract_text(path))
        print(f"--- END RAW TEXT ({path.name}) ---\n")

    if len(resume_paths) == 1:
        profile = build_profile(resume_paths[0])
    else:
        profile = build_combined_profile(resume_paths)

    print("--- STRUCTURED PROFILE ---")
    print(json.dumps(profile, indent=2))

    DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    print(f"\nSaved structured profile to {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
