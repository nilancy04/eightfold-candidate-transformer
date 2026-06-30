"""Tests for ATS JSON extraction edge cases and integration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from extractors.ats_extractor import ATSExtractor, extract_all_from_ats  # noqa: E402


# ---------------------------------------------------------------------------
# Unit tests — ATS extractor
# ---------------------------------------------------------------------------


def test_valid_single_ats_record(tmp_path: Path) -> None:
    """A well-formed single ATS record should produce one ExtractedCandidate."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text(
        json.dumps([
            {
                "candidateName": "Priya Sharma",
                "mail": "priya.sharma@example.com",
                "mobile": "+91 9876543210",
                "designation": "Senior Software Engineer",
                "organization": "Infosys",
                "skills": ["Python", "Java"],
            }
        ])
    )

    results = extract_all_from_ats(ats_file)
    assert len(results) == 1
    assert results[0].data.full_name == "Priya Sharma"
    assert "priya.sharma@example.com" in results[0].data.emails
    assert results[0].source_type == "ats"


def test_valid_multiple_ats_records(tmp_path: Path) -> None:
    """Multiple records should all be extracted."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text(
        json.dumps([
            {"candidateName": "Alice", "mail": "alice@example.com"},
            {"candidateName": "Bob", "mail": "bob@example.com"},
            {"candidateName": "Carol", "mail": "carol@example.com"},
        ])
    )

    results = extract_all_from_ats(ats_file)
    assert len(results) == 3
    names = [r.data.full_name for r in results]
    assert "Alice" in names
    assert "Bob" in names
    assert "Carol" in names


def test_missing_ats_file(tmp_path: Path) -> None:
    """Missing file must return empty list without crashing."""
    results = extract_all_from_ats(tmp_path / "nonexistent.json")
    assert results == []


def test_empty_ats_file(tmp_path: Path) -> None:
    """Empty file must return empty list."""
    ats_file = tmp_path / "empty.json"
    ats_file.write_text("")
    results = extract_all_from_ats(ats_file)
    assert results == []


def test_invalid_json_ats_file(tmp_path: Path) -> None:
    """Invalid JSON must return empty list without crashing."""
    ats_file = tmp_path / "bad.json"
    ats_file.write_text("{ not valid json :::}")
    results = extract_all_from_ats(ats_file)
    assert results == []


def test_empty_json_array(tmp_path: Path) -> None:
    """Empty JSON array must return empty list."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text("[]")
    results = extract_all_from_ats(ats_file)
    assert results == []


def test_json_object_not_array(tmp_path: Path) -> None:
    """JSON object (not array) at top level must return empty list with warning."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text('{"candidateName": "Alice"}')
    results = extract_all_from_ats(ats_file)
    assert results == []


def test_malformed_records_skipped(tmp_path: Path) -> None:
    """Non-object records in the array must be skipped; valid ones extracted."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text(
        json.dumps([
            "not an object",
            None,
            42,
            {"candidateName": "Valid User", "mail": "valid@example.com"},
        ])
    )
    results = extract_all_from_ats(ats_file)
    assert len(results) == 1
    assert results[0].data.full_name == "Valid User"


def test_empty_record_skipped(tmp_path: Path) -> None:
    """A record with all empty/null fields must be skipped."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text(
        json.dumps([
            {"candidateName": "", "mail": None, "mobile": "", "skills": []},
            {"candidateName": "Alice", "mail": "alice@example.com"},
        ])
    )
    results = extract_all_from_ats(ats_file)
    assert len(results) == 1
    assert results[0].data.full_name == "Alice"


def test_ats_field_mapping_phone_normalized(tmp_path: Path) -> None:
    """Phone numbers should be normalized to E.164 via ATSExtractor."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text(
        json.dumps([{"candidateName": "Alice", "mail": "a@example.com", "mobile": "9876543210"}])
    )
    results = ATSExtractor().extract(ats_file)
    assert results[0].data.phones == ["+919876543210"]


def test_ats_field_mapping_email_lowercased(tmp_path: Path) -> None:
    """Emails from ATS must be lowercased after normalization."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text(
        json.dumps([{"candidateName": "Bob", "mail": "BOB@EXAMPLE.COM"}])
    )
    results = ATSExtractor().extract(ats_file)
    assert results[0].data.emails == ["bob@example.com"]


def test_ats_skills_normalized(tmp_path: Path) -> None:
    """Skill aliases must be normalized (e.g. reactjs -> React)."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text(
        json.dumps([
            {
                "candidateName": "Dev",
                "mail": "dev@example.com",
                "skills": ["reactjs", "python", "nodejs"],
            }
        ])
    )
    results = ATSExtractor().extract(ats_file)
    skill_names = [s.name for s in results[0].data.skills]
    assert "React" in skill_names
    assert "Python" in skill_names
    assert "Node.js" in skill_names


def test_ats_experience_mapped_from_designation_organization(tmp_path: Path) -> None:
    """designation → title, organization → company in ExperienceEntry."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text(
        json.dumps([
            {
                "candidateName": "Alice",
                "mail": "alice@example.com",
                "designation": "Data Scientist",
                "organization": "Google",
            }
        ])
    )
    results = ATSExtractor().extract(ats_file)
    assert len(results[0].data.experience) == 1
    exp = results[0].data.experience[0]
    assert exp.title == "Data Scientist"
    assert exp.company == "Google"


def test_ats_provenance_method_is_ats_field_mapping(tmp_path: Path) -> None:
    """Every provenance entry from ATS must have method='ATS field mapping'."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text(
        json.dumps([{"candidateName": "Alice", "mail": "alice@example.com"}])
    )
    results = ATSExtractor().extract(ats_file)
    ats_entries = [p for p in results[0].data.provenance if p.method == "ATS field mapping"]
    assert len(ats_entries) >= 1


def test_ats_source_type_is_ats(tmp_path: Path) -> None:
    """ExtractedCandidate source_type must be 'ats'."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text(
        json.dumps([{"candidateName": "Alice", "mail": "alice@example.com"}])
    )
    results = extract_all_from_ats(ats_file)
    assert results[0].source_type == "ats"


def test_ats_invalid_phone_excluded(tmp_path: Path) -> None:
    """Invalid phone numbers must be removed and not appear in output."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text(
        json.dumps([{"candidateName": "Alice", "mail": "alice@example.com", "mobile": "123"}])
    )
    results = ATSExtractor().extract(ats_file)
    assert results[0].data.phones == []


def test_ats_skills_as_comma_string(tmp_path: Path) -> None:
    """Skills provided as a comma-separated string should be split correctly."""
    ats_file = tmp_path / "ats.json"
    ats_file.write_text(
        json.dumps([
            {"candidateName": "Alice", "mail": "alice@example.com", "skills": "Python, Java, SQL"}
        ])
    )
    results = ATSExtractor().extract(ats_file)
    skill_names = [s.name for s in results[0].data.skills]
    assert "Python" in skill_names
    assert "Java" in skill_names
    assert "SQL" in skill_names


def test_ats_extractor_many(tmp_path: Path) -> None:
    """extract_many should work across multiple ATS files."""
    f1 = tmp_path / "ats1.json"
    f2 = tmp_path / "ats2.json"
    f1.write_text(json.dumps([{"candidateName": "Alice", "mail": "alice@example.com"}]))
    f2.write_text(json.dumps([{"candidateName": "Bob", "mail": "bob@example.com"}]))

    results = ATSExtractor().extract_many([f1, f2])
    assert len(results) == 2
