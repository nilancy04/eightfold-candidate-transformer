"""Tests for email normalization."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from normalizers.email_normalizer import normalize_email, normalize_emails  # noqa: E402


def test_email_lowercase_and_trim() -> None:
    assert normalize_email("  RAHUL.VERMA@gmail.com  ") == "rahul.verma@gmail.com"
    assert normalize_email("CASE.TEST@GMAIL.COM") == "case.test@gmail.com"


def test_email_deduplication() -> None:
    emails = normalize_emails(
        ["Alice@Example.com", "alice@example.com", "bob@example.com"]
    )
    assert emails == ["alice@example.com", "bob@example.com"]


def test_invalid_email_removed() -> None:
    emails = normalize_emails(["not-an-email", "valid@example.com"])
    assert emails == ["valid@example.com"]
