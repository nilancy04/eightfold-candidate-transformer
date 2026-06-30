"""Tests for output profile validation."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from validator import validate_output_profile  # noqa: E402


def test_valid_output_profile_no_warnings() -> None:
    profile = {
        "candidate_id": "abc-123",
        "full_name": "Jane Doe",
        "emails": ["jane@example.com"],
        "phones": ["+919876543210"],
        "skills": ["Python", "Java"],
        "overall_confidence": 0.89,
    }
    assert validate_output_profile(profile) == []


def test_duplicate_emails_detected() -> None:
    profile = {
        "candidate_id": "abc-123",
        "emails": ["a@example.com", "a@example.com"],
        "phones": [],
        "skills": [],
    }
    warnings = validate_output_profile(profile)
    assert any("Duplicate email" in w for w in warnings)


def test_duplicate_skills_detected() -> None:
    profile = {
        "candidate_id": "abc-123",
        "emails": [],
        "phones": [],
        "skills": ["Python", "python"],
    }
    warnings = validate_output_profile(profile)
    assert any("Duplicate skill" in w for w in warnings)


def test_missing_candidate_id_detected() -> None:
    profile = {
        "candidate_id": "",
        "emails": [],
        "phones": [],
        "skills": [],
    }
    warnings = validate_output_profile(profile)
    assert any("candidate_id" in w for w in warnings)
