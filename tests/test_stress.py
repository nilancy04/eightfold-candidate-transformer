"""Stress test: run the pipeline against 10,000+ candidate CSV."""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from generate_stress_csv import generate_stress_csv  # noqa: E402
from main import run_pipeline  # noqa: E402


def test_stress_10000_candidates(tmp_path: Path) -> None:
    """Pipeline must process 10,000+ rows without crashing and within 60 seconds."""
    random.seed(42)

    csv_path = tmp_path / "candidate_10000.csv"
    generate_stress_csv(csv_path, total_count=10_000)

    output_path = tmp_path / "profiles.json"

    start_time = time.time()
    exit_code = run_pipeline(
        csv_path=csv_path,
        resume_path=None,
        resumes_dir=None,
        config_path=None,
        output_path=output_path,
    )
    elapsed = time.time() - start_time

    assert exit_code == 0, f"Pipeline failed with exit code {exit_code}"
    assert output_path.exists(), "Output file was not created"

    profiles = json.loads(output_path.read_text())
    assert isinstance(profiles, list)
    assert len(profiles) > 0

    # Performance stats.
    print(f"\n{'='*60}")
    print(f"STRESS TEST RESULTS")
    print(f"{'='*60}")
    print(f"Input rows:       10,050 (10,000 + 50 duplicates)")
    print(f"Profiles output:  {len(profiles)}")
    print(f"Execution time:   {elapsed:.2f}s")
    print(f"Rows/second:      {10050 / elapsed:.0f}")
    print(f"{'='*60}")

    # Must complete within 60 seconds.
    assert elapsed < 60, f"Pipeline took {elapsed:.1f}s (limit: 60s)"

    # Validate all profiles have required fields.
    for profile in profiles:
        assert "candidate_id" in profile
        assert "provenance" in profile


def test_stress_profiles_have_valid_confidence(tmp_path: Path) -> None:
    """All stress test profiles should have valid confidence scores."""
    random.seed(42)

    csv_path = tmp_path / "candidate_1000.csv"
    generate_stress_csv(csv_path, total_count=1_000)

    output_path = tmp_path / "profiles.json"
    exit_code = run_pipeline(
        csv_path=csv_path,
        resume_path=None,
        resumes_dir=None,
        config_path=None,
        output_path=output_path,
    )

    assert exit_code == 0
    profiles = json.loads(output_path.read_text())

    for profile in profiles:
        confidence = profile.get("overall_confidence")
        if confidence is not None:
            assert 0.0 <= confidence <= 1.0, f"Invalid confidence: {confidence}"
