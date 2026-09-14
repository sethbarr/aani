"""Preserve prior experiments and replay the three development samples under v6."""

import argparse
import subprocess
from pathlib import Path

from scripts.verify_day2 import compare_artifacts, file_hash, frozen_checks
from scripts.verify_grounding_development import scientific_names
from scripts.verify_grounding_v5 import SAMPLES, execute_offline
from src.common.io import read_json, read_jsonl, timestamp, write_json
from src.evaluation.glyph_comparison import compare_proposal_samples

REPORT = Path("results/grounding_development_v6")
SNAPSHOT = REPORT / "preserved_inputs.json"
OUTPUT = Path("data/interim/extraction_saverschek_multispan_v6")
REPLAY = Path("data/interim/grounding_v6_replay")
INTEGRATION = {Path("src/extraction/pipeline.py"), Path("scripts/extract.py")}


def capture() -> dict:
    """Save hashes of all prior experimental artifacts before mode integration."""
    if SNAPSHOT.exists():
        raise ValueError("v6_preservation_snapshot_exists")
    paths = set(Path("src/extraction").glob("*.py"))
    paths -= {Path("src/extraction/cache_control_grounding.py"),
              Path("src/extraction/multispan_v6.py"),
              Path("src/extraction/single_attempt_transport.py")}
    paths.update(Path("src/evaluation").glob("*.py"))
    paths.discard(Path("src/evaluation/cache_control_comparison.py"))
    paths.discard(Path("src/evaluation/cache_control_failures.py"))
    paths.update(Path(name) for name in (
        "scripts/extract.py", "config/grounding_glyphs_v4.json", "config/grounding_glyphs_v5.json",
        "config/analysis.json", "docs/analysis_plan.md", "src/common/cache.py", "src/common/io.py",
        "results/recall_baseline.json", "results/recall_baseline.md"))
    baseline = read_json(Path("results/recall_baseline.json"))
    paths.update(Path(row["path"]) for row in baseline["inputs"])
    directories = [directory for directory in Path("results").glob("grounding_development_v*")
                   if directory != REPORT]
    directories += [directory for directory in Path("data/interim").glob("extraction_saverschek*")
                    if directory != OUTPUT]
    directories += list(Path("data/interim").glob("extraction_jobs_saverschek*"))
    for directory in directories:
        paths.update(path for path in directory.rglob("*") if path.is_file())
    for sample in SAMPLES.values():
        for response in (sample["v4"] / "responses").glob("*.json"):
            key = read_json(response)["request_hash"]
            paths.add(sample["cache"] / "http" / f"{key}.json")
    report = {"captured_at": timestamp(), "files": [
        {"path": str(path), "sha256": file_hash(path)} for path in sorted(paths - INTEGRATION)
    ], "allowed_mode_integration_files": [
        {"path": str(path), "before_sha256": file_hash(path)} for path in sorted(INTEGRATION)
    ]}
    write_json(SNAPSHOT, report)
    return {"status": "captured", "protected_files": len(report["files"])}


def preservation_checks() -> list[dict]:
    """Require every protected prior file to retain its original bytes."""
    return [{**row, "unchanged": Path(row["path"]).is_file()
             and file_hash(Path(row["path"])) == row["sha256"]}
            for row in read_json(SNAPSHOT)["files"]]


def survivor_delta(previous: Path, current: Path) -> dict:
    """Compare record identities and structured outcomes without changing any labels."""
    before = {row["record_id"]: row for row in read_jsonl(previous / "observations.jsonl")}
    after = {row["record_id"]: row for row in read_jsonl(current / "observations.jsonl")}
    return {
        "previous": str(previous), "current": str(current),
        "previous_survivors": len(before), "current_survivors": len(after),
        "lost_record_ids": sorted(before.keys() - after.keys()),
        "new_record_ids": sorted(after.keys() - before.keys()),
        "direction_changes": [{"record_id": key, "before": before[key]["outcome"],
                               "after": after[key]["outcome"]}
                              for key in sorted(before.keys() & after.keys())
                              if before[key]["outcome"] != after[key]["outcome"]],
    }


def run_sample(name: str, sample: dict[str, Path]) -> dict:
    """Validate and replay a complete saved sample with zero model requests."""
    destination = OUTPUT / name
    run = execute_offline("multispan_v6", destination, sample["cache"])
    if run["status"] != "complete":
        return {"sample": name, "status": "blocked", "run": run,
                "blocked_reason": run["blocked_reason"]}
    replay = execute_offline("multispan_v6", REPLAY / name, sample["cache"])
    names = scientific_names(destination) + ["source_ant_identities.json", "glyph_policy.json",
                                             "glyph_source_hashes.json", "glyph_grounding_audit.jsonl"]
    comparisons = compare_artifacts(destination, REPLAY / name, names) if replay["status"] == "complete" else []
    identity = compare_proposal_samples(sample["v4"], destination, True)
    regressions = {mode: survivor_delta(sample[mode], destination) for mode in ("v4", "v5")}
    passed = (replay["status"] == "complete" and identity["status"] == "complete"
              and bool(comparisons) and all(row["identical"] for row in comparisons)
              and all(not value["lost_record_ids"] and not value["direction_changes"]
                      for value in regressions.values()))
    return {"sample": name, "status": "passed" if passed else "failed", "run": run,
            "replay": replay, "sample_identity": identity, "byte_comparisons": comparisons,
            "regressions": regressions,
            "blocked_reason": None if passed else "v6_regression_or_replay_failed"}


def verify() -> dict:
    """Run the three development samples and verify references and earlier experiments."""
    if not all(row["unchanged"] for row in preservation_checks()):
        raise ValueError("v6_prior_inputs_changed_before_regression")
    samples = [run_sample(name, sample) for name, sample in SAMPLES.items()]
    protected = preservation_checks()
    frozen = frozen_checks()
    passed = (all(row["status"] == "passed" for row in samples)
              and all(row["unchanged"] for row in protected)
              and all(row["matches_frozen_commit"] for row in frozen))
    return {"status": "passed" if passed else "failed", "verified_at": timestamp(),
            "blocked_reason": None if passed else "v6_development_regression_or_preservation_failed",
            "model_requests": 0, "samples": samples, "protected_inputs": protected,
            "frozen_files": frozen, "sample_roles": "Samples 1–3 are DEVELOPMENT-SET evidence for v6."}


def main() -> None:
    """Capture once or save a complete development regression and baseline-convention score."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    if args.capture:
        print(capture())
        return
    destination = REPORT / "development_verification.json"
    if destination.exists():
        raise ValueError("v6_development_verification_exists")
    try:
        report = verify()
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        report = {"status": "blocked", "blocked_reason": f"{type(error).__name__}: {error}"}
    write_json(destination, report)
    print({key: report.get(key) for key in ("status", "blocked_reason")})
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
