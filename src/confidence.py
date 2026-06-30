"""Confidence scoring for sources and fields."""

from __future__ import annotations

import logging
from typing import Optional

from common import round_confidence
from models import Candidate

logger = logging.getLogger(__name__)

SOURCE_CONFIDENCE: dict[str, float] = {
    "csv": 0.95,
    "resume": 0.85,
    "notes": 0.70,
}

# Field weights applied on top of source confidence.
FIELD_WEIGHTS: dict[str, float] = {
    "full_name": 1.0,
    "emails": 0.98,
    "phones": 0.95,
    "headline": 0.85,
    "years_experience": 0.80,
    "skills": 0.88,
    "experience": 0.82,
    "education": 0.80,
    "location": 0.75,
    "links": 0.70,
}


def get_source_confidence(source_type: str) -> float:
    """
    Return confidence for a data source type.

    CSV = 0.95, Resume = 0.85, Notes = 0.70. Unknown sources default to 0.70.
    """
    return SOURCE_CONFIDENCE.get(source_type.lower(), 0.70)


def field_confidence(field: str, source_type: str, has_value: bool = True) -> float:
    """
    Compute confidence for a specific field from a given source.

    Returns a value between 0 and 1, rounded to two decimal places.
    """
    if not has_value:
        return 0.0

    base = get_source_confidence(source_type)
    weight = FIELD_WEIGHTS.get(field, 0.85)
    return round_confidence(base * weight)


def overall_confidence(
    candidate: Candidate,
    source_types: Optional[list[str]] = None,
) -> float:
    """
    Compute overall confidence for a merged candidate profile.

    Averages field-level scores for populated fields.
    """
    if source_types is None:
        source_types = ["csv", "resume"]

    primary_source = source_types[0] if source_types else "csv"

    scored_fields: list[tuple[str, bool]] = [
        ("full_name", bool(candidate.full_name)),
        ("emails", bool(candidate.emails)),
        ("phones", bool(candidate.phones)),
        ("skills", bool(candidate.skills)),
        ("experience", bool(candidate.experience)),
        ("education", bool(candidate.education)),
    ]

    active_scores: list[float] = []
    field_scores: dict[str, float] = {}

    for field_name, has_value in scored_fields:
        score = field_confidence(field_name, primary_source, has_value=has_value)
        field_scores[field_name] = score
        if has_value:
            active_scores.append(score)

    candidate.field_confidence = field_scores

    if not active_scores:
        return 0.0

    average = sum(active_scores) / len(active_scores)
    return round_confidence(average)


def apply_confidence(candidate: Candidate, source_types: list[str]) -> Candidate:
    """Attach rounded overall and field confidence scores to a candidate."""
    candidate.overall_confidence = overall_confidence(candidate, source_types)
    logger.info(
        "Confidence computed: overall=%.2f, fields=%d",
        candidate.overall_confidence,
        len(candidate.field_confidence),
    )
    return candidate
