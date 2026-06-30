"""Tests for skill normalization."""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from normalizers.skill_normalizer import normalize_skill, normalize_skills  # noqa: E402


def test_skill_aliases() -> None:
    assert normalize_skill("python") == "Python"
    assert normalize_skill("java") == "Java"
    assert normalize_skill("sql") == "SQL"
    assert normalize_skill("aws") == "AWS"
    assert normalize_skill("html") == "HTML"
    assert normalize_skill("css") == "CSS"
    assert normalize_skill("go") == "Go"
    assert normalize_skill("cpp") == "C++"
    assert normalize_skill("reactjs") == "React"
    assert normalize_skill("react") == "React"
    assert normalize_skill("js") == "JavaScript"
    assert normalize_skill("javascript") == "JavaScript"
    assert normalize_skill("nodejs") == "Node.js"
    assert normalize_skill("ml") == "Machine Learning"
    assert normalize_skill("ai") == "Artificial Intelligence"


def test_deduplication() -> None:
    skills = normalize_skills(["cpp", "C++", "python", "Python", "javascript", "JavaScript"])
    assert skills == ["C++", "Python", "JavaScript"]
