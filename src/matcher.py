"""Match structured and unstructured candidate records across sources."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Optional

from models import ExtractedCandidate
from normalizers.email_normalizer import normalize_email
from normalizers.phone_normalizer import normalize_phones

logger = logging.getLogger(__name__)

# Minimum similarity for conservative fuzzy name matching (0–1).
_FUZZY_NAME_THRESHOLD = 0.92


def normalize_name(name: str) -> str:
    """Normalize a name for exact matching (lowercase, collapsed whitespace)."""
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", name.lower())
    return " ".join(cleaned.split())


def normalize_filename_name(filename: str) -> str:
    """Derive a normalized name hint from a resume filename like John_Doe.pdf."""
    stem = filename.rsplit(".", 1)[0]
    return normalize_name(stem.replace("_", " ").replace("-", " "))


def _token_sorted_name(name: str) -> str:
    """Return a token-sorted normalized name for order-insensitive comparison."""
    tokens = normalize_name(name).split()
    return " ".join(sorted(tokens))


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
    return set(normalize_phones(phone for phone in record.data.phones if phone))


def _record_names(record: ExtractedCandidate) -> set[str]:
    names: set[str] = set()
    if record.data.full_name:
        normalized = normalize_name(record.data.full_name)
        names.add(normalized)
        names.add(_token_sorted_name(record.data.full_name))
    if record.source_type == "resume":
        names.add(normalize_filename_name(record.source_name))
    return {name for name in names if name}


def _exact_names_overlap(left_names: set[str], right_names: set[str]) -> bool:
    """Return True when normalized or token-sorted names match exactly."""
    return bool(left_names & right_names)


def _fuzzy_names_match(left: str, right: str) -> bool:
    """
    Conservative fuzzy name match.

    Requires at least two name tokens on each side to avoid merging people
    who only share a common first name (e.g. two different "John" records).
    """
    left_norm = normalize_name(left)
    right_norm = normalize_name(right)
    if left_norm == right_norm:
        return True

    left_tokens = left_norm.split()
    right_tokens = right_norm.split()
    if len(left_tokens) < 2 or len(right_tokens) < 2:
        return False

    if sorted(left_tokens) == sorted(right_tokens):
        return True

    return SequenceMatcher(None, left_norm, right_norm).ratio() >= _FUZZY_NAME_THRESHOLD


def _fuzzy_names_overlap(left_names: set[str], right_names: set[str]) -> bool:
    """Return True when any name pair passes conservative fuzzy matching."""
    for left in left_names:
        for right in right_names:
            if _fuzzy_names_match(left, right):
                return True
    return False


def _fuzzy_name_bucket(name: str) -> Optional[str]:
    """Bucket multi-token names by first and last token for conservative fuzzy matching."""
    tokens = normalize_name(name).split()
    if len(tokens) < 2:
        return None
    return f"{tokens[0]}|{tokens[-1]}"


def _record_fuzzy_buckets(record: ExtractedCandidate) -> set[str]:
    buckets: set[str] = set()
    if record.data.full_name:
        bucket = _fuzzy_name_bucket(record.data.full_name)
        if bucket:
            buckets.add(bucket)
    if record.source_type == "resume":
        bucket = _fuzzy_name_bucket(normalize_filename_name(record.source_name))
        if bucket:
            buckets.add(bucket)
    return buckets


def _records_match(left: ExtractedCandidate, right: ExtractedCandidate) -> Optional[str]:
    """
    Return the match reason if two records refer to the same candidate.

    Matching policy (strict, priority order):
      1. Email — if BOTH records have emails, match ONLY on identical email.
         Never merge records with different emails.
      2. Phone — use ONLY when at least one record lacks an email.
      3. Exact normalized name — when BOTH records lack email AND phone.
      4. Conservative fuzzy name — same contact constraints as (3).
    """
    left_emails = _record_emails(left)
    right_emails = _record_emails(right)

    # Priority 1: both have emails — match only on overlap; never merge different emails.
    if left_emails and right_emails:
        if left_emails & right_emails:
            return "email"
        return None

    left_phones = _record_phones(left)
    right_phones = _record_phones(right)

    # Priority 2: phone — only when email is missing on at least one side.
    if left_phones and right_phones and (left_phones & right_phones):
        return "phone"

    # Priority 3/4: name — only when both email and phone are unavailable.
    if not left_emails and not right_emails and not left_phones and not right_phones:
        left_names = _record_names(left)
        right_names = _record_names(right)
        if _exact_names_overlap(left_names, right_names):
            return "name"
        if _fuzzy_names_overlap(left_names, right_names):
            return "fuzzy_name"

    return None


def _build_indexes(
    records: list[ExtractedCandidate],
) -> tuple[
    dict[str, list[int]],
    dict[str, list[int]],
    dict[str, list[int]],
    dict[str, list[int]],
]:
    """Build hash-based indexes for email, phone, name, and fuzzy-name keys."""
    email_index: dict[str, list[int]] = defaultdict(list)
    phone_index: dict[str, list[int]] = defaultdict(list)
    name_index: dict[str, list[int]] = defaultdict(list)
    fuzzy_index: dict[str, list[int]] = defaultdict(list)

    for idx, record in enumerate(records):
        for email in _record_emails(record):
            email_index[email].append(idx)
        for phone in _record_phones(record):
            phone_index[phone].append(idx)
        for name in _record_names(record):
            name_index[name].append(idx)
        for bucket in _record_fuzzy_buckets(record):
            fuzzy_index[bucket].append(idx)

    return email_index, phone_index, name_index, fuzzy_index


def _split_on_conflicting_emails(
    group: list[tuple[int, ExtractedCandidate]],
) -> list[list[ExtractedCandidate]]:
    """Split a matched group if members have conflicting (different non-empty) emails."""
    with_emails: list[tuple[int, ExtractedCandidate, set[str]]] = []
    without_emails: list[ExtractedCandidate] = []

    for _idx, record in group:
        emails = _record_emails(record)
        if emails:
            with_emails.append((_idx, record, emails))
        else:
            without_emails.append(record)

    if not with_emails:
        return [[rec for _, rec in group]]

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
        return [[rec for _, rec in group]]

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
    email_index, phone_index, name_index, fuzzy_index = _build_indexes(records)

    for _email, indices in email_index.items():
        for k in range(1, len(indices)):
            if _records_match(records[indices[0]], records[indices[k]]):
                union_find.union(indices[0], indices[k])

    for _phone, indices in phone_index.items():
        for k in range(1, len(indices)):
            if _records_match(records[indices[0]], records[indices[k]]):
                union_find.union(indices[0], indices[k])

    for _name, indices in name_index.items():
        for k in range(1, len(indices)):
            if _records_match(records[indices[0]], records[indices[k]]):
                union_find.union(indices[0], indices[k])

    for indices in fuzzy_index.values():
        if len(indices) < 2:
            continue
        for left_pos in range(len(indices)):
            for right_pos in range(left_pos + 1, len(indices)):
                left_idx = indices[left_pos]
                right_idx = indices[right_pos]
                reason = _records_match(records[left_idx], records[right_idx])
                if reason == "fuzzy_name":
                    union_find.union(left_idx, right_idx)

    grouped: dict[int, list[tuple[int, ExtractedCandidate]]] = {}
    for index, record in enumerate(records):
        root = union_find.find(index)
        grouped.setdefault(root, []).append((index, record))

    groups: list[list[ExtractedCandidate]] = []
    for raw_group in grouped.values():
        groups.extend(_split_on_conflicting_emails(raw_group))

    logger.info("Candidate matching completed: %d record(s) -> %d profile(s)", len(records), len(groups))

    for group in groups:
        if len(group) > 1:
            label = group[0].data.full_name or group[0].source_name
            logger.info("Resume matched successfully: %d source(s) for '%s'", len(group), label)

    return groups
