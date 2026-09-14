"""Verify completed reader measurements against raw requests and frozen scoring."""

import base64
import hashlib
import json
from pathlib import Path

from scripts.detection_variance import DRAWS, PRIVATE, REPORT, descriptor, verify
from src.common.io import digest, read_json, read_jsonl, timestamp, write_json
from src.evaluation.comparison import reference_rows
from src.evaluation.recall import score_species, summarise_group


def check_draw(draw: str) -> dict:
    """Reconcile raw responses, adapter records, scores, and transport evidence."""
    saved = read_json(REPORT / f"{draw}.json")
    validation = read_jsonl(PRIVATE / draw / "validation.jsonl")
    candidates = []
    failures = []
    response_hashes = []
    model_names = []
    chunks = []
    for idx in range(3):
        job = read_json(PRIVATE / "jobs" / f"{draw[0]}_{idx}.json")
        request = descriptor(job)
        request_hash = digest(request)
        cache_path = PRIVATE / draw / "cache" / "http" / f"{request_hash}.json"
        response_path = PRIVATE / draw / "responses" / f"{idx}.json"
        if not cache_path.exists():
            failures.append(f"chunk_{idx}_cache_missing")
            continue
        cache = read_json(cache_path)
        good = (cache["request"] == request and len(cache["transport_attempts"]) == 1
                and cache["transport_attempts"][0]["http_status"] == 200)
        response_bytes = base64.b64decode(cache["attempts"][0]["body_base64"])
        body = json.loads(response_bytes)
        response_hashes.append(hashlib.sha256(response_bytes).hexdigest())
        model_names.append(body.get("model", "unspecified"))
        if not good:
            failures.append(f"chunk_{idx}_request_mismatch")
        if not response_path.exists():
            outcomes = [row for row in saved["sampling"]["outcomes"] if row["chunk_index"] == idx]
            expected_failure = len(outcomes) == 1 and outcomes[0]["status"] == "failed"
            if not expected_failure:
                failures.append(f"chunk_{idx}_unexplained_missing_response")
            chunks.append({"chunk_index": idx, "request_hash": request_hash,
                           "request_matches": good, "response_saved_in_transport_cache": True,
                           "parse_failure": outcomes[0].get("reason") if outcomes else None,
                           "missingness_reported": expected_failure})
            continue
        envelope = read_json(response_path)
        if (envelope["input_hash"] != job["input_hash"]
                or envelope["request_hash"] != request_hash):
            failures.append(f"chunk_{idx}_envelope_mismatch")
        chunks.append({"chunk_index": idx, "request_hash": request_hash,
                       "response_sha256": hashlib.sha256(response_path.read_bytes()).hexdigest(),
                       "request_matches": good})
        for number, raw in enumerate(envelope["output"]["records"]):
            candidate_id = f"{draw}:{idx}:{number}"
            matches = [row for row in validation if row["candidate_id"] == candidate_id]
            if len(matches) != 1:
                failures.append(f"validation_missing_or_duplicate:{candidate_id}")
                continue
            entry = matches[0]
            if entry["raw"] != raw:
                failures.append(f"raw_changed:{candidate_id}")
            if draw[0] == "B" and entry["adapted"] is not None:
                adapted = entry["adapted"].copy()
                span = adapted.pop("name_evidence")
                support = adapted.pop("supporting_evidence")
                if (adapted != raw or support != [] or span != {
                    "block_id": raw["block_id"], "section": raw["section"],
                    "quote": raw["evidence_quote"],
                }):
                    failures.append(f"adapter_added_evidence:{candidate_id}")
            candidates.append({"candidate_id": candidate_id, "record": raw,
                               "grounding_status": "passed" if entry["validated"] else "failed",
                               "blocked_reason": None})
    refs = reference_rows(read_json(Path("results/recall_baseline.json")))
    species = [score_species(row, candidates) for row in refs]
    primary = summarise_group(species, "PRIMARY")
    if saved["status"] == "complete":
        for stage in ("detection", "survival", "correctness"):
            if saved["primary"][stage] != primary["stages"][stage]["species_count"]:
                failures.append(f"score_mismatch:{stage}")
    if len(candidates) != len(validation) or len(candidates) != saved["total_candidates"]:
        failures.append("candidate_inventory_mismatch")
    return {"draw": draw, "failures": failures, "chunks": chunks,
            "response_hashes": response_hashes, "resolved_models": sorted(set(model_names)),
            "candidate_count": len(candidates), "baseline_scores_match": not failures}


def main() -> None:
    """Save an independent reconciliation and enforce distinct request executions."""
    integrity = verify()
    rows = [check_draw(draw) for draw in DRAWS]
    ids = [identity for row in rows for identity in row["response_hashes"]]
    protocol = read_json(PRIVATE / "execution_protocol.json")
    starts = [read_json(PRIVATE / draw / "sampling.json")["attempt_log"][0]["started_at"]
              for draw in DRAWS]
    chronology = protocol["execution_prepared_at"] < min(starts)
    passed = (not any(row["failures"] for row in rows) and len(ids) == 24
              and len(set(ids)) == 24 and chronology)
    result = {"status": "passed" if passed else "failed", "verified_at": timestamp(),
              "integrity": integrity, "draws": rows, "response_count": len(ids),
              "distinct_response_byte_hashes": len(set(ids)), "preparation_precedes_calls": chronology,
              "model_requests_during_verification": 0,
              "response_id_note": "Provider responses omit IDs; independence is checked using fresh caches, attempt logs, and distinct response-byte hashes."}
    write_json(REPORT / "reconciliation.json", result)
    print(json.dumps({key: result[key] for key in (
        "status", "response_count", "distinct_response_byte_hashes", "preparation_precedes_calls")}))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
