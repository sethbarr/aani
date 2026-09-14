"""Compare saved exploratory system proposals with v5 entirely offline."""

import argparse
from pathlib import Path

from scripts.replay_system_grounding_v4 import load_saved_jobs
from src.chemistry.export_cache import file_hash
from src.common.io import digest, read_json, read_jsonl, write_json, write_jsonl
from src.extraction.printable_confusable_grounding import GLYPH_POLICY_V5
from src.systems.config import load_system_config, system_paths
from src.systems.grounding_v5 import audit_system_candidate_v5, bind_system_job_v5

OUTPUT_FILES = (
    "observations.jsonl",
    "candidate_audit.jsonl",
    "metrics.json",
    "job_status.jsonl",
)


def protected_paths(root: Path, interim: Path, results: Path) -> list[Path]:
    """List immutable inputs, v4 evidence, and frozen analysis files."""
    paths = {
        root / "config/analysis.json",
        root / "docs/analysis_plan.md",
        root / "config/grounding_glyphs_v4.json",
        root / "src/extraction/adaptive_glyph_grounding.py",
        root / "src/extraction/multispan_v4.py",
        root / "src/systems/grounding_v4.py",
    }
    for relative in ("extraction", "extraction_payloads", "grounding_v4"):
        directory = interim / relative
        if directory.exists():
            paths.update(path for path in directory.rglob("*") if path.is_file())
    v4_results = results / "grounding_v4"
    if v4_results.exists():
        paths.update(path for path in v4_results.rglob("*") if path.is_file())
    return sorted(paths)


def propolis_semantic_outcome(paths: dict[str, Path], audits: list[dict]) -> dict:
    """Apply saved semantic classifications after successful v5 grounding."""
    previous = read_json(paths["interim"] / "extraction/semantic_review.json")
    by_hash = {row["candidate_hash"]: row for row in previous["decisions"]}
    advancing = [row for row in audits if row["v5_accepted"] and not row["v4_accepted"]]
    decisions: list[dict] = []
    for audit in advancing:
        saved = by_hash.get(audit["candidate_hash"])
        if saved is None:
            raise ValueError("propolis_saved_semantic_classification_missing")
        decisions.append({
            "candidate_hash": audit["candidate_hash"],
            "target_name_as_written": audit["candidate"]["target_name_as_written"],
            "grounding_outcome": "passed_v5",
            "semantic_secondary": saved["semantic_secondary"],
            "semantic_direct_observation": saved["semantic_direct_observation"],
            "focal_eligible": saved["focal_eligible"],
            "semantic_outcome": (
                "focal_eligible" if saved["focal_eligible"]
                else "excluded_from_focal_retention"
            ),
            "basis": (
                "Saved semantic audit classification; the grounding-only exclusion is removed."
            ),
        })
    return {
        "status": "complete",
        "review_type": "v5_reassessment_from_saved_semantic_classifications",
        "grounding_passes_advancing": len(advancing),
        "reviewed": len(decisions),
        "semantic_secondary": sum(row["semantic_secondary"] for row in decisions),
        "semantic_direct_observations": sum(
            row["semantic_direct_observation"] for row in decisions
        ),
        "focal_eligible": sum(row["focal_eligible"] for row in decisions),
        "focal_retained": sum(
            row["semantic_outcome"] == "focal_eligible" for row in decisions
        ),
        "decisions": decisions,
    }


def replay_once(root: Path, slug: str, output: Path) -> dict:
    """Read every saved response and apply v5 once to each candidate."""
    config = load_system_config(root / "config/systems" / f"{slug}.json")
    paths = system_paths(config, root)
    jobs = load_saved_jobs(paths["interim"], paths["results"])
    threshold = read_json(root / "config/analysis.json")["extraction_confidence"]
    records: list[dict] = []
    audits: list[dict] = []
    statuses: list[dict] = []
    for job in jobs:
        bound = bind_system_job_v5(job)
        write_json(output / "jobs" / f"{bound['input_hash']}.json", bound)
        response = paths["interim"] / "extraction/responses" / f"{job['input_hash']}.json"
        envelope = read_json(response)
        if envelope["input_hash"] != job["input_hash"]:
            raise ValueError("saved_response_input_hash_mismatch")
        candidates = envelope["output"]["records"]
        for index, candidate in enumerate(candidates):
            record, audit = audit_system_candidate_v5(
                candidate, job, bound, config, threshold,
            )
            audit.update(candidate_index=index, response_sha256=file_hash(response))
            audits.append(audit)
            if record is not None:
                records.append({
                    **record,
                    "response_hash": digest(envelope),
                    "extraction_request_hash": envelope.get("request_hash"),
                })
        statuses.append({
            "source_id": job["source_id"],
            "input_hash": job["input_hash"],
            "v5_input_hash": bound["input_hash"],
            "candidates": len(candidates),
            "status": "saved_response_replayed",
            "response_sha256": file_hash(response),
        })
    v4_records = read_jsonl(paths["interim"] / "grounding_v4/run/observations.jsonl")
    v4_by_id = {row["record_id"]: row for row in v4_records}
    v5_by_id = {row["record_id"]: row for row in records}
    v4_ids = set(v4_by_id)
    v5_ids = set(v5_by_id)
    audit_v4_ids = {row["record_id"] for row in audits if row["v4_accepted"]}
    if audit_v4_ids != v4_ids:
        raise ValueError("v4_validator_drift_from_saved_system_replay")
    direction_changes = [
        {
            "record_id": record_id,
            "v4_direction": v4_by_id[record_id]["direction"],
            "v5_direction": v5_by_id[record_id]["direction"],
        }
        for record_id in sorted(v4_ids & v5_ids)
        if v4_by_id[record_id]["direction"] != v5_by_id[record_id]["direction"]
    ]
    metrics = {
        "system": slug,
        "mode": "printable_confusables_v5_on_system_single_quote_v1",
        "status": "complete",
        "blocked_reason": None,
        "offline": True,
        "model_calls": 0,
        "network_calls": 0,
        "jobs_replayed": len(jobs),
        "candidate_records": len(audits),
        "v4_accepted": len(v4_ids),
        "v5_accepted": len(v5_ids),
        "exact_grounding_routes": sum(
            row["quote_grounding_route"] == "exact" for row in records
        ),
        "control_glyph_grounding_routes": sum(
            row["quote_grounding_route"] == "source_anchored_control_glyph"
            for row in records
        ),
        "printable_confusable_grounding_routes": sum(
            row["quote_grounding_route"] == "source_anchored_printable_confusable"
            for row in records
        ),
        "newly_accepted_record_ids": sorted(v5_ids - v4_ids),
        "lost_record_ids": sorted(v4_ids - v5_ids),
        "unchanged_record_ids": sorted(v4_ids & v5_ids),
        "direction_changes": direction_changes,
    }
    if slug == "propolis":
        semantic = propolis_semantic_outcome(paths, audits)
        write_json(output / "semantic_review.json", semantic)
        metrics["semantic_review"] = {
            key: semantic[key]
            for key in (
                "grounding_passes_advancing",
                "reviewed",
                "semantic_secondary",
                "semantic_direct_observations",
                "focal_eligible",
                "focal_retained",
            )
        }
    write_jsonl(output / "observations.jsonl", records)
    write_jsonl(output / "candidate_audit.jsonl", audits)
    write_jsonl(output / "job_status.jsonl", statuses)
    write_json(output / "metrics.json", metrics)
    return metrics


def run(root: Path, slug: str) -> dict:
    """Create one system comparison and verify a second offline replay."""
    root = root.resolve()
    config = load_system_config(root / "config/systems" / f"{slug}.json")
    paths = system_paths(config, root)
    output = paths["interim"] / "grounding_v5"
    result = paths["results"] / "grounding_v5"
    if output.exists() or result.exists():
        raise ValueError("refusing_to_overwrite_system_v5_comparison")
    if read_json(root / "config/grounding_glyphs_v5.json") != GLYPH_POLICY_V5:
        raise ValueError("v5_policy_config_mismatch")
    protected = [
        {"path": str(path.relative_to(root)), "sha256": file_hash(path)}
        for path in protected_paths(root, paths["interim"], paths["results"])
    ]
    metrics = replay_once(root, slug, output / "run")
    replay_once(root, slug, output / "replay")
    names = list(OUTPUT_FILES)
    if slug == "propolis":
        names.append("semantic_review.json")
    names.extend(
        str(path.relative_to(output / "run"))
        for path in sorted((output / "run/jobs").glob("*.json"))
    )
    comparisons = [
        {
            "path": name,
            "sha256": file_hash(output / "run" / name),
            "identical": file_hash(output / "run" / name)
            == file_hash(output / "replay" / name),
        }
        for name in names
    ]
    preservation = [
        {
            **row,
            "unchanged": file_hash(root / row["path"]) == row["sha256"],
        }
        for row in protected
    ]
    passed = (
        all(row["identical"] for row in comparisons)
        and all(row["unchanged"] for row in preservation)
        and not metrics["lost_record_ids"]
        and not metrics["direction_changes"]
    )
    report = {
        "status": "passed" if passed else "failed",
        "metrics": metrics,
        "byte_comparisons": comparisons,
        "protected_inputs": preservation,
        "model_calls": 0,
        "network_calls": 0,
    }
    write_json(result / "comparison.json", report)
    return report


def main() -> None:
    """Run selected saved systems through v5 and verify offline replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--system",
        action="append",
        required=True,
        choices=("propolis", "monarch", "attine_actino"),
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    failed = False
    for slug in args.system:
        report = run(args.root, slug)
        print({"verification": report["status"], **report["metrics"]})
        failed = failed or report["status"] != "passed"
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
