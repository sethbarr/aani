"""Compare generalized glyph grounding separately on both saved model samples."""

from pathlib import Path

from src.common.io import read_json, read_jsonl
from src.evaluation.comparison import baseline_integrity
from src.evaluation.glyph_comparison import V3_EXTRACTION, compare_proposal_samples
from src.evaluation.identity_comparison import score_variant
from src.evaluation.repeat_comparison import V3_REPEAT_EXTRACTION

V4_EXTRACTION = Path("data/interim/extraction_saverschek_multispan_v4")
V4_REPEAT_EXTRACTION = Path("data/interim/extraction_saverschek_multispan_v4_repeat")
SAMPLE_PATHS = {
    "sample1": (V3_EXTRACTION, V4_EXTRACTION),
    "sample2": (V3_REPEAT_EXTRACTION, V4_REPEAT_EXTRACTION),
}
VARIANTS = ("sample1_v3", "sample1_v4", "sample2_v3", "sample2_v4")


def transition_record(original: dict, current: dict, observation: dict | None) -> dict:
    """Describe one changed grounding outcome using its original raw-record digest.

    Args:
        original: Reconciled candidate under v3 rules.
        current: The identical proposal under v4 rules.
        observation: Accepted v4 observation when the current candidate survives.

    Returns:
        Candidate identities, before/after outcomes, and source-match provenance.
    """
    return {
        "v3_candidate_id": original["candidate_id"],
        "v4_candidate_id": current["candidate_id"],
        "record_digest": original["record_digest"],
        "v3_input_hash": original["input_hash"],
        "v4_input_hash": current["input_hash"],
        "species": original["record"]["plant_name_as_written"],
        "direction": original["record"]["outcome"],
        "v3_grounding_status": original["grounding_status"],
        "v4_grounding_status": current["grounding_status"],
        "v3_failure_reason": original["grounding_failure_reason"],
        "v4_failure_reason": current["grounding_failure_reason"],
        "quote_grounding_route": observation.get("quote_grounding_route") if observation else None,
        "grounded_source_spans": observation.get("grounded_source_spans", []) if observation else [],
    }


def compare_survivors(v3: dict, v4: dict, sample_check: dict) -> dict:
    """Track recoveries and losses within one unchanged proposal sample.

    Args:
        v3: Scored v3 candidate inventory.
        v4: Scored v4 candidate inventory.
        sample_check: Request and proposal identity checks for each corresponding chunk.

    Returns:
        Counted recoveries, retained survivors, losses, and explicit comparison blockers.
        A measured loss remains visible as a regression without suppressing scored counts.
    """
    reasons = [reason for reason in (
        sample_check["blocked_reason"], v3["blocked_reason"], v4["blocked_reason"]
    ) if reason]
    result = {
        "status": "blocked" if reasons else "complete",
        "blocked_reason": ";".join(reasons) or None,
        "alignment": "Corresponding manifest chunk and unchanged raw-record digest.",
        "recovered_records": [], "recovered_count": None,
        "lost_records": [], "lost_count": None,
        "retained_survivor_count": None, "no_lost_v3_survivors": None,
    }
    if reasons:
        return result
    current_input = {
        row["v2_input_hash"]: row["current_input_hash"] for row in sample_check["chunks"]
    }
    current_candidates = {
        (row["input_hash"], row["record_digest"]): row for row in v4["candidates"]
    }
    observations = {
        (row["input_hash"], row["record_id"]): row
        for row in read_jsonl(Path(v4["extraction"]) / "observations.jsonl")
    }
    retained = 0
    for original in v3["candidates"]:
        key = (current_input[original["input_hash"]], original["record_digest"])
        current = current_candidates[key]
        was_passed = original["grounding_status"] == "passed"
        now_passed = current["grounding_status"] == "passed"
        if was_passed and now_passed:
            retained += 1
        elif was_passed:
            result["lost_records"].append(transition_record(original, current, None))
        elif now_passed:
            result["recovered_records"].append(
                transition_record(original, current, observations[key])
            )
    result.update({
        "recovered_count": len(result["recovered_records"]),
        "lost_count": len(result["lost_records"]),
        "retained_survivor_count": retained,
        "no_lost_v3_survivors": not result["lost_records"],
    })
    return result


def build_generalized_comparison(root: Path) -> dict:
    """Score both saved samples under v3 and v4 with the unchanged baseline scorer.

    Args:
        root: Repository containing the preserved reference and four extraction outputs.

    Returns:
        Separate count-only measurements, fixed-proposal checks, and survivor transitions.
        Missing runs remain unscorable with the original species and pair denominators.
    """
    baseline = read_json(root / "results/recall_baseline.json")
    integrity = baseline_integrity(baseline, root)
    runs = {}
    checks = {}
    transitions = {}
    reasons = [integrity["blocked_reason"]] if integrity["blocked_reason"] else []
    for sample, paths in SAMPLE_PATHS.items():
        original, current = (root / path for path in paths)
        check = compare_proposal_samples(original, current, True)
        checks[sample] = check
        current_reasons = [reason for reason in (
            integrity["blocked_reason"], check["blocked_reason"]
        ) if reason]
        v3 = score_variant(original, baseline, integrity["blocked_reason"])
        v4 = score_variant(current, baseline, ";".join(current_reasons) or None)
        runs[f"{sample}_v3"] = v3
        runs[f"{sample}_v4"] = v4
        transitions[sample] = compare_survivors(v3, v4, check)
        for rules, run in (("v3", v3), ("v4", v4)):
            if run["blocked_reason"]:
                reasons.append(f"{sample}_{rules}:{run['blocked_reason']}")
    return {
        "schema_version": 1,
        "set_type": "DEVELOPMENT SET",
        "unit": "species-direction pair",
        "source_id": baseline["source_id"],
        "panel_species_denominator": 11,
        "panel_species_direction_pair_denominator": 16,
        "sampling_scope": baseline["sampling_scope"],
        "status": "complete" if not reasons else "partially_blocked",
        "blocked_reason": ";".join(reasons) or None,
        "baseline_integrity": integrity,
        "sample_checks": checks,
        "sample_transitions": transitions,
        "variant_order": list(VARIANTS),
        "samples_pooled": False,
        "direction_scoring": baseline["direction_scoring"],
        "correctness_definition": "Every run uses the unchanged baseline score_species and "
        "summarise_group convention: correctness requires a surviving record whose structured "
        "species and outcome match the fixed reference pair. No semantic-review gate is added.",
        "contamination_risk": "The curator matrix was produced by reading the same text blocks "
        "the extractor read, so shared blind spots would inflate apparent recall. The curator "
        "had the complete cached text including tables; the original extractor worked "
        "chunk-wise under a strict quote constraint. Implementers know the reference. This is "
        "one panel from one paper and is not a sample from any population.",
        "sampling_caveat": "Both existing samples informed development of the generalized "
        "glyph rule. Neither sample is an independent test of that rule. Both samples are "
        "reported separately, with every raw proposal retained.",
        "table_caveat": "The numerical table transcription was never visually verified against "
        "the PDF, so table-derived labels are weaker ground truth. Reference labels remain "
        "unchanged.",
        **runs,
    }
