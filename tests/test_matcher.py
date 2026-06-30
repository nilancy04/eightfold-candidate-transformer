"""Tests for candidate matching across sources."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from matcher import match_candidates, normalize_name  # noqa: E402
from models import Candidate, ExtractedCandidate  # noqa: E402


def _record(name: str, email: str, phone: str, source: str, source_type: str) -> ExtractedCandidate:
    return ExtractedCandidate(
        data=Candidate(full_name=name, emails=[email], phones=[phone]),
        source_name=source,
        source_type=source_type,
    )


def test_match_by_email_priority() -> None:
    csv_record = _record("John Doe", "john@example.com", "+919999999999", "data.csv", "csv")
    resume_record = _record("Johnny D", "john@example.com", "+918888888888", "John_Doe.pdf", "resume")

    groups = match_candidates([csv_record, resume_record])
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_same_phone_different_emails_must_not_merge() -> None:
    """Critical: different emails must never merge even with shared phone."""
    aman = _record("Aman Gupta", "aman@gmail.com", "+919765432109", "a.csv", "csv")
    akash = _record("Akash Jain", "akash@gmail.com", "+919765432109", "b.csv", "csv")
    aditi = _record("Aditi Rao", "aditi@gmail.com", "+919765432109", "c.csv", "csv")

    groups = match_candidates([aman, akash, aditi])
    assert len(groups) == 3


def test_same_name_different_emails_must_not_merge() -> None:
    john_a = _record("John Doe", "john.a@example.com", "+911111111111", "a.csv", "csv")
    john_b = _record("John Doe", "john.b@example.com", "+912222222222", "b.csv", "csv")

    groups = match_candidates([john_a, john_b])
    assert len(groups) == 2


def test_match_by_phone_when_email_missing() -> None:
    csv_record = ExtractedCandidate(
        data=Candidate(full_name="Priya Sharma", phones=["+919876543210"]),
        source_name="data.csv",
        source_type="csv",
    )
    resume_record = ExtractedCandidate(
        data=Candidate(full_name="Priya S", phones=["+919876543210"]),
        source_name="Priya_Sharma.pdf",
        source_type="resume",
    )

    groups = match_candidates([csv_record, resume_record])
    assert len(groups) == 1


def test_phone_not_used_when_both_have_different_emails() -> None:
    csv_record = _record("Alice", "alice@example.com", "+919876543210", "a.csv", "csv")
    resume_record = _record("Bob", "bob@example.com", "+919876543210", "Bob.pdf", "resume")

    groups = match_candidates([csv_record, resume_record])
    assert len(groups) == 2


def test_unmatched_records_stay_separate() -> None:
    alice = _record("Alice", "alice@example.com", "+911111111111", "a.csv", "csv")
    bob = _record("Bob", "bob@example.com", "+912222222222", "b.csv", "csv")

    groups = match_candidates([alice, bob])
    assert len(groups) == 2


def test_normalize_name() -> None:
    assert normalize_name("  John   Doe ") == "john doe"
