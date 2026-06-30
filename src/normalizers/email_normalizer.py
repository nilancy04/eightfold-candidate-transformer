"""Email normalization utilities."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import ProvenanceEntry

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
    re.IGNORECASE,
)


def is_valid_email(email: str) -> bool:
    """Return True if the email matches a basic RFC-like format."""
    return bool(EMAIL_PATTERN.match(email.strip()))


def normalize_email(raw: str) -> str:
    """Normalize a single email: trim whitespace and lowercase."""
    return raw.strip().lower()


def normalize_emails(raw_emails: list[str]) -> list[str]:
    """
    Normalize emails: trim, lowercase, remove duplicates and invalid entries.

    Examples:
        RAHUL.VERMA@gmail.com -> rahul.verma@gmail.com
        CASE.TEST@GMAIL.COM   -> case.test@gmail.com
    """
    seen: set[str] = set()
    result: list[str] = []

    for raw in raw_emails:
        if not raw or not str(raw).strip():
            continue

        normalized = normalize_email(str(raw))
        if not is_valid_email(normalized):
            logger.warning("Invalid email ignored: %s", raw)
            continue
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    return result


def normalize_emails_with_provenance(
    raw_emails: list[str],
    source_name: str,
) -> tuple[list[str], list["ProvenanceEntry"]]:
    """Normalize emails and return provenance entries for normalization decisions.

    Tracks: email lowercased, invalid email removed, duplicate email removed.
    """
    from models import ProvenanceEntry

    provenance: list[ProvenanceEntry] = []
    seen: set[str] = set()
    result: list[str] = []

    for raw in raw_emails:
        if not raw or not str(raw).strip():
            continue

        original = str(raw).strip()
        normalized = normalize_email(original)

        if not is_valid_email(normalized):
            logger.warning("Invalid email ignored: %s", raw)
            provenance.append(ProvenanceEntry(
                field="emails", source=source_name,
                method="normalization",
                details=f"invalid email removed: {original}",
            ))
            continue

        if original != normalized:
            provenance.append(ProvenanceEntry(
                field="emails", source=source_name,
                method="normalization",
                details=f"email lowercased: {original} -> {normalized}",
            ))

        if normalized in seen:
            provenance.append(ProvenanceEntry(
                field="emails", source=source_name,
                method="normalization",
                details=f"duplicate email removed: {normalized}",
            ))
            continue

        seen.add(normalized)
        result.append(normalized)

    return result, provenance
