"""Tests for phone normalization."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from normalizers.phone_normalizer import normalize_phone, normalize_phones  # noqa: E402


def test_indian_phone_normalized_to_e164() -> None:
    assert normalize_phone("9876543210") == "+919876543210"


def test_invalid_phone_ignored() -> None:
    assert normalize_phone("123") is None
    assert normalize_phone("0000000000") is None
    assert normalize_phone("1111111111") is None
    assert normalize_phone("") is None
    assert normalize_phone("not-a-phone") is None


def test_duplicate_phones_removed() -> None:
    phones = normalize_phones(["9876543210", "+919876543210", "9876543210"])
    assert phones == ["+919876543210"]
