"""Preserve prior artifacts and replay all three extraction variants without network access."""

import argparse
import subprocess
from pathlib import Path

from scripts.verify_day2 import compare_artifacts, file_hash, frozen_checks
from scripts.verify_grounding_development import rejection_changes, scientific_names
from src.common.io import read_json, read_jsonl, timestamp, write_json
from src.evaluation.comparison import baseline_integrity

OUTPUT = Path("results/grounding_development_v2")
SNAPSHOT = OUTPUT / "preserved_inputs.json"
CORPUS = Path("data/interim/corpus_targeted_saverschek")
REPLAY = Path("data/interim/grounding_v2_replay")
VARIANTS = {
    "baseline": ("single_quote_v1", Path("data/interim/extraction_saverschek")),
    "v1": ("multispan_v1", Path("data/interim/extraction_saverschek_multispan_v1")),
    "v2": ("multispan_v2", Path("data/interim/extraction_saverschek_multispan_v2")),
}


def capture_inputs() -> dict:
    """Snapshot protected inputs before the single v2 model run, refusing to replace the snapshot."""
    if SNAPSHOT.exists():
        raise ValueError("preserved_input_snapshot_already_exists")
    baseline = read_json(Path("results/recall_baseline.json"))
    paths = {Path(row["path"]) for row in baseline["inputs"]}
    paths.update(Path(name) for name in (
        "results/recall_baseline.json", "results/recall_baseline.md", "results/metrics.json",
        "results/funnel.json", "results/summary.json", "docs/analysis_plan.md",
        "config/analysis.json", "src/extraction/multispan.py", "src/extraction/prompts.py",
        "src/extraction/schema.py", "src/extraction/gemini.py",
    ))
    directories = [Path("results/grounding_development_v1")]
    directories += sorted(Path("data/interim").glob("extraction_saverschek_multispan_v1*"))
    directories.append(Path("data/interim/extraction_jobs_saverschek_multispan_v1"))
    for directory in directories:
        paths.update(path for path in directory.rglob("*") if path.is_file())
    report = {"captured_at": timestamp(), "files": [
        {"path": str(path), "sha256": file_hash(path)} for path in sorted(paths)
    ]}
    write_json(SNAPSHOT, report)
    return report


def replay_variant(name: str, mode: str, original: Path) -> dict:
    """Execute one offline replay and compare scientific bytes against its saved counterpart."""
    destination = REPLAY / name
    command = [str(Path(".venv/bin/python")), "-m", "scripts.extract", "--provider", "gemini",
               "--model", "gemini-3.8-flash", "--grounding", mode, "--corpus", str(CORPUS),
               "--output", str(destination), "--offline"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode:
        return {"variant": name, "status": "blocked", "command": command,
                "blocked_reason": completed.stderr.strip() or completed.stdout.strip()}
    try:
        metrics = read_json(destination / "metrics.json")
        if metrics["response_failures"] or metrics["unattempted_chunks"] or metrics["blocked_reason"]:
            failures = read_jsonl(destination / "failures.jsonl")
            return {"variant": name, "status": "blocked", "command": command,
                    "blocked_reason": "offline_cache_or_run_incomplete",
                    "response_failures": metrics["response_failures"], "failures": failures,
                    "unattempted_chunks": metrics["unattempted_chunks"]}
        expected = original.with_name(f"{original.name}_hardened_replay") if name == "v1" else original
        names = scientific_names(expected)
        if name == "v2":
            names.append("source_ant_identities.json")
        checks = compare_artifacts(expected, destination, names)
        complete = (metrics["chunks"] == 3 and metrics["complete_papers"] == 1
                    and metrics["response_failures"] == 0 and metrics["unattempted_chunks"] == 0
                    and metrics["blocked_reason"] is None)
        preserved_first_checks = []
        if name == "v1":
            preserved_first_checks = compare_artifacts(
                original, destination, [item for item in names if item != "rejections.jsonl"]
            )
        passed = complete and all(row["identical"] for row in checks + preserved_first_checks)
        return {"variant": name, "status": "passed" if passed else "failed", "command": command,
                "blocked_reason": None if passed else "offline_artifact_or_completeness_mismatch",
                "completed_chunks": metrics["chunks"], "response_failures": metrics["response_failures"],
                "byte_comparisons": checks, "preserved_first_v1_comparisons": preserved_first_checks,
                "v1_expected_rejection_difference": rejection_changes() if name == "v1" else None}
    except (OSError, KeyError, ValueError) as error:
        return {"variant": name, "status": "blocked", "command": command,
                "blocked_reason": f"{type(error).__name__}: {error}"}


def verify() -> dict:
    """Replay each variant, then verify preserved inputs and the frozen protocol."""
    if not SNAPSHOT.is_file():
        raise ValueError("preserved_input_snapshot_missing")
    snapshot = read_json(SNAPSHOT)
    replays = [replay_variant(name, mode, original) for name, (mode, original) in VARIANTS.items()]
    protected = [{**row, "unchanged": Path(row["path"]).is_file()
                  and file_hash(Path(row["path"])) == row["sha256"]} for row in snapshot["files"]]
    baseline = baseline_integrity(read_json(Path("results/recall_baseline.json")), Path.cwd())
    frozen = frozen_checks()
    passed = (all(row["status"] == "passed" for row in replays)
              and all(row["unchanged"] for row in protected)
              and baseline["all_original_bytes_unchanged"]
              and all(row["matches_frozen_commit"] for row in frozen)
              and replays[1]["v1_expected_rejection_difference"]["only_expected_change"])
    blockers = [f"{row['variant']}:{row['blocked_reason']}" for row in replays
                if row["status"] == "blocked"]
    return {"status": "passed" if passed else "blocked" if blockers else "failed",
            "verified_at": timestamp(),
            "blocked_reason": ";".join(blockers) if blockers else (
                None if passed else "offline_replay_or_preservation_check_failed"),
            "variants": replays, "protected_inputs": protected, "frozen_files": frozen,
            "baseline_integrity": baseline,
            "scope": "Fresh offline execution for baseline, v1 and v2. V1 first-run responses "
            "and stage counts are unchanged; the prior full-name hardening changes one rejection "
            "reason. All saved v1 artifacts are preserved byte-for-byte."}


def main() -> None:
    """Capture pre-run inputs or write explicit offline replay and preservation status."""
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
