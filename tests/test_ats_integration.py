"""Integration tests for ATS source with the full pipeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from main import run_pipeline  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ats(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False))


def _write_csv(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join(rows) + "\n")


# ---------------------------------------------------------------------------
# ATS + CSV merge by email
# ---------------------------------------------------------------------------


def test_ats_csv_merge_by_email(tmp_path: Path) -> None:
    """ATS and CSV records with the same email must merge into ONE profile."""
    csv_file = tmp_path / "c.csv"
    _write_csv(csv_file, [
        "name,email,phone,current_company,title",
        "John Doe,john@gmail.com,9876543210,Google,Engineer",
    ])

    ats_file = tmp_path / "ats.json"
    _write_ats(ats_file, [
        {
            "candidateName": "John Doe",
            "mail": "john@gmail.com",
            "mobile": "9876543210",
            "designation": "Full Stack Developer",
            "organization": "Sikar Infotech",
            "skills": ["Python", "React"],
        }
    ])

    output = tmp_path / "out.json"
    exit_code = run_pipeline(csv_path=csv_file, resume_path=None, resumes_dir=None,
                             config_path=None, output_path=output, ats_path=ats_file)
    assert exit_code == 0
    profiles = json.loads(output.read_text())
    assert len(profiles) == 1
    assert profiles[0]["full_name"] == "John Doe"


def test_ats_csv_conflict_resolution_csv_wins(tmp_path: Path) -> None:
    """CSV (confidence 0.95) beats ATS (confidence 0.90) for company field."""
    csv_file = tmp_path / "c.csv"
    _write_csv(csv_file, [
        "name,email,current_company,title",
        "Alice,alice@example.com,Google,Engineer",
    ])

    ats_file = tmp_path / "ats.json"
    _write_ats(ats_file, [
        {
            "candidateName": "Alice",
            "mail": "alice@example.com",
            "organization": "Microsoft",
            "designation": "SDE",
        }
    ])

    output = tmp_path / "out.json"
    exit_code = run_pipeline(csv_path=csv_file, resume_path=None, resumes_dir=None,
                             config_path=None, output_path=output, ats_path=ats_file)
    assert exit_code == 0
    profiles = json.loads(output.read_text())
    assert len(profiles) == 1
    experience = profiles[0]["experience"]
    companies = [e["company"] for e in experience]
    # Google must appear (CSV wins company, but both experience entries included)
    assert any("Google" in (c or "") for c in companies)


def test_ats_csv_different_email_no_merge(tmp_path: Path) -> None:
    """ATS and CSV records with DIFFERENT emails must NOT merge."""
    csv_file = tmp_path / "c.csv"
    _write_csv(csv_file, [
        "name,email",
        "Alice,alice@example.com",
    ])

    ats_file = tmp_path / "ats.json"
    _write_ats(ats_file, [
        {"candidateName": "Alice", "mail": "alice.other@example.com"}
    ])

    output = tmp_path / "out.json"
    exit_code = run_pipeline(csv_path=csv_file, resume_path=None, resumes_dir=None,
                             config_path=None, output_path=output, ats_path=ats_file)
    assert exit_code == 0
    profiles = json.loads(output.read_text())
    assert len(profiles) == 2


def test_ats_match_by_phone_when_no_email(tmp_path: Path) -> None:
    """ATS record with phone but no email merges with CSV record with same phone, no email."""
    csv_file = tmp_path / "c.csv"
    _write_csv(csv_file, [
        "name,phone",
        "Alice,9876543210",
    ])

    ats_file = tmp_path / "ats.json"
    _write_ats(ats_file, [
        {"candidateName": "Alice", "mobile": "+919876543210"}
    ])

    output = tmp_path / "out.json"
    exit_code = run_pipeline(csv_path=csv_file, resume_path=None, resumes_dir=None,
                             config_path=None, output_path=output, ats_path=ats_file)
    assert exit_code == 0
    profiles = json.loads(output.read_text())
    assert len(profiles) == 1


def test_ats_unmatched_stays_separate(tmp_path: Path) -> None:
    """ATS record with no matching CSV record must remain its own profile."""
    csv_file = tmp_path / "c.csv"
    _write_csv(csv_file, [
        "name,email",
        "Alice,alice@example.com",
    ])

    ats_file = tmp_path / "ats.json"
    _write_ats(ats_file, [
        {"candidateName": "Bob", "mail": "bob@example.com"}
    ])

    output = tmp_path / "out.json"
    exit_code = run_pipeline(csv_path=csv_file, resume_path=None, resumes_dir=None,
                             config_path=None, output_path=output, ats_path=ats_file)
    assert exit_code == 0
    profiles = json.loads(output.read_text())
    assert len(profiles) == 2


def test_ats_skills_appear_in_merged_profile(tmp_path: Path) -> None:
    """Skills from ATS should appear in the merged profile's skills list."""
    ats_file = tmp_path / "ats.json"
    _write_ats(ats_file, [
        {
            "candidateName": "Dev",
            "mail": "dev@example.com",
            "skills": ["Python", "ReactJS", "Machine Learning"],
        }
    ])

    output = tmp_path / "out.json"
    exit_code = run_pipeline(csv_path=None, resume_path=None, resumes_dir=None,
                             config_path=None, output_path=output, ats_path=ats_file)
    assert exit_code == 0
    profiles = json.loads(output.read_text())
    skills = profiles[0]["skills"]
    assert "Python" in skills
    assert "React" in skills           # reactjs -> React (normalized)
    assert "Machine Learning" in skills


def test_ats_provenance_in_output(tmp_path: Path) -> None:
    """Output profiles from ATS should contain provenance with method='ATS field mapping'."""
    ats_file = tmp_path / "ats.json"
    _write_ats(ats_file, [
        {"candidateName": "Alice", "mail": "alice@example.com", "organization": "Google"}
    ])

    output = tmp_path / "out.json"
    exit_code = run_pipeline(csv_path=None, resume_path=None, resumes_dir=None,
                             config_path=None, output_path=output, ats_path=ats_file)
    assert exit_code == 0
    profiles = json.loads(output.read_text())
    prov = profiles[0]["provenance"]
    ats_entries = [p for p in prov if p.get("method") == "ATS field mapping"]
    assert len(ats_entries) >= 1


def test_ats_only_no_csv_no_resume(tmp_path: Path) -> None:
    """Pipeline must succeed with --ats as the sole source."""
    ats_file = tmp_path / "ats.json"
    _write_ats(ats_file, [
        {"candidateName": "Solo", "mail": "solo@example.com"}
    ])

    output = tmp_path / "out.json"
    exit_code = run_pipeline(csv_path=None, resume_path=None, resumes_dir=None,
                             config_path=None, output_path=output, ats_path=ats_file)
    assert exit_code == 0
    profiles = json.loads(output.read_text())
    assert len(profiles) == 1
    assert profiles[0]["full_name"] == "Solo"


def test_ats_confidence_score_valid(tmp_path: Path) -> None:
    """ATS-only profile must have a valid confidence score in [0, 1]."""
    ats_file = tmp_path / "ats.json"
    _write_ats(ats_file, [
        {
            "candidateName": "Dev",
            "mail": "dev@example.com",
            "mobile": "9876543210",
            "skills": ["Python"],
        }
    ])

    output = tmp_path / "out.json"
    run_pipeline(csv_path=None, resume_path=None, resumes_dir=None,
                 config_path=None, output_path=output, ats_path=ats_file)
    profiles = json.loads(output.read_text())
    conf = profiles[0].get("overall_confidence")
    assert conf is not None
    assert 0.0 <= conf <= 1.0


def test_ats_missing_file_pipeline_continues(tmp_path: Path) -> None:
    """Missing ATS file must not crash the pipeline when CSV is provided."""
    csv_file = tmp_path / "c.csv"
    _write_csv(csv_file, ["name,email", "Alice,alice@example.com"])

    output = tmp_path / "out.json"
    exit_code = run_pipeline(
        csv_path=csv_file,
        resume_path=None,
        resumes_dir=None,
        config_path=None,
        output_path=output,
        ats_path=tmp_path / "nonexistent.json",
    )
    assert exit_code == 0
    profiles = json.loads(output.read_text())
    assert len(profiles) == 1


def test_ats_invalid_json_pipeline_continues(tmp_path: Path) -> None:
    """Invalid ATS JSON must not crash the pipeline when CSV is provided."""
    csv_file = tmp_path / "c.csv"
    _write_csv(csv_file, ["name,email", "Alice,alice@example.com"])

    ats_file = tmp_path / "ats.json"
    ats_file.write_text("{ INVALID }")

    output = tmp_path / "out.json"
    exit_code = run_pipeline(
        csv_path=csv_file,
        resume_path=None,
        resumes_dir=None,
        config_path=None,
        output_path=output,
        ats_path=ats_file,
    )
    assert exit_code == 0
    profiles = json.loads(output.read_text())
    assert len(profiles) == 1


def test_ats_csv_resume_three_way_merge(tmp_path: Path) -> None:
    """CSV + ATS + Resume all sharing the same email must produce ONE profile."""
    import struct
    import zlib

    csv_file = tmp_path / "c.csv"
    _write_csv(csv_file, [
        "name,email",
        "John Doe,john@gmail.com",
    ])

    ats_file = tmp_path / "ats.json"
    _write_ats(ats_file, [
        {
            "candidateName": "John Doe",
            "mail": "john@gmail.com",
            "skills": ["Python", "React"],
        }
    ])

    # Create minimal valid PDF with John Doe text
    def _make_pdf(text: str) -> bytes:
        stream = text.encode("latin-1", errors="replace")
        compressed = zlib.compress(stream)
        length = len(compressed)
        content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
            + f"4 0 obj\n<< /Length {length} /Filter /FlateDecode >>\nstream\n".encode()
            + compressed
            + b"\nendstream\nendobj\n"
            b"xref\n0 5\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"0000000207 00000 n \n"
            b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n400\n%%EOF\n"
        )
        return content

    resume_path = tmp_path / "john_doe.pdf"
    resume_path.write_bytes(_make_pdf("John Doe\njohn@gmail.com\nSkills: Python, React"))

    output = tmp_path / "out.json"
    exit_code = run_pipeline(
        csv_path=csv_file,
        resume_path=resume_path,
        resumes_dir=None,
        config_path=None,
        output_path=output,
        ats_path=ats_file,
    )
    assert exit_code == 0
    profiles = json.loads(output.read_text())
    # All three share john@gmail.com → must be one merged profile
    emails_flat = [e for p in profiles for e in p.get("emails", [])]
    assert emails_flat.count("john@gmail.com") == 1


def test_ats_multiple_candidates_separate_profiles(tmp_path: Path) -> None:
    """Multiple ATS records with distinct emails must produce separate profiles."""
    ats_file = tmp_path / "ats.json"
    _write_ats(ats_file, [
        {"candidateName": "Alice", "mail": "alice@example.com"},
        {"candidateName": "Bob", "mail": "bob@example.com"},
        {"candidateName": "Carol", "mail": "carol@example.com"},
    ])

    output = tmp_path / "out.json"
    exit_code = run_pipeline(csv_path=None, resume_path=None, resumes_dir=None,
                             config_path=None, output_path=output, ats_path=ats_file)
    assert exit_code == 0
    profiles = json.loads(output.read_text())
    assert len(profiles) == 3
