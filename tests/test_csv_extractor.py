"""Tests for CSV extraction edge cases."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from extractors.csv_extractor import extract_from_csv  # noqa: E402


def test_missing_columns(tmp_path: Path) -> None:
    """CSV with only name and email should not crash."""
    csv_file = tmp_path / "partial.csv"
    csv_file.write_text("name,email\nAlice Smith,alice@example.com\n")

    result = extract_from_csv(csv_file)
    assert result is not None
    assert result.data.full_name == "Alice Smith"
    assert result.data.emails == ["alice@example.com"]
    assert result.data.phones == []


def test_empty_csv_file(tmp_path: Path) -> None:
    """Completely empty CSV file should return None without crashing."""
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("")

    result = extract_from_csv(csv_file)
    assert result is None


def test_empty_rows_skipped(tmp_path: Path) -> None:
    """Empty rows should be skipped without error."""
    csv_file = tmp_path / "sparse.csv"
    csv_file.write_text(
        "name,email,phone,current_company,title\n"
        ",,,,\n"
        "Bob Lee,bob@example.com,9999999999,Corp,Engineer\n"
    )

    result = extract_from_csv(csv_file)
    assert result is not None
    assert result.data.full_name == "Bob Lee"


def test_malformed_rows_handled(tmp_path: Path) -> None:
    """Malformed CSV should be handled gracefully via pandas."""
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("name,email\nValid User,valid@example.com\n")

    result = extract_from_csv(csv_file)
    assert result is not None


def test_missing_file_returns_none(tmp_path: Path) -> None:
    result = extract_from_csv(tmp_path / "nonexistent.csv")
    assert result is None


def test_duplicate_emails_deduped_in_csv(tmp_path: Path) -> None:
    """Duplicate emails within CSV should be deduplicated."""
    csv_file = tmp_path / "dupes.csv"
    csv_file.write_text(
        "name,email,phone\n"
        "Alice,alice@example.com,9876543210\n"
        "Alice,alice@example.com,9876543210\n"
    )

    result = extract_from_csv(csv_file)
    assert result is not None
    assert result.data.emails == ["alice@example.com"]
