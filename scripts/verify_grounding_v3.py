"""Snapshot prior work and verify a glyph-only offline grounding replay."""

import argparse
import base64
import hashlib
import subprocess
from pathlib import Path

from scripts.verify_day2 import compare_artifacts, file_hash, frozen_checks
from scripts.verify_grounding_development import scientific_names
from src.common.io import read_json, read_jsonl, timestamp, write_json

OUTPUT = Path("results/grounding_development_v3")
SNAPSHOT = OUTPUT / "preserved_inputs.json"
ORIGINAL = Path("data/interim/extraction_saverschek_multispan_v3")
REPEAT = Path("data/interim/extraction_saverschek_multispan_v2_repeat_for_v3")
CORPUS = Path("data/interim/corpus_targeted_saverschek")


def capture_inputs() -> dict:
    """Save original input hashes once, excluding the separately running repeat."""
    if SNAPSHOT.exists():
        raise ValueError("preserved_input_snapshot_already_exists")
    previous = read_json(Path("results/grounding_development_v2/preserved_inputs.json"))
    paths = {Path(row["path"]) for row in previous["files"]}
    paths.update(Path(name) for name in (
        "src/extraction/multispan_v2.py", "src/extraction/ant_identity.py",
        "src/extraction/identity_prompt.py", "src/evaluation/recall.py",
        "src/evaluation/identity_comparison.py",
    ))
    directories = [Path("results/grounding_development_v2"), CORPUS,
                   Path("data/interim/extraction_jobs_saverschek_multispan_v2")]
    directories += [path for path in Path("data/interim").glob(
        "extraction_saverschek_multispan_v2*"
    ) if path != REPEAT]
    for directory in directories:
        paths.update(path for path in directory.rglob("*") if path.is_file())
    for path in Path("data/interim/extraction_saverschek_multispan_v2/responses").glob("*.json"):
        envelope = read_json(path)
        paths.add(Path("data/raw/http") / f"{envelope['request_hash']}.json")
    report = {"captured_at": timestamp(), "files": [
        {"path": str(path), "sha256": file_hash(path)} for path in sorted(paths)
    ]}
    write_json(SNAPSHOT, report)
    return report


def replay_variant(name: str, mode: str, original: Path, cache: Path) -> dict:
    """Run a credential-free replay and compare all scientific output bytes."""
    destination = Path("data/interim/grounding_v3_replay") / name
    command = [".venv/bin/python", "-m", "scripts.extract", "--provider", "gemini",
               "--model", "gemini-3.8-flash", "--grounding", mode, "--corpus", str(CORPUS),
               "--output", str(destination), "--cache", str(cache), "--offline"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode:
        return {"variant": name, "status": "blocked", "command": command,
                "blocked_reason": completed.stderr.strip() or completed.stdout.strip()}
    metrics = read_json(destination / "metrics.json")
    complete = (metrics["chunks"] == 3 and metrics["complete_papers"] == 1
                and metrics["response_failures"] == 0 and metrics["unattempted_chunks"] == 0
                and metrics["blocked_reason"] is None)
    names = scientific_names(original) + ["source_ant_identities.json"]
    if name == "v3":
        names.extend(["glyph_policy.json", "glyph_grounding_audit.jsonl"])
    checks = compare_artifacts(original, destination, names)
    passed = complete and all(row["identical"] for row in checks)
    return {"variant": name, "status": "passed" if passed else "failed", "command": command,
            "blocked_reason": None if passed else "offline_artifact_or_completeness_mismatch",
            "completed_chunks": metrics["chunks"], "response_failures": metrics["response_failures"],
            "byte_comparisons": checks}


def verify() -> dict:
    """Verify saved inputs, frozen protocol, and offline outputs for v3 and its repeat."""
    snapshot = read_json(SNAPSHOT)
    replays = [replay_variant("v3", "multispan_v3", ORIGINAL, Path("data/raw"))]
    repeat_metrics = REPEAT / "metrics.json"
    if repeat_metrics.is_file() and read_json(repeat_metrics).get("complete_papers") == 1:
        replays.append(replay_variant("v2_repeat", "multispan_v2", REPEAT,
                                      Path("data/raw/grounding_v3_repeat")))
    protected = [{**row, "unchanged": Path(row["path"]).is_file()
                  and file_hash(Path(row["path"])) == row["sha256"]} for row in snapshot["files"]]
    frozen = frozen_checks()
    statuses = read_jsonl(ORIGINAL / "chunk_status.jsonl")
    comparison = read_json(OUTPUT / "compare.json")
    repeat = repeat_cache_provenance()
    write_json(OUTPUT / "repeat_status.json", repeat)
    passed = (all(row["status"] == "passed" for row in replays)
              and all(row["unchanged"] for row in protected)
              and all(row["matches_frozen_commit"] for row in frozen)
              and len(statuses) == 3 and all(row["status"] == "complete" for row in statuses)
              and comparison.get("blocked_reason") is None
              and comparison["glyph_recoveries"]["blocked_reason"] is None
              and comparison["fixed_sample_check"]["status"] == "complete")
    return {"status": "passed" if passed else "failed", "verified_at": timestamp(),
            "blocked_reason": None if passed else "offline_replay_or_preservation_check_failed",
            "variants": replays, "protected_inputs": protected, "frozen_files": frozen}


def repeat_cache_provenance() -> dict:
    """Record separate-cache request identity and saved response byte provenance."""
    repeat_cache = Path("data/raw/grounding_v3_repeat/http")
    rows = []
    for path in sorted((REPEAT / "responses").glob("*.json")):
        envelope = read_json(path)
        key = envelope["request_hash"]
        current_path = repeat_cache / f"{key}.json"
        original_path = Path("data/raw/http") / f"{key}.json"
        current = read_json(current_path)
        original = read_json(original_path)
        current_bytes = base64.b64decode(current["attempts"][-1]["body_base64"])
        original_bytes = base64.b64decode(original["attempts"][-1]["body_base64"])
        rows.append({"input_hash": envelope["input_hash"], "request_hash": key,
                     "request_descriptor_identical": current["request"] == original["request"],
                     "repeat_cache_path": str(current_path),
                     "original_cache_path": str(original_path),
                     "repeat_attempt_count": len(current["attempts"]),
                     "repeat_attempt_statuses": [row["status"] for row in current["attempts"]],
                     "repeat_response_sha256": hashlib.sha256(current_bytes).hexdigest(),
                     "original_response_sha256": hashlib.sha256(original_bytes).hexdigest(),
                     "response_bytes_differ": current_bytes != original_bytes,
                     "response_id": envelope.get("response_id")})
    metrics = read_json(REPEAT / "metrics.json") if (REPEAT / "metrics.json").is_file() else {}
    complete = len(rows) == 3 and metrics.get("complete_papers") == 1
    return {"label": "repeat sample", "status": "complete" if complete else "blocked",
            "blocked_reason": None if complete else metrics.get("blocked_reason")
            or "repeat_sample_incomplete", "sampled_once": True,
            "cache": str(repeat_cache.parent), "output": str(REPEAT),
            "pooled_with_v3": False, "requests": rows}


def main() -> None:
    """Capture protected files once or record an explicit replay outcome."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-inputs", action="store_true")
    args = parser.parse_args()
    if args.capture_inputs:
        report = capture_inputs()
        print({"snapshot": str(SNAPSHOT), "files": len(report["files"])})
        return
    try:
        report = verify()
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        report = {"status": "blocked", "blocked_reason": f"{type(error).__name__}: {error}"}
    write_json(OUTPUT / "verification.json", report)
    print({key: report.get(key) for key in ("status", "blocked_reason")})
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
