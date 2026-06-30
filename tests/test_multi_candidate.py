"""Tests for multi-candidate CSV extraction."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from extractors.csv_extractor import extract_all_from_csv  # noqa: E402


def test_multiple_candidates_from_csv(tmp_path: Path) -> None:
    csv_file = tmp_path / "candidates.csv"
    csv_file.write_text(
        "name,email,phone,current_company,title\n"
        "John Doe,john@example.com,9876543210,Google,Engineer\n"
        "Priya Sharma,priya@example.com,9876543211,Microsoft,Analyst\n"
    )

    records = extract_all_from_csv(csv_file)
    assert len(records) == 2
    assert records[0].data.full_name == "John Doe"
    assert records[1].data.full_name == "Priya Sharma"


def test_duplicate_rows_skipped(tmp_path: Path) -> None:
    csv_file = tmp_path / "dupes.csv"
    csv_file.write_text(
        "name,email,phone\n"
        "John Doe,john@example.com,9876543210\n"
        "John Doe,john@example.com,9876543210\n"
    )

    records = extract_all_from_csv(csv_file)
    assert len(records) == 1
