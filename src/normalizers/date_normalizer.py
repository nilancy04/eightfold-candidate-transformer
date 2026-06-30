"""Date normalization to YYYY-MM format."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

from dateutil import parser as date_parser

logger = logging.getLogger(__name__)

YYYY_MM_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")
YEAR_ONLY_PATTERN = re.compile(r"^(\d{4})$")


def normalize_date(raw: str) -> Optional[str]:
    """
    Convert a date string to YYYY-MM format whenever possible.

    Returns None if the value cannot be parsed.
    """
    if not raw or not str(raw).strip():
        return None

    text = str(raw).strip()

    if YYYY_MM_PATTERN.match(text):
        return text

    if YEAR_ONLY_PATTERN.match(text):
        return f"{text}-01"

    try:
        parsed = date_parser.parse(text, fuzzy=True, default=datetime(2000, 1, 1))
        return parsed.strftime("%Y-%m")
    except (ValueError, OverflowError, TypeError) as exc:
        logger.debug("Could not normalize date '%s': %s", raw, exc)
        return None


def normalize_dates_in_experience(entries: list[dict]) -> list[dict]:
    """Normalize start/end dates on experience dict entries."""
    normalized: list[dict] = []
    for entry in entries:
        item = dict(entry)
        if item.get("start_date"):
            item["start_date"] = normalize_date(item["start_date"]) or item["start_date"]
        if item.get("end_date"):
            item["end_date"] = normalize_date(item["end_date"]) or item["end_date"]
        normalized.append(item)
    return normalized


def normalize_dates_in_education(entries: list[dict]) -> list[dict]:
    """Normalize start/end dates on education dict entries."""
    normalized: list[dict] = []
    for entry in entries:
        item = dict(entry)
        if item.get("start_date"):
            item["start_date"] = normalize_date(item["start_date"]) or item["start_date"]
        if item.get("end_date"):
            item["end_date"] = normalize_date(item["end_date"]) or item["end_date"]
        normalized.append(item)
    return normalized
