"""Merge candidate data from multiple sources with conflict resolution."""

from __future__ import annotations

import logging
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


def _dedupe_skills(skills: list[SkillEntry]) -> list[SkillEntry]:
    """Normalize and deduplicate skill entries."""
    canonical_names = normalize_skills([skill.name for skill in skills])
    return [SkillEntry(name=name) for name in canonical_names]


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
        experience=all_experience,
        education=all_education,
        provenance=all_provenance,
    )

    logger.info(
        "Merge completed: name=%s, emails=%d, phones=%d, skills=%d, experience=%d, provenance=%d",
        merged.full_name,
        len(merged.emails),
        len(merged.phones),
        len(merged.skills),
        len(merged.experience),
        len(merged.provenance),
    )

    return merged
