"""Extract candidate data from ATS (Applicant Tracking System) JSON exports."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from common import append_provenance, apply_candidate_normalization
from extractors.base import BaseExtractor
from models import Candidate, ExperienceEntry, ExtractedCandidate, ProvenanceEntry, SkillEntry

logger = logging.getLogger(__name__)

ATS_METHOD = "ATS field mapping"

# Mapping from ATS JSON field names to canonical model field names.
ATS_FIELD_MAP: dict[str, str] = {
    "candidateName": "full_name",
    "mail": "emails",
    "mobile": "phones",
    "designation": "title",
    "organization": "company",
    "skills": "skills",
}


def _safe_str(value: Any) -> str | None:
    """Convert a JSON value to a trimmed string, or None if empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _safe_str_list(value: Any) -> list[str]:
    """Convert a JSON value to a list of non-empty strings.

    Handles: list of strings, a single comma-separated string, or None.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [s.strip() for s in value if isinstance(s, str) and str(s).strip()]
    if isinstance(value, str) and value.strip():
        return [s.strip() for s in value.split(",") if s.strip()]
    return []


def _build_candidate_from_record(
    record: dict[str, Any],
    source_name: str,
) -> ExtractedCandidate | None:
    """Build a single ExtractedCandidate from one ATS JSON record.

    Stores raw values; normalization (with provenance) is applied later
    by apply_ats_normalization in ATSExtractor.extract().
    """
    name = _safe_str(record.get("candidateName"))
    email_raw = _safe_str(record.get("mail"))
    phone_raw = _safe_str(record.get("mobile"))
    designation = _safe_str(record.get("designation"))
    organization = _safe_str(record.get("organization"))
    skills_raw = _safe_str_list(record.get("skills"))

    if not any([name, email_raw, phone_raw, designation, organization, skills_raw]):
        return None

    provenance: list[ProvenanceEntry] = []
    emails: list[str] = []
    phones: list[str] = []

    if name:
        append_provenance(provenance, "full_name", source_name, ATS_METHOD)
    if email_raw:
        emails.append(email_raw)
        append_provenance(provenance, "emails", source_name, ATS_METHOD)
    if phone_raw:
        phones.append(phone_raw)
        append_provenance(provenance, "phones", source_name, ATS_METHOD)

    experience: list[ExperienceEntry] = []
    if organization or designation:
        experience.append(ExperienceEntry(company=organization, title=designation))
        append_provenance(provenance, "experience", source_name, ATS_METHOD)

    skills: list[SkillEntry] = []
    if skills_raw:
        skills = [SkillEntry(name=s) for s in skills_raw]
        append_provenance(provenance, "skills", source_name, ATS_METHOD)

    candidate = Candidate(
        candidate_id=str(uuid.uuid4()),
        full_name=name,
        emails=emails,
        phones=phones,
        skills=skills,
        experience=experience,
        provenance=provenance,
    )

    return ExtractedCandidate(data=candidate, source_name=source_name, source_type="ats")


def extract_all_from_ats(ats_path: str | Path) -> list[ExtractedCandidate]:
    """Read an ATS JSON file and return one ExtractedCandidate per record.

    Handles missing files, empty files, invalid JSON, and malformed records
    gracefully — never crashes the pipeline.
    """
    path = Path(ats_path)
    source_name = path.name

    logger.info("ATS extraction started: %s", path)

    if not path.exists():
        logger.warning("ATS file not found: %s", path)
        return []

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to read ATS file %s: %s", path, exc)
        return []

    if not raw_text.strip():
        logger.warning("ATS file is empty: %s", path)
        return []

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON in ATS file %s: %s", path, exc)
        return []

    if not isinstance(data, list):
        logger.warning("ATS file %s must contain a JSON array; got %s", path, type(data).__name__)
        return []

    if len(data) == 0:
        logger.warning("ATS file contains no records: %s", path)
        return []

    records: list[ExtractedCandidate] = []

    for index, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "ATS record %d in %s is not an object; skipping", index, source_name
            )
            continue

        try:
            extracted = _build_candidate_from_record(item, source_name)
        except Exception as exc:
            logger.warning(
                "Failed to parse ATS record %d in %s: %s", index, source_name, exc
            )
            continue

        if extracted is None:
            logger.debug("Skipping empty ATS record %d in %s", index, source_name)
            continue

        records.append(extracted)
        logger.info(
            "Processing candidate from ATS: %s",
            extracted.data.full_name or extracted.data.emails[0] if extracted.data.emails else f"record-{index}",
        )

    logger.info("ATS extraction completed: %d candidate(s) from %s", len(records), source_name)
    return records


def apply_ats_normalization(extracted: ExtractedCandidate) -> ExtractedCandidate:
    """Apply email, phone, and skill normalization to ATS-extracted data."""
    logger.info("Normalization started for ATS source: %s", extracted.source_name)
    normalized = apply_candidate_normalization(extracted)
    logger.info("Normalization completed for ATS source: %s", extracted.source_name)
    return normalized


class ATSExtractor(BaseExtractor):
    """Adapter for ATS JSON candidate extraction."""

    source_type = "ats"

    def extract(self, source: Path) -> list[ExtractedCandidate]:
        records = extract_all_from_ats(source)
        return [apply_ats_normalization(record) for record in records]

    def extract_many(self, sources: list[Path]) -> list[ExtractedCandidate]:
        results: list[ExtractedCandidate] = []
        for source in sources:
            results.extend(self.extract(source))
        return results
