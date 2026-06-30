"""Base extractor interface for adapter-style source ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from models import ExtractedCandidate


class BaseExtractor(ABC):
    """
    Abstract base class for candidate data extractors.

    Each source type (CSV, resume, notes, LinkedIn, etc.) implements this
    interface so new sources can be added without changing the pipeline core.
    """

    source_type: str

    @abstractmethod
    def extract(self, source: Path) -> list[ExtractedCandidate]:
        """Extract one or more candidate records from a source path."""

    @abstractmethod
    def extract_many(self, sources: list[Path]) -> list[ExtractedCandidate]:
        """Extract candidate records from multiple source paths."""
