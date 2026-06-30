"""Tests for output projection."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from models import Candidate, ProjectionConfig, ProjectionFieldConfig, SkillEntry  # noqa: E402
from projector import project_candidate  # noqa: E402


def test_projection_mapping() -> None:
    candidate = Candidate(
        full_name="Alice",
        emails=["alice@example.com"],
        phones=["+919876543210"],
        skills=[SkillEntry(name="Python"), SkillEntry(name="React")],
        overall_confidence=0.9,
        field_confidence={"full_name": 0.95},
    )

    config = ProjectionConfig(
        fields=[
            ProjectionFieldConfig(path="full_name"),
            ProjectionFieldConfig(path="primary_email", from_="emails[0]"),
            ProjectionFieldConfig(path="skill_names", from_="skills[].name"),
        ],
        include_confidence=True,
        on_missing="null",
    )

    output = project_candidate(candidate, config)
    assert output["full_name"] == "Alice"
    assert output["primary_email"] == "alice@example.com"
    assert output["skill_names"] == ["Python", "React"]
    assert output["overall_confidence"] == 0.9
