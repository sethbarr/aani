"""Apply frozen v4 and save held-out scores before any diagnostic inspection."""

import subprocess
from pathlib import Path

from scripts.draw_grounding_holdout import CACHE, CORPUS, PROTOCOL, REPORT, V4, unchanged_inputs
from scripts.verify_day2 import file_hash
from src.common.io import read_json, timestamp, write_json
from src.evaluation.heldout_comparison import build_heldout_comparison


def main() -> None:
    """Run the unchanged validator offline and publish scores before exposing failures."""
    score_path = REPORT / "heldout_scores.json"
    if score_path.exists() or V4.exists():
        raise ValueError("heldout_validation_or_scoring_already_started")
    if not all(row["unchanged"] for row in unchanged_inputs()):
        raise ValueError("heldout_rule_or_inputs_changed_before_scoring")
    sampling = read_json(REPORT / "heldout_sampling.json")
    if sampling["status"] != "complete":
        raise ValueError(f"heldout_sampling_blocked:{sampling['blocked_reason']}")
    command = [".venv/bin/python", "-m", "scripts.extract", "--provider", "gemini",
               "--model", "gemini-3.8-flash", "--grounding", "multispan_v4",
               "--corpus", str(CORPUS), "--output", str(V4), "--cache", str(CACHE), "--offline"]
    started = timestamp()
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    validation = {"started_at": started, "finished_at": timestamp(), "command": command,
                  "returncode": completed.returncode, "model_requests": 0,
                  "candidate_failure_details_inspected_before_scoring": False,
                  "blocked_reason": completed.stderr.strip() if completed.returncode else None}
    write_json(REPORT / "heldout_validation.json", validation)
    report = build_heldout_comparison(Path.cwd())
    frozen = unchanged_inputs()
    if not all(row["unchanged"] for row in frozen):
        report["status"] = "blocked"
        report["blocked_reason"] = "heldout_rule_or_inputs_changed_during_scoring"
    report["score_completed_at"] = timestamp()
    report["protocol_path"] = str(PROTOCOL)
    report["protocol_sha256"] = file_hash(PROTOCOL)
    report["frozen_inputs_unchanged_at_scoring"] = all(row["unchanged"] for row in frozen)
    report["candidate_failure_details_inspected_before_scoring"] = False
    write_json(score_path, report)
    print({"status": report["status"], "blocked_reason": report["blocked_reason"],
           "score_path": str(score_path), "score_sha256": file_hash(score_path),
           "sample3_groups": report["sample3_v4"]["groups"],
           "sample3_stage_yield": report["stage_yields"]["sample3_v4"]})
    if report["blocked_reason"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
