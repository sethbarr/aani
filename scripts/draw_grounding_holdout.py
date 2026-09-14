"""Predeclare and draw exactly one held-out v2 sample for the frozen v4 rule."""

import argparse
from pathlib import Path

import httpx

from scripts.verify_day2 import file_hash, frozen_checks
from src.common.environment import load_local_environment
from src.common.io import read_json, read_jsonl, timestamp, write_json
from src.extraction.gemini import request_gemini
from src.extraction.heldout_transport import HeldoutHTTP
from src.extraction.pipeline import export_jobs, make_jobs

REPORT = Path("results/grounding_development_v4")
SNAPSHOT = REPORT / "heldout_preserved_inputs.json"
PROTOCOL = REPORT / "heldout_protocol.json"
CACHE = Path("data/raw/grounding_v4_sample3")
RAW = Path("data/interim/extraction_saverschek_multispan_v2_sample3")
V4 = Path("data/interim/extraction_saverschek_multispan_v4_sample3")
CORPUS = Path("data/interim/corpus_targeted_saverschek")
JOBS = Path("data/interim/extraction_jobs_saverschek_heldout_sample3")


def protected_paths() -> set[Path]:
    """Collect all prior grounding artifacts and the v4 implementation dependencies."""
    previous = read_json(REPORT / "preserved_inputs.json")
    paths = {Path(row["path"]) for row in previous["files"]}
    paths.update(Path(row["path"]) for row in previous["allowed_mode_integration_files"])
    paths.update(Path("src/extraction").glob("*.py"))
    paths.update(Path(name) for name in (
        "config/grounding_glyphs_v4.json", "src/common/cache.py", "src/common/io.py",
        "src/evaluation/recall.py", "src/evaluation/comparison.py",
        "src/evaluation/identity_comparison.py", "src/evaluation/heldout_comparison.py",
    ))
    directories = list(Path("results").glob("grounding_development_v*"))
    directories += list(Path("data/interim").glob("extraction_saverschek*"))
    directories += list(Path("data/interim").glob("extraction_jobs_saverschek*"))
    directories += list(Path("data/interim").glob("grounding_v4_replay"))
    for directory in directories:
        paths.update(path for path in directory.rglob("*") if path.is_file())
    return paths


def prepare() -> dict:
    """Freeze prior files and request identities before sample three can exist."""
    if any(path.exists() for path in (SNAPSHOT, PROTOCOL, CACHE, RAW, V4, JOBS)):
        raise ValueError("heldout_sample3_preparation_or_output_already_exists")
    jobs = make_jobs(CORPUS, grounding_version="multispan_v2")
    original = read_json(Path("data/interim/extraction_saverschek_multispan_v2/run_manifest.json"))
    if len(jobs) != 3 or [job["input_hash"] for job in jobs] != original["input_hashes"]:
        raise ValueError("heldout_original_v2_jobs_changed")
    requests = []
    for job in jobs:
        envelope_path = Path("data/interim/extraction_saverschek_multispan_v2/responses") / f"{job['input_hash']}.json"
        envelope = read_json(envelope_path)
        cache_path = Path("data/raw/http") / f"{envelope['request_hash']}.json"
        saved = read_json(cache_path)
        requests.append({"chunk_index": job["chunk_index"], "input_hash": job["input_hash"],
                         "request_hash": envelope["request_hash"], "original_cache": str(cache_path),
                         "original_cache_sha256": file_hash(cache_path), "descriptor": saved["request"]})
    snapshot = {"captured_at": timestamp(), "files": [
        {"path": str(path), "sha256": file_hash(path)} for path in sorted(protected_paths())
    ]}
    write_json(SNAPSHOT, snapshot)
    protocol = {
        "sample": 3, "role": "held-out model draw", "prepared_at": timestamp(),
        "status": "prepared_before_sampling", "model": "gemini-3.8-flash", "provider": "gemini",
        "source_id": "SAVERSCHEK2010", "jobs": 3, "cache": str(CACHE), "raw_output": str(RAW),
        "grounding_configuration_sampled": "multispan_v2", "rules_applied": "multispan_v4",
        "network_policy": "One HTTP response per job. One extra attempt only after a transport error; every attempt is persisted. No retries for HTTP, parsing, schema, or grounding failures.",
        "inspection_order": ["draw_sample3", "apply_frozen_v4_offline", "save_baseline_convention_scores",
                             "inspect_and_classify_failures", "verify_offline_replay", "report"],
        "rule_changes_after_sampling": "forbidden",
        "verdict_scope": "Describe glyph failures and stage counts on this untouched draw; one paper and panel with a known reference cannot establish population performance.",
        "snapshot_path": str(SNAPSHOT), "snapshot_sha256": file_hash(SNAPSHOT),
        "frozen_files": frozen_checks(), "requests": requests,
    }
    write_json(PROTOCOL, protocol)
    export_jobs(jobs, JOBS / "v2")
    export_jobs(make_jobs(CORPUS, grounding_version="multispan_v4"), JOBS / "v4")
    return {"status": "prepared", "protected_files": len(snapshot["files"]), "jobs": len(jobs)}


def unchanged_inputs() -> list[dict]:
    """Rehash every frozen input without loading any new candidate or failure."""
    snapshot = read_json(SNAPSHOT)
    return [{**row, "unchanged": Path(row["path"]).is_file()
             and file_hash(Path(row["path"])) == row["sha256"]} for row in snapshot["files"]]


def draw() -> dict:
    """Collect three fixed v2 responses without reading or classifying any failures."""
    protocol = read_json(PROTOCOL)
    if file_hash(SNAPSHOT) != protocol["snapshot_sha256"] or not all(row["unchanged"] for row in unchanged_inputs()):
        raise ValueError("heldout_frozen_inputs_changed_before_sampling")
    if CACHE.exists() or RAW.exists() or (REPORT / "heldout_sampling.json").exists():
        raise ValueError("heldout_sample3_already_started_no_resampling")
    jobs = make_jobs(CORPUS, grounding_version="multispan_v2")
    if [job["input_hash"] for job in jobs] != [row["input_hash"] for row in protocol["requests"]]:
        raise ValueError("heldout_predeclared_job_identity_changed")
    expected = {row["request_hash"]: row["descriptor"] for row in protocol["requests"]}
    write_json(RAW / "run_manifest.json", {
        "sample": 3, "role": "held-out model draw", "started_at": timestamp(),
        "model": protocol["model"], "provider": protocol["provider"], "jobs": len(jobs),
        "grounding_version": "multispan_v2", "corpus": str(CORPUS),
        "input_hashes": [job["input_hash"] for job in jobs],
        "source_ant_identities": {job["source_id"]: job["source_ant_identity"] for job in jobs},
        "corpus_papers": len(read_jsonl(CORPUS / "manifest.jsonl")),
        "raw_proposals_only": True, "protocol_path": str(PROTOCOL),
    })
    load_local_environment()
    client = httpx.Client(timeout=180, follow_redirects=False, transport=httpx.HTTPTransport(retries=0))
    cache = HeldoutHTTP(CACHE, expected, client)
    outcomes = []
    try:
        for job in jobs:
            try:
                envelope = request_gemini(job, cache, protocol["model"])
                path = RAW / "responses" / f"{job['input_hash']}.json"
                write_json(path, envelope)
                outcomes.append({"chunk_index": job["chunk_index"], "status": "response_saved",
                                 "request_hash": envelope["request_hash"], "response_path": str(path),
                                 "response_sha256": file_hash(path)})
            except (OSError, RuntimeError, ValueError, KeyError, httpx.HTTPError) as error:
                outcomes.append({"chunk_index": job["chunk_index"], "status": "blocked",
                                 "blocked_reason": f"{type(error).__name__}: {error}"})
            print({"sample": 3, "job": job["chunk_index"], "status": outcomes[-1]["status"]}, flush=True)
    finally:
        cache.close()
    reasons = [row["blocked_reason"] for row in outcomes if row["status"] == "blocked"]
    report = {
        "sample": 3, "role": "held-out model draw", "finished_at": timestamp(),
        "status": "complete" if len(outcomes) == 3 and not reasons else "blocked",
        "blocked_reason": ";".join(reasons) or None, "cache": str(CACHE), "raw_output": str(RAW),
        "network_attempts": len(cache.attempt_log), "transport_retries": sum(
            row["retry_reason"] is not None for row in cache.attempt_log),
        "attempt_log": cache.attempt_log, "outcomes": outcomes,
        "failure_candidates_inspected": False,
    }
    write_json(REPORT / "heldout_sampling.json", report)
    return {key: report[key] for key in ("status", "blocked_reason", "network_attempts", "transport_retries")}


def main() -> None:
    """Prepare once or execute the predeclared held-out sample once."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    result = prepare() if args.prepare else draw()
    print(result)
    if result["status"] == "blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
