"""Tests for candidate validation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from models import Candidate  # noqa: E402
from normalizers.email_normalizer import is_valid_email  # noqa: E402
from validator import CandidateValidationError, validate_candidate, validate_emails  # noqa: E402


def test_missing_required_field_returns_warning() -> None:
    candidate = Candidate(emails=["a@example.com"])
    warnings = validate_candidate(candidate)
    assert any("full_name" in warning for warning in warnings)


def test_valid_candidate_no_warnings() -> None:
    candidate = Candidate(
        full_name="Valid User",
        emails=["valid@example.com"],
        overall_confidence=0.85,
    )
    warnings = validate_candidate(candidate)
    assert warnings == []


def test_invalid_confidence_returns_warning() -> None:
    candidate = Candidate.model_construct(full_name="User", overall_confidence=1.5)
    warnings = validate_candidate(candidate)
    assert any("overall_confidence" in warning for warning in warnings)


def test_invalid_email_format() -> None:
    with pytest.raises(CandidateValidationError, match="Invalid email format"):
        validate_emails(["not-an-email"])


def test_valid_email_format() -> None:
    assert is_valid_email("user@example.com")
    assert not is_valid_email("bad-email")


def test_duplicate_phone_detected() -> None:
    """Duplicate phones should trigger validation error."""
    from validator import validate_phones

    with pytest.raises(CandidateValidationError, match="Duplicate phone"):
        validate_phones(["+919876543210", "+919876543210"])


def test_invalid_phone_format_detected() -> None:
    """Non-E.164 phones should trigger validation error."""
    from validator import validate_phones

    with pytest.raises(CandidateValidationError, match="E.164"):
        validate_phones(["9876543210"])

