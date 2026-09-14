"""Apply the existing v3 rules to the saved repeat cache with offline preservation checks."""

import argparse
import subprocess
from pathlib import Path

from scripts.verify_day2 import compare_artifacts, file_hash, frozen_checks
from scripts.verify_grounding_development import scientific_names
from src.common.io import read_json, read_jsonl, timestamp, write_json
from src.evaluation.glyph_comparison import compare_proposal_samples

REPORT = Path("results/grounding_development_v3")
SNAPSHOT = REPORT / "repeat_preserved_inputs.json"
SOURCE = Path("data/interim/extraction_saverschek_multispan_v2_repeat_for_v3")
OUTPUT = Path("data/interim/extraction_saverschek_multispan_v3_repeat")
REPLAY = Path("data/interim/grounding_v3_repeat_validation_replay")
CACHE = Path("data/raw/grounding_v3_repeat")
CORPUS = Path("data/interim/corpus_targeted_saverschek")


def capture_inputs() -> dict:
    """Snapshot every prior experiment artifact and the unchanged validator once."""
    if SNAPSHOT.exists():
        raise ValueError("repeat_preservation_snapshot_already_exists")
    previous = read_json(REPORT / "preserved_inputs.json")
    paths = {Path(row["path"]) for row in previous["files"]}
    paths.update(Path(name) for name in (
        "config/grounding_glyphs_v3.json", "src/extraction/glyph_grounding.py",
        "src/extraction/multispan_v3.py", "src/extraction/pipeline.py", "scripts/extract.py",
        "src/evaluation/glyph_comparison.py", "src/common/cache.py",
    ))
    directories = [REPORT, CACHE, Path("data/interim/grounding_v3_replay")]
    directories += list(Path("data/interim").glob("extraction_saverschek*"))
    directories += list(Path("data/interim").glob("extraction_jobs_saverschek*"))
    directories += list(Path("results").glob("grounding_development_v*"))
    for directory in directories:
        paths.update(path for path in directory.rglob("*") if path.is_file())
    result = {"captured_at": timestamp(), "files": [
        {"path": str(path), "sha256": file_hash(path)} for path in sorted(paths)
    ]}
    write_json(SNAPSHOT, result)
    return result


def run_offline(destination: Path) -> dict:
    """Run the existing CLI with network forbidden and a new output directory.

    Args:
        destination: Previously unused output directory.

    Returns:
        Executed command, completion status, and explicit blocking reason.
    """
    if destination.exists():
        raise ValueError(f"refusing_to_overwrite_existing_artifacts:{destination}")
    command = [".venv/bin/python", "-m", "scripts.extract", "--provider", "gemini",
               "--model", "gemini-3.8-flash", "--grounding", "multispan_v3",
               "--corpus", str(CORPUS), "--output", str(destination),
               "--cache", str(CACHE), "--offline"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    metrics_path = destination / "metrics.json"
    metrics = read_json(metrics_path) if metrics_path.is_file() else {}
    complete = (completed.returncode == 0 and metrics.get("chunks") == 3
                and metrics.get("complete_papers") == 1 and not metrics.get("response_failures")
                and not metrics.get("unattempted_chunks") and not metrics.get("blocked_reason"))
    return {"status": "complete" if complete else "blocked", "command": command,
            "offline": True, "model_network_requests": 0,
            "blocked_reason": None if complete else metrics.get("blocked_reason")
            or completed.stderr.strip() or completed.stdout.strip() or "offline_run_incomplete",
            "metrics": metrics}


def verify(run: dict, replay: dict) -> dict:
    """Check proposal identity, policy identity, protected inputs, and offline bytes."""
    snapshot = read_json(SNAPSHOT)
    protected = [{**row, "unchanged": Path(row["path"]).is_file()
                  and file_hash(Path(row["path"])) == row["sha256"]} for row in snapshot["files"]]
    frozen = frozen_checks()
    sample = compare_proposal_samples(SOURCE, OUTPUT, True)
    policy_paths = [Path("config/grounding_glyphs_v3.json"), OUTPUT / "glyph_policy.json",
                    Path("data/interim/extraction_saverschek_multispan_v3/glyph_policy.json")]
    policies = [read_json(path) for path in policy_paths]
    same_policy = all(policy == policies[0] for policy in policies)
    names = scientific_names(OUTPUT) + ["source_ant_identities.json", "glyph_policy.json",
                                        "glyph_grounding_audit.jsonl"]
    checks = compare_artifacts(OUTPUT, REPLAY, names) if replay["status"] == "complete" else []
    audits = read_jsonl(OUTPUT / "glyph_grounding_audit.jsonl")
    passed = (run["status"] == replay["status"] == "complete"
              and sample["status"] == "complete" and same_policy
              and len(audits) == run["metrics"]["candidate_records"]
              and all(row["unchanged"] for row in protected)
              and all(row["matches_frozen_commit"] for row in frozen)
              and bool(checks) and all(row["identical"] for row in checks))
    return {"status": "passed" if passed else "failed", "verified_at": timestamp(),
            "blocked_reason": None if passed else "repeat_replay_or_preservation_failed",
            "run": run, "replay": replay, "model_network_requests": 0,
            "sample_identity": sample, "same_glyph_policy": same_policy,
            "policy_paths": [str(path) for path in policy_paths],
            "byte_comparisons": checks, "protected_inputs": protected, "frozen_files": frozen}


def main() -> None:
    """Capture old files or create a new offline run and a separate replay once."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-inputs", action="store_true")
    args = parser.parse_args()
    if args.capture_inputs:
        snapshot = capture_inputs()
        print({"snapshot": str(SNAPSHOT), "files": len(snapshot["files"])})
        return
    destination = REPORT / "repeat_verification.json"
    if destination.exists():
        raise ValueError("repeat_verification_already_exists")
    try:
        if not SNAPSHOT.is_file():
            raise ValueError("repeat_preservation_snapshot_missing")
        run = run_offline(OUTPUT)
        replay = run_offline(REPLAY) if run["status"] == "complete" else {
            "status": "blocked", "blocked_reason": "original_repeat_run_incomplete"}
        report = verify(run, replay) if run["status"] == "complete" else {
            "status": "blocked", "blocked_reason": run["blocked_reason"], "run": run}
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        report = {"status": "blocked", "blocked_reason": f"{type(error).__name__}: {error}"}
    write_json(destination, report)
    print({key: report.get(key) for key in ("status", "blocked_reason")})
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
