"""Run and record the required v6 checks before freezing a fresh sample."""

import subprocess
from pathlib import Path

from src.common.io import timestamp, write_json

TESTS = [
    "tests/test_cache_control_grounding.py", "tests/test_multispan_v6.py",
    "tests/test_cache_control_comparison.py", "tests/test_cache_control_failures.py",
    "tests/test_single_attempt_transport.py", "tests/test_adaptive_glyph_grounding.py",
    "tests/test_multispan_v4.py", "tests/test_printable_confusable_grounding.py",
    "tests/test_v5_grounding_modes.py", "tests/test_generalized_glyph_modes.py",
    "tests/test_v6_grounding_modes.py",
]
CODE = [
    "scripts/verify_grounding_v6.py", "scripts/draw_grounding_v6_holdout.py",
    "scripts/run_frozen_v6.py", "scripts/audit_grounding_v6_holdout.py",
    "scripts/report_grounding_v6.py", "scripts/test_grounding_v6.py",
    "src/extraction/cache_control_grounding.py", "src/extraction/multispan_v6.py",
    "src/extraction/single_attempt_transport.py", "src/evaluation/cache_control_comparison.py",
    "src/evaluation/cache_control_failures.py", "src/extraction/pipeline.py", "scripts/extract.py",
]


def run_check(command: list[str]) -> dict:
    """Run a local check and retain its actual status and concise result."""
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    lines = completed.stdout.strip().splitlines()
    return {"command": command, "returncode": completed.returncode,
            "result": lines[-1] if lines else None,
            "blocked_reason": completed.stderr.strip() or completed.stdout.strip()
            if completed.returncode else None}


def main() -> None:
    """Save actual test and lint outcomes once, before any sample-four draw."""
    destination = Path("results/grounding_development_v6/test_status.json")
    if destination.exists():
        raise ValueError("v6_test_status_already_exists")
    missing = [name for name in TESTS + CODE if not Path(name).is_file()]
    if missing:
        raise ValueError("v6_required_test_or_code_missing:" + ";".join(missing))
    tests = run_check([".venv/bin/pytest", "-q", *TESTS])
    lint = run_check([".venv/bin/ruff", "check", *CODE, *TESTS])
    passed = tests["returncode"] == lint["returncode"] == 0
    report = {"status": "passed" if passed else "failed", "completed_at": timestamp(),
              "blocked_reason": None if passed else "v6_required_tests_or_lint_failed",
              "tests": tests, "lint": lint, "sample4_not_drawn": not Path(
                  "data/raw/grounding_v6_sample4").exists()}
    write_json(destination, report)
    print({"status": report["status"], "tests": tests["result"], "lint": lint["result"]})
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
