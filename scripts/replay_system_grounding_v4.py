"""Compare saved exploratory system proposals with v4 grounding entirely offline."""

import argparse
from pathlib import Path

from src.chemistry.export_cache import file_hash
from src.common.io import digest, read_json, read_jsonl, timestamp, write_json, write_jsonl
from src.extraction.adaptive_glyph_grounding import GLYPH_POLICY_V4
from src.systems.config import load_system_config, system_paths
from src.systems.grounding_v4 import audit_system_candidate_v4, bind_system_job_v4

OUTPUT_FILES = ("observations.jsonl", "candidate_audit.jsonl", "metrics.json", "job_status.jsonl")
METHOD_FILES = (
    "config/grounding_glyphs_v4.json", "src/extraction/adaptive_glyph_grounding.py",
    "src/extraction/glyph_grounding.py", "src/extraction/multispan_v4.py",
    "src/systems/extraction.py", "src/systems/schema.py", "src/systems/grounding_v4.py",
    "scripts/replay_system_grounding_v4.py", "config/analysis.json", "docs/analysis_plan.md",
)


def protected_files(root: Path, interim: Path, results: Path) -> list[dict]:
    """Capture previous system artifacts, primary inputs and method implementation."""
    paths = {root / name for name in METHOD_FILES}
    for directory in (interim, results):
        paths.update(path for path in directory.rglob("*")
                     if path.is_file() and "grounding_v4" not in path.relative_to(directory).parts)
    primary = read_json(root / "results/funnel.json")
    paths.add(root / "results/funnel.json")
    paths.add(root / "results/systems/summary.md")
    paths.update(root / row["path"] for row in primary["input_manifests"])
    return [{"path": str(path.relative_to(root)), "sha256": file_hash(path)}
            for path in sorted(paths)]


def load_saved_jobs(interim: Path, results: Path) -> list[dict]:
    """Require the completed, approved execution selection and immutable payloads."""
    selection = interim / "execution_selection.json"
    if not selection.exists():
        selection = interim / "extraction_payloads/index.json"
    index = read_json(selection)
    approval = read_json(results / "payload_approval.json")
    selected_hashes = [item["input_hash"] for item in index["jobs"]]
    if len(selected_hashes) != len(set(selected_hashes)) or len(selected_hashes) > 12:
        raise ValueError("saved_execution_job_selection_invalid")
    if not approval["approved"] or approval["input_hashes"] != [
        item["input_hash"] for item in index["jobs"]
    ]:
        raise ValueError("saved_execution_approval_mismatch")
    statuses = read_jsonl(interim / "extraction/job_status.jsonl")
    if {row["input_hash"] for row in statuses if row["status"] == "complete"} != set(
        approval["input_hashes"]
    ):
        raise ValueError("saved_execution_incomplete")
    jobs = []
    for item in index["jobs"]:
        path = (interim / item.get("path", f"extraction_payloads/{item['input_hash']}.json")).resolve()
        if not path.is_relative_to(interim.resolve()):
            raise ValueError("source_payload_outside_system")
        job = read_json(path)
        if job["input_hash"] != item["input_hash"]:
            raise ValueError("saved_payload_index_mismatch")
        jobs.append(job)
    return jobs


def replay_once(root: Path, slug: str, output: Path) -> dict:
    """Read saved responses and compare every original candidate exactly once."""
    config = load_system_config(root / "config/systems" / f"{slug}.json")
    paths = system_paths(config, root)
    jobs = load_saved_jobs(paths["interim"], paths["results"])
    if any(job["system_slug"] != slug for job in jobs):
        raise ValueError("cross_system_payload")
    threshold = read_json(root / "config/analysis.json")["extraction_confidence"]
    records, audits, statuses, baseline_ids = [], [], [], set()
    for job in jobs:
        bound = bind_system_job_v4(job)
        write_json(output / "jobs" / f"{bound['input_hash']}.json", bound)
        response = paths["interim"] / "extraction/responses" / f"{job['input_hash']}.json"
        envelope = read_json(response)
        if envelope["input_hash"] != job["input_hash"]:
            raise ValueError("saved_response_input_hash_mismatch")
        candidates = envelope["output"]["records"]
        for index, candidate in enumerate(candidates):
            record, audit = audit_system_candidate_v4(candidate, job, bound, config, threshold)
            audit.update(candidate_index=index, response_sha256=file_hash(response))
            audits.append(audit)
            if audit["baseline_accepted"]:
                baseline_ids.add(audit["record_id"])
            if record is not None:
                records.append({**record, "response_hash": digest(envelope),
                                "extraction_request_hash": envelope.get("request_hash")})
        statuses.append({"source_id": job["source_id"], "input_hash": job["input_hash"],
                         "v4_input_hash": bound["input_hash"], "candidates": len(candidates),
                         "status": "saved_response_replayed", "response_sha256": file_hash(response)})
    saved_ids = {row["record_id"] for row in read_jsonl(paths["interim"] / "extraction/observations.jsonl")}
    saved_metrics = read_json(paths["interim"] / "extraction/metrics.json")
    if baseline_ids != saved_ids or len(audits) != saved_metrics["candidate_records"]:
        raise ValueError("baseline_validator_drift_from_saved_records")
    v4_ids = {row["record_id"] for row in records}
    semantic_ids = {row["record_id"] for row in read_jsonl(
        paths["interim"] / "semantic_review/observations.jsonl"
    )}
    metrics = {
        "system": slug, "mode": "glyph_v4_on_system_single_quote_v1", "status": "complete",
        "blocked_reason": None, "offline": True, "model_calls": 0, "network_calls": 0,
        "jobs_replayed": len(jobs), "empty_response_jobs": sum(row["candidates"] == 0 for row in statuses),
        "candidate_records": len(audits), "baseline_accepted": sum(row["baseline_accepted"] for row in audits),
        "v4_accepted": len(records),
        "exact_quote_matches": sum((row["quote_match"] or {}).get("route") == "exact" for row in audits),
        "glyph_quote_matches": sum((row["quote_match"] or {}).get("route") == "source_anchored_control_glyph" for row in audits),
        "newly_accepted_record_ids": sorted(v4_ids - baseline_ids),
        "lost_record_ids": sorted(baseline_ids - v4_ids),
        "unchanged_record_ids": sorted(v4_ids & baseline_ids),
        "prior_semantic_inclusions_surviving": len(v4_ids & semantic_ids),
        "new_records_requiring_semantic_review": len(v4_ids - baseline_ids),
        "full_multispan_validator_run": False, "downstream_rerun": False,
    }
    if config.positive_control:
        reference = read_json(paths["results"] / "positive_control.json")
        metrics["reference_recall_unchanged"] = v4_ids == baseline_ids
        metrics["prior_reference_recovered"] = reference["recovered_reference_items"]
        metrics["fixed_reference_denominator"] = reference["fixed_reference_denominator"]
    write_jsonl(output / "observations.jsonl", records)
    write_jsonl(output / "candidate_audit.jsonl", audits)
    write_jsonl(output / "job_status.jsonl", statuses)
    write_json(output / "metrics.json", metrics)
    return metrics


def run(root: Path, slug: str) -> dict:
    """Create an isolated comparison once and verify replay and input preservation."""
    root = root.resolve()
    config = load_system_config(root / "config/systems" / f"{slug}.json")
    paths = system_paths(config, root)
    output, results = paths["interim"] / "grounding_v4", paths["results"] / "grounding_v4"
    if output.exists() or results.exists():
        raise ValueError("refusing_to_overwrite_system_v4_comparison")
    if read_json(root / "config/grounding_glyphs_v4.json") != GLYPH_POLICY_V4:
        raise ValueError("v4_policy_config_mismatch")
    snapshot = protected_files(root, paths["interim"], paths["results"])
    config_name = f"config/systems/{slug}.json"
    snapshot.append({"path": config_name, "sha256": file_hash(root / config_name)})
    write_json(results / "protocol.json", {
        "recorded_at": timestamp(), "system": slug, "user_request": "try the grounding with our new v4 methods",
        "mode": "glyph_v4_on_system_single_quote_v1", "glyph_policy": GLYPH_POLICY_V4,
        "scope": "Existing v4 quote matcher on all saved single-quote proposals; original section, target, direction and confidence checks remain active.",
        "limitations": "No new proposals or multi-span fields are generated. This comparison cannot evaluate full multi-span identity extraction or recover missing model proposals.",
        "network_calls": 0, "model_calls": 0, "protected_inputs": snapshot,
    })
    metrics = replay_once(root, slug, output / "run")
    replay_once(root, slug, output / "replay")
    names = list(OUTPUT_FILES) + [str(path.relative_to(output / "run"))
                                for path in sorted((output / "run/jobs").glob("*.json"))]
    comparisons = [{"path": name, "sha256": file_hash(output / "run" / name),
                    "identical": file_hash(output / "run" / name) == file_hash(output / "replay" / name)}
                   for name in names]
    preserved = [{**row, "unchanged": file_hash(root / row["path"]) == row["sha256"]}
                 for row in snapshot]
    verified = all(row["identical"] for row in comparisons) and all(row["unchanged"] for row in preserved)
    report = {"status": "passed" if verified else "failed", "completed_at": timestamp(),
              "metrics": metrics, "byte_comparisons": comparisons, "protected_inputs": preserved,
              "model_calls": 0, "network_calls": 0}
    write_json(results / "comparison.json", report)
    return report


def main() -> None:
    """Run explicitly selected systems through local v4 comparison and replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system", action="append", required=True,
                        choices=("propolis", "monarch", "attine_actino"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    for slug in args.system:
        report = run(args.root, slug)
        print({"verification": report["status"], **report["metrics"]})
        if report["status"] != "passed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
