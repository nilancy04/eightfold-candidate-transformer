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


def test_experience_comma_format_with_location() -> None:
    text = (
        "PROFESSIONAL EXPERIENCE\n"
        "AR/VR Consultant Intern, PMKVY 4.0 2024 – 2025 | Chennai, India\n"
        "AI/ML Intern, Google AI-ML Program 10/2024 – 12/2024 | Remote\n"
        "PROJECTS"
    )
    entries = _extract_experience(text)
    assert len(entries) == 2
    assert entries[0].title == "AR/VR Consultant Intern"
    assert entries[0].company == "PMKVY 4.0"
    assert entries[1].title == "AI/ML Intern"
    assert entries[1].company == "Google AI/ML Program"


def test_experience_rejects_date_as_company() -> None:
    text = (
        "PROFESSIONAL EXPERIENCE\n"
        "Some Role, 2025 | Chennai, India\n"
        "PROJECTS"
    )
    entries = _extract_experience(text)
    assert entries == []
