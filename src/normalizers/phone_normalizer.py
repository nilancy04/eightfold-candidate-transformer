"""Phone number normalization using the phonenumbers library."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Optional

import phonenumbers
from phonenumbers import NumberParseException

if TYPE_CHECKING:
    from models import ProvenanceEntry

logger = logging.getLogger(__name__)

DEFAULT_REGION = "IN"
E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")

# Known invalid placeholder numbers to reject before parsing.
BLOCKED_DIGIT_SEQUENCES = {
    "123",
    "0000000000",
    "1111111111",
}


def _digits_only(raw: str) -> str:
    return re.sub(r"\D", "", raw)


def _is_blocked_phone(raw: str) -> bool:
    """Return True for known-invalid or obviously fake phone numbers."""
    digits = _digits_only(raw)
    if not digits or len(digits) < 7:
        return True
    if digits in BLOCKED_DIGIT_SEQUENCES:
        return True
    # Reject numbers where every digit is identical (e.g. 0000000000, 1111111111).
    if len(set(digits)) == 1:
        return True
    return False


def is_valid_e164(phone: str) -> bool:
    """Return True if the phone is a valid E.164 formatted number."""
    return bool(E164_PATTERN.match(phone.strip()))


def normalize_phone(raw: str, default_region: str = DEFAULT_REGION) -> Optional[str]:
    """
    Normalize a phone number to E.164 format (e.g. +919876543210).

    Returns None for invalid or empty numbers; invalid numbers are logged as warnings.
    """
    if not raw or not str(raw).strip():
        return None

    text = str(raw).strip()
    if _is_blocked_phone(text):
        logger.warning("Invalid phone number ignored: %s", raw)
        return None

    try:
        parsed = phonenumbers.parse(text, default_region)
        if not phonenumbers.is_valid_number(parsed):
            logger.warning("Invalid phone number ignored: %s", raw)
            return None
        formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        if _is_blocked_phone(formatted):
            logger.warning("Invalid phone number ignored: %s", raw)
            return None
        return formatted
    except NumberParseException:
        logger.warning("Could not parse phone number: %s", raw)
        return None


def normalize_phones(raw_phones: list[str], default_region: str = DEFAULT_REGION) -> list[str]:
    """Normalize a list of phones, removing duplicates and invalid entries."""
    seen: set[str] = set()
    result: list[str] = []

    for raw in raw_phones:
        normalized = normalize_phone(raw, default_region)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    return result


def normalize_phones_with_provenance(
    raw_phones: list[str],
    source_name: str,
    default_region: str = DEFAULT_REGION,
) -> tuple[list[str], list["ProvenanceEntry"]]:
    """Normalize phones and return provenance entries for normalization decisions.

    Tracks: invalid phone removed, phone converted to E.164, duplicate phone removed.
    """
    from models import ProvenanceEntry

    provenance: list[ProvenanceEntry] = []
    seen: set[str] = set()
    result: list[str] = []

    for raw in raw_phones:
        if not raw or not str(raw).strip():
            continue

        original = str(raw).strip()
        normalized = normalize_phone(original, default_region)

        if normalized is None:
            provenance.append(ProvenanceEntry(
                field="phones", source=source_name,
                method="normalization",
                details=f"invalid phone removed: {original}",
            ))
            continue

        if original != normalized:
            provenance.append(ProvenanceEntry(
                field="phones", source=source_name,
                method="normalization",
                details=f"phone converted to E.164: {original} -> {normalized}",
            ))

        if normalized in seen:
            provenance.append(ProvenanceEntry(
                field="phones", source=source_name,
                method="normalization",
                details=f"duplicate phone removed: {normalized}",
            ))
            continue

        seen.add(normalized)
        result.append(normalized)

    return result, provenance
