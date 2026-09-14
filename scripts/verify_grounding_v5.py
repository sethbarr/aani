"""Replay all three saved leafcutter samples through v5 offline."""

import argparse
import subprocess
from pathlib import Path

from scripts.verify_day2 import compare_artifacts, file_hash, frozen_checks
from scripts.verify_grounding_development import scientific_names
from src.common.io import read_json, read_jsonl, write_json
from src.evaluation.glyph_comparison import compare_proposal_samples

REPORT = Path("results/grounding_development_v5")
CORPUS = Path("data/interim/corpus_targeted_saverschek")
SAMPLES = {
    "sample1": {
        "v4": Path("data/interim/extraction_saverschek_multispan_v4"),
        "v5": Path("data/interim/extraction_saverschek_multispan_v5"),
        "cache": Path("data/raw"),
    },
    "sample2": {
        "v4": Path("data/interim/extraction_saverschek_multispan_v4_repeat"),
        "v5": Path("data/interim/extraction_saverschek_multispan_v5_repeat"),
        "cache": Path("data/raw/grounding_v3_repeat"),
    },
    "sample3": {
        "v2": Path("data/interim/extraction_saverschek_multispan_v2_sample3"),
        "v4": Path("data/interim/extraction_saverschek_multispan_v4_sample3"),
        "v5": Path("data/interim/extraction_saverschek_multispan_v5_sample3"),
        "cache": Path("data/raw/grounding_v4_sample3"),
    },
}


def prior_file_snapshot() -> list[dict]:
    """Hash v4 evidence and saved proposal samples before creating v5 outputs."""
    paths: set[Path] = set()
    directories = [
        Path("results/grounding_development_v4"),
        SAMPLES["sample1"]["v4"],
        SAMPLES["sample2"]["v4"],
        SAMPLES["sample3"]["v2"],
    ]
    for directory in directories:
        paths.update(path for path in directory.rglob("*") if path.is_file())
    return [
        {"path": str(path), "sha256": file_hash(path)}
        for path in sorted(paths)
    ]


def execute_offline(mode: str, destination: Path, cache: Path) -> dict:
    """Run one grounding mode from a saved HTTP cache with offline enforced."""
    if destination.exists():
        raise ValueError(f"refusing_to_overwrite_existing_output:{destination}")
    command = [
        ".venv/bin/python",
        "-m",
        "scripts.extract",
        "--provider",
        "gemini",
        "--model",
        "gemini-3.8-flash",
        "--grounding",
        mode,
        "--corpus",
        str(CORPUS),
        "--output",
        str(destination),
        "--cache",
        str(cache),
        "--offline",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    metrics_path = destination / "metrics.json"
    metrics = read_json(metrics_path) if metrics_path.is_file() else {}
    complete = (
        completed.returncode == 0
        and metrics.get("chunks") == 3
        and metrics.get("complete_papers") == 1
        and not metrics.get("response_failures")
        and not metrics.get("unattempted_chunks")
        and not metrics.get("blocked_reason")
    )
    return {
        "status": "complete" if complete else "blocked",
        "command": command,
        "offline": True,
        "model_calls": 0,
        "network_calls": 0,
        "metrics": metrics,
        "blocked_reason": None if complete else (
            metrics.get("blocked_reason")
            or completed.stderr.strip()
            or completed.stdout.strip()
            or "offline_run_incomplete"
        ),
    }


def ensure_sample3_v4() -> dict:
    """Create the previously prepared sample-3 v4 baseline from its saved cache."""
    path = SAMPLES["sample3"]["v4"]
    if path.exists():
        return {"status": "already_present", "path": str(path)}
    result = execute_offline("multispan_v4", path, SAMPLES["sample3"]["cache"])
    if result["status"] != "complete":
        return result
    identity = compare_proposal_samples(SAMPLES["sample3"]["v2"], path, True)
    return {**result, "sample_identity": identity}


def regression_delta(v4: Path, v5: Path) -> dict:
    """Compare survivor identities and assigned directions between v4 and v5."""
    before = {row["record_id"]: row for row in read_jsonl(v4 / "observations.jsonl")}
    after = {row["record_id"]: row for row in read_jsonl(v5 / "observations.jsonl")}
    before_ids = set(before)
    after_ids = set(after)
    direction_changes = [
        {
            "record_id": record_id,
            "v4_outcome": before[record_id]["outcome"],
            "v5_outcome": after[record_id]["outcome"],
        }
        for record_id in sorted(before_ids & after_ids)
        if before[record_id]["outcome"] != after[record_id]["outcome"]
    ]
    route_counts = {
        route: sum(row.get("quote_grounding_route") == route for row in after.values())
        for route in (
            "exact",
            "source_anchored_control_glyph",
            "source_anchored_printable_confusable",
        )
    }
    return {
        "v4_survivors": len(before_ids),
        "v5_survivors": len(after_ids),
        "previous_survivors_retained": len(before_ids & after_ids),
        "lost_record_ids": sorted(before_ids - after_ids),
        "new_record_ids": sorted(after_ids - before_ids),
        "direction_changes": direction_changes,
        "v5_route_counts": route_counts,
    }


def run_sample(name: str, sample: dict[str, Path]) -> dict:
    """Run v5, repeat it offline, and compare it with the saved v4 output."""
    run = execute_offline("multispan_v5", sample["v5"], sample["cache"])
    if run["status"] != "complete":
        return {"sample": name, "status": "blocked", "run": run}
    replay = Path("data/interim/grounding_v5_replay") / name
    replay_result = execute_offline("multispan_v5", replay, sample["cache"])
    identity = compare_proposal_samples(sample["v4"], sample["v5"], True)
    names = scientific_names(sample["v5"]) + [
        "source_ant_identities.json",
        "glyph_policy.json",
        "glyph_source_hashes.json",
        "glyph_grounding_audit.jsonl",
    ]
    comparisons = (
        compare_artifacts(sample["v5"], replay, names)
        if replay_result["status"] == "complete" else []
    )
    delta = regression_delta(sample["v4"], sample["v5"])
    passed = (
        replay_result["status"] == "complete"
        and identity["status"] == "complete"
        and comparisons
        and all(row["identical"] for row in comparisons)
        and not delta["lost_record_ids"]
        and not delta["direction_changes"]
    )
    return {
        "sample": name,
        "status": "passed" if passed else "failed",
        "run": run,
        "replay": replay_result,
        "sample_identity": identity,
        "byte_comparisons": comparisons,
        "regression": delta,
        "blocked_reason": None if passed else "v5_regression_or_replay_failed",
    }


def verify() -> dict:
    """Run every existing leafcutter sample and verify preserved inputs."""
    snapshot = prior_file_snapshot()
    sample3_v4 = ensure_sample3_v4()
    if sample3_v4["status"] == "blocked":
        return {
            "status": "blocked",
            "blocked_reason": sample3_v4["blocked_reason"],
            "sample3_v4": sample3_v4,
        }
    samples = [run_sample(name, sample) for name, sample in SAMPLES.items()]
    protected = [
        {
            **row,
            "unchanged": Path(row["path"]).is_file()
            and file_hash(Path(row["path"])) == row["sha256"],
        }
        for row in snapshot
    ]
    frozen = frozen_checks()
    passed = (
        all(row["status"] == "passed" for row in samples)
        and all(row["unchanged"] for row in protected)
        and all(row["matches_frozen_commit"] for row in frozen)
    )
    return {
        "status": "passed" if passed else "failed",
        "blocked_reason": None if passed else "v5_regression_replay_or_preservation_failed",
        "offline": True,
        "model_calls": 0,
        "network_calls": 0,
        "sample3_v4": sample3_v4,
        "samples": samples,
        "protected_inputs": protected,
        "frozen_files": frozen,
    }


def main() -> None:
    """Write one machine-readable verification report without overwriting it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    path = REPORT / "verification.json"
    if path.exists():
        raise FileExistsError(f"preserve_existing_artifact:{path}")
    try:
        report = verify()
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        report = {
            "status": "blocked",
            "blocked_reason": f"{type(error).__name__}: {error}",
            "offline": True,
            "model_calls": 0,
            "network_calls": 0,
        }
    write_json(path, report)
    print({
        "status": report["status"],
        "blocked_reason": report.get("blocked_reason"),
        "samples": [
            {
                "sample": row["sample"],
                "status": row["status"],
                "regression": row.get("regression"),
            }
            for row in report.get("samples", [])
        ],
        "model_calls": 0,
        "network_calls": 0,
    })
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
