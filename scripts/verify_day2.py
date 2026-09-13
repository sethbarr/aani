"""Verify the day-two outputs against frozen inputs and an offline stage replay."""

import hashlib
import subprocess
from pathlib import Path

from scripts.analyse import run_analysis
from scripts.bioactivity import run_bioactivity
from src.behaviour.pipeline import run_merge
from src.common.io import read_json, timestamp, write_json

COMMIT = "98b5e09199a5eef0c46be452793e953f5a2af31e"


def file_hash(path: Path) -> str:
    """Hash exact artifact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_checks() -> list[dict]:
    """Compare both scientific protocol files with the original Git objects."""
    checks = []
    for name in ("docs/analysis_plan.md", "config/analysis.json"):
        original = subprocess.run(["git", "show", f"{COMMIT}:{name}"],
                                  check=True, capture_output=True)
        checks.append({"path": name, "sha256": file_hash(Path(name)),
                       "matches_frozen_commit": Path(name).read_bytes() == original.stdout})
    return checks


def compare_artifacts(original: Path, replay: Path, names: list[str]) -> list[dict]:
    """Record exact byte comparisons of scientific output artifacts."""
    return [{"original": str(original / name), "replay": str(replay / name),
             "sha256": file_hash(original / name),
             "identical": file_hash(original / name) == file_hash(replay / name)} for name in names]


def verify() -> dict:
    """Replay behaviour, activity and analysis; preserve the completed chemistry scan."""
    root = Path.cwd()
    processed = Path("data/processed")
    replay = Path("data/interim/day2_replay")
    baseline = read_json(Path("results/recall_baseline.json"))
    source_checks = [{**item, "unchanged": file_hash(Path(item["path"])) == item["sha256"]}
                     for item in baseline["inputs"]]
    run_merge(root, replay / "behaviour", [Path("data/interim/trema_resolution/manifest.json")])
    run_bioactivity(processed / "chemistry/occurrences.jsonl", replay / "bioactivity",
                   Path("data/raw"), offline=True,
                   chemistry_metrics_path=processed / "chemistry/metrics.json",
                   primary_genera_path=processed / "behaviour/genera.jsonl")
    run_analysis(processed / "behaviour/observations.jsonl", processed / "chemistry/occurrences.jsonl",
                 replay / "bioactivity/labels.jsonl", replay / "analysis", replay / "prepared",
                 processed / "chemistry/metrics.json", replay / "bioactivity/metrics.json", offline=True)
    comparisons = compare_artifacts(processed / "behaviour", replay / "behaviour",
                                    ["observations.jsonl", "genera.jsonl", "all_genera.jsonl", "metrics.json"])
    comparisons += compare_artifacts(processed / "bioactivity", replay / "bioactivity",
                                     ["labels.jsonl", "measurements.jsonl", "retrieval_status.jsonl", "metrics.json"])
    comparisons += compare_artifacts(Path("results"), replay / "analysis",
                                     ["summary.json", "metrics.json", "candidate_genera.csv"] + [
                                         f"{subset}/{name}" for subset in
                                         ("primary", "experimental", "delayed", "nondiscordant")
                                         for name in ("genera.csv", "compounds.csv", "summary.json")])
    frozen = frozen_checks()
    passed = (all(c["identical"] for c in comparisons)
              and all(c["unchanged"] for c in source_checks)
              and all(c["matches_frozen_commit"] for c in frozen))
    return {"status": "passed" if passed else "failed", "verified_at": timestamp(),
            "blocked_reason": None if passed else "day2_artifact_verification_failed",
            "files_compared": len(comparisons), "checks": comparisons,
            "baseline_inputs": source_checks, "frozen_files": frozen,
            "scope": "Offline replay of behaviour with Trema supplement, full activity retrieval and analysis. Chemistry is the completed day-two full export scan, reused unchanged as an input.",
            "prior_day1_replay": "results/day2_blockers/offline_replay.json"}


def main() -> None:
    """Write explicit success or an actual failure reason for the verification run."""
    try:
        report = verify()
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.CalledProcessError) as error:
        report = {"status": "blocked", "blocked_reason": f"{type(error).__name__}: {error}"}
    write_json(Path("results/offline_replay.json"), report)
    print({key: report.get(key) for key in ("status", "files_compared", "blocked_reason")})
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
