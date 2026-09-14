"""Audit sample-four failures after scoring, using only saved frozen-rule artifacts."""

from scripts.draw_grounding_v6_holdout import frozen_checks_v6, saved_jobs
from scripts.verify_grounding_v6 import OUTPUT, REPORT
from src.common.io import write_json
from src.evaluation.cache_control_failures import classify_failures


def main() -> None:
    """Save the immutable post-score rejection audit with no model requests."""
    destination = REPORT / "heldout_sample4_failures.json"
    if destination.exists():
        raise ValueError("sample4_failure_audit_already_exists")
    if not all(row["unchanged"] for row in frozen_checks_v6(True)):
        raise ValueError("sample4_frozen_inputs_changed_before_failure_audit")
    report = classify_failures(OUTPUT / "sample4", saved_jobs("v6"),
                               REPORT / "heldout_sample4_scores.json")
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
