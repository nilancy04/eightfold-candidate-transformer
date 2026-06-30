"""Validation for candidate profiles and projection output."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from common import round_confidence
from models import Candidate
from normalizers.email_normalizer import is_valid_email, normalize_email
from normalizers.phone_normalizer import is_valid_e164

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
    re.IGNORECASE,
)


class CandidateValidationError(Exception):
    """Raised when candidate validation fails."""


REQUIRED_FIELDS = ["full_name"]


def _validate_confidence_range(value: Optional[float], field_name: str) -> None:
    """Ensure a confidence value is numeric, within [0, 1], and rounded to 2 decimals."""
    if value is None:
        return
    if not isinstance(value, (int, float)):
        raise CandidateValidationError(
            f"Field '{field_name}' must be numeric, got {type(value).__name__}"
        )
    numeric_value = float(value)
    if not 0.0 <= numeric_value <= 1.0:
        raise CandidateValidationError(
            f"Field '{field_name}' must be between 0 and 1, got {value}"
        )
    if numeric_value != round_confidence(numeric_value):
        raise CandidateValidationError(
            f"Field '{field_name}' must be rounded to 2 decimal places, got {value}"
        )


def validate_emails(emails: list[str]) -> None:
    """Validate email list structure, format, and lowercase normalization."""
    if not isinstance(emails, list):
        raise CandidateValidationError("Field 'emails' must be a list")

    seen: set[str] = set()
    for index, email in enumerate(emails):
        if not isinstance(email, str):
            raise CandidateValidationError(
                f"Email at index {index} must be a string, got {type(email).__name__}"
            )
        if not is_valid_email(email):
            raise CandidateValidationError(
                f"Invalid email format at index {index}: '{email}'"
            )
        normalized = normalize_email(email)
        if email != normalized:
            raise CandidateValidationError(
                f"Email at index {index} must be lowercase and trimmed: '{email}'"
            )
        if normalized in seen:
            raise CandidateValidationError(
                f"Duplicate email at index {index}: '{email}'"
            )
        seen.add(normalized)


def validate_phones(phones: list[str]) -> None:
    """Validate phone list contains only unique E.164 numbers."""
    if not isinstance(phones, list):
        raise CandidateValidationError("Field 'phones' must be a list")

    seen: set[str] = set()
    for index, phone in enumerate(phones):
        if not isinstance(phone, str):
            raise CandidateValidationError(
                f"Phone at index {index} must be a string, got {type(phone).__name__}"
            )
        if not is_valid_e164(phone):
            raise CandidateValidationError(
                f"Phone at index {index} must be valid E.164 format: '{phone}'"
            )
        if phone in seen:
            raise CandidateValidationError(
                f"Duplicate phone at index {index}: '{phone}'"
            )
        seen.add(phone)


def validate_skills(skills: list[str]) -> None:
    """Validate skill list has no duplicates."""
    if not isinstance(skills, list):
        raise CandidateValidationError("Field 'skills' must be a list")

    seen: set[str] = set()
    for index, skill in enumerate(skills):
        if not isinstance(skill, str):
            raise CandidateValidationError(
                f"Skill at index {index} must be a string, got {type(skill).__name__}"
            )
        key = skill.lower()
        if key in seen:
            raise CandidateValidationError(
                f"Duplicate skill at index {index}: '{skill}'"
            )
        seen.add(key)


def validate_output_profile(profile: dict[str, Any]) -> list[str]:
    """
    Validate a serialized output profile before saving.

    Checks candidate_id, emails, phones, skills, and confidence.
    """
    warnings: list[str] = []

    if not profile.get("candidate_id"):
        warnings.append("Missing candidate_id")

    emails = profile.get("emails", [])
    try:
        validate_emails(emails)
    except CandidateValidationError as exc:
        warnings.append(str(exc))

    phones = profile.get("phones", [])
    try:
        validate_phones(phones)
    except CandidateValidationError as exc:
        warnings.append(str(exc))

    skills = profile.get("skills", [])
    try:
        validate_skills(skills)
    except CandidateValidationError as exc:
        warnings.append(str(exc))

    confidence = profile.get("overall_confidence")
    if confidence is not None:
        try:
            _validate_confidence_range(confidence, "overall_confidence")
        except CandidateValidationError as exc:
            warnings.append(str(exc))

    for warning in warnings:
        logger.warning("Output validation: %s", warning)

    return warnings


def validate_candidate(
    candidate: Candidate,
    required_fields: Optional[list[str]] = None,
) -> list[str]:
    """
    Validate candidate schema, required fields, data types, emails, and confidence.

    Returns a list of validation warning messages.
    """
    warnings: list[str] = []
    required = required_fields or REQUIRED_FIELDS

    data = candidate.model_dump()

    for field in required:
        value = data.get(field)
        if value is None or value == "" or value == []:
            warnings.append(f"Required field missing or empty: '{field}'")

    if confidence := candidate.overall_confidence:
        try:
            _validate_confidence_range(confidence, "overall_confidence")
        except CandidateValidationError as exc:
            warnings.append(str(exc))

    for field_name, score in (candidate.field_confidence or {}).items():
        try:
            _validate_confidence_range(score, f"field_confidence.{field_name}")
        except CandidateValidationError as exc:
            warnings.append(str(exc))

    if candidate.emails:
        try:
            validate_emails(candidate.emails)
        except CandidateValidationError as exc:
            warnings.append(str(exc))

    if candidate.phones:
        try:
            validate_phones(candidate.phones)
        except CandidateValidationError as exc:
            warnings.append(str(exc))

    if candidate.skills:
        try:
            validate_skills([skill.name for skill in candidate.skills])
        except CandidateValidationError as exc:
            warnings.append(str(exc))

    for warning in warnings:
        logger.warning("Validation: %s", warning)

    return warnings


def validate_projected_output(output: dict[str, Any]) -> list[str]:
    """Validate projected output confidence values if present."""
    warnings: list[str] = []

    if "overall_confidence" in output:
        try:
            _validate_confidence_range(output["overall_confidence"], "overall_confidence")
        except CandidateValidationError as exc:
            warnings.append(str(exc))

    field_confidence = output.get("field_confidence")
    if field_confidence is not None:
        if not isinstance(field_confidence, dict):
            warnings.append("field_confidence must be a dictionary")
        else:
            for field_name, score in field_confidence.items():
                try:
                    _validate_confidence_range(score, f"field_confidence.{field_name}")
                except CandidateValidationError as exc:
                    warnings.append(str(exc))

    for warning in warnings:
        logger.warning("Projected output validation: %s", warning)

    return warnings
