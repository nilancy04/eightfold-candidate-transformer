"""Extract candidate data from CSV files using pandas."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import pandas as pd

from common import (
    append_provenance,
    apply_candidate_normalization,
    safe_cell_value,
)
from extractors.base import BaseExtractor
from models import Candidate, ExperienceEntry, ExtractedCandidate, ProvenanceEntry

logger = logging.getLogger(__name__)

CSV_METHOD = "csv column mapping"


def _build_candidate_from_row(
    row_name: str | None,
    row_email: str | None,
    row_phone: str | None,
    row_company: str | None,
    row_title: str | None,
    source_name: str,
) -> ExtractedCandidate | None:
    """Build a single ExtractedCandidate from one CSV row.

    Stores raw values; normalization (with provenance) is applied later
    by apply_candidate_normalization in the CSVExtractor.extract() method.
    """
    if not any([row_name, row_email, row_phone, row_company, row_title]):
        return None

    provenance: list[ProvenanceEntry] = []
    emails: list[str] = []
    phones: list[str] = []
    experience: list[ExperienceEntry] = []

    if row_name:
        append_provenance(provenance, "full_name", source_name, CSV_METHOD)
    if row_email:
        emails.append(row_email)
        append_provenance(provenance, "emails", source_name, CSV_METHOD)
    if row_phone:
        phones.append(row_phone)
        append_provenance(provenance, "phones", source_name, CSV_METHOD)
    if row_company or row_title:
        experience.append(ExperienceEntry(company=row_company, title=row_title))
        append_provenance(provenance, "experience", source_name, CSV_METHOD)

    candidate = Candidate(
        candidate_id=str(uuid.uuid4()),
        full_name=row_name,
        emails=emails,
        phones=phones,
        experience=experience,
        provenance=provenance,
    )

    return ExtractedCandidate(data=candidate, source_name=source_name, source_type="csv")


def extract_all_from_csv(csv_path: str | Path) -> list[ExtractedCandidate]:
    """
    Read a CSV file and return one ExtractedCandidate per data row.

    Handles missing columns, malformed rows, empty rows, and duplicates gracefully.
    """
    path = Path(csv_path)
    source_name = path.name

    logger.info("CSV extraction started: %s", path)

    try:
        dataframe = pd.read_csv(
            path,
            dtype=str,
            keep_default_na=True,
            on_bad_lines="skip",
        )
    except FileNotFoundError:
        logger.warning("CSV file not found: %s", path)
        return []
    except pd.errors.EmptyDataError:
        logger.warning("CSV file is empty: %s", path)
        return []
    except Exception as exc:
        logger.warning("Failed to read CSV %s: %s", path, exc)
        return []

    if dataframe.empty:
        logger.warning("CSV file contains no data rows: %s", path)
        return []

    dataframe.columns = [str(column).strip().lower() for column in dataframe.columns]
    missing_columns = {"name", "email", "phone", "current_company", "title"} - set(dataframe.columns)
    if missing_columns:
        logger.warning(
            "CSV %s is missing optional columns: %s",
            source_name,
            ", ".join(sorted(missing_columns)),
        )

    records: list[ExtractedCandidate] = []
    seen_row_keys: set[str] = set()

    for row_index, row in dataframe.iterrows():
        row_name = safe_cell_value(row.get("name")) if "name" in dataframe.columns else None
        row_email = safe_cell_value(row.get("email")) if "email" in dataframe.columns else None
        row_phone = safe_cell_value(row.get("phone")) if "phone" in dataframe.columns else None
        row_company = (
            safe_cell_value(row.get("current_company"))
            if "current_company" in dataframe.columns
            else None
        )
        row_title = safe_cell_value(row.get("title")) if "title" in dataframe.columns else None

        if not any([row_name, row_email, row_phone, row_company, row_title]):
            logger.debug("Skipping empty row %s in %s", row_index, source_name)
            continue

        # Skip exact duplicate rows (same email + phone + name).
        row_key = "|".join(
            [
                (row_email or "").lower(),
                (row_phone or "").strip(),
                (row_name or "").lower(),
            ]
        )
        if row_key in seen_row_keys:
            logger.warning("Skipping duplicate CSV row %s in %s", row_index, source_name)
            continue
        seen_row_keys.add(row_key)

        extracted = _build_candidate_from_row(
            row_name, row_email, row_phone, row_company, row_title, source_name
        )
        if extracted:
            records.append(extracted)
            logger.info(
                "Processing candidate from CSV: %s",
                row_name or row_email or f"row-{row_index}",
            )

    logger.info("CSV extraction completed: %d candidate(s) from %s", len(records), source_name)
    return records


def extract_from_csv(csv_path: str | Path) -> ExtractedCandidate | None:
    """Backward-compatible helper returning the first CSV candidate, if any."""
    records = extract_all_from_csv(csv_path)
    return records[0] if records else None


def apply_csv_normalization(extracted: ExtractedCandidate) -> ExtractedCandidate:
    """Apply phone and skill normalization to CSV-extracted data."""
    logger.info("Normalization started for CSV source: %s", extracted.source_name)
    normalized = apply_candidate_normalization(extracted)
    logger.info("Normalization completed for CSV source: %s", extracted.source_name)
    return normalized


class CSVExtractor(BaseExtractor):
    """Adapter for CSV candidate extraction."""

    source_type = "csv"

    def extract(self, source: Path) -> list[ExtractedCandidate]:
        records = extract_all_from_csv(source)
        return [apply_csv_normalization(record) for record in records]

    def extract_many(self, sources: list[Path]) -> list[ExtractedCandidate]:
        results: list[ExtractedCandidate] = []
        for source in sources:
            results.extend(self.extract(source))
        return results
