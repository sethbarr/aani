"""Classify held-out failures only after the complete frozen-rule score is saved."""

from scripts.draw_grounding_holdout import CORPUS, REPORT, V4, unchanged_inputs
from src.common.io import timestamp, write_json
from src.evaluation.heldout_failures import classify_heldout_failures
from src.extraction.pipeline import make_jobs


def main() -> None:
    """Write post-score evidence once without any rule or candidate changes."""
    destination = REPORT / "heldout_failures.json"
    if destination.exists():
        raise ValueError("heldout_failure_audit_already_exists")
    if not all(row["unchanged"] for row in unchanged_inputs()):
        raise ValueError("heldout_frozen_inputs_changed_before_audit")
    started = timestamp()
    jobs = make_jobs(CORPUS, grounding_version="multispan_v4")
    report = classify_heldout_failures(V4, jobs, REPORT / "heldout_scores.json")
    report["audit_started_at"] = started
    report["audit_completed_at"] = timestamp()
    write_json(destination, report)
    print({key: report[key] for key in (
        "status", "blocked_reason", "rejected_records", "category_counts",
        "ordered_failure_reason_counts", "first_failure_substitutions",
        "all_rejected_span_substitutions",
    )})
    if report["blocked_reason"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
