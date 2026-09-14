"""Replay the held-out sample offline and verify its frozen inputs and sampling history."""

import base64
import hashlib
import subprocess
from pathlib import Path

from scripts.draw_grounding_holdout import (
    CACHE,
    PROTOCOL,
    RAW,
    REPORT,
    SNAPSHOT,
    V4,
    unchanged_inputs,
)
from scripts.verify_day2 import compare_artifacts, file_hash, frozen_checks
from scripts.verify_grounding_development import scientific_names
from src.common.io import read_json, timestamp, write_json
from src.evaluation.glyph_comparison import compare_proposal_samples
from src.evaluation.identity_comparison import score_variant

REPLAY = Path("data/interim/grounding_v4_sample3_replay")
RECOVERED = ("src/extraction/pipeline.py", "scripts/extract.py")


def replay_input_checks() -> list[dict]:
    """Check live dependencies and the byte-exact copies of concurrently edited runners."""
    checks = []
    for row in unchanged_inputs():
        path = (Path("data/interim/grounding_v4_sample3_frozen_code") / row["path"]
                if row["path"] in RECOVERED else Path(row["path"]))
        checks.append({**row, "replay_input_path": str(path),
                       "replay_matches_predraw_hash": path.is_file()
                       and file_hash(path) == row["sha256"]})
    return checks


def execute_frozen_offline() -> dict:
    """Execute the pinned runner copies in a new process with offline cache access only."""
    command = [".venv/bin/python", "-m", "scripts.run_frozen_holdout"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    path = REPLAY / "metrics.json"
    metrics = read_json(path) if path.is_file() else {}
    complete = (completed.returncode == 0 and metrics.get("chunks") == 3
                and metrics.get("complete_papers") == 1 and not metrics.get("response_failures")
                and not metrics.get("unattempted_chunks") and not metrics.get("blocked_reason"))
    return {"status": "complete" if complete else "blocked", "command": command,
            "offline": True, "model_network_requests": 0, "metrics": metrics,
            "blocked_reason": None if complete else metrics.get("blocked_reason")
            or completed.stderr.strip() or completed.stdout.strip() or "offline_run_incomplete"}


def response_hash(cache: dict) -> str:
    """Hash the exact last HTTP response bytes from an existing cache entry."""
    return hashlib.sha256(base64.b64decode(cache["attempts"][-1]["body_base64"])).hexdigest()


def request_evidence(protocol: dict) -> list[dict]:
    """Compare each new request and response with both earlier saved samples."""
    checks = []
    for request in protocol["requests"]:
        filename = f"{request['request_hash']}.json"
        current_path = CACHE / "http" / filename
        current = read_json(current_path)
        originals = [read_json(Path(request["original_cache"])), read_json(
            Path("data/raw/grounding_v3_repeat/http") / filename)]
        old_hashes = [response_hash(original) for original in originals]
        new_hash = response_hash(current)
        checks.append({
            "chunk_index": request["chunk_index"], "request_hash": request["request_hash"],
            "sample3_cache": str(current_path), "sample3_cache_sha256": file_hash(current_path),
            "descriptors_identical": all(
                original["request"] == current["request"] == request["descriptor"]
                for original in originals),
            "sample1_response_bytes_sha256": old_hashes[0],
            "sample2_response_bytes_sha256": old_hashes[1],
            "sample3_response_bytes_sha256": new_hash,
            "new_response_bytes_distinct_from_both": new_hash not in old_hashes,
            "http_response_count": len(current["attempts"]),
            "transport_attempts": current["transport_attempts"],
        })
    return checks


def chronology_evidence(protocol: dict, sampling: dict, score: dict, audit: dict) -> dict:
    """Check the recorded pre-draw freeze and score-before-audit order."""
    validation = read_json(REPORT / "heldout_validation.json")
    first_attempt = min(row["started_at"] for row in sampling["attempt_log"])
    return {
        "prepared_at": protocol["prepared_at"], "first_model_attempt_at": first_attempt,
        "sampling_finished_at": sampling["finished_at"],
        "validation_started_at": validation["started_at"],
        "score_completed_at": score["score_completed_at"],
        "audit_started_at": audit["audit_started_at"],
        "recorded_order_correct": protocol["prepared_at"] < first_attempt
        <= sampling["finished_at"] <= validation["started_at"]
        <= validation["finished_at"] <= score["score_completed_at"] <= audit["audit_started_at"],
        "pre_score_inspection_reported": score["candidate_failure_details_inspected_before_scoring"],
        "score_sha256_unchanged_since_audit": file_hash(REPORT / "heldout_scores.json")
        == audit["score_sha256"],
        "protocol_sha256_unchanged_since_scoring": file_hash(PROTOCOL) == score["protocol_sha256"],
        "snapshot_sha256_unchanged_since_preparation": file_hash(SNAPSHOT)
        == protocol["snapshot_sha256"],
    }


def verify() -> dict:
    """Replay sample three and compare its scientific artifacts and fixed stage counts."""
    protocol = read_json(PROTOCOL)
    sampling = read_json(REPORT / "heldout_sampling.json")
    score = read_json(REPORT / "heldout_scores.json")
    audit = read_json(REPORT / "heldout_failures.json")
    if not all(row["replay_matches_predraw_hash"] for row in replay_input_checks()):
        raise ValueError("heldout_frozen_inputs_changed_before_replay")
    if any(report["status"] != "complete" for report in (sampling, score, audit)):
        raise ValueError("heldout_sampling_scoring_or_audit_incomplete")
    sample_paths = {REPORT / name for name in (
        "heldout_sampling.json", "heldout_scores.json", "heldout_failures.json",
        "heldout_protocol.json", "heldout_preserved_inputs.json", "heldout_validation.json")}
    for directory in (CACHE, RAW, V4):
        sample_paths.update(path for path in directory.rglob("*") if path.is_file())
    before = {path: file_hash(path) for path in sorted(sample_paths)}
    replay = execute_frozen_offline()
    names = scientific_names(V4) + ["source_ant_identities.json", "glyph_policy.json",
                                    "glyph_source_hashes.json", "glyph_grounding_audit.jsonl"]
    comparisons = compare_artifacts(V4, REPLAY, names) if replay["status"] == "complete" else []
    baseline = read_json(Path("results/recall_baseline.json"))
    replay_score = score_variant(REPLAY, baseline, None)
    counts_match = (replay_score["status"] == "complete"
                    and replay_score["groups"] == score["sample3_v4"]["groups"]
                    and replay_score["inventory"] == score["sample3_v4"]["inventory"])
    identity = compare_proposal_samples(RAW, V4, True)
    requests = request_evidence(protocol)
    chronology = chronology_evidence(protocol, sampling, score, audit)
    protected = replay_input_checks()
    sample_checks = [{"path": str(path), "sha256": digest,
                      "unchanged": path.is_file() and file_hash(path) == digest}
                     for path, digest in before.items()]
    frozen = frozen_checks()
    passed = (replay["status"] == "complete" and bool(comparisons)
              and all(row["identical"] for row in comparisons) and counts_match
              and identity["status"] == "complete"
              and len(requests) == sampling["network_attempts"] == 3
              and sampling["transport_retries"] == 0
              and all(row["descriptors_identical"] and row["new_response_bytes_distinct_from_both"]
                      and row["http_response_count"] == 1 for row in requests)
              and all(row["replay_matches_predraw_hash"] for row in protected)
              and all(row["unchanged"] for row in sample_checks)
              and all(row["matches_frozen_commit"] for row in frozen)
              and chronology["recorded_order_correct"]
              and not chronology["pre_score_inspection_reported"]
              and all(chronology[key] for key in (
                  "score_sha256_unchanged_since_audit", "protocol_sha256_unchanged_since_scoring",
                  "snapshot_sha256_unchanged_since_preparation")))
    return {
        "status": "passed" if passed else "failed", "verified_at": timestamp(),
        "blocked_reason": None if passed else "heldout_replay_or_preservation_check_failed",
        "model_network_requests_during_replay": 0,
        "sampling_model_calls": sampling["network_attempts"],
        "sampling_transport_retries": sampling["transport_retries"],
        "offline_replay": replay, "scientific_files_compared": len(comparisons),
        "byte_comparisons": comparisons, "baseline_convention_counts_identical": counts_match,
        "replay_groups": replay_score["groups"], "sample_identity": identity,
        "request_and_response_checks": requests, "chronology": chronology,
        "protected_inputs": protected, "heldout_artifacts": sample_checks, "frozen_files": frozen,
        "initial_live_runner_verification": read_json(REPORT / "heldout_verification.json"),
        "concurrent_live_runner_changes": [row["path"] for row in protected if not row["unchanged"]],
        "recovery_scope": "The two runner copies exactly match the pre-draw SHA256 hashes. "
        "Live concurrent v5 edits were preserved. V4 policy and validator were never changed.",
    }


def main() -> None:
    """Save a new verification artifact without overwriting any previous run."""
    destination = REPORT / "heldout_frozen_verification.json"
    if destination.exists() or REPLAY.exists():
        raise ValueError("heldout_offline_verification_already_exists")
    try:
        report = verify()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        report = {"status": "blocked", "blocked_reason": f"{type(error).__name__}: {error}"}
    write_json(destination, report)
    print({key: report.get(key) for key in (
        "status", "blocked_reason", "scientific_files_compared", "baseline_convention_counts_identical")})
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
