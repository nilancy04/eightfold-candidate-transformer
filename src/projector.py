"""Config-based output projection for candidate profiles."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from models import Candidate, ProjectionConfig

logger = logging.getLogger(__name__)

ARRAY_INDEX_PATTERN = re.compile(r"^(.+)\[(\d+)\]$")
ARRAY_WILDCARD_PATTERN = re.compile(r"^(.+)\[\]\.(.+)$")


class ProjectionError(Exception):
    """Raised when projection config references a missing required field."""


def _get_nested_value(obj: Any, path: str) -> Any:
    """
    Resolve a dotted/bracket path against a candidate dict.

    Supports paths such as full_name, emails[0], skills[].name, location.city.
    """
    if not path:
        return obj

    wildcard = ARRAY_WILDCARD_PATTERN.match(path)
    if wildcard:
        array_path, sub_field = wildcard.group(1), wildcard.group(2)
        array_value = _get_nested_value(obj, array_path)
        if not isinstance(array_value, list):
            return None
        return [
            item.get(sub_field) if isinstance(item, dict) else getattr(item, sub_field, None)
            for item in array_value
        ]

    current = obj
    for part in path.split("."):
        if current is None:
            return None

        index_match = ARRAY_INDEX_PATTERN.match(part)
        if index_match:
            key, index_str = index_match.group(1), index_match.group(2)
            index = int(index_str)
            if key:
                current = current.get(key) if isinstance(current, dict) else getattr(current, key, None)
            if not isinstance(current, list) or index >= len(current):
                return None
            current = current[index]
        elif isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None

    return current


def _set_nested_value(target: dict[str, Any], path: str, value: Any) -> None:
    """Set a value at a dotted path, creating intermediate dicts as needed."""
    parts = path.split(".")
    current = target
    for index, part in enumerate(parts):
        if index == len(parts) - 1:
            current[part] = value
        else:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]


def load_projection_config(config_path: str | Path) -> Optional[ProjectionConfig]:
    """
    Load projection configuration from a JSON file.

    Returns None and logs a warning if the file is missing or invalid.
    """
    path = Path(config_path)

    if not path.exists():
        logger.warning("Projection config not found: %s", path)
        return None

    try:
        with path.open("r", encoding="utf-8") as handle:
            raw_config = json.load(handle)
        config = ProjectionConfig.model_validate(raw_config)
        logger.info("Projection config loaded: %s", path)
        return config
    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON in projection config %s: %s", path, exc)
        return None
    except Exception as exc:
        logger.warning("Failed to load projection config %s: %s", path, exc)
        return None


def project_candidate(
    candidate: Candidate,
    config: ProjectionConfig,
) -> dict[str, Any]:
    """
    Project a candidate into a custom output shape based on config.

    Supports field selection, renaming, path mapping, and confidence inclusion.
    """
    source_data = candidate.model_dump(mode="json")
    output: dict[str, Any] = {}

    for field_config in config.fields:
        source_path = field_config.from_ or field_config.path
        value = _get_nested_value(source_data, source_path)

        if value is None:
            if config.on_missing == "error":
                raise ProjectionError(
                    f"Missing required field for projection path '{source_path}'"
                )
            if config.on_missing == "omit":
                continue
            value = None

        _set_nested_value(output, field_config.path, value)

    if config.include_confidence:
        output["overall_confidence"] = candidate.overall_confidence
        output["field_confidence"] = dict(candidate.field_confidence)

    logger.info("Projection applied: %d field(s) mapped", len(config.fields))
    return output


def default_projection(candidate: Candidate) -> dict[str, Any]:
    """Return the full candidate as a dictionary when no config is provided."""
    return candidate.model_dump(mode="json")
