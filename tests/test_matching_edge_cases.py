"""Tests for matching edge cases including transitive merge bugs."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from matcher import match_candidates  # noqa: E402
from models import Candidate, ExtractedCandidate  # noqa: E402


def _record(
    name: str = "",
    emails: list[str] | None = None,
    phones: list[str] | None = None,
    source: str = "test.csv",
    source_type: str = "csv",
) -> ExtractedCandidate:
    return ExtractedCandidate(
        data=Candidate(
            full_name=name or None,
            emails=emails or [],
            phones=phones or [],
        ),
        source_name=source,
        source_type=source_type,
    )


def test_transitive_merge_different_emails_split() -> None:
    """Critical: A has email, B has same email+phone, C has same phone+different email.

    Union-Find would transitively merge A-B-C. Post-validation must split them
    because A and C have different emails.
    """
    a = _record(name="Alice", emails=["alice@example.com"], phones=[], source="a.csv")
    b = _record(name="Bob", emails=["alice@example.com"], phones=["+919876543210"], source="b.csv")
    c = _record(name="Charlie", emails=[], phones=["+919876543210"], source="c.csv")

    groups = match_candidates([a, b, c])

    # A and B share email — must be together.
    # C shares phone with B but has no email — can join B's group.
    # All records are compatible (no conflicting emails), so one group is correct.
    assert len(groups) == 1


def test_transitive_merge_conflicting_emails_split() -> None:
    """A(email1) matches B(email1+phone) by email, C(email2+phone) matches B by phone.

    C has email2, which conflicts with A/B's email1. Must split.
    """
    a = _record(emails=["alice@example.com"], phones=[], source="a.csv")
    b = _record(emails=["alice@example.com"], phones=["+919876543210"], source="b.csv")
    c = _record(emails=["charlie@example.com"], phones=["+919876543210"], source="c.csv")

    groups = match_candidates([a, b, c])

    # C has a different email from A/B — must be split into separate groups.
    assert len(groups) >= 2

    # Verify no group contains both alice@example.com and charlie@example.com
    for group in groups:
        all_emails = set()
        for rec in group:
            all_emails.update(rec.data.emails)
        assert not ({"alice@example.com", "charlie@example.com"} <= all_emails)


def test_match_by_name_when_no_email_no_phone() -> None:
    """Name-only match when both records lack email and phone."""
    a = _record(name="John Doe", source="a.csv")
    b = _record(name="John Doe", source="b.csv")

    groups = match_candidates([a, b])
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_single_record_produces_single_group() -> None:
    a = _record(name="Alice", emails=["alice@example.com"])
    groups = match_candidates([a])
    assert len(groups) == 1
    assert len(groups[0]) == 1


def test_empty_records_produces_empty_groups() -> None:
    groups = match_candidates([])
    assert groups == []


def test_phone_match_when_one_side_has_no_email() -> None:
    """Phone matching is allowed when at least one side lacks email."""
    csv_rec = _record(name="Alice", emails=["alice@example.com"], phones=["+919876543210"])
    resume_rec = _record(name="Alice R", emails=[], phones=["+919876543210"], source_type="resume")

    groups = match_candidates([csv_rec, resume_rec])
    assert len(groups) == 1


def test_no_match_when_different_everything() -> None:
    a = _record(name="Alice", emails=["alice@example.com"], phones=["+911111111111"])
    b = _record(name="Bob", emails=["bob@example.com"], phones=["+912222222222"])

    groups = match_candidates([a, b])
    assert len(groups) == 2
