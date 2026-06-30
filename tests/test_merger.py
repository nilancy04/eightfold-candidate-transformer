"""Tests for merge engine and confidence scoring."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from common import round_confidence  # noqa: E402
from confidence import apply_confidence, field_confidence, get_source_confidence, overall_confidence  # noqa: E402
from merger import merge_candidates  # noqa: E402
from models import Candidate, ExtractedCandidate, SkillEntry  # noqa: E402


def test_source_confidence_values() -> None:
    assert get_source_confidence("csv") == 0.95
    assert get_source_confidence("resume") == 0.85


def test_csv_wins_name_conflict() -> None:
    """Higher-confidence CSV source should win scalar conflicts."""
    csv_candidate = ExtractedCandidate(
        data=Candidate(full_name="CSV Name", emails=["a@example.com"]),
        source_name="data.csv",
        source_type="csv",
    )
    resume_candidate = ExtractedCandidate(
        data=Candidate(full_name="Resume Name", emails=["b@example.com"]),
        source_name="resume.pdf",
        source_type="resume",
    )

    merged = merge_candidates([csv_candidate, resume_candidate])
    assert merged.full_name == "CSV Name"
    assert set(merged.emails) == {"a@example.com", "b@example.com"}


def test_duplicate_skills_merged() -> None:
    csv_candidate = ExtractedCandidate(
        data=Candidate(
            full_name="Dev",
            skills=[SkillEntry(name="python"), SkillEntry(name="Python")],
        ),
        source_name="data.csv",
        source_type="csv",
    )
    resume_candidate = ExtractedCandidate(
        data=Candidate(
            full_name="Dev",
            skills=[SkillEntry(name="javascript"), SkillEntry(name="JavaScript")],
        ),
        source_name="resume.pdf",
        source_type="resume",
    )

    merged = merge_candidates([csv_candidate, resume_candidate])
    assert [skill.name for skill in merged.skills] == ["Python", "JavaScript"]


def test_provenance_tracked_after_merge() -> None:
    csv_candidate = ExtractedCandidate(
        data=Candidate(full_name="Alice", emails=["alice@example.com"]),
        source_name="data.csv",
        source_type="csv",
    )

    merged = merge_candidates([csv_candidate])
    fields = {entry.field for entry in merged.provenance}
    assert "full_name" in fields
    assert "emails" in fields


def test_confidence_rounded_to_two_decimals() -> None:
    candidate = Candidate(
        full_name="Test",
        emails=["t@example.com"],
        phones=["+919876543210"],
        skills=[SkillEntry(name="Python")],
    )
    apply_confidence(candidate, ["csv"])
    assert candidate.overall_confidence == round_confidence(candidate.overall_confidence or 0)
    assert len(str(candidate.overall_confidence).split(".")[-1]) <= 2


def test_overall_confidence_in_range() -> None:
    candidate = Candidate(
        full_name="Test",
        emails=["t@example.com"],
        phones=["+919876543210"],
        skills=[SkillEntry(name="Python")],
    )
    score = overall_confidence(candidate, ["csv"])
    assert 0.0 <= score <= 1.0
    assert score == round_confidence(score)


def test_merge_empty_sources() -> None:
    """Merging empty sources list should return empty candidate."""
    merged = merge_candidates([])
    assert merged.candidate_id is not None
    assert merged.full_name is None
    assert merged.emails == []


def test_merge_preserves_normalization_provenance() -> None:
    """Normalization provenance entries from extractors should survive merge."""
    from models import ProvenanceEntry

    csv_candidate = ExtractedCandidate(
        data=Candidate(
            full_name="Alice",
            emails=["alice@example.com"],
            provenance=[
                ProvenanceEntry(
                    field="emails", source="test.csv",
                    method="normalization",
                    details="email lowercased: ALICE@EXAMPLE.COM -> alice@example.com",
                ),
            ],
        ),
        source_name="test.csv",
        source_type="csv",
    )

    merged = merge_candidates([csv_candidate])
    normalization_entries = [
        p for p in merged.provenance if p.method == "normalization"
    ]
    assert len(normalization_entries) >= 1
    assert any("email lowercased" in (p.details or "") for p in normalization_entries)

