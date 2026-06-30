"""Shared utilities used across the candidate transformation pipeline."""

from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd

from models import Candidate, ExtractedCandidate, ProvenanceEntry, SkillEntry
from normalizers.email_normalizer import normalize_emails, normalize_emails_with_provenance
from normalizers.phone_normalizer import normalize_phones, normalize_phones_with_provenance
from normalizers.skill_normalizer import normalize_skills, normalize_skills_with_provenance

logger = logging.getLogger(__name__)


def round_confidence(value: float) -> float:
    """Clamp a confidence score to [0, 1] and round to two decimal places."""
    clamped = min(max(float(value), 0.0), 1.0)
    return round(clamped, 2)


def safe_cell_value(value: object) -> Optional[str]:
    """Convert a spreadsheet cell to a trimmed string, or None if empty/NaN."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text if text else None


def dedupe_emails(emails: list[str]) -> list[str]:
    """Normalize and deduplicate emails (trim, lowercase)."""
    return normalize_emails(emails)


def append_provenance(
    provenance: list[ProvenanceEntry],
    field: str,
    source: str,
    method: str,
    details: Optional[str] = None,
) -> None:
    """Record provenance for an extracted or merged field."""
    provenance.append(
        ProvenanceEntry(field=field, source=source, method=method, details=details)
    )


def apply_candidate_normalization(extracted: ExtractedCandidate) -> ExtractedCandidate:
    """
    Normalize emails, phones, and skills on an extracted candidate record.

    Tracks normalization decisions (lowercasing, invalid removal, dedup) as
    provenance entries on the candidate. Shared by CSV and resume extractors
    to avoid duplicated normalization logic.
    """
    candidate = extracted.data
    source_name = extracted.source_name

    # Normalize with provenance tracking.
    candidate.emails, email_prov = normalize_emails_with_provenance(
        candidate.emails, source_name,
    )
    candidate.phones, phone_prov = normalize_phones_with_provenance(
        candidate.phones, source_name,
    )
    normalized_skill_names, skill_prov = normalize_skills_with_provenance(
        [skill.name for skill in candidate.skills], source_name,
    )
    candidate.skills = [SkillEntry(name=name) for name in normalized_skill_names]

    # Append normalization provenance entries.
    candidate.provenance.extend(email_prov)
    candidate.provenance.extend(phone_prov)
    candidate.provenance.extend(skill_prov)

    return extracted


def candidate_to_output_profile(candidate: Candidate) -> dict[str, Any]:
    """Serialize a candidate to the standard multi-profile output shape.

    Data is already normalized by the extraction stage, so no re-normalization
    is needed here — just serialize to the output format.
    """
    confidence = (
        round_confidence(candidate.overall_confidence)
        if candidate.overall_confidence is not None
        else None
    )
    return {
        "candidate_id": candidate.candidate_id,
        "full_name": candidate.full_name,
        "emails": list(candidate.emails),
        "phones": list(candidate.phones),
        "skills": [skill.name for skill in candidate.skills],
        "experience": [entry.model_dump(mode="json") for entry in candidate.experience],
        "education": [entry.model_dump(mode="json") for entry in candidate.education],
        "overall_confidence": confidence,
        "provenance": [entry.model_dump(mode="json") for entry in candidate.provenance],
    }
