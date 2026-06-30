"""Tests for resume experience extraction."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from extractors.resume_extractor import _clean_company_name, _extract_experience  # noqa: E402


def test_company_name_strips_date_fragments() -> None:
    assert _clean_company_name("Sikar Infotech 05/2025 – 07/2025") == "Sikar Infotech"
    assert _clean_company_name("Sikar Infotech 05") == "Sikar Infotech"
    assert _clean_company_name("Google 2023") == "Google"


def test_experience_line_with_dash_dates() -> None:
    text = "Full Stack Developer Intern – Sikar Infotech 05/2025 – 07/2025"
    entries = _extract_experience(text)

    assert len(entries) == 1
    assert entries[0].title == "Full Stack Developer Intern"
    assert entries[0].company == "Sikar Infotech"
    assert entries[0].start_date == "2025-05"
    assert entries[0].end_date == "2025-07"
