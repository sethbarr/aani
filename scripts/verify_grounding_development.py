"""Verify the preserved first experiment and the separately hardened cached replay."""

import subprocess
from pathlib import Path

from scripts.verify_day2 import compare_artifacts, file_hash, frozen_checks
from src.common.io import read_json, read_jsonl, timestamp, write_json
from src.evaluation.comparison import BASELINE_COMMIT, baseline_integrity, build_comparison
from src.extraction.pipeline import make_jobs

FIRST_VALIDATOR_HASH = "ef94cfa873ee131aa7e77ff8fc70507ec4e3b2b438bd81b9fe6d956bb329cc40"
HARDENED_VALIDATOR_HASH = "8156b704d7835ed142699028c5f47d5b855008cf5a6a6195d90856a0cfcfaaf5"
RUN = Path("data/interim/extraction_saverschek_multispan_v1")
HARDENED = RUN.with_name(f"{RUN.name}_hardened_replay")
CORPUS = Path("data/interim/corpus_targeted_saverschek")


def scientific_names(directory: Path) -> list[str]:
    """List scientific outputs and each saved response, excluding run timestamps."""
    names = ["observations.jsonl", "rejections.jsonl", "metrics.json", "failures.jsonl",
             "partial_observations.jsonl", "chunk_status.jsonl"]
    return names + [str(path.relative_to(directory))
                    for path in sorted((directory / "responses").glob("*.json"))]


def committed_checks() -> list[dict]:
    """Verify unchanged biological results and the original extraction client settings."""
    names = ["results/metrics.json", "results/funnel.json", "results/summary.json",
             "data/processed/behaviour/metrics.json", "data/processed/chemistry/metrics.json",
             "data/processed/bioactivity/metrics.json", "src/extraction/schema.py",
             "src/extraction/gemini.py"]
    checks = []
    for name in names:
        original = subprocess.run(["git", "show", f"{BASELINE_COMMIT}:{name}"],
                                  check=True, capture_output=True)
        path = Path(name)
        checks.append({"path": name, "sha256": file_hash(path),
                       "matches_baseline_commit": path.read_bytes() == original.stdout})
    return checks


def rejection_changes() -> dict:
    """Allow only the independently identified abbreviated full-name check correction."""
    original = read_jsonl(RUN / "rejections.jsonl")
    hardened = read_jsonl(HARDENED / "rejections.jsonl")
    changes = []
    candidates_unchanged = len(original) == len(hardened)
    for before, after in zip(original, hardened):
        candidates_unchanged &= (
            before["candidate"] == after["candidate"]
            and before["input_hash"] == after["input_hash"]
            and before["source_id"] == after["source_id"]
        )
        if before["reason"] != after["reason"]:
            changes.append({"plant": before["candidate"]["plant_name_as_written"],
                            "before": before["reason"], "after": after["reason"]})
    expected = [{"plant": "S. lindenianum", "before": "ant_requires_review",
                 "after": "unabbreviated_genus_required"}]
    return {"candidates_unchanged": candidates_unchanged, "changes": changes,
            "only_expected_change": candidates_unchanged and changes == expected,
            "first_sha256": file_hash(RUN / "rejections.jsonl"),
            "hardened_sha256": file_hash(HARDENED / "rejections.jsonl")}


def verify() -> dict:
    """Check replay bytes, fixed references, protocol integrity and unchanged stage counts."""
    legacy = Path("data/interim/extraction_saverschek")
    comparisons = compare_artifacts(
        legacy, legacy.with_name(f"{legacy.name}_v1_regression"), scientific_names(legacy)
    )
    comparisons += compare_artifacts(
        RUN, RUN.with_name(f"{RUN.name}_replay"), scientific_names(RUN)
    )
    comparisons += compare_artifacts(
        RUN, HARDENED, [name for name in scientific_names(RUN) if name != "rejections.jsonl"]
    )
    baseline = baseline_integrity(read_json(Path("results/recall_baseline.json")), Path.cwd())
    frozen = frozen_checks()
    committed = committed_checks()
    changed_rejections = rejection_changes()
    original_report = build_comparison(RUN, Path.cwd())
    hardened_report = build_comparison(HARDENED, Path.cwd())
    counts_unchanged = (original_report["development"]["groups"]
                        == hardened_report["development"]["groups"])
    job_checks = []
    for mode, directory in (("single_quote_v1", legacy), ("multispan_v1", RUN)):
        hashes = [job["input_hash"] for job in make_jobs(CORPUS, grounding_version=mode)]
        job_checks.append({"mode": mode, "input_hashes": hashes,
                           "matches_saved_run": hashes == read_json(
                               directory / "run_manifest.json")["input_hashes"]})
    actual_validator_hash = file_hash(Path("src/extraction/multispan.py"))
    passed = (all(row["identical"] for row in comparisons)
              and baseline["all_original_bytes_unchanged"]
              and all(row["matches_frozen_commit"] for row in frozen)
              and all(row["matches_baseline_commit"] for row in committed)
              and all(row["matches_saved_run"] for row in job_checks)
              and changed_rejections["only_expected_change"] and counts_unchanged
              and original_report["status"] == hardened_report["status"] == "complete"
              and actual_validator_hash == HARDENED_VALIDATOR_HASH)
    return {
        "status": "passed" if passed else "failed", "verified_at": timestamp(),
        "blocked_reason": None if passed else "grounding_development_verification_failed",
        "files_compared": len(comparisons), "byte_comparisons": comparisons,
        "baseline_integrity": baseline, "frozen_files": frozen,
        "committed_biology_and_client": committed, "job_checks": job_checks,
        "first_validator_sha256": FIRST_VALIDATOR_HASH,
        "hardened_validator_sha256": actual_validator_hash,
        "hardened_rejection_check": changed_rejections,
        "hardened_stage_counts_unchanged": counts_unchanged,
        "scope": "Preserved first-model-run artifacts and their pre-hardening offline replay; "
        "separate post-hardening replay of identical cached responses; default-mode regression. "
        "No new model sample and no biological join.",
    }


def main() -> None:
    """Write explicit verification status, including actual errors if checks cannot run."""
    try:
        report = verify()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        report = {"status": "blocked", "blocked_reason": f"{type(error).__name__}: {error}"}
    write_json(Path("results/grounding_development_v1/verification.json"), report)
    print({key: report.get(key) for key in ("status", "files_compared", "blocked_reason")})
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
