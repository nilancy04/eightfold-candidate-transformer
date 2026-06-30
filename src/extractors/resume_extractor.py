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

EDUCATION_PATTERN = re.compile(
    r"(?:B\.?\s?(?:Tech|M\.?\s?Sc|Sc|A|Com)|M\.?\s?(?:Tech|Sc|BA|Com)|"
    r"Bachelor|Master|Ph\.?D|MBA|BSc|MSc|BE|ME|BCA|MCA)"
    r"[\s,:-]+(?:\w[\w\s&.-]{2,60})",
    re.IGNORECASE,
)

# Title – Company MM/YYYY – MM/YYYY  (e.g. Full Stack Developer Intern – Sikar Infotech 05/2025 – 07/2025)
EXPERIENCE_DASH_DATE_PATTERN = re.compile(
    r"^(.+?)\s*[–—\-]\s*(.+?)\s+(\d{1,2}/\d{4})\s*[–—\-]\s*(\d{1,2}/\d{4})\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# Title | Company (YYYY-MM - YYYY-MM)
EXPERIENCE_PIPE_PATTERN = re.compile(
    r"(?:^|\n)\s*([A-Z][\w\s&./-]{2,60}?)\s*[|\-–—]\s*([A-Z][\w\s&.-]{2,60})"
    r"(?:\s*\((\d{4}(?:-\d{2})?(?:\s*[-–—]\s*(?:\d{4}(?:-\d{2})?|Present|Current))?)\))?",
    re.MULTILINE,
)

DATE_SUFFIX_PATTERNS = [
    re.compile(r"\s+\d{1,2}/\d{4}\s*[–—\-]\s*\d{1,2}/\d{4}\s*$"),
    re.compile(r"\s+\d{1,2}/\d{4}\s*$"),
    re.compile(r"\s+\d{4}\s*[-–—]\s*\d{4}\s*$"),
    re.compile(r"\s+\d{4}\s*$"),
    re.compile(r"\s+\d{2}\s*$"),
]


def _clean_text(value: str) -> str:
    """Collapse whitespace and trim extracted text."""
    return " ".join(value.split()).strip()


def _clean_company_name(company: str) -> str:
    """Remove date fragments accidentally captured in company names."""
    cleaned = _clean_text(company)
    for pattern in DATE_SUFFIX_PATTERNS:
        cleaned = pattern.sub("", cleaned).strip()
    return cleaned


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

    # Fallback: derive from filename John_Doe.pdf -> John Doe
    stem = Path(filename).stem.replace("_", " ").replace("-", " ")
    if stem and not stem.lower().startswith("resume"):
        return _clean_text(stem)

    return None


def _extract_skills(text: str) -> list[str]:
    lower_text = text.lower()
    found = [keyword for keyword in SKILL_KEYWORDS if keyword in lower_text]
    return normalize_skills(found)


def _extract_education(text: str) -> list[EducationEntry]:
    entries: list[EducationEntry] = []
    for match in EDUCATION_PATTERN.finditer(text):
        snippet = _clean_text(match.group(0))
        parts = re.split(r"[\s,:-]+", snippet, maxsplit=1)
        degree = parts[0].strip() if parts else snippet
        institution = parts[1].strip() if len(parts) > 1 else None
        entries.append(EducationEntry(degree=degree, institution=institution))
    return entries


def _extract_experience(text: str) -> list[ExperienceEntry]:
    """Extract experience entries, keeping dates out of company names."""
    entries: list[ExperienceEntry] = []
    seen: set[tuple[str, str]] = set()

    for match in EXPERIENCE_DASH_DATE_PATTERN.finditer(text):
        title = _clean_text(match.group(1))
        company = _clean_company_name(match.group(2))
        start_date = normalize_date(match.group(3))
        end_date = normalize_date(match.group(4))
        key = (title.lower(), company.lower())
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            ExperienceEntry(
                title=title,
                company=company,
                start_date=start_date,
                end_date=end_date,
            )
        )

    for match in EXPERIENCE_PIPE_PATTERN.finditer(text):
        title = _clean_text(match.group(1))
        company = _clean_company_name(match.group(2))
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

        key = (title.lower(), company.lower())
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            ExperienceEntry(
                title=title,
                company=company,
                start_date=start_date,
                end_date=end_date,
            )
        )

    return entries


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
        "Resume extraction completed: source=%s, name=%s, emails=%d, phones=%d, skills=%d",
        source_name,
        full_name,
        len(emails),
        len(phones),
        len(skill_names),
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
