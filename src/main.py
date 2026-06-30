"""CLI entry point for the Eightfold Candidate Transformer pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from common import candidate_to_output_profile
from confidence import apply_confidence
from extractors.csv_extractor import CSVExtractor
from extractors.resume_extractor import ResumeExtractor
from matcher import match_candidates
from merger import merge_candidates
from models import ExtractedCandidate
from projector import ProjectionError, default_projection, load_projection_config, project_candidate
from validator import validate_candidate, validate_output_profile, validate_projected_output

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("eightfold-candidate-transformer")

DEFAULT_OUTPUT = Path("output/profiles.json")


def _resolve_path(path_str: str | None) -> Path | None:
    """Convert a CLI path string to a Path object."""
    return Path(path_str) if path_str else None


def _collect_csv_records(csv_path: Path | None) -> list[ExtractedCandidate]:
    """Extract all candidates from a CSV file."""
    if csv_path is None:
        return []

    if not csv_path.exists():
        logger.warning("CSV file not found: %s; skipping CSV source", csv_path)
        return []

    logger.info("Stage 1: CSV extraction")
    try:
        return CSVExtractor().extract(csv_path)
    except Exception as exc:
        logger.warning("CSV extraction failed for %s: %s", csv_path, exc)
        return []


def _collect_resume_records(
    resume_path: Path | None,
    resumes_dir: Path | None,
) -> list[ExtractedCandidate]:
    """Extract candidates from a single resume and/or a resume directory."""
    records: list[ExtractedCandidate] = []
    extractor = ResumeExtractor()

    if resume_path:
        if not resume_path.exists():
            logger.warning("Resume file not found: %s; skipping", resume_path)
        else:
            logger.info("Stage 2a: Single resume extraction")
            try:
                records.extend(extractor.extract(resume_path))
            except Exception as exc:
                logger.warning("Resume extraction failed for %s: %s", resume_path, exc)

    if resumes_dir:
        logger.info("Stage 2b: Resume folder extraction")
        try:
            records.extend(extractor.extract(resumes_dir))
        except Exception as exc:
            logger.warning("Resume folder extraction failed for %s: %s", resumes_dir, exc)

    return records


def _apply_projection(candidate, config_path: Path | None) -> dict:
    """Apply custom projection config or fall back to the default output shape."""
    if config_path is None:
        return default_projection(candidate)

    config = load_projection_config(config_path)
    if config is None:
        logger.warning("Using default projection due to config load failure")
        return default_projection(candidate)

    try:
        return project_candidate(candidate, config)
    except ProjectionError as exc:
        logger.warning("Projection error: %s; using default projection", exc)
        return default_projection(candidate)


def _process_candidate_group(
    group: list[ExtractedCandidate],
    config_path: Path | None,
    use_projection: bool,
) -> dict | None:
    """Merge, score, validate, and serialize one matched candidate group."""
    label = (
        group[0].data.full_name
        or (group[0].data.emails[0] if group[0].data.emails else None)
        or group[0].source_name
    )
    logger.info("Processing candidate: %s", label)

    try:
        merged = merge_candidates(group)
        source_types = [record.source_type for record in group]
        merged = apply_confidence(merged, source_types)

        if use_projection:
            output_data = _apply_projection(merged, config_path)
        else:
            output_data = candidate_to_output_profile(merged)

        warnings = validate_candidate(merged)
        if isinstance(output_data, dict):
            warnings.extend(validate_output_profile(output_data))
            warnings.extend(validate_projected_output(output_data))

        if warnings:
            logger.warning(
                "Candidate '%s' validation completed with %d warning(s)",
                label,
                len(warnings),
            )
        else:
            logger.info("Candidate profile generated: %s", label)

        return output_data
    except Exception as exc:
        logger.warning("Failed to process candidate '%s': %s", label, exc)
        return None


def run_pipeline(
    csv_path: Path | None,
    resume_path: Path | None,
    resumes_dir: Path | None,
    config_path: Path | None,
    output_path: Path = DEFAULT_OUTPUT,
) -> int:
    """Execute the multi-candidate transformation pipeline."""
    logger.info("Pipeline started")

    csv_records = _collect_csv_records(csv_path)
    resume_records = _collect_resume_records(resume_path, resumes_dir)
    all_records = csv_records + resume_records

    if not all_records:
        logger.warning("No data extracted from any source; output will not be written")
        return 1

    logger.info(
        "Stage 3: Candidate matching (%d CSV + %d resume record(s))",
        len(csv_records),
        len(resume_records),
    )
    matched_groups = match_candidates(all_records)

    logger.info("Stage 4: Merge and confidence scoring for %d profile(s)", len(matched_groups))
    use_projection = config_path is not None and config_path.exists()

    profiles: list[dict] = []
    for group in matched_groups:
        profile = _process_candidate_group(group, config_path, use_projection)
        if profile:
            profiles.append(profile)

    if not profiles:
        logger.warning("No candidate profiles generated")
        return 1

    logger.info("Stage 5: Saving %d profile(s) to %s", len(profiles), output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(profiles, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        logger.info("Output saved successfully: %s", output_path)
    except OSError as exc:
        logger.warning("Failed to save output to %s: %s", output_path, exc)
        return 1

    logger.info("Pipeline completed successfully: %d profile(s)", len(profiles))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Eightfold Candidate Transformer — ingest, normalize, merge, "
            "and export canonical candidate profiles."
        ),
    )
    parser.add_argument("--csv", dest="csv_path", help="Path to candidate CSV file")
    parser.add_argument("--resume", dest="resume_path", help="Path to a single resume PDF")
    parser.add_argument(
        "--resumes",
        dest="resumes_dir",
        help="Path to a folder containing resume PDFs",
    )
    parser.add_argument("--config", dest="config_path", help="Path to projection config JSON")
    parser.add_argument(
        "--output",
        dest="output_path",
        default=str(DEFAULT_OUTPUT),
        help="Path for output profiles JSON (default: output/profiles.json)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    csv_path = _resolve_path(args.csv_path)
    resume_path = _resolve_path(args.resume_path)
    resumes_dir = _resolve_path(args.resumes_dir)
    config_path = _resolve_path(args.config_path)
    output_path = Path(args.output_path)

    if not csv_path and not resume_path and not resumes_dir:
        logger.warning("At least one of --csv, --resume, or --resumes must be provided")
        parser.print_help()
        return 1

    return run_pipeline(csv_path, resume_path, resumes_dir, config_path, output_path)


if __name__ == "__main__":
    sys.exit(main())
