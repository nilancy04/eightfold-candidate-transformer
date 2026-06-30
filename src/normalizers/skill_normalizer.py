"""Skill name normalization and deduplication."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import ProvenanceEntry

# Canonical skill aliases (keys are lowercase for lookup).
SKILL_ALIASES: dict[str, str] = {
    "python": "Python",
    "java": "Java",
    "cpp": "C++",
    "c++": "C++",
    "reactjs": "React",
    "react.js": "React",
    "react": "React",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "sql": "SQL",
    "aws": "AWS",
    "html": "HTML",
    "css": "CSS",
    "go": "Go",
    "ml": "Machine Learning",
    "ai": "Artificial Intelligence",
    "machine learning": "Machine Learning",
    "artificial intelligence": "Artificial Intelligence",
}


def normalize_skill(raw: str) -> str:
    """
    Normalize a single skill name using alias mapping.

    Unknown skills are returned with stripped whitespace unchanged.
    """
    if not raw or not str(raw).strip():
        return ""

    key = str(raw).strip().lower()
    return SKILL_ALIASES.get(key, str(raw).strip())


def normalize_skills(raw_skills: list[str]) -> list[str]:
    """Normalize skills and remove duplicates while preserving order."""
    seen: set[str] = set()
    result: list[str] = []

    for raw in raw_skills:
        normalized = normalize_skill(raw)
        if not normalized:
            continue
        lookup_key = normalized.lower()
        if lookup_key not in seen:
            seen.add(lookup_key)
            result.append(normalized)

    return result


def normalize_skills_with_provenance(
    raw_skills: list[str],
    source_name: str,
) -> tuple[list[str], list["ProvenanceEntry"]]:
    """Normalize skills and return provenance entries for normalization decisions.

    Tracks: skill aliased (e.g. reactjs -> React), duplicate skill removed.
    """
    from models import ProvenanceEntry

    provenance: list[ProvenanceEntry] = []
    seen: set[str] = set()
    result: list[str] = []

    for raw in raw_skills:
        if not raw or not str(raw).strip():
            continue

        original = str(raw).strip()
        normalized = normalize_skill(original)
        if not normalized:
            continue

        lookup_key = normalized.lower()

        if original != normalized:
            provenance.append(ProvenanceEntry(
                field="skills", source=source_name,
                method="normalization",
                details=f"skill normalized: {original} -> {normalized}",
            ))

        if lookup_key in seen:
            provenance.append(ProvenanceEntry(
                field="skills", source=source_name,
                method="normalization",
                details=f"duplicate skill removed: {normalized}",
            ))
            continue

        seen.add(lookup_key)
        result.append(normalized)

    return result, provenance
