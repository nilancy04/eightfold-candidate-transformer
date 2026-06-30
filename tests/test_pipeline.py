"""Integration tests for the multi-candidate CLI pipeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
TESTS = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from helpers import create_minimal_pdf  # noqa: E402
from main import run_pipeline  # noqa: E402


def test_multi_candidate_csv_output(tmp_path: Path) -> None:
    csv_file = tmp_path / "candidates.csv"
    csv_file.write_text(
        "name,email,phone,current_company,title\n"
        "John Doe,john@example.com,9876543210,Google,Engineer\n"
        "Priya Sharma,priya@example.com,9876543211,Microsoft,Analyst\n"
    )
    output_file = tmp_path / "profiles.json"

    exit_code = run_pipeline(
        csv_path=csv_file,
        resume_path=None,
        resumes_dir=None,
        config_path=None,
        output_path=output_file,
    )

    assert exit_code == 0
    profiles = json.loads(output_file.read_text())
    assert isinstance(profiles, list)
    assert len(profiles) == 2


def test_pipeline_continues_when_resume_missing(tmp_path: Path) -> None:
    csv_file = tmp_path / "candidate.csv"
    csv_file.write_text("name,email,phone\nAlice,alice@example.com,9876543210\n")
    output_file = tmp_path / "profiles.json"

    exit_code = run_pipeline(
        csv_path=csv_file,
        resume_path=tmp_path / "missing.pdf",
        resumes_dir=None,
        config_path=None,
        output_path=output_file,
    )

    assert exit_code == 0
    profiles = json.loads(output_file.read_text())
    assert len(profiles) == 1
    assert profiles[0]["full_name"] == "Alice"


def test_pipeline_continues_when_config_missing(tmp_path: Path) -> None:
    csv_file = tmp_path / "candidate.csv"
    csv_file.write_text("name,email\nBob,bob@example.com\n")
    output_file = tmp_path / "profiles.json"

    exit_code = run_pipeline(
        csv_path=csv_file,
        resume_path=None,
        resumes_dir=None,
        config_path=tmp_path / "missing.json",
        output_path=output_file,
    )

    assert exit_code == 0
    assert output_file.exists()


def test_csv_and_resume_matching(tmp_path: Path) -> None:
    csv_file = tmp_path / "candidate.csv"
    csv_file.write_text("name,email,phone\nJohn Doe,john@example.com,9876543210\n")

    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    create_minimal_pdf(
        resume_dir / "John_Doe.pdf",
        ["John Doe", "john@example.com", "9876543210", "Skills: Python, Java"],
    )

    output_file = tmp_path / "profiles.json"
    exit_code = run_pipeline(
        csv_path=csv_file,
        resume_path=None,
        resumes_dir=resume_dir,
        config_path=None,
        output_path=output_file,
    )

    assert exit_code == 0
    profiles = json.loads(output_file.read_text())
    assert len(profiles) == 1
    assert profiles[0]["full_name"] == "John Doe"
    assert "john@example.com" in profiles[0]["emails"]


def test_multi_resume_folder_processing(tmp_path: Path) -> None:
    """Multiple resumes in a folder should each produce records."""
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    create_minimal_pdf(
        resume_dir / "Alice_Smith.pdf",
        ["Alice Smith", "alice@example.com", "9876543210", "Skills: Python"],
    )
    create_minimal_pdf(
        resume_dir / "Bob_Jones.pdf",
        ["Bob Jones", "bob@example.com", "9876543211", "Skills: Java"],
    )

    output_file = tmp_path / "profiles.json"
    exit_code = run_pipeline(
        csv_path=None,
        resume_path=None,
        resumes_dir=resume_dir,
        config_path=None,
        output_path=output_file,
    )

    assert exit_code == 0
    profiles = json.loads(output_file.read_text())
    assert len(profiles) >= 2


def test_corrupted_pdf_in_folder_continues(tmp_path: Path) -> None:
    """Pipeline continues when one PDF in a folder is corrupted."""
    csv_file = tmp_path / "candidate.csv"
    csv_file.write_text("name,email\nAlice,alice@example.com\n")

    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    (resume_dir / "bad.pdf").write_bytes(b"%PDF-1.4\ncorrupted content\n%%EOF")

    output_file = tmp_path / "profiles.json"
    exit_code = run_pipeline(
        csv_path=csv_file,
        resume_path=None,
        resumes_dir=resume_dir,
        config_path=None,
        output_path=output_file,
    )

    assert exit_code == 0
    profiles = json.loads(output_file.read_text())
    assert len(profiles) >= 1


def test_empty_csv_produces_warning(tmp_path: Path) -> None:
    """Empty CSV file should not crash, just produce no output."""
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("")

    output_file = tmp_path / "profiles.json"
    exit_code = run_pipeline(
        csv_path=csv_file,
        resume_path=None,
        resumes_dir=None,
        config_path=None,
        output_path=output_file,
    )

    # Should return 1 (no data) but not crash.
    assert exit_code == 1


def test_unsupported_files_in_resume_dir_skipped(tmp_path: Path) -> None:
    """Non-PDF files in resume directory should be skipped."""
    csv_file = tmp_path / "candidate.csv"
    csv_file.write_text("name,email\nAlice,alice@example.com\n")

    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir()
    (resume_dir / "notes.txt").write_text("Some notes")
    (resume_dir / "data.docx").write_bytes(b"fake docx")

    output_file = tmp_path / "profiles.json"
    exit_code = run_pipeline(
        csv_path=csv_file,
        resume_path=None,
        resumes_dir=resume_dir,
        config_path=None,
        output_path=output_file,
    )

    assert exit_code == 0
    profiles = json.loads(output_file.read_text())
    assert len(profiles) >= 1


def test_provenance_in_output_profile(tmp_path: Path) -> None:
    """Output profiles should contain provenance entries."""
    csv_file = tmp_path / "candidate.csv"
    csv_file.write_text("name,email\nAlice,alice@example.com\n")

    output_file = tmp_path / "profiles.json"
    exit_code = run_pipeline(
        csv_path=csv_file,
        resume_path=None,
        resumes_dir=None,
        config_path=None,
        output_path=output_file,
    )

    assert exit_code == 0
    profiles = json.loads(output_file.read_text())
    assert len(profiles) == 1
    assert "provenance" in profiles[0]
    assert len(profiles[0]["provenance"]) > 0

