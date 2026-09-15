"""Run prepared behavioural inputs through chemistry, activity and honest analysis."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from src.analysis.protocol import committed_protocol
from src.common.io import read_json, timestamp, write_json

ROOT = Path(__file__).resolve().parents[1]
PREPARED_INPUT_GUIDE = "docs/pipeline.md"
FRESH_CLONE_COMMAND = "python -m scripts.render_report"


def stage_commands(processed: Path, results: Path, interim: Path, offline: bool) -> list[dict]:
    """Describe sequential stages without embedding data or credentials in commands."""
    behaviour = processed / "behaviour"
    chemistry = processed / "chemistry"
    activity = processed / "bioactivity"
    stages = [
        {"name": "behaviour", "module": "scripts.behaviour", "metrics": behaviour / "metrics.json",
         "arguments": ["--output", str(behaviour)]},
        {"name": "chemistry", "module": "scripts.chemistry", "metrics": chemistry / "metrics.json",
         "arguments": ["--lotus-export", "--genera", str(behaviour / "all_genera.jsonl"),
                       "--output", str(chemistry), "--interim", str(interim)]},
        {"name": "bioactivity", "module": "scripts.bioactivity", "metrics": activity / "metrics.json",
         "arguments": ["--occurrences", str(chemistry / "occurrences.jsonl"),
                       "--primary-genera", str(behaviour / "genera.jsonl"),
                       "--chemistry-metrics", str(chemistry / "metrics.json"), "--output", str(activity)]},
        {"name": "analysis", "module": "scripts.analyse", "metrics": results / "metrics.json",
         "arguments": ["--observations", str(behaviour / "observations.jsonl"),
                       "--occurrences", str(chemistry / "occurrences.jsonl"),
                       "--labels", str(activity / "labels.jsonl"),
                       "--occurrence-metrics", str(chemistry / "metrics.json"),
                       "--label-metrics", str(activity / "metrics.json"),
                       "--processed", str(processed / "analysis"), "--output", str(results)]},
        {"name": "funnel", "module": "scripts.funnel", "metrics": results / "funnel.json",
         "arguments": ["--processed", str(processed), "--results", str(results)]},
    ]
    if offline:
        for stage in stages:
            stage["arguments"].append("--offline")
    return stages


def missing_prepared_inputs(start_at: str, supplements: list[Path]) -> list[Path]:
    """Return prepared, untracked inputs the requested stages need but cannot find.

    Args:
        start_at: First stage to run.
        supplements: Taxonomy supplement manifests passed on the command line.

    Returns:
        Missing paths, empty when the run can start.
    """
    required = [ROOT / "data/interim/corpus/manifest.jsonl"]
    if start_at == "behaviour":
        required.append(ROOT / "data/interim/taxonomy_pilot/observations.jsonl")
        required.extend(supplements)
    return [path for path in required if not path.exists()]


def run_stage(stage: dict, logs: Path) -> dict:
    """Run a stage, preserving its log and making process failures explicit."""
    command = [sys.executable, "-m", stage["module"], *stage["arguments"]]
    log = logs / f"{stage['name']}.log"
    logs.mkdir(parents=True, exist_ok=True)
    started = timestamp()
    print(json.dumps({"stage": stage["name"], "status": "running", "log": str(log)}), flush=True)
    try:
        with log.open("w") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False, cwd=ROOT)
        returncode = result.returncode
        reason = None if returncode == 0 else f"stage_process_exit_{returncode};see:{log}"
    except OSError as error:
        returncode, reason = 1, f"stage_launch_failed:{error}"
    metrics_path = stage["metrics"]
    metrics = read_json(metrics_path) if metrics_path.exists() else {}
    if reason and metrics.get("status") != "blocked":
        if metrics:
            write_json(logs / f"{stage['name']}_previous_metrics.json", metrics)
        write_json(metrics_path, {"status": "blocked", "blocked_reason": reason})
    entry = {"stage": stage["name"], "command": command, "returncode": returncode,
             "started_at": started, "finished_at": timestamp(), "log": str(log),
             "blocked_reason": reason or metrics.get("blocked_reason"), "metrics": str(metrics_path)}
    print(json.dumps(entry), flush=True)
    return entry


def main() -> None:
    """Run every requested stage and retain a resumable execution manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--interim", type=Path, default=ROOT / "data/interim/chemistry")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--taxonomy-supplement", type=Path, action="append", default=[])
    parser.add_argument("--start-at", choices=["behaviour", "chemistry", "bioactivity", "analysis", "funnel"],
                        default="behaviour")
    args = parser.parse_args()
    missing = missing_prepared_inputs(args.start_at, args.taxonomy_supplement)
    if missing:
        print(json.dumps({
            "status": "blocked",
            "blocked_reason": "prepared_inputs_missing",
            "missing": [str(path) for path in missing],
            "hint": (f"These inputs are not tracked by Git; see {PREPARED_INPUT_GUIDE}. "
                     f"From a fresh clone, run `{FRESH_CLONE_COMMAND}` to render the committed results."),
        }, indent=2), flush=True)
        raise SystemExit(2)
    protocol = committed_protocol(ROOT)
    stages = stage_commands(args.processed, args.results, args.interim, args.offline)
    for supplement in args.taxonomy_supplement:
        stages[0]["arguments"].extend(["--taxonomy-supplement", str(supplement)])
    start = next(index for index, stage in enumerate(stages) if stage["name"] == args.start_at)
    manifest = {"project": "aani", "protocol_commit": protocol, "offline": args.offline,
                "started_at": timestamp(), "stages": [], "prepared_upstream_stages": ["corpus", "extraction", "taxonomy"]}
    for stage in stages[start:]:
        manifest["stages"].append(run_stage(stage, args.results / "pipeline_logs"))
        write_json(args.results / "pipeline_execution.json", manifest)
    manifest["completed_at"] = timestamp()
    manifest["status"] = "blocked" if any(s["blocked_reason"] for s in manifest["stages"]) else "complete"
    write_json(args.results / "pipeline_execution.json", manifest)
    if any(s["returncode"] for s in manifest["stages"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
