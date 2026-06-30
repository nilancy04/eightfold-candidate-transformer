"""Tests for normalization decision provenance tracking."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from normalizers.email_normalizer import normalize_emails_with_provenance  # noqa: E402
from normalizers.phone_normalizer import normalize_phones_with_provenance  # noqa: E402
from normalizers.skill_normalizer import normalize_skills_with_provenance  # noqa: E402


def test_email_lowercased_provenance() -> None:
    """Lowercasing an email should produce a provenance entry."""
    emails, prov = normalize_emails_with_provenance(
        ["ALICE@EXAMPLE.COM"], source_name="test.csv"
    )
    assert emails == ["alice@example.com"]
    assert any("email lowercased" in (p.details or "") for p in prov)


def test_invalid_email_removed_provenance() -> None:
    """Removing an invalid email should produce a provenance entry."""
    emails, prov = normalize_emails_with_provenance(
        ["not-an-email", "valid@example.com"], source_name="test.csv"
    )
    assert emails == ["valid@example.com"]
    assert any("invalid email removed" in (p.details or "") for p in prov)


def test_duplicate_email_removed_provenance() -> None:
    """Removing a duplicate email should produce a provenance entry."""
    emails, prov = normalize_emails_with_provenance(
        ["a@example.com", "a@example.com"], source_name="test.csv"
    )
    assert emails == ["a@example.com"]
    assert any("duplicate email removed" in (p.details or "") for p in prov)


def test_invalid_phone_removed_provenance() -> None:
    """Removing an invalid phone should produce a provenance entry."""
    phones, prov = normalize_phones_with_provenance(
        ["123", "9876543210"], source_name="test.csv"
    )
    assert len(phones) == 1
    assert any("invalid phone removed" in (p.details or "") for p in prov)


def test_phone_e164_conversion_provenance() -> None:
    """Converting a phone to E.164 should produce a provenance entry."""
    phones, prov = normalize_phones_with_provenance(
        ["9876543210"], source_name="test.csv"
    )
    assert phones == ["+919876543210"]
    assert any("phone converted to E.164" in (p.details or "") for p in prov)


def test_duplicate_phone_removed_provenance() -> None:
    """Removing a duplicate phone should produce a provenance entry."""
    phones, prov = normalize_phones_with_provenance(
        ["9876543210", "+919876543210"], source_name="test.csv"
    )
    assert phones == ["+919876543210"]
    assert any("duplicate phone removed" in (p.details or "") for p in prov)


def test_skill_normalized_provenance() -> None:
    """Aliasing a skill should produce a provenance entry."""
    skills, prov = normalize_skills_with_provenance(
        ["reactjs", "python"], source_name="test.csv"
    )
    assert skills == ["React", "Python"]
    assert any("skill normalized" in (p.details or "") for p in prov)


def test_duplicate_skill_removed_provenance() -> None:
    """Removing a duplicate skill should produce a provenance entry."""
    skills, prov = normalize_skills_with_provenance(
        ["python", "Python"], source_name="test.csv"
    )
    assert skills == ["Python"]
    assert any("duplicate skill removed" in (p.details or "") for p in prov)


def test_provenance_entries_have_correct_fields() -> None:
    """Provenance entries should have field, source, method, and details."""
    _, prov = normalize_emails_with_provenance(
        ["UPPER@EXAMPLE.COM"], source_name="resume.pdf"
    )
    assert len(prov) >= 1
    entry = prov[0]
    assert entry.field == "emails"
    assert entry.source == "resume.pdf"
    assert entry.method == "normalization"
    assert entry.details is not None
