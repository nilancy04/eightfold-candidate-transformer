"""Pydantic models for the canonical candidate schema."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class Location(BaseModel):
    """Geographic location for a candidate."""

    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None


class Links(BaseModel):
    """Professional and social links."""

    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: list[str] = Field(default_factory=list)


class SkillEntry(BaseModel):
    """Normalized skill with canonical name."""

    name: str


class ExperienceEntry(BaseModel):
    """Work experience record."""

    company: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class EducationEntry(BaseModel):
    """Education record."""

    institution: Optional[str] = None
    degree: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ProvenanceEntry(BaseModel):
    """Tracks where a field value originated and normalization decisions."""

    field: str
    source: str
    method: str
    details: Optional[str] = None


class Candidate(BaseModel):
    """Canonical candidate profile after merge and normalization."""

    candidate_id: Optional[str] = None
    full_name: Optional[str] = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    links: Links = Field(default_factory=Links)
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list[SkillEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    provenance: list[ProvenanceEntry] = Field(default_factory=list)
    overall_confidence: Optional[float] = None
    field_confidence: dict[str, float] = Field(default_factory=dict)

    @field_validator("overall_confidence")
    @classmethod
    def validate_overall_confidence(cls, value: Optional[float]) -> Optional[float]:
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError("overall_confidence must be between 0 and 1")
        return value


class ExtractedCandidate(BaseModel):
    """Partial candidate data from a single source before merge."""

    data: Candidate
    source_name: str
    source_type: str  # "csv" | "resume"


class ProjectionFieldConfig(BaseModel):
    """Single field mapping in output projection config."""

    path: str
    from_: Optional[str] = Field(default=None, alias="from")

    model_config = {"populate_by_name": True}


class ProjectionConfig(BaseModel):
    """Configuration for custom output projection."""

    fields: list[ProjectionFieldConfig] = Field(default_factory=list)
    include_confidence: bool = False
    on_missing: str = "null"  # null | omit | error

    @field_validator("on_missing")
    @classmethod
    def validate_on_missing(cls, value: str) -> str:
        allowed = {"null", "omit", "error"}
        if value not in allowed:
            raise ValueError(f"on_missing must be one of {allowed}")
        return value


def candidate_to_dict(candidate: Candidate) -> dict[str, Any]:
    """Serialize candidate to a plain dictionary."""
    return candidate.model_dump(mode="json")
