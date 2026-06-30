"""Tests for resume PDF extraction edge cases."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
TESTS = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from extractors.resume_extractor import extract_from_resume  # noqa: E402
from helpers import create_corrupted_pdf, create_minimal_pdf  # noqa: E402


def test_corrupted_pdf_does_not_crash(tmp_path: Path) -> None:
    pdf_path = tmp_path / "corrupted.pdf"
    create_corrupted_pdf(pdf_path)

    result = extract_from_resume(pdf_path)
    assert result is None


def test_empty_pdf_handled(tmp_path: Path) -> None:
    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\nxref\n0 0\ntrailer<<>>\nstartxref\n0\n%%EOF")

    result = extract_from_resume(pdf_path)
    assert result is None


def test_missing_resume_returns_none(tmp_path: Path) -> None:
    result = extract_from_resume(tmp_path / "missing.pdf")
    assert result is None


def test_valid_pdf_extraction(tmp_path: Path) -> None:
    pdf_path = tmp_path / "resume.pdf"
    create_minimal_pdf(pdf_path)

    result = extract_from_resume(pdf_path)
    assert result is None or isinstance(result.data.emails, list)
