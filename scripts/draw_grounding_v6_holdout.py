"""Freeze v6, draw one sample four, and save its scores before exposing failures."""

import argparse
import base64
import hashlib
import shutil
import signal
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import FrameType

import httpx

from scripts.verify_day2 import compare_artifacts, file_hash, frozen_checks
from scripts.verify_grounding_development import scientific_names
from scripts.verify_grounding_v6 import OUTPUT, REPORT, preservation_checks
from src.common.environment import load_local_environment
from src.common.io import read_json, timestamp, write_json
from src.extraction.gemini import request_gemini
from src.extraction.pipeline import export_jobs, make_jobs
from src.extraction.single_attempt_transport import SingleAttemptHTTP

START = datetime(2026, 9, 13, 19, 20, 5, tzinfo=UTC)
DEADLINE = START + timedelta(minutes=90)
CORPUS = Path("data/interim/corpus_targeted_saverschek")
CACHE = Path("data/raw/grounding_v6_sample4")
RAW = Path("data/interim/extraction_saverschek_multispan_v2_sample4")
JOBS = Path("data/interim/extraction_jobs_saverschek_v6_sample4")
PROTOCOL = REPORT / "heldout_sample4_protocol.json"
CODE = Path("data/interim/grounding_v6_sample4_frozen_code")
RUNNERS = ("src/extraction/pipeline.py", "scripts/extract.py")


def time_remaining() -> float:
    """Return remaining wall-clock seconds in the user-specified task window."""
    return (DEADLINE - datetime.now(UTC)).total_seconds()


def stop_at_deadline(signum: int, frame: FrameType | None) -> None:
    """Interrupt a stalled network request when the wall-clock time box expires."""
    raise TimeoutError("v6_wall_clock_deadline_reached")


def frozen_checks_v6(use_runner_copies: bool = False) -> list[dict]:
    """Verify the rule frozen before sample four, optionally using pinned runner copies."""
    protocol = read_json(PROTOCOL)
    checks = []
    for row in protocol["frozen_inputs"]:
        path = (CODE / row["path"] if use_runner_copies and row["path"] in RUNNERS
                else Path(row["path"]))
        checks.append({**row, "checked_path": str(path), "unchanged": path.is_file()
                       and file_hash(path) == row["sha256"]})
    return checks


def prepare() -> dict:
    """Freeze tested code and predeclare all requests while sample four is still unseen."""
    if any(path.exists() for path in (PROTOCOL, CACHE, RAW, JOBS, CODE, OUTPUT / "sample4")):
        raise ValueError("sample4_preparation_or_output_already_exists")
    if time_remaining() < 15 * 60:
        raise ValueError("insufficient_time_remaining_for_sample4_draw_and_score")
    if read_json(REPORT / "development_verification.json")["status"] != "passed":
        raise ValueError("sample4_requires_passed_development_regression")
    if read_json(REPORT / "test_status.json")["status"] != "passed":
        raise ValueError("sample4_requires_passed_synthetic_and_regression_tests")
    if not all(row["unchanged"] for row in preservation_checks()):
        raise ValueError("prior_inputs_changed_before_sample4_freeze")
    original = read_json(Path("results/grounding_development_v4/heldout_protocol.json"))
    jobs = make_jobs(CORPUS, grounding_version="multispan_v2")
    if [job["input_hash"] for job in jobs] != [row["input_hash"] for row in original["requests"]]:
        raise ValueError("sample4_jobs_differ_from_original_v2")
    export_jobs(jobs, JOBS / "v2")
    export_jobs(make_jobs(CORPUS, grounding_version="multispan_v6"), JOBS / "v6")
    paths = {Path(row["path"]) for row in read_json(REPORT / "preserved_inputs.json")["files"]}
    for directory in (Path("src/extraction"), Path("src/evaluation"), Path("src/common")):
        paths.update(directory.glob("*.py"))
    paths.update(Path(name) for name in (
        "scripts/extract.py", "scripts/draw_grounding_v6_holdout.py", "scripts/run_frozen_v6.py",
        "scripts/verify_grounding_v6.py", "scripts/audit_grounding_v6_holdout.py",
        "scripts/report_grounding_v6.py", "scripts/test_grounding_v6.py", "config/grounding_glyphs_v6.json",
        "docs/amendment_2026-09-13_v6_cache_side_controls.md",
        "results/grounding_development_v6/test_status.json",
        "results/grounding_development_v6/development_scores.json",
        "results/grounding_development_v6/development_verification.json"))
    paths.update(path for path in JOBS.rglob("*") if path.is_file())
    paths.update(Path("tests").glob("test_cache_control*.py"))
    paths.update(Path(name) for name in ("tests/test_multispan_v6.py", "tests/test_single_attempt_transport.py",
                                       "tests/test_v6_grounding_modes.py"))
    for name in RUNNERS:
        destination = CODE / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(name, destination)
    protocol = {
        "sample": 4, "role": "held_out_for_v6", "prepared_at": timestamp(),
        "task_started_at": START.isoformat(), "deadline": DEADLINE.isoformat(),
        "provider": "gemini", "model": "gemini-3.8-flash", "jobs": 3,
        "requests": original["requests"], "http_cache": str(CACHE),
        "network_policy": "One attempt per job. No retries for any failure.",
        "inspection_order": ["draw", "apply_frozen_v6", "save_scores", "inspect_failures"],
        "rule_changes_after_draw": "forbidden", "scoring": "baseline_structured_direction",
        "frozen_inputs": [{"path": str(path), "sha256": file_hash(path)} for path in sorted(paths)],
        "runner_copies": [{"path": name, "copy": str(CODE / name),
                           "sha256": file_hash(CODE / name)} for name in RUNNERS],
        "frozen_protocol_files": frozen_checks(),
    }
    write_json(PROTOCOL, protocol)
    return {"status": "prepared", "frozen_inputs": len(protocol["frozen_inputs"]),
            "seconds_remaining": time_remaining()}


def saved_jobs(mode: str) -> list[dict]:
    """Read the exact predeclared jobs without rebuilding a prompt or identity context."""
    return [read_json(JOBS / mode / f"{row['input_hash']}.json")
            for row in read_json(JOBS / mode / "index.json")]


def sample() -> dict:
    """Draw exactly one response per original v2 job and save all outcomes."""
    if CACHE.exists() or RAW.exists() or (REPORT / "heldout_sample4_sampling.json").exists():
        raise ValueError("sample4_already_started_no_resampling")
    if time_remaining() < 15 * 60:
        raise ValueError("insufficient_time_remaining_for_sample4_draw_and_score")
    if not all(row["unchanged"] for row in frozen_checks_v6()):
        raise ValueError("sample4_frozen_inputs_changed_before_draw")
    protocol = read_json(PROTOCOL)
    jobs = saved_jobs("v2")
    write_json(RAW / "run_manifest.json", {
        "sample": 4, "role": "held_out_for_v6", "started_at": timestamp(),
        "model": protocol["model"], "provider": "gemini", "jobs": len(jobs),
        "grounding_version": "multispan_v2", "corpus": str(CORPUS),
        "input_hashes": [job["input_hash"] for job in jobs],
        "source_ant_identities": {job["source_id"]: job["source_ant_identity"] for job in jobs},
        "raw_proposals_only": True,
    })
    load_local_environment()
    client = httpx.Client(timeout=120, follow_redirects=False, transport=httpx.HTTPTransport(retries=0))
    cache = SingleAttemptHTTP(CACHE, {row["request_hash"]: row["descriptor"]
                                    for row in protocol["requests"]}, client)
    outcomes = []
    try:
        for job in jobs:
            if time_remaining() <= 0:
                outcomes.append({"chunk_index": job["chunk_index"], "status": "blocked",
                                 "blocked_reason": "time_box_expired_no_further_calls"})
                continue
            try:
                envelope = request_gemini(job, cache, protocol["model"])
                path = RAW / "responses" / f"{job['input_hash']}.json"
                write_json(path, envelope)
                outcomes.append({"chunk_index": job["chunk_index"], "status": "response_saved",
                                 "request_hash": envelope["request_hash"],
                                 "response_path": str(path), "response_sha256": file_hash(path)})
            except (OSError, RuntimeError, ValueError, KeyError, httpx.HTTPError) as error:
                outcomes.append({"chunk_index": job["chunk_index"], "status": "blocked",
                                 "blocked_reason": f"{type(error).__name__}: {error}"})
            print({"sample": 4, "chunk": job["chunk_index"], "status": outcomes[-1]["status"]}, flush=True)
    finally:
        cache.close()
    reasons = [row["blocked_reason"] for row in outcomes if row["status"] == "blocked"]
    report = {"sample": 4, "status": "complete" if not reasons and len(outcomes) == 3 else "blocked",
              "blocked_reason": ";".join(reasons) or None, "finished_at": timestamp(),
              "network_attempts": len(cache.attempt_log), "retries": 0,
              "attempt_log": cache.attempt_log, "outcomes": outcomes,
              "failure_candidates_inspected": False, "seconds_remaining": time_remaining()}
    write_json(REPORT / "heldout_sample4_sampling.json", report)
    return report


def score_sample() -> dict:
    """Apply the frozen validator offline and save scores before diagnostic inspection."""
    from src.evaluation.cache_control_comparison import build_comparison

    destination = REPORT / "heldout_sample4_scores.json"
    if destination.exists():
        raise ValueError("sample4_scores_already_exist")
    if time_remaining() <= 0:
        raise ValueError("time_box_expired_before_sample4_scoring")
    if not all(row["unchanged"] for row in frozen_checks_v6(True)):
        raise ValueError("sample4_rule_changed_before_scoring")
    command = [".venv/bin/python", "-m", "scripts.run_frozen_v6", "--sample4"]
    started = timestamp()
    completed = subprocess.run(command, check=False, capture_output=True, text=True,
                               timeout=max(0.01, time_remaining()))
    write_json(REPORT / "heldout_sample4_validation.json", {
        "started_at": started, "finished_at": timestamp(), "command": command,
        "returncode": completed.returncode, "model_requests": 0,
        "blocked_reason": completed.stderr.strip() if completed.returncode else None,
    })
    report = build_comparison(Path.cwd(), include_sample4=True)
    audit_path = OUTPUT / "sample4/glyph_grounding_audit.jsonl"
    report.update({"score_completed_at": timestamp(), "seconds_remaining": time_remaining(),
                   "completed_within_time_box": time_remaining() >= 0,
                   "failure_candidates_inspected_before_scoring": False,
                   "protocol_sha256": file_hash(PROTOCOL),
                   "sample4_audit_sha256": file_hash(audit_path) if audit_path.is_file() else None})
    if completed.returncode or time_remaining() < 0:
        report["status"] = "blocked"
        report["blocked_reason"] = completed.stderr.strip() or "time_box_expired_before_score_saved"
    write_json(destination, report)
    return {"status": report["status"], "score_path": str(destination),
            "score_sha256": file_hash(destination), "blocked_reason": report["blocked_reason"],
            "sample4_groups": report["sample4_v6"]["groups"],
            "sample4_stage_yield": report["stage_yields"]["sample4_v6"]}


def request_checks() -> list[dict]:
    """Record identical descriptors and response-byte hashes across all four draws."""
    checks = []
    caches = (Path("data/raw"), Path("data/raw/grounding_v3_repeat"),
              Path("data/raw/grounding_v4_sample3"), CACHE)
    for request in read_json(PROTOCOL)["requests"]:
        rows = [read_json(cache / "http" / f"{request['request_hash']}.json") for cache in caches]
        hashes = [hashlib.sha256(base64.b64decode(row["attempts"][-1]["body_base64"])).hexdigest()
                  for row in rows]
        checks.append({"chunk_index": request["chunk_index"], "request_hash": request["request_hash"],
                       "descriptors_identical": all(row["request"] == request["descriptor"] for row in rows),
                       "response_bytes_sha256_samples_1_to_4": hashes,
                       "sample4_response_distinct": hashes[3] not in hashes[:3],
                       "sample4_attempt_count": len(rows[3]["transport_attempts"])})
    return checks


def verify_replay() -> dict:
    """Replay with pinned code and compare all scientific outputs and protocol hashes."""
    from src.evaluation.identity_comparison import score_variant

    path = REPORT / "heldout_sample4_verification.json"
    if path.exists():
        raise ValueError("sample4_replay_verification_already_exists")
    score_path = REPORT / "heldout_sample4_scores.json"
    scores = read_json(score_path)
    audit = read_json(REPORT / "heldout_sample4_failures.json")
    completed = subprocess.run([".venv/bin/python", "-m", "scripts.run_frozen_v6", "--replay"],
                               check=False, capture_output=True, text=True)
    original, replay = OUTPUT / "sample4", Path("data/interim/grounding_v6_replay/sample4")
    names = scientific_names(original) + ["source_ant_identities.json", "glyph_policy.json",
                                          "glyph_source_hashes.json", "glyph_grounding_audit.jsonl"]
    comparisons = compare_artifacts(original, replay, names) if completed.returncode == 0 else []
    replay_score = score_variant(replay, read_json(Path("results/recall_baseline.json")), None)
    counts_match = replay_score["groups"] == scores["sample4_v6"]["groups"]
    inputs = frozen_checks_v6(True)
    prior = preservation_checks()
    requests = request_checks()
    sampling = read_json(REPORT / "heldout_sample4_sampling.json")
    chronology = (read_json(PROTOCOL)["prepared_at"] < sampling["attempt_log"][0]["started_at"]
                  <= sampling["finished_at"] <= scores["score_completed_at"] <= audit["audit_started_at"])
    passed = (completed.returncode == 0 and bool(comparisons) and all(row["identical"] for row in comparisons)
              and counts_match and all(row["unchanged"] for row in inputs + prior)
              and all(row["descriptors_identical"] and row["sample4_response_distinct"]
                      and row["sample4_attempt_count"] == 1 for row in requests)
              and sampling["network_attempts"] == 3 and sampling["retries"] == 0 and chronology
              and scores["completed_within_time_box"]
              and scores["protocol_sha256"] == file_hash(PROTOCOL)
              and audit["score_sha256"] == file_hash(score_path))
    report = {"status": "passed" if passed else "failed", "verified_at": timestamp(),
              "blocked_reason": None if passed else completed.stderr.strip() or "sample4_replay_or_integrity_failed",
              "model_requests_during_replay": 0, "scientific_files_compared": len(comparisons),
              "byte_comparisons": comparisons, "baseline_counts_identical": counts_match,
              "frozen_inputs": inputs, "prior_inputs": prior, "request_checks": requests,
              "chronology_verified": chronology, "frozen_protocol_files": frozen_checks()}
    write_json(path, report)
    return {key: report[key] for key in ("status", "blocked_reason", "scientific_files_compared")}


def main() -> None:
    """Prepare, draw-and-score once, or replay without overwriting saved evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "draw-and-score", "verify"))
    args = parser.parse_args()
    if args.action == "prepare":
        print(prepare())
    elif args.action == "verify":
        print(verify_replay())
    else:
        signal.signal(signal.SIGALRM, stop_at_deadline)
        signal.setitimer(signal.ITIMER_REAL, max(0.01, time_remaining()))
        try:
            sampling = sample()
            if sampling["status"] != "complete":
                result = {"status": "blocked", "blocked_reason": sampling["blocked_reason"]}
            else:
                result = score_sample()
        except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
            result = {"status": "blocked", "blocked_reason": f"{type(error).__name__}: {error}"}
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        status_path = REPORT / "heldout_sample4_workflow_status.json"
        if not status_path.exists():
            write_json(status_path, {**result, "finished_at": timestamp(),
                                     "seconds_remaining": time_remaining()})
        print(result)
        if result["status"] != "complete":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
