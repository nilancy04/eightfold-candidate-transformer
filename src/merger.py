"""Merge candidate data from multiple sources with conflict resolution."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from common import append_provenance, dedupe_emails
from confidence import get_source_confidence
from models import (
    Candidate,
    EducationEntry,
    ExperienceEntry,
    ExtractedCandidate,
    ProvenanceEntry,
    SkillEntry,
)
from normalizers.phone_normalizer import normalize_phones
from normalizers.skill_normalizer import normalize_skills

logger = logging.getLogger(__name__)

MERGE_METHOD = "merge conflict resolution"

PAGE_NUMBER_SUFFIX = re.compile(
    r"\s*(?:\|\s*)(?:page\s*)?\d{1,2}\s*(?:/\s*\d{1,2})?\s*$",
    re.IGNORECASE,
)

PAGE_WORD_SUFFIX = re.compile(
    r"\s*page\s+\d+\s*(?:/\s*\d+)?\s*$",
    re.IGNORECASE,
)

GENERIC_PLACEHOLDER_DEGREES = frozenset(
    {"student", "graduate", "undergraduate", "pursuing", "n/a", "na", "none"}
)


def _normalize_match_key(value: str) -> str:
    """Normalize text for case-insensitive deduplication comparisons."""
    cleaned = " ".join((value or "").split()).lower()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return " ".join(cleaned.split())


def _dedupe_consecutive_words(text: str) -> str:
    """Remove immediately repeated words (e.g. 'Developer Developer')."""
    words = text.split()
    if not words:
        return text
    result = [words[0]]
    for word in words[1:]:
        if word.lower() != result[-1].lower():
            result.append(word)
    return " ".join(result)


def _strip_page_numbers(text: str) -> str:
    """Remove trailing page-number artifacts from extracted text."""
    cleaned = PAGE_WORD_SUFFIX.sub("", text).strip()
    cleaned = PAGE_NUMBER_SUFFIX.sub("", cleaned).strip()
    if re.fullmatch(r"(?:page\s*)?\d{1,2}(?:\s*/\s*\d{1,2})?", cleaned, flags=re.IGNORECASE):
        return ""
    return cleaned


def _clean_experience_field(value: str | None) -> str | None:
    """Trim and clean a company or title field before merge."""
    if not value:
        return None
    cleaned = _strip_page_numbers(_dedupe_consecutive_words(" ".join(value.split()).strip()))
    return cleaned or None


def _clean_experience_entry(entry: ExperienceEntry) -> ExperienceEntry | None:
    """Normalize and validate a single experience entry."""
    company = _clean_experience_field(entry.company)
    title = _clean_experience_field(entry.title)
    if not company or not title:
        return None
    return ExperienceEntry(
        company=company,
        title=title,
        start_date=entry.start_date,
        end_date=entry.end_date,
        description=(entry.description or "").strip() or None,
    )


def _clean_education_entry(entry: EducationEntry) -> EducationEntry | None:
    """Normalize and reject empty education records."""
    institution = _clean_experience_field(entry.institution)
    degree = _clean_experience_field(entry.degree)
    if not institution and not degree:
        return None
    return EducationEntry(
        institution=institution,
        degree=degree,
        start_date=entry.start_date,
        end_date=entry.end_date,
    )


def _dedupe_skills(skills: list[SkillEntry]) -> list[SkillEntry]:
    """Normalize and deduplicate skill entries."""
    canonical_names = normalize_skills([skill.name for skill in skills])
    return [SkillEntry(name=name) for name in canonical_names]


def _merge_experience_entries(
    existing: ExperienceEntry, new: ExperienceEntry
) -> ExperienceEntry:
    """Merge duplicate experience records from multiple sources."""
    existing_desc = existing.description or ""
    new_desc = new.description or ""
    description = new_desc if len(new_desc) > len(existing_desc) else existing_desc

    return ExperienceEntry(
        company=existing.company or new.company,
        title=existing.title or new.title,
        start_date=existing.start_date or new.start_date,
        end_date=existing.end_date or new.end_date,
        description=description or None,
    )


def _normalize_company_title(entry: ExperienceEntry) -> tuple[str, str]:
    return _normalize_match_key(entry.company or ""), _normalize_match_key(entry.title or "")


def _dedupe_experience(entries: list[ExperienceEntry]) -> list[ExperienceEntry]:
    """Deduplicate experience by company + title across merged sources."""
    merged: dict[tuple[str, str], ExperienceEntry] = {}

    for raw_entry in entries:
        entry = _clean_experience_entry(raw_entry)
        if not entry:
            continue
        company_key, title_key = _normalize_company_title(entry)
        if not company_key or not title_key:
            continue
        key = (company_key, title_key)
        if key not in merged:
            merged[key] = entry
        else:
            merged[key] = _merge_experience_entries(merged[key], entry)

    return list(merged.values())


def _normalize_institution_key(institution: str) -> str:
    key = re.sub(r"\s+\d{4}.*$", "", institution).strip()
    return _normalize_match_key(key)


def _pick_better_degree(
    left: str | None, right: str | None
) -> str | None:
    """Prefer formal degrees over placeholders like 'Student'."""
    if not left:
        return right
    if not right:
        return left

    left_lower = left.lower()
    right_lower = right.lower()

    if left_lower in GENERIC_PLACEHOLDER_DEGREES and right_lower not in GENERIC_PLACEHOLDER_DEGREES:
        return right
    if right_lower in GENERIC_PLACEHOLDER_DEGREES and left_lower not in GENERIC_PLACEHOLDER_DEGREES:
        return left
    return right if len(right) > len(left) else left


def _merge_education_entries(
    existing: EducationEntry, new: EducationEntry
) -> EducationEntry:
    """Merge duplicate education records from multiple sources."""
    return EducationEntry(
        institution=existing.institution or new.institution,
        degree=_pick_better_degree(existing.degree, new.degree),
        start_date=existing.start_date or new.start_date,
        end_date=existing.end_date or new.end_date,
    )


def _dedupe_education(entries: list[EducationEntry]) -> list[EducationEntry]:
    """
    Deduplicate education across merged sources.

    Primary key: institution + degree (case-insensitive).
    Complementary records with the same institution but placeholder degrees
    (e.g. 'Student') merge into the richer degree entry.
    """
    cleaned = [item for entry in entries if (item := _clean_education_entry(entry))]
    by_institution: dict[str, EducationEntry] = {}

    for entry in cleaned:
        inst_key = _normalize_institution_key(entry.institution or "")
        if not inst_key:
            continue
        if inst_key not in by_institution:
            by_institution[inst_key] = entry
        else:
            by_institution[inst_key] = _merge_education_entries(by_institution[inst_key], entry)

    final: dict[tuple[str, str], EducationEntry] = {}
    for entry in by_institution.values():
        inst_key = _normalize_institution_key(entry.institution or "")
        deg_key = _normalize_match_key(entry.degree or "")
        key = (inst_key, deg_key)
        if key in final:
            final[key] = _merge_education_entries(final[key], entry)
        else:
            final[key] = entry

    return list(final.values())


def _filter_institution_experience_overlap(
    experience: list[ExperienceEntry],
    education: list[EducationEntry],
) -> list[ExperienceEntry]:
    """
    Remove experience rows misclassified from CSV when the company is an
    education institution already captured in the education section.
    """
    institution_keys = {
        _normalize_institution_key(entry.institution or "")
        for entry in education
        if entry.institution
    }

    filtered: list[ExperienceEntry] = []
    for entry in experience:
        company_key = _normalize_institution_key(entry.company or "")
        if (
            company_key
            and company_key in institution_keys
            and not entry.start_date
            and not entry.end_date
        ):
            continue
        filtered.append(entry)

    return filtered


def _pick_scalar(
    field: str,
    values: list[tuple[Any, float, str]],
) -> tuple[Any, list[ProvenanceEntry]]:
    """
    Choose a scalar value from competing sources by highest confidence.

    Args:
        field: Canonical field name being resolved.
        values: List of (value, source_confidence, source_filename) tuples.
    """
    provenance: list[ProvenanceEntry] = []
    if not values:
        return None, provenance

    non_empty = [(value, conf, source) for value, conf, source in values if value not in (None, "", [])]
    if not non_empty:
        return None, provenance

    best_value, _, best_source = max(non_empty, key=lambda item: item[1])
    append_provenance(provenance, field, best_source, MERGE_METHOD)
    return best_value, provenance


def merge_candidates(sources: list[ExtractedCandidate]) -> Candidate:
    """
    Merge multiple extracted candidates into a single canonical profile.

    Deduplicates emails, phones, and skills. Resolves scalar conflicts
    using source confidence (CSV=0.95, Resume=0.85).
    """
    logger.info("Merge started: %d source(s)", len(sources))

    if not sources:
        logger.warning("No sources to merge; returning empty candidate")
        return Candidate(candidate_id=str(uuid.uuid4()))

    all_provenance: list[ProvenanceEntry] = []
    all_emails: list[str] = []
    all_phones: list[str] = []
    all_skills: list[SkillEntry] = []
    all_experience: list[ExperienceEntry] = []
    all_education: list[EducationEntry] = []

    name_candidates: list[tuple[str, float, str]] = []
    headline_candidates: list[tuple[str, float, str]] = []
    years_candidates: list[tuple[float, float, str]] = []

    for extracted in sources:
        candidate_data = extracted.data
        source_confidence = get_source_confidence(extracted.source_type)

        if candidate_data.full_name:
            name_candidates.append(
                (candidate_data.full_name, source_confidence, extracted.source_name)
            )
        if candidate_data.headline:
            headline_candidates.append(
                (candidate_data.headline, source_confidence, extracted.source_name)
            )
        if candidate_data.years_experience is not None:
            years_candidates.append(
                (candidate_data.years_experience, source_confidence, extracted.source_name)
            )

        all_emails.extend(candidate_data.emails)
        all_phones.extend(candidate_data.phones)
        all_skills.extend(candidate_data.skills)
        all_experience.extend(candidate_data.experience)
        all_education.extend(candidate_data.education)
        all_provenance.extend(candidate_data.provenance)

    full_name, name_provenance = _pick_scalar("full_name", name_candidates)
    headline, headline_provenance = _pick_scalar("headline", headline_candidates)
    years_experience, years_provenance = _pick_scalar("years_experience", years_candidates)

    all_provenance.extend(name_provenance)
    all_provenance.extend(headline_provenance)
    all_provenance.extend(years_provenance)

    merged_emails = dedupe_emails(all_emails)
    merged_phones = normalize_phones(all_phones)
    merged_skills = _dedupe_skills(all_skills)
    merged_education = _dedupe_education(all_education)
    merged_experience = _filter_institution_experience_overlap(
        _dedupe_experience(all_experience),
        merged_education,
    )

    # Record provenance for merged list fields sourced from each input file.
    for extracted in sources:
        source_name = extracted.source_name
        if extracted.data.emails:
            append_provenance(all_provenance, "emails", source_name, MERGE_METHOD)
        if extracted.data.phones:
            append_provenance(all_provenance, "phones", source_name, MERGE_METHOD)
        if extracted.data.skills:
            append_provenance(all_provenance, "skills", source_name, MERGE_METHOD)
        if extracted.data.experience:
            append_provenance(all_provenance, "experience", source_name, MERGE_METHOD)
        if extracted.data.education:
            append_provenance(all_provenance, "education", source_name, MERGE_METHOD)

    merged = Candidate(
        candidate_id=str(uuid.uuid4()),
        full_name=full_name,
        emails=merged_emails,
        phones=merged_phones,
        headline=headline,
        years_experience=years_experience,
        skills=merged_skills,
        experience=merged_experience,
        education=merged_education,
        provenance=all_provenance,
    )

    logger.info(
        "Merge completed: name=%s, emails=%d, phones=%d, skills=%d, experience=%d, "
        "education=%d, provenance=%d",
        merged.full_name,
        len(merged.emails),
        len(merged.phones),
        len(merged.skills),
        len(merged.experience),
        len(merged.education),
        len(merged.provenance),
    )

    return merged
