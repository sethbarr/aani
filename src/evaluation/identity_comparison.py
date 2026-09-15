"""Compare three saved extraction runs using the frozen baseline scoring convention."""

from collections import Counter
from copy import deepcopy
from pathlib import Path

from src.common.io import read_json
from src.evaluation.comparison import (
    baseline_integrity,
    development_inventory,
    file_record,
    reference_rows,
)
from src.evaluation.recall import score_species, summarise_group

STAGES = ("detection", "survival", "correctness")
VARIANTS = ("baseline", "v1", "v2")
V1_EXTRACTION = Path("data/interim/extraction_saverschek_multispan_v1")
V2_EXTRACTION = Path("data/interim/extraction_saverschek_multispan_v2")
EXPECTED_JOBS = 3


def check_job_coverage(extraction: Path) -> dict:
    """Require all three saved responses identified by the source-run manifest.

    Args:
        extraction: Directory containing the saved extraction artifacts.

    Returns:
        Manifest, response input hashes, and explicit completeness blockers.
    """
    path = extraction / "run_manifest.json"
    if not path.is_file():
        return {"manifest": None, "response_input_hashes": [],
                "blocked_reason": "development_run_manifest_missing"}
    manifest = read_json(path)
    responses = [read_json(item) for item in sorted((extraction / "responses").glob("*.json"))]
    hashes = [response.get("input_hash") for response in responses]
    expected = manifest.get("input_hashes", [])
    reasons = []
    if manifest.get("jobs") != EXPECTED_JOBS or len(expected) != EXPECTED_JOBS:
        reasons.append("development_expected_three_jobs")
    if len(set(expected)) != len(expected):
        reasons.append("development_manifest_duplicate_input_hashes")
    if len(hashes) != EXPECTED_JOBS or set(hashes) != set(expected):
        reasons.append("development_response_job_coverage_incomplete")
    return {"manifest": manifest, "response_input_hashes": hashes,
            "blocked_reason": ";".join(reasons) or None}


def count_failure_reasons(candidates: list[dict], panel_names: set[str]) -> dict:
    """Count recorded grounding failures for every candidate and panel-name candidates."""
    failed = [row for row in candidates if row["grounding_status"] == "failed"]
    all_reasons = Counter(row["grounding_failure_reason"] for row in failed)
    panel_reasons = Counter(row["grounding_failure_reason"] for row in failed
                            if row["record"].get("plant_name_as_written") in panel_names)
    maximum = max(all_reasons.values(), default=0)
    return {
        "all_candidates": dict(sorted(all_reasons.items())),
        "panel_name_candidates": dict(sorted(panel_reasons.items())),
        "dominant_reasons": sorted(reason for reason, count in all_reasons.items()
                                   if count == maximum),
        "dominant_reason_count": maximum,
        "failed_candidate_count": len(failed),
    }


def score_variant(extraction: Path, baseline: dict, integrity_reason: str | None) -> dict:
    """Apply the unchanged baseline scorer to a reconciled, complete saved run.

    Args:
        extraction: Existing output directory for one extraction variant.
        baseline: Saved baseline containing the fixed reference rows.
        integrity_reason: Blocker when a frozen baseline artifact changed.

    Returns:
        Candidate inventory, species scores, separate group counts, and provenance.
    """
    candidates, inventory = development_inventory(extraction)
    coverage = check_job_coverage(extraction)
    reasons = [reason for reason in (
        integrity_reason, inventory["blocked_reason"], coverage["blocked_reason"]
    ) if reason]
    reason = ";".join(reasons) or None
    references = reference_rows(baseline)
    if reason:
        for row in references:
            row["scorable"] = False
            row["blocked_reason"] = ";".join(filter(None, [row["blocked_reason"], reason]))
    rows = [score_species(reference, candidates) for reference in references]
    groups = {group: summarise_group(rows, group) for group in ("PRIMARY", "CONTEXT")}
    panel_names = {row["species"] for row in rows}
    scoped = [row for row in candidates if row["record"].get("plant_name_as_written") in panel_names]
    paths = [extraction / name for name in (
        "run_manifest.json", "metrics.json", "observations.jsonl", "rejections.jsonl"
    )]
    paths.extend(sorted((extraction / "responses").glob("*.json")))
    return {
        "extraction": str(extraction), "status": "complete" if not reason else "blocked",
        "blocked_reason": reason, "manifest": coverage["manifest"],
        "response_input_hashes": coverage["response_input_hashes"],
        "files": [file_record(path) for path in paths],
        "inventory": {**inventory, "panel_name_candidates": len(scoped),
                      "outside_panel_name_candidates": len(candidates) - len(scoped)},
        "failure_reasons": count_failure_reasons(candidates, panel_names),
        "groups": groups, "species": rows, "candidates": candidates,
    }


def assess_primary_change(baseline: dict, v2: dict) -> dict:
    """Compare complete PRIMARY counts and request investigation of reduced proposals."""
    original = baseline["groups"]["PRIMARY"]
    current = v2["groups"]["PRIMARY"]
    complete = not current["unscorable_species"] and v2["blocked_reason"] is None
    original_survival = original["stages"]["survival"]["species_count"]
    current_survival = current["stages"]["survival"]["species_count"]
    original_detection = original["stages"]["detection"]["species_count"]
    current_detection = current["stages"]["detection"]["species_count"]
    return {
        "species_denominator": original["species_denominator"],
        "baseline_survival": original_survival,
        "v2_survival": current_survival if complete else None,
        "v2_beats_baseline_survival": current_survival > original_survival if complete else None,
        "baseline_detection": original_detection,
        "v2_detection": current_detection if complete else None,
        "v2_detection_below_baseline": current_detection < original_detection if complete else None,
        "proposal_suppression_investigation_required": (
            current_detection < original_detection if complete else None
        ),
        "blocked_reason": None if complete else v2["blocked_reason"] or "primary_unscorable",
    }


def build_identity_comparison(extraction: Path, root: Path) -> dict:
    """Build a comparable three-run measurement from the unchanged saved reference.

    Args:
        extraction: The sole saved v2 extraction run to measure.
        root: Repository containing the frozen baseline and original v1 artifacts.

    Returns:
        Count-only report with baseline, v1, and v2 using structured-direction matching.
    """
    baseline = read_json(root / "results/recall_baseline.json")
    integrity = baseline_integrity(baseline, root)
    v1 = score_variant(root / V1_EXTRACTION, baseline, integrity["blocked_reason"])
    v2 = score_variant(extraction, baseline, integrity["blocked_reason"])
    run_status_path = root / "results/grounding_development_v2/run_status.json"
    run_status = read_json(run_status_path) if run_status_path.is_file() else None
    reasons = [f"{name}:{run['blocked_reason']}" for name, run in (("v1", v1), ("v2", v2))
               if run["blocked_reason"]]
    if integrity["blocked_reason"]:
        reasons.insert(0, integrity["blocked_reason"])
    if v2["status"] == "blocked" and run_status and run_status.get("blocked_reason"):
        reasons.insert(0, run_status["blocked_reason"])
    return {
        "schema_version": 1, "set_type": "DEVELOPMENT SET", "unit": "species-direction pair",
        "source_id": baseline["source_id"], "panel_species_denominator": 11,
        "panel_species_direction_pair_denominator": 16,
        "sampling_scope": baseline["sampling_scope"],
        "status": "complete" if not reasons else "partially_blocked",
        "blocked_reason": ";".join(reasons) or None,
        "baseline_integrity": integrity,
        "baseline": {"groups": deepcopy(baseline["groups"]),
                     "species": deepcopy(baseline["species"]),
                     "inventory": deepcopy(baseline["inventory"])},
        "v1": v1, "v2": v2, "live_run_status": run_status,
        "primary_change": assess_primary_change(baseline, v2),
        "direction_scoring": baseline["direction_scoring"],
        "correctness_definition": "Every variant uses the baseline score_species and summarise_group "
        "convention: a surviving record is correct when its structured species and outcome match "
        "the fixed reference pair. No semantic-review gate is added to this comparison.",
        "v1_scoring_note": "The original v1 report and artifacts are preserved. Its candidates are "
        "rescored here with the baseline convention, which is also used for v2.",
        "contamination_risk": "The curator matrix was produced by reading the same text blocks the "
        "extractor read, so shared blind spots would inflate apparent recall. The curator had the "
        "complete cached text including tables; the original extractor worked chunk-wise under a "
        "strict quote constraint. Implementers know the reference. This is one panel from one paper "
        "and is not a sample from any population.",
        "reference_provenance_species": {
            strength: sum(row["provenance_strength"] == strength for row in baseline["species"])
            for strength in ("author_prose", "author_table_grouping")
        },
        "table_caveat": "Directions were checked against Table 1 of the original PDF and the groupings are "
        "author-assigned, not our inference from numerical signs. What remains unverified "
        "is the semantic support for individual rows and captions. Reference labels remain "
        "unchanged.",
    }


def stage_cell(group: dict, stage: str, context: bool) -> str:
    """Format one variant's stage with fixed denominators and explicit unscorable counts."""
    values = group["stages"][stage]
    unknown = len(group["unscorable_species"])
    if context:
        coverage = values["direction_coverage"]
        text = (f"both {coverage['both_directions_surfaced']}; "
                f"collapsed {coverage['collapsed_to_one']}; absent {coverage['absent']}; "
                f"unscorable {coverage['unscorable']}; "
                f"pairs {values['species_direction_pair_count']} of "
                f"{group['species_direction_pair_denominator']}")
    else:
        text = (f"{values['species_count']} of {group['species_denominator']} species; "
                f"{values['species_direction_pair_count']} of "
                f"{group['species_direction_pair_denominator']} pairs")
        if unknown:
            text += f"; {unknown} unscorable"
    return text + " (scored species only)" if unknown else text


def render_identity_summary(report: dict) -> str:
    """Render separate three-variant tables and the required development-set caveats."""
    lines = [
        "# Source-level ant identity — DEVELOPMENT SET", "",
        "This is one panel from one paper; implementers know the reference. It is not a sample "
        "from any population. All three variants use baseline structured-direction matching for "
        "correctness. An extra direction in a quote counts only if emitted as a structured outcome.",
        "", "## PRIMARY", "",
        "The denominator is six species and six species-direction pairs.", "",
        "| Stage | baseline | v1 | v2 |", "| --- | --- | --- | --- |",
    ]
    for stage in STAGES:
        cells = [stage_cell(report[variant]["groups"]["PRIMARY"], stage, False)
                 for variant in VARIANTS]
        lines.append(f"| {stage} | {' | '.join(cells)} |")
    lines += [
        "", "## CONTEXT", "",
        "Each stage classifies five species as both directions surfaced, collapsed to one, "
        "absent, or unscorable; the pair denominator is ten.", "",
        "| Stage | baseline | v1 | v2 |", "| --- | --- | --- | --- |",
    ]
    for stage in STAGES:
        cells = [stage_cell(report[variant]["groups"]["CONTEXT"], stage, True)
                 for variant in VARIANTS]
        lines.append(f"| {stage} | {' | '.join(cells)} |")
    change = report["primary_change"]
    if change["v2_beats_baseline_survival"] is None:
        outcome = f"The PRIMARY survival comparison is blocked: {change['blocked_reason']}."
    elif change["v2_beats_baseline_survival"]:
        outcome = (f"v2 PRIMARY survival is {change['v2_survival']} of 6, above the "
                   f"baseline {change['baseline_survival']} of 6.")
    else:
        outcome = (f"v2 PRIMARY survival is {change['v2_survival']} of 6 and does not beat "
                   f"the baseline {change['baseline_survival']} of 6.")
    failures = report["v2"]["failure_reasons"]
    if report["v2"]["blocked_reason"]:
        failure_text = "The dominant v2 failure reason is unscorable because the run is blocked."
    elif failures["dominant_reasons"]:
        failure_text = (f"The dominant recorded v2 grounding failure reason is "
                        f"{', '.join(failures['dominant_reasons'])} "
                        f"({failures['dominant_reason_count']} of "
                        f"{failures['failed_candidate_count']} failed candidates per listed reason).")
    else:
        failure_text = "v2 has zero recorded grounding failures."
    lines += ["", outcome, "", failure_text, ""]
    if change["proposal_suppression_investigation_required"]:
        lines += [
            f"v2 PRIMARY detection is {change['v2_detection']} of 6, below baseline "
            f"{change['baseline_detection']} of 6. This requires investigation of whether the "
            "two-span schema suppresses proposals; these counts alone do not establish the cause.", "",
        ]
    provenance = report["reference_provenance_species"]
    lines += [
        f"Reference provenance remains {provenance['author_prose']} author_prose and "
        f"{provenance['author_table_grouping']} author_table_grouping species. PRIMARY has "
        "2 author_prose and 4 author_table_grouping; CONTEXT has 4 author_prose and "
        "1 author_table_grouping. " + report["table_caveat"],
        "", report["contamination_risk"], "", report["v1_scoring_note"], "",
        "Candidate pass/failure counts are stage yields.", "",
        f"Baseline artifacts and recorded inputs unchanged: "
        f"{report['baseline_integrity']['all_original_bytes_unchanged']}. "
        f"Comparison status: {report['status']}. Blocked reason: {report['blocked_reason'] or 'none'}.",
        "",
    ]
    return "\n".join(lines)
