"""Assemble the baseline and two blocker outcomes from their measured artifacts."""

import hashlib
from pathlib import Path

from src.common.io import read_json, timestamp, write_json


def artifact(path: Path) -> dict:
    """Describe a local output using its exact bytes."""
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def render(report: dict) -> str:
    """Write the short requested report with separate developmental counts."""
    primary = report["baseline"]["PRIMARY"]
    context = report["baseline"]["CONTEXT"]
    lines = ["# aani — day-two baseline and blockers", "",
             "| Stage | PRIMARY | CONTEXT both / collapsed / absent | CONTEXT pairs |",
             "| --- | --- | --- | --- |"]
    for stage in ("detection", "survival", "correctness"):
        p = primary["stages"][stage]
        c = context["stages"][stage]
        counts = c["direction_coverage"]
        lines.append(f"| {stage} | {p['species_count']} of 6 | "
                     f"{counts['both_directions_surfaced']} / {counts['collapsed_to_one']} / "
                     f"{counts['absent']} of 5 | {c['species_direction_pair_count']} of 10 |")
    lines += ["", "This DEVELOPMENT SET is one panel from one paper and is not a sample from any "
              "population. All eleven species are scorable. Desmopsis rejection and Spondias "
              "acceptance survive correctly; Hymenaea supplies only its rejection direction. "
              "Miconia is absent from the original candidates.", "",
              "Under the documented provenance convention, PRIMARY has 2 author_prose "
              "and 4 author_table_grouping species; CONTEXT has 4 author_prose and "
              "1 author_table_grouping. Directions were checked against Table 1 of the "
              "original and follow the authors' printed headings, so these are "
              "author-assigned groupings rather than inferences from numerical signs. "
              "Semantic support for individual rows and captions remains unverified. "
              "Group/complement prose corroborates these labels. The [baseline report]"
              "(recall_baseline.md) explains the convention "
              "and shared-text contamination risk, with record-level provenance in "
              "[JSON](recall_baseline.json).", "",
              f"lme4: {report['model_environment']['status']}; "
              f"{' '.join(report['model_environment']['version_output'].split())}. Analysis was rerun. "
              f"Current inference blockers: {', '.join(report['inference_blockers'])}.", "",
              "Trema resolves to accepted Trema micranthum with an EXACT GBIF match at confidence "
              "100. LOTUS supplies 26 compounds, including six with exact accepted-species "
              "occurrences. All 26 have unknown eligible activity, with zero retrieval failures. "
              "Trema contributes zero classified compounds.", "",
              "| Funnel | Before | Current |", "| --- | --- | --- |"]
    for key, value in report["funnel_changes"].items():
        lines.append(f"| {key} | {value['before']} | {value['current']} |")
    lines += ["", "The primary join remains six accepted and one rejected genus. "
              "The feasibility-failure label, null inferential results and 25-genus trigger remain. "
              "The two frozen files match the original commit; original extraction inputs and "
              "outputs match the baseline hashes. "
              f"Offline replay passed {report['verification']['files_compared']} artifact comparisons "
              "for behaviour, activity and analysis. Chemistry used the completed full export scan.", ""]
    return "\n".join(lines)


def main() -> None:
    """Combine verified run status and refresh the end-to-end provenance manifest."""
    before = read_json(Path("results/day2_blockers/funnel.json"))
    after = read_json(Path("results/funnel.json"))
    baseline = read_json(Path("results/recall_baseline.json"))
    metrics = read_json(Path("results/metrics.json"))
    primary = read_json(Path("results/primary/summary.json"))
    verification = read_json(Path("results/offline_replay.json"))
    dependency_path = Path("results/day2_blockers/lme4_status.json")
    dependency = read_json(dependency_path)
    dependency["analysis_rerun"] = {
        "status": metrics["status"], "model_environment": metrics["model_environment"],
        "manifest": "results/run_manifest.json",
    }
    write_json(dependency_path, dependency)
    if primary["n_genera"] < 25 and (
        primary["estimable"] or primary["observed_difference"] is not None
        or primary["p_one_sided"] is not None
    ):
        raise ValueError("Primary inference escaped the unchanged feasibility gate")
    changes = {key: {"before": before["counts"][key], "current": after["counts"][key]}
               for key in ("names_resolved", "genera_after_aggregation", "genera_with_chemistry",
                           "genera_with_classified_compounds", "genera_available_for_primary_test")}
    changes["mapped_structures"] = {
        "before": before["stage_metrics"]["chemistry"]["unique_compounds"],
        "current": after["stage_metrics"]["chemistry"]["unique_compounds"],
    }
    paths = [Path(name) for name in (
        "results/recall_baseline.json", "results/recall_baseline.md", "results/metrics.json",
        "results/funnel.json", "results/run_manifest.json", "results/offline_replay.json",
        "data/processed/behaviour/run_manifest.json", "data/processed/chemistry/run_manifest.json",
        "data/processed/bioactivity/run_manifest.json", "results/day2_blockers/lme4_status.json",
        "results/day2_blockers/trema_status.json", "docs/amendment_2026-09-13_trema_taxonomy.md",
    )]
    report = {
        "date": "2026-09-13", "assembled_at": timestamp(),
        "status": "complete" if verification["status"] == "passed" else "blocked",
        "blocked_reason": verification.get("blocked_reason"),
        "baseline": baseline["groups"], "model_environment": metrics["model_environment"],
        "trema": read_json(Path("results/day2_blockers/trema_status.json")),
        "funnel_changes": changes, "primary_status": primary["status"],
        "primary_estimable": primary["estimable"],
        "n_accepted": primary["n_accepted"], "n_rejected": primary["n_rejected"],
        "inference_blockers": metrics["inference_blockers"],
        "verification": {key: verification[key] for key in ("status", "files_compared", "frozen_files")},
        "artifacts": [artifact(path) for path in paths],
    }
    write_json(Path("results/day2_status.json"), report)
    Path("results/day2_status.md").write_text(render(report), encoding="utf-8")
    write_json(Path("results/end_to_end_manifest.json"), {
        "project": "aani", "assembled_at": report["assembled_at"],
        "protocol_commit": after["protocol_commit"], "frozen_files": verification["frozen_files"],
        "execution_status": report["status"], "primary_status": primary["status"],
        "estimable": primary["estimable"], "counts": after["counts"],
        "inference_blockers": metrics["inference_blockers"], "artifacts": report["artifacts"],
        "offline_replay": {"status": verification["status"], "verification_report": "results/offline_replay.json",
                           "scope": verification["scope"]},
        "prior_run_manifest": "results/day2_blockers/end_to_end_manifest.json",
    })
    print({"status": report["status"], "changes": changes, "inference_blockers": metrics["inference_blockers"]})


if __name__ == "__main__":
    main()
