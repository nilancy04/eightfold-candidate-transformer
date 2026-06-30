"""Extract candidate data from resume PDFs using pdfplumber and regex."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Optional

import pdfplumber

from common import append_provenance, apply_candidate_normalization
from extractors.base import BaseExtractor
from models import (
    Candidate,
    EducationEntry,
    ExperienceEntry,
    ExtractedCandidate,
    ProvenanceEntry,
    SkillEntry,
)
from normalizers.date_normalizer import normalize_date
from normalizers.phone_normalizer import normalize_phones
from normalizers.skill_normalizer import normalize_skills

logger = logging.getLogger(__name__)

RESUME_METHOD = "regex extraction"
SUPPORTED_RESUME_SUFFIXES = {".pdf"}

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)

PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4,6}\b"
)

NAME_PATTERN = re.compile(
    r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*$",
    re.MULTILINE,
)

SKILL_KEYWORDS = [
    "python",
    "java",
    "javascript",
    "react",
    "reactjs",
    "react.js",
    "node.js",
    "nodejs",
    "c++",
    "cpp",
    "sql",
    "aws",
    "docker",
    "kubernetes",
    "ml",
    "ai",
    "machine learning",
    "artificial intelligence",
    "typescript",
    "go",
    "rust",
    "html",
    "css",
]

# --- Section headings (normalized comparison) ---
EXPERIENCE_SECTION_STARTS = frozenset(
    {
        "EXPERIENCE",
        "WORK EXPERIENCE",
        "PROFESSIONAL EXPERIENCE",
        "EMPLOYMENT",
        "INTERNSHIPS",
        "INTERNSHIP",
    }
)

EXPERIENCE_SECTION_STOPS = frozenset(
    {
        "PROJECTS",
        "PROJECT",
        "CERTIFICATIONS",
        "CERTIFICATION",
        "ACHIEVEMENTS",
        "ACHIEVEMENT",
        "AWARDS",
        "AWARD",
        "PUBLICATIONS",
        "PUBLICATION",
        "SKILLS",
        "EDUCATION",
        "TECHNICAL SKILLS",
        "TECH STACK",
        "RESEARCH",
        "RESEARCH EXPERIENCE",
        "RESEARCH PAPER",
        "POSITIONS OF RESPONSIBILITY",
        "EXTRACURRICULAR",
        "EXTRACURRICULARS",
        "HACKATHONS",
        "HACKATHON",
        "LANGUAGES",
        "INTERESTS",
        "SUMMARY",
        "OBJECTIVE",
        "REFERENCES",
    }
)

EDUCATION_SECTION_STARTS = frozenset(
    {
        "EDUCATION",
        "ACADEMICS",
        "ACADEMIC BACKGROUND",
    }
)

EDUCATION_SECTION_STOPS = frozenset(
    {
        "EXPERIENCE",
        "WORK EXPERIENCE",
        "PROFESSIONAL EXPERIENCE",
        "EMPLOYMENT",
        "INTERNSHIPS",
        "INTERNSHIP",
        "PROJECTS",
        "SKILLS",
        "TECHNICAL SKILLS",
        "TECH STACK",
        "CERTIFICATIONS",
        "ACHIEVEMENTS",
        "AWARDS",
        "PUBLICATIONS",
        "RESEARCH",
        "LANGUAGES",
        "INTERESTS",
        "EXTRACURRICULAR",
        "EXTRACURRICULARS",
        "POSITIONS OF RESPONSIBILITY",
    }
)

EXPERIENCE_REJECT_KEYWORDS = frozenset(
    {
        "PROJECT",
        "PROJECTS",
        "CERTIFICATE",
        "CERTIFICATION",
        "HACKATHON",
        "AWARD",
        "ACHIEVEMENT",
        "PUBLICATION",
        "RESEARCH PAPER",
        "TECH STACK",
        "SKILLS",
        "LANGUAGES",
        "TOOLS",
    }
)

BAD_DEGREES = frozenset({"me", "by", "m", "tech stack", "project", "projects", "skills"})

GENERIC_SECTION_HEADINGS = frozenset(
    {
        "education",
        "academics",
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "internships",
        "projects",
        "project",
        "skills",
        "technical skills",
        "tech stack",
        "certifications",
        "certification",
        "achievements",
        "achievement",
        "awards",
        "award",
        "publications",
        "publication",
        "research",
        "languages",
        "interests",
        "extracurricular",
        "extracurriculars",
        "positions of responsibility",
        "summary",
        "objective",
        "profile",
        "references",
        "contact",
        "personal",
        "hackathon",
        "hackathons",
    }
)

BAD_INSTITUTION_KEYWORDS = frozenset(
    {
        "tech stack",
        "projects",
        "project",
        "skills",
        "stock visualization",
        "award",
        "hackathon",
        "certification",
        "achievement",
        "languages",
        "tools",
    }
)

# Conservative experience line patterns (single-line, no multiline greed).
EXPERIENCE_DASH_DATE_PATTERN = re.compile(
    r"^(.{2,70}?)\s*[–—\-]\s*(.{2,70}?)\s+(\d{1,2}/\d{4})\s*[–—\-]\s*(\d{1,2}/\d{4})\s*$",
    re.IGNORECASE,
)

EXPERIENCE_PIPE_PATTERN = re.compile(
    r"^(.{2,60}?)\s*[|\-–—]\s*(.{2,60}?)"
    r"(?:\s*\((\d{4}(?:-\d{2})?(?:\s*[-–—]\s*(?:\d{4}(?:-\d{2})?|Present|Current))?)\))?\s*$",
    re.IGNORECASE,
)

_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)

DATE_RANGE_LINE = re.compile(
    rf"^(?:{_MONTH}\.?\s+\d{{4}}|\d{{1,2}}/\d{{4}})\s*[–—\-]\s*"
    rf"(?:{_MONTH}\.?\s+\d{{4}}|\d{{1,2}}/\d{{4}}|Present|Current)\s*$",
    re.IGNORECASE,
)

DEGREE_PATTERN = re.compile(
    r"^(B\.?\s?Tech|M\.?\s?Tech|B\.?\s?E\.?|M\.?\s?E\.?|Bachelor|Master|Ph\.?D|"
    r"MBA|BSc|MSc|BCA|MCA|B\.?\s?Com|M\.?\s?Com|B\.?\s?Sc|M\.?\s?Sc)",
    re.IGNORECASE,
)

DEGREE_LINE_PATTERN = re.compile(
    r"^(B\.?\s?Tech|M\.?\s?Tech|B\.?\s?E\.?|M\.?\s?E\.?|Bachelor|Master|Ph\.?D|"
    r"MBA|BSc|MSc|BCA|MCA|B\.?\s?Com|M\.?\s?Com|B\.?\s?Sc|M\.?\s?Sc)"
    r"[^,|]*",
    re.IGNORECASE,
)

EXPERIENCE_COMMA_MMYYYY_PATTERN = re.compile(
    r"^(.+?),\s*(.+?)\s+(\d{1,2}/\d{4})\s*[–—\-]\s*(\d{1,2}/\d{4})\s*\|\s*.+$",
    re.IGNORECASE,
)

EXPERIENCE_COMMA_YEAR_PATTERN = re.compile(
    r"^(.+?),\s*(.+?)\s+(\d{4})\s*[–—\-]\s*(\d{4})\s*\|\s*.+$",
    re.IGNORECASE,
)

DATE_ONLY_COMPANY_PATTERN = re.compile(
    r"^[\d\s|,\-–—/\.]+$",
    re.IGNORECASE,
)

LOCATION_PIPE_PATTERN = re.compile(
    r"^\d{4}\s*\|\s*.+$",
    re.IGNORECASE,
)

TITLE_DATE_SUFFIX = re.compile(
    r"\s+\d{1,2}/\d{4}\s*[–—\-]\s*\d{1,2}/\d{4}(\s*\|\s*.+)?$",
    re.IGNORECASE,
)

TITLE_YEAR_SUFFIX = re.compile(
    r"\s+\d{4}\s*[–—\-]\s*\d{4}(\s*\|\s*.+)?$",
    re.IGNORECASE,
)

TITLE_LOCATION_SUFFIX = re.compile(r"\s*\|\s*.+$")

YEAR_LOCATION_SUFFIX = re.compile(
    r"\s+\d{4}(?:\s*[–—\-]\s*\d{4})?(?:\s*[|\-–—]\s*[^|]+)?\s*$",
    re.IGNORECASE,
)

SCHOOL_INSTITUTION_PATTERN = re.compile(
    r"^(.+?\b(?:University|Institute|College|School|Academy|Polytechnic|Vidyalaya)\b[^|]*)",
    re.IGNORECASE,
)

LOCATION_DATE_SUFFIX = re.compile(
    r"\s+\d{4}\s*[–—\-]\s*\d{4}(?:\s*[|\-–—]\s*[^|]+)?\s*$",
    re.IGNORECASE,
)

CGPA_SUFFIX = re.compile(r"\s*,?\s*CGPA\s*:.*$", re.IGNORECASE)

INSTITUTION_HINT = re.compile(
    r"\b(University|Institute|College|School|Academy|Polytechnic)\b",
    re.IGNORECASE,
)

DATE_SUFFIX_PATTERNS = [
    re.compile(r"\s+\d{1,2}/\d{4}\s*[–—\-]\s*\d{1,2}/\d{4}\s*$"),
    re.compile(r"\s+\d{1,2}/\d{4}\s*$"),
    re.compile(r"\s+\d{4}\s*[-–—]\s*\d{4}\s*$"),
    re.compile(r"\s+\d{4}\s*$"),
    re.compile(r"\s+\d{2}\s*$"),
]

PAGE_NUMBER_SUFFIX = re.compile(
    r"\s*(?:\|\s*)(?:page\s*)?\d{1,2}\s*(?:/\s*\d{1,2})?\s*$",
    re.IGNORECASE,
)

PAGE_WORD_SUFFIX = re.compile(
    r"\s*page\s+\d+\s*(?:/\s*\d+)?\s*$",
    re.IGNORECASE,
)

BULLET_PREFIX = re.compile(r"^[\u2022\-\*•]\s*")

JOB_TITLE_HINT = re.compile(
    r"\b(intern|engineer|developer|analyst|manager|consultant|architect|designer|"
    r"specialist|associate|director|lead|scientist|administrator|coordinator|"
    r"executive|officer|technician|trainee|researcher|professor|teacher)\b",
    re.IGNORECASE,
)


def _clean_text(value: str) -> str:
    """Collapse whitespace and trim extracted text."""
    return " ".join(value.split()).strip()


def _dedupe_consecutive_words(text: str) -> str:
    """Remove immediately repeated words from extracted text."""
    words = text.split()
    if not words:
        return text
    result = [words[0]]
    for word in words[1:]:
        if word.lower() != result[-1].lower():
            result.append(word)
    return " ".join(result)


def _strip_page_numbers(text: str) -> str:
    """Remove trailing page-number artifacts without stripping date ranges."""
    cleaned = PAGE_WORD_SUFFIX.sub("", text).strip()
    cleaned = PAGE_NUMBER_SUFFIX.sub("", cleaned).strip()
    if re.fullmatch(r"(?:page\s*)?\d{1,2}(?:\s*/\s*\d{1,2})?", cleaned, flags=re.IGNORECASE):
        return ""
    return cleaned


def _normalize_abbrev_hyphens(text: str) -> str:
    """Convert abbreviation hyphens to slashes (e.g. AI-ML -> AI/ML)."""
    return re.sub(
        r"\b([A-Za-z]{1,5})-([A-Za-z]{1,5})\b",
        lambda match: (
            f"{match.group(1)}/{match.group(2)}"
            if match.group(1).isupper() or match.group(2).isupper()
            else match.group(0)
        ),
        text,
    )


def _strip_company_from_title(title: str, company: str) -> str:
    """Remove embedded company fragments from a job title."""
    if not title or not company:
        return title

    cleaned = _clean_text(title)
    company_clean = re.escape(_clean_text(company))
    for pattern in (
        rf",\s*{company_clean}\s*$",
        rf"\s+at\s+{company_clean}\s*$",
        rf"\s+@\s+{company_clean}\s*$",
    ):
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    if "," in cleaned:
        left, right = cleaned.rsplit(",", 1)
        right_clean = _clean_text(right)
        if _normalize_match_key(right_clean) == _normalize_match_key(company):
            cleaned = left.strip()

    return cleaned


def _normalize_match_key(value: str) -> str:
    """Normalize text for comparison during deduplication."""
    cleaned = _clean_text(value).lower()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return " ".join(cleaned.split())


def _looks_like_section_heading(text: str) -> bool:
    """Return True when text is a generic resume section heading, not content."""
    normalized = _normalize_section_heading(text).lower()
    return normalized in GENERIC_SECTION_HEADINGS


def _normalize_section_heading(line: str) -> str:
    """Normalize a line for section heading comparison."""
    cleaned = re.sub(r"[^\w\s]", " ", line.upper())
    return " ".join(cleaned.split())


def _matches_heading(line: str, headings: frozenset[str]) -> bool:
    """
    Return True if line is a section heading (not inline content like 'Tech Stack: React').

    Headings must match exactly or be a short extension (e.g. 'RESEARCH EXPERIENCE').
    """
    normalized = _normalize_section_heading(line)
    for heading in sorted(headings, key=len, reverse=True):
        if normalized == heading:
            return True
        if normalized.startswith(f"{heading} "):
            remainder = normalized[len(heading) :].strip()
            # Allow at most two extra words (e.g. 'RESEARCH EXPERIENCE', 'TECHNICAL SKILLS').
            if remainder and len(remainder.split()) <= 2:
                return True
    return False


def _extract_section_content(
    text: str,
    start_headings: frozenset[str],
    stop_headings: frozenset[str],
) -> Optional[str]:
    """
    Extract body text for a resume section bounded by known headings.

    Returns None if the start heading is not found.
    """
    lines = text.splitlines()
    in_section = False
    content_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_section:
                content_lines.append("")
            continue

        if not in_section:
            if _matches_heading(stripped, start_headings):
                in_section = True
            continue

        if _matches_heading(stripped, stop_headings):
            break

        content_lines.append(stripped)

    body = "\n".join(content_lines).strip()
    return body if body else None


def _clean_company_name(company: str) -> str:
    """Remove dates, locations, and pipe fragments from company names."""
    cleaned = _strip_page_numbers(_dedupe_consecutive_words(_clean_text(company)))
    cleaned = BULLET_PREFIX.sub("", cleaned).strip()
    cleaned = TITLE_LOCATION_SUFFIX.sub("", cleaned).strip()
    for pattern in DATE_SUFFIX_PATTERNS:
        cleaned = pattern.sub("", cleaned).strip()
    cleaned = TITLE_DATE_SUFFIX.sub("", cleaned).strip()
    cleaned = TITLE_YEAR_SUFFIX.sub("", cleaned).strip()
    cleaned = re.sub(r"\s*,\s*$", "", cleaned).strip()
    cleaned = _normalize_abbrev_hyphens(cleaned)
    return cleaned


def _clean_title(title: str, company: str | None = None) -> str:
    """Remove dates, locations, and trailing company fragments from titles."""
    cleaned = _strip_page_numbers(_dedupe_consecutive_words(_clean_text(title)))
    cleaned = BULLET_PREFIX.sub("", cleaned).strip()
    cleaned = TITLE_LOCATION_SUFFIX.sub("", cleaned).strip()
    cleaned = TITLE_DATE_SUFFIX.sub("", cleaned).strip()
    cleaned = TITLE_YEAR_SUFFIX.sub("", cleaned).strip()
    for pattern in DATE_SUFFIX_PATTERNS:
        cleaned = pattern.sub("", cleaned).strip()
    if company:
        cleaned = _strip_company_from_title(cleaned, company)
    return cleaned


def _is_valid_company(company: str) -> bool:
    """Return False when company looks like a date, location, or garbage."""
    cleaned = _clean_company_name(company)
    if not cleaned or _looks_like_section_heading(cleaned):
        return False
    if LOCATION_PIPE_PATTERN.match(cleaned):
        return False
    if DATE_ONLY_COMPANY_PATTERN.match(cleaned):
        return False
    if _alpha_count(cleaned) < 2:
        return False
    return True


def _is_valid_title(title: str) -> bool:
    """Return False when title looks like a date, location, heading, or company line."""
    cleaned = _clean_title(title)
    if not cleaned or _looks_like_section_heading(cleaned):
        return False
    if DATE_ONLY_COMPANY_PATTERN.match(cleaned):
        return False
    if LOCATION_PIPE_PATTERN.match(cleaned):
        return False
    if _alpha_count(cleaned) < 2:
        return False
    return True


def _is_plausible_experience(title: str, company: str) -> bool:
    """Reject entries that do not resemble realistic employment records."""
    if not _is_valid_company(company) or not _is_valid_title(title):
        return False
    if _normalize_match_key(title) == _normalize_match_key(company):
        return False
    combined = f"{title} {company}"
    if not JOB_TITLE_HINT.search(combined) and not DATE_RANGE_LINE.search(combined):
        # Allow when dates are present elsewhere; otherwise require a role-like token.
        if _alpha_count(title) < 4:
            return False
    return True


def _is_experience_content_line(line: str) -> bool:
    """Return False for bullet points, descriptions, and section headings."""
    stripped = BULLET_PREFIX.sub("", line.strip())
    if not stripped or stripped.startswith(("•", "-", "*")):
        return False
    if _looks_like_section_heading(stripped):
        return False
    lower = stripped.lower()
    if lower.startswith(
        (
            "developed ",
            "built ",
            "optimized ",
            "contributed ",
            "analyzed ",
            "collaborated ",
            "designed ",
            "implemented ",
            "tech stack",
            "responsible for ",
            "worked on ",
        )
    ):
        return False
    return True


def _alpha_count(value: str) -> int:
    return sum(1 for char in value if char.isalpha())


def _is_rejected_experience(title: str, company: str) -> bool:
    """Reject experience entries that look like projects, awards, etc."""
    combined = f"{title} {company}".upper()
    return any(keyword in combined for keyword in EXPERIENCE_REJECT_KEYWORDS)


def _is_valid_education(degree: Optional[str], institution: Optional[str]) -> bool:
    """Reject education entries that look like garbage extractions."""
    degree_clean = _clean_text(degree or "").lower()
    institution_clean = _clean_text(institution or "")

    if degree_clean in BAD_DEGREES:
        return False

    if institution_clean and _looks_like_section_heading(institution_clean):
        return False
    if degree_clean and _looks_like_section_heading(degree_clean):
        return False

    if institution_clean and _alpha_count(institution_clean) < 3:
        return False

    institution_lower = institution_clean.lower()
    if any(keyword in institution_lower for keyword in BAD_INSTITUTION_KEYWORDS):
        return False

    if degree_clean and any(keyword in degree_clean for keyword in BAD_INSTITUTION_KEYWORDS):
        return False

    if degree_clean and len(degree_clean.split()) == 1 and degree_clean in {"in", "at", "of", "by"}:
        return False

    has_degree = bool(degree_clean and DEGREE_PATTERN.match(degree_clean))
    has_institution = bool(
        institution_clean
        and (_alpha_count(institution_clean) >= 3 or INSTITUTION_HINT.search(institution_clean))
    )
    return has_degree or has_institution


def _parse_date_range_line(line: str) -> tuple[Optional[str], Optional[str]]:
    """Parse a standalone date-range line into start/end dates."""
    if not DATE_RANGE_LINE.match(line):
        return None, None

    parts = re.split(r"\s*[–—\-]\s*", line.strip(), maxsplit=1)
    start_date = normalize_date(parts[0].strip()) if parts else None
    end_date = None
    if len(parts) > 1:
        end_raw = parts[1].strip()
        if end_raw.lower() not in {"present", "current"}:
            end_date = normalize_date(end_raw)
    return start_date, end_date


def _parse_comma_experience_line(line: str) -> Optional[ExperienceEntry]:
    """
    Parse: Title, Company MM/YYYY – MM/YYYY | Location
    Example: AI/ML Intern, Google AI-ML Program 10/2024 – 12/2024 | Remote
    """
    match = EXPERIENCE_COMMA_MMYYYY_PATTERN.match(line)
    if match:
        company = _clean_company_name(match.group(2))
        title = _clean_title(match.group(1), company)
        if not _is_plausible_experience(title, company):
            return None
        return ExperienceEntry(
            title=title,
            company=company,
            start_date=normalize_date(match.group(3)),
            end_date=normalize_date(match.group(4)),
        )

    match = EXPERIENCE_COMMA_YEAR_PATTERN.match(line)
    if match:
        company = _clean_company_name(match.group(2))
        title = _clean_title(match.group(1), company)
        if not _is_plausible_experience(title, company):
            return None
        return ExperienceEntry(
            title=title,
            company=company,
            start_date=normalize_date(match.group(3)),
            end_date=normalize_date(match.group(4)),
        )

    return None


def _parse_experience_line(line: str) -> Optional[ExperienceEntry]:
    """Parse a single conservative experience line."""
    line = _clean_text(line)
    if not line or len(line) > 150 or not _is_experience_content_line(line):
        return None

    entry = _parse_comma_experience_line(line)
    if entry:
        return entry

    match = EXPERIENCE_DASH_DATE_PATTERN.match(line)
    if match:
        company = _clean_company_name(match.group(2))
        title = _clean_title(match.group(1), company)
        if not _is_plausible_experience(title, company):
            return None
        return ExperienceEntry(
            title=title,
            company=company,
            start_date=normalize_date(match.group(3)),
            end_date=normalize_date(match.group(4)),
        )

    # Pipe pattern only when line has no comma (avoid Title, Co | Location mis-parse).
    if "," not in line:
        match = EXPERIENCE_PIPE_PATTERN.match(line)
        if match:
            company = _clean_company_name(match.group(2))
            title = _clean_title(match.group(1), company)
            if not _is_plausible_experience(title, company):
                return None
            date_range = match.group(3)
            start_date: Optional[str] = None
            end_date: Optional[str] = None
            if date_range:
                dates = re.split(r"\s*[-–—]\s*", date_range)
                if dates:
                    start_date = normalize_date(dates[0].strip())
                if len(dates) > 1:
                    end_raw = dates[1].strip()
                    if end_raw.lower() not in {"present", "current"}:
                        end_date = normalize_date(end_raw)
            return ExperienceEntry(
                title=title, company=company, start_date=start_date, end_date=end_date
            )

    return None


def _parse_experience_blocks(section: str) -> list[ExperienceEntry]:
    """
    Parse multi-line experience blocks: company, title, date range.

    Example:
        Sikar Infotech
        Full Stack Developer Intern
        May 2025 – July 2025
    """
    entries: list[ExperienceEntry] = []
    blocks = re.split(r"\n\s*\n", section)

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        if len(lines) == 1:
            entry = _parse_experience_line(lines[0])
            if entry:
                entries.append(entry)
            continue

        # Three-line block: company, title, date range.
        if len(lines) >= 3 and DATE_RANGE_LINE.match(lines[-1]):
            company = _clean_company_name(lines[0])
            title = _clean_title(lines[1], company)
            if not _is_plausible_experience(title, company):
                continue
            start_date, end_date = _parse_date_range_line(lines[-1])
            entries.append(
                ExperienceEntry(
                    title=title,
                    company=company,
                    start_date=start_date,
                    end_date=end_date,
                )
            )
            continue

        # Fallback: parse each plausible experience line individually.
        for line in lines:
            if not _is_experience_content_line(line):
                continue
            entry = _parse_experience_line(line)
            if entry:
                entries.append(entry)

    return entries


def _merge_experience_entries(
    existing: ExperienceEntry, new: ExperienceEntry
) -> ExperienceEntry:
    """Merge two experience entries with the same company and title."""
    existing_desc = existing.description or ""
    new_desc = new.description or ""
    description = new_desc if len(new_desc) > len(existing_desc) else existing_desc
    if description:
        description = description or None

    return ExperienceEntry(
        company=existing.company or new.company,
        title=existing.title or new.title,
        start_date=existing.start_date or new.start_date,
        end_date=existing.end_date or new.end_date,
        description=description or None,
    )


def _merge_duplicate_experience(entries: list[ExperienceEntry]) -> list[ExperienceEntry]:
    """Merge entries with the same company and title; preserve dates and longest description."""
    merged: dict[tuple[str, str], ExperienceEntry] = {}

    for entry in entries:
        if not _is_plausible_experience(entry.title or "", entry.company or ""):
            continue
        company_key = _normalize_match_key(entry.company or "")
        title_key = _normalize_match_key(entry.title or "")
        if not company_key or not title_key:
            continue
        key = (company_key, title_key)

        if key not in merged:
            merged[key] = entry
        else:
            merged[key] = _merge_experience_entries(merged[key], entry)

    return list(merged.values())


def _looks_like_standalone_experience(text: str) -> bool:
    """True for short snippet text used in unit tests or single-line entries."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or len(lines) > 5:
        return False
    return any(_parse_experience_line(line) for line in lines)


def _extract_experience(text: str) -> list[ExperienceEntry]:
    """Extract experience only from the experience section with filtering."""
    section = _extract_section_content(
        text,
        EXPERIENCE_SECTION_STARTS,
        EXPERIENCE_SECTION_STOPS,
    )

    if section is None:
        if _looks_like_standalone_experience(text):
            section = text
        else:
            return []

    raw_entries = _parse_experience_blocks(section)
    filtered = [
        entry
        for entry in raw_entries
        if not _is_rejected_experience(entry.title or "", entry.company or "")
    ]
    return _merge_duplicate_experience(filtered)


def _parse_education_line(line: str) -> Optional[EducationEntry]:
    """Parse a single education line conservatively."""
    line = _clean_text(line)
    if not line or len(line) > 150:
        return None

    if line.upper().startswith("CGPA"):
        return None

    # Institution line with optional dates/location suffix.
    institution_match = SCHOOL_INSTITUTION_PATTERN.match(line)
    if institution_match:
        institution = _clean_text(institution_match.group(1))
        institution = YEAR_LOCATION_SUFFIX.sub("", institution).strip()
        institution = LOCATION_DATE_SUFFIX.sub("", institution).strip()
        institution = institution.split("|")[0].strip()
        if _is_valid_education(None, institution):
            return EducationEntry(degree=None, institution=institution)
        return None

    degree_match = DEGREE_LINE_PATTERN.match(line)
    if degree_match:
        degree = _clean_text(degree_match.group(0))
        degree = CGPA_SUFFIX.sub("", degree).strip()
        if _is_valid_education(degree, None):
            return EducationEntry(degree=degree, institution=None)
        return None

    return None


def _parse_education_blocks(section: str) -> list[EducationEntry]:
    """
    Parse education blocks: institution line + degree line.

    Example:
        SRM Institute of Science and Technology
        B.Tech Computer Science
    """
    entries: list[EducationEntry] = []
    lines = [line.strip() for line in section.splitlines() if line.strip()]

    index = 0
    while index < len(lines):
        line = lines[index]

        if line.upper().startswith("CGPA"):
            index += 1
            continue

        # Two-line block: institution then degree (most common).
        if index + 1 < len(lines):
            first, second = lines[index], lines[index + 1]
            inst_entry = _parse_education_line(first)
            deg_entry = _parse_education_line(second)

            if (
                inst_entry
                and inst_entry.institution
                and deg_entry
                and deg_entry.degree
            ):
                if _is_valid_education(deg_entry.degree, inst_entry.institution):
                    entries.append(
                        EducationEntry(
                            degree=deg_entry.degree,
                            institution=inst_entry.institution,
                        )
                    )
                    index += 2
                    continue

        parsed = _parse_education_line(line)
        if parsed and (parsed.degree or parsed.institution):
            entries.append(parsed)

        index += 1

    return entries


def _normalize_institution_key(institution: str) -> str:
    """Normalize institution name for deduplication."""
    key = YEAR_LOCATION_SUFFIX.sub("", institution).strip()
    return _normalize_match_key(key)


def _pick_better_degree(left: str | None, right: str | None) -> str | None:
    """Prefer formal degrees over placeholder values."""
    if not left:
        return right
    if not right:
        return left

    placeholders = {"student", "graduate", "undergraduate", "pursuing", "n/a", "na", "none"}
    left_lower = left.lower()
    right_lower = right.lower()

    if left_lower in placeholders and right_lower not in placeholders:
        return right
    if right_lower in placeholders and left_lower not in placeholders:
        return left
    return right if len(right) > len(left) else left


def _merge_education_entries(
    existing: EducationEntry, new: EducationEntry
) -> EducationEntry:
    """Merge two education entries for the same institution."""
    return EducationEntry(
        institution=existing.institution or new.institution,
        degree=_pick_better_degree(existing.degree, new.degree),
        start_date=existing.start_date or new.start_date,
        end_date=existing.end_date or new.end_date,
    )


def _merge_duplicate_education(entries: list[EducationEntry]) -> list[EducationEntry]:
    """Remove duplicate education entries; merge by institution then institution+degree."""
    valid = [entry for entry in entries if _is_valid_education(entry.degree, entry.institution)]
    by_institution: dict[str, EducationEntry] = {}

    for entry in valid:
        institution_key = _normalize_institution_key(entry.institution or "")
        if not institution_key:
            continue
        if institution_key not in by_institution:
            by_institution[institution_key] = entry
        else:
            by_institution[institution_key] = _merge_education_entries(
                by_institution[institution_key], entry
            )

    final: dict[tuple[str, str], EducationEntry] = {}
    for entry in by_institution.values():
        inst_key = _normalize_institution_key(entry.institution or "")
        deg_key = _normalize_match_key(entry.degree or "")
        dedupe_key = (inst_key, deg_key)
        if dedupe_key in final:
            final[dedupe_key] = _merge_education_entries(final[dedupe_key], entry)
        else:
            final[dedupe_key] = entry

    return list(final.values())


def _extract_education(text: str) -> list[EducationEntry]:
    """Extract education only from the education section with filtering."""
    section = _extract_section_content(
        text,
        EDUCATION_SECTION_STARTS,
        EDUCATION_SECTION_STOPS,
    )

    if section is None:
        return []

    raw_entries = _parse_education_blocks(section)
    valid = [
        entry
        for entry in raw_entries
        if _is_valid_education(entry.degree, entry.institution)
    ]
    return _merge_duplicate_education(valid)


def _extract_text_from_pdf(pdf_path: Path) -> Optional[str]:
    """Extract all text from a PDF, returning None on failure."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                logger.warning("PDF has no pages: %s", pdf_path)
                return None

            page_texts = [page.extract_text() or "" for page in pdf.pages]
            combined_text = "\n".join(page_texts).strip()

            if not combined_text:
                logger.warning("PDF contains no extractable text: %s", pdf_path)
                return None

            return combined_text
    except Exception as exc:
        logger.warning("Failed to read PDF %s: %s", pdf_path, exc)
        return None


def _extract_emails(text: str) -> list[str]:
    return list(dict.fromkeys(EMAIL_PATTERN.findall(text)))


def _extract_phones(text: str) -> list[str]:
    return normalize_phones(PHONE_PATTERN.findall(text))


def _extract_name(text: str, filename: str) -> Optional[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:8]:
        match = NAME_PATTERN.match(line)
        if match:
            return _clean_text(match.group(1))

    if lines and len(lines[0].split()) <= 4:
        return _clean_text(lines[0])

    stem = Path(filename).stem.replace("_", " ").replace("-", " ")
    if stem and not stem.lower().startswith("resume"):
        return _clean_text(stem)

    return None


def _extract_skills(text: str) -> list[str]:
    lower_text = text.lower()
    found = [keyword for keyword in SKILL_KEYWORDS if keyword in lower_text]
    return normalize_skills(found)


def extract_from_resume(resume_path: str | Path) -> Optional[ExtractedCandidate]:
    """
    Extract candidate fields from a resume PDF using regex-based parsing.

    Handles missing, empty, corrupted, and unsupported files without crashing.
    """
    path = Path(resume_path)
    source_name = path.name

    logger.info("Resume extraction started: %s", path)

    if not path.exists():
        logger.warning("Resume file not found: %s", path)
        return None

    if path.suffix.lower() not in SUPPORTED_RESUME_SUFFIXES:
        logger.warning("Unsupported resume format (expected PDF): %s", path)
        return None

    text = _extract_text_from_pdf(path)
    if text is None:
        logger.warning("Resume extraction produced no text: %s", path)
        return None

    provenance: list[ProvenanceEntry] = []

    full_name = _extract_name(text, source_name)
    if full_name:
        append_provenance(provenance, "full_name", source_name, RESUME_METHOD)

    emails = _extract_emails(text)
    if emails:
        append_provenance(provenance, "emails", source_name, RESUME_METHOD)

    phones = _extract_phones(text)
    if phones:
        append_provenance(provenance, "phones", source_name, RESUME_METHOD)

    skill_names = _extract_skills(text)
    if skill_names:
        append_provenance(provenance, "skills", source_name, RESUME_METHOD)

    education = _extract_education(text)
    if education:
        append_provenance(provenance, "education", source_name, RESUME_METHOD)

    experience = _extract_experience(text)
    if experience:
        append_provenance(provenance, "experience", source_name, RESUME_METHOD)

    candidate = Candidate(
        candidate_id=str(uuid.uuid4()),
        full_name=full_name,
        emails=emails,
        phones=phones,
        skills=[SkillEntry(name=name) for name in skill_names],
        education=education,
        experience=experience,
        provenance=provenance,
    )

    logger.info(
        "Resume extraction completed: source=%s, name=%s, emails=%d, phones=%d, skills=%d, "
        "experience=%d, education=%d",
        source_name,
        full_name,
        len(emails),
        len(phones),
        len(skill_names),
        len(experience),
        len(education),
    )

    return ExtractedCandidate(data=candidate, source_name=source_name, source_type="resume")


def extract_all_from_directory(resume_dir: str | Path) -> list[ExtractedCandidate]:
    """Extract candidates from all PDF resumes in a directory."""
    directory = Path(resume_dir)
    logger.info("Resume folder extraction started: %s", directory)

    if not directory.exists():
        logger.warning("Resume directory not found: %s", directory)
        return []

    if not directory.is_dir():
        logger.warning("Resume path is not a directory: %s", directory)
        return []

    records: list[ExtractedCandidate] = []
    pdf_files = sorted(directory.glob("*.pdf"))

    if not pdf_files:
        logger.warning("No PDF resumes found in: %s", directory)
        return []

    for pdf_path in pdf_files:
        try:
            extracted = extract_from_resume(pdf_path)
            if extracted:
                records.append(extracted)
        except Exception as exc:
            logger.warning("Skipping corrupted resume %s: %s", pdf_path, exc)

    logger.info("Resume folder extraction completed: %d resume(s)", len(records))
    return records


def apply_resume_normalization(extracted: ExtractedCandidate) -> ExtractedCandidate:
    """Apply phone and skill normalization to resume-extracted data."""
    logger.info("Normalization started for resume source: %s", extracted.source_name)
    normalized = apply_candidate_normalization(extracted)
    logger.info("Normalization completed for resume source: %s", extracted.source_name)
    return normalized


class ResumeExtractor(BaseExtractor):
    """Adapter for resume PDF extraction."""

    source_type = "resume"

    def extract(self, source: Path) -> list[ExtractedCandidate]:
        if source.is_dir():
            records = extract_all_from_directory(source)
        else:
            single = extract_from_resume(source)
            records = [single] if single else []
        return [apply_resume_normalization(record) for record in records]

    def extract_many(self, sources: list[Path]) -> list[ExtractedCandidate]:
        results: list[ExtractedCandidate] = []
        for source in sources:
            results.extend(self.extract(source))
        return results
