"""Match structured and unstructured candidate records across sources."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional

from models import ExtractedCandidate
from normalizers.email_normalizer import normalize_email

logger = logging.getLogger(__name__)


def normalize_name(name: str) -> str:
    """Normalize a name for exact matching (lowercase, collapsed whitespace)."""
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", name.lower())
    return " ".join(cleaned.split())


def normalize_filename_name(filename: str) -> str:
    """Derive a normalized name hint from a resume filename like John_Doe.pdf."""
    stem = filename.rsplit(".", 1)[0]
    return normalize_name(stem.replace("_", " ").replace("-", " "))


class _UnionFind:
    """Disjoint-set structure for grouping matched records."""

    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, index: int) -> int:
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self.parent[root_right] = root_left


def _record_emails(record: ExtractedCandidate) -> set[str]:
    return {normalize_email(email) for email in record.data.emails if email and str(email).strip()}


def _record_phones(record: ExtractedCandidate) -> set[str]:
    return {phone.strip() for phone in record.data.phones if phone}


def _record_names(record: ExtractedCandidate) -> set[str]:
    names: set[str] = set()
    if record.data.full_name:
        names.add(normalize_name(record.data.full_name))
    if record.source_type == "resume":
        names.add(normalize_filename_name(record.source_name))
    return {name for name in names if name}


def _records_match(left: ExtractedCandidate, right: ExtractedCandidate) -> Optional[str]:
    """
    Return the match reason if two records refer to the same candidate.

    Matching policy (strict):
      1. Email — if BOTH records have emails, match ONLY on identical email.
         Never merge records with different emails.
      2. Phone — use ONLY when at least one record lacks an email.
      3. Name  — use ONLY when BOTH records lack email AND phone.
    """
    left_emails = _record_emails(left)
    right_emails = _record_emails(right)

    # Priority 1: both have emails — match only on overlap; never merge different emails.
    if left_emails and right_emails:
        if left_emails & right_emails:
            return "email"
        return None

    # Extract phones once for priority 2 and 3 checks.
    left_phones = _record_phones(left)
    right_phones = _record_phones(right)

    # Priority 2: phone — only when email is missing on at least one side.
    if left_phones and right_phones and (left_phones & right_phones):
        return "phone"

    # Priority 3: name — only when both email and phone are unavailable.
    if not left_emails and not right_emails:
        if not left_phones and not right_phones:
            left_names = _record_names(left)
            right_names = _record_names(right)
            if left_names & right_names:
                return "name"

    return None


def _build_indexes(
    records: list[ExtractedCandidate],
) -> tuple[dict[str, list[int]], dict[str, list[int]], dict[str, list[int]]]:
    """Build hash-based indexes for email, phone, and name keys.

    Returns three dicts mapping normalized key → list of record indices.
    This enables O(n) matching instead of O(n²) pairwise comparison.
    """
    email_index: dict[str, list[int]] = defaultdict(list)
    phone_index: dict[str, list[int]] = defaultdict(list)
    name_index: dict[str, list[int]] = defaultdict(list)

    for idx, record in enumerate(records):
        for email in _record_emails(record):
            email_index[email].append(idx)
        for phone in _record_phones(record):
            phone_index[phone].append(idx)
        for name in _record_names(record):
            name_index[name].append(idx)

    return email_index, phone_index, name_index


def _split_on_conflicting_emails(
    group: list[tuple[int, ExtractedCandidate]],
) -> list[list[ExtractedCandidate]]:
    """Split a matched group if members have conflicting (different non-empty) emails.

    This is a post-merge safety net against transitive merges via Union-Find
    that violate the "never merge candidates with different emails" rule.
    """
    # Separate records with emails from those without.
    with_emails: list[tuple[int, ExtractedCandidate, set[str]]] = []
    without_emails: list[ExtractedCandidate] = []

    for _idx, record in group:
        emails = _record_emails(record)
        if emails:
            with_emails.append((_idx, record, emails))
        else:
            without_emails.append(record)

    if not with_emails:
        # No emails at all — single group, no conflict possible.
        return [[rec for _, rec in group]]

    # Cluster email-bearing records by overlapping email sets.
    email_clusters: list[tuple[set[str], list[ExtractedCandidate]]] = []
    for _idx, record, emails in with_emails:
        merged = False
        for cluster_emails, cluster_records in email_clusters:
            if cluster_emails & emails:
                cluster_emails |= emails
                cluster_records.append(record)
                merged = True
                break
        if not merged:
            email_clusters.append((set(emails), [record]))

    if len(email_clusters) == 1:
        # All email-bearing records share overlapping emails — no conflict.
        return [[rec for _, rec in group]]

    # Conflict detected: split. Assign email-less records to the first cluster.
    result: list[list[ExtractedCandidate]] = []
    for i, (_cluster_emails, cluster_records) in enumerate(email_clusters):
        if i == 0:
            cluster_records.extend(without_emails)
        result.append(cluster_records)

    logger.warning(
        "Split merged group into %d sub-groups due to conflicting emails",
        len(result),
    )
    return result


def match_candidates(records: list[ExtractedCandidate]) -> list[list[ExtractedCandidate]]:
    """
    Group extracted records that belong to the same candidate.

    Uses index-based matching for O(n) performance, then validates
    groups to prevent transitive merges across different emails.
    """
    if not records:
        return []

    union_find = _UnionFind(len(records))
    email_index, phone_index, name_index = _build_indexes(records)

    # Union by shared email.
    for _email, indices in email_index.items():
        for k in range(1, len(indices)):
            if _records_match(records[indices[0]], records[indices[k]]):
                union_find.union(indices[0], indices[k])

    # Union by shared phone.
    for _phone, indices in phone_index.items():
        for k in range(1, len(indices)):
            if _records_match(records[indices[0]], records[indices[k]]):
                union_find.union(indices[0], indices[k])

    # Union by shared name.
    for _name, indices in name_index.items():
        for k in range(1, len(indices)):
            if _records_match(records[indices[0]], records[indices[k]]):
                union_find.union(indices[0], indices[k])

    # Collect groups.
    grouped: dict[int, list[tuple[int, ExtractedCandidate]]] = {}
    for index, record in enumerate(records):
        root = union_find.find(index)
        grouped.setdefault(root, []).append((index, record))

    # Post-merge validation: split groups with conflicting emails.
    groups: list[list[ExtractedCandidate]] = []
    for raw_group in grouped.values():
        groups.extend(_split_on_conflicting_emails(raw_group))

    logger.info("Candidate matching completed: %d record(s) -> %d profile(s)", len(records), len(groups))

    for group in groups:
        if len(group) > 1:
            label = group[0].data.full_name or group[0].source_name
            logger.info("Resume matched successfully: %d source(s) for '%s'", len(group), label)

    return groups
