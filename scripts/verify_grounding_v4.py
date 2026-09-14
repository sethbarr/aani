"""Run both saved samples through v4 offline and preserve prior experiment artifacts."""

import argparse
import subprocess
from pathlib import Path

from scripts.verify_day2 import compare_artifacts, file_hash, frozen_checks
from scripts.verify_grounding_development import scientific_names
from src.common.io import read_json, timestamp, write_json
from src.evaluation.glyph_comparison import compare_proposal_samples

REPORT = Path("results/grounding_development_v4")
SNAPSHOT = REPORT / "preserved_inputs.json"
CORPUS = Path("data/interim/corpus_targeted_saverschek")
SAMPLES = {
    "sample1": (Path("data/interim/extraction_saverschek_multispan_v3"),
                Path("data/interim/extraction_saverschek_multispan_v4"), Path("data/raw")),
    "sample2": (Path("data/interim/extraction_saverschek_multispan_v3_repeat"),
                Path("data/interim/extraction_saverschek_multispan_v4_repeat"),
                Path("data/raw/grounding_v3_repeat")),
}


def capture_inputs() -> dict:
    """Snapshot existing results and old validators before adding the v4 mode."""
    if SNAPSHOT.exists():
        raise ValueError("v4_preservation_snapshot_already_exists")
    previous = read_json(Path("results/grounding_development_v3/repeat_preserved_inputs.json"))
    integration = {Path("src/extraction/pipeline.py"), Path("scripts/extract.py")}
    paths = {Path(row["path"]) for row in previous["files"]} - integration
    directories = [Path("results/grounding_development_v1"),
                   Path("results/grounding_development_v2"),
                   Path("results/grounding_development_v3"),
                   Path("data/interim/grounding_v3_repeat_validation_replay")]
    directories += list(Path("data/interim").glob("extraction_saverschek*"))
    directories += list(Path("data/interim").glob("extraction_jobs_saverschek*"))
    for directory in directories:
        paths.update(path for path in directory.rglob("*") if path.is_file())
    result = {"captured_at": timestamp(), "files": [
        {"path": str(path), "sha256": file_hash(path)} for path in sorted(paths)
    ], "allowed_mode_integration_files": [
        {"path": str(path), "before_sha256": file_hash(path)} for path in sorted(integration)
    ]}
    write_json(SNAPSHOT, result)
    return result


def execute_offline(destination: Path, cache: Path) -> dict:
    """Run the same three jobs using saved responses and a fresh output directory.

    Args:
        destination: Unused directory for this v4 run.
        cache: Existing HTTP cache for one complete saved model sample.

    Returns:
        Command, explicit completion status, and any actual failure details.
    """
    if destination.exists():
        raise ValueError(f"refusing_to_overwrite_existing_output:{destination}")
    command = [".venv/bin/python", "-m", "scripts.extract", "--provider", "gemini",
               "--model", "gemini-3.8-flash", "--grounding", "multispan_v4",
               "--corpus", str(CORPUS), "--output", str(destination),
               "--cache", str(cache), "--offline"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    path = destination / "metrics.json"
    metrics = read_json(path) if path.is_file() else {}
    complete = (completed.returncode == 0 and metrics.get("chunks") == 3
                and metrics.get("complete_papers") == 1 and not metrics.get("response_failures")
                and not metrics.get("unattempted_chunks") and not metrics.get("blocked_reason"))
    return {"status": "complete" if complete else "blocked", "command": command,
            "offline": True, "model_network_requests": 0, "metrics": metrics,
            "blocked_reason": None if complete else metrics.get("blocked_reason")
            or completed.stderr.strip() or completed.stdout.strip() or "offline_run_incomplete"}


def run_sample(name: str, original: Path, destination: Path, cache: Path) -> dict:
    """Execute and independently replay one fixed proposal sample.

    Args:
        name: Sample identifier used to separate replay outputs.
        original: Preserved v3 output for the same sample.
        destination: New v4 output directory.
        cache: Original cache that contains this sample's response bytes.

    Returns:
        Run and replay statuses, sample identity, and scientific byte comparisons.
    """
    run = execute_offline(destination, cache)
    if run["status"] != "complete":
        return {"sample": name, "status": "blocked", "blocked_reason": run["blocked_reason"],
                "run": run}
    replay_path = Path("data/interim/grounding_v4_replay") / name
    replay = execute_offline(replay_path, cache)
    identity = compare_proposal_samples(original, destination, True)
    names = scientific_names(destination) + ["source_ant_identities.json", "glyph_policy.json",
                                             "glyph_source_hashes.json", "glyph_grounding_audit.jsonl"]
    checks = compare_artifacts(destination, replay_path, names) if replay["status"] == "complete" else []
    passed = (replay["status"] == "complete" and identity["status"] == "complete"
              and bool(checks) and all(row["identical"] for row in checks))
    return {"sample": name, "status": "passed" if passed else "failed", "run": run,
            "replay": replay, "sample_identity": identity, "byte_comparisons": checks,
            "blocked_reason": None if passed else "sample_identity_or_offline_replay_failed"}


def verify() -> dict:
    """Run both samples and verify all previously protected files and frozen rules."""
    snapshot = read_json(SNAPSHOT)
    samples = [run_sample(name, *arguments) for name, arguments in SAMPLES.items()]
    protected = [{**row, "unchanged": Path(row["path"]).is_file()
                  and file_hash(Path(row["path"])) == row["sha256"]} for row in snapshot["files"]]
    frozen = frozen_checks()
    passed = (all(row["status"] == "passed" for row in samples)
              and all(row["unchanged"] for row in protected)
              and all(row["matches_frozen_commit"] for row in frozen))
    return {"status": "passed" if passed else "failed", "verified_at": timestamp(),
            "blocked_reason": None if passed else "v4_replay_or_preservation_failed",
            "model_network_requests": 0, "samples": samples, "protected_inputs": protected,
            "frozen_files": frozen, "allowed_mode_integration_files": [
                {**row, "after_sha256": file_hash(Path(row["path"]))}
                for row in snapshot["allowed_mode_integration_files"]
            ]}


def main() -> None:
    """Capture prior files once or run the saved-sample offline experiment once."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-inputs", action="store_true")
    args = parser.parse_args()
    if args.capture_inputs:
        result = capture_inputs()
        print({"snapshot": str(SNAPSHOT), "files": len(result["files"])})
        return
    path = REPORT / "verification.json"
    if path.exists():
        raise ValueError("v4_verification_already_exists")
    try:
        report = verify()
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        report = {"status": "blocked", "blocked_reason": f"{type(error).__name__}: {error}"}
    write_json(path, report)
    print({key: report.get(key) for key in ("status", "blocked_reason")})
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
