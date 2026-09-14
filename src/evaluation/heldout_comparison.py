"""Score a held-out model draw under the unchanged v4 grounding rule."""

from pathlib import Path

from src.common.io import read_json
from src.evaluation.comparison import baseline_integrity
from src.evaluation.generalized_glyph_comparison import V4_EXTRACTION, V4_REPEAT_EXTRACTION
from src.evaluation.glyph_comparison import compare_proposal_samples
from src.evaluation.identity_comparison import STAGES, score_variant, stage_cell

V2_SAMPLE3_EXTRACTION = Path("data/interim/extraction_saverschek_multispan_v2_sample3")
V4_SAMPLE3_EXTRACTION = Path("data/interim/extraction_saverschek_multispan_v4_sample3")
SAMPLE_PATHS = {
    "sample1_v4": V4_EXTRACTION,
    "sample2_v4": V4_REPEAT_EXTRACTION,
    "sample3_v4": V4_SAMPLE3_EXTRACTION,
}
VARIANTS = tuple(SAMPLE_PATHS)


def stage_yield(run: dict) -> dict:
    """Report the candidate pass count with an explicit completeness blocker.

    Args:
        run: Output from the unchanged baseline-convention variant scorer.

    Returns:
        Candidate counts for a complete run, or null counts and the blocking reason.
    """
    complete = run["blocked_reason"] is None
    inventory = run["inventory"]
    return {
        "status": "complete" if complete else "blocked",
        "blocked_reason": run["blocked_reason"],
        "grounding_passes": inventory["grounding_passes"] if complete else None,
        "candidate_records": inventory["candidate_records"] if complete else None,
        "grounding_failures": inventory["grounding_failures"] if complete else None,
        "interpretation": "Candidate stage yield includes outside-panel proposals.",
    }


def build_heldout_comparison(root: Path) -> dict:
    """Score three separate samples using the unchanged baseline structured directions.

    Args:
        root: Repository containing the reference and all saved extraction outputs.

    Returns:
        Separate v4 measurements and a fixed-proposal check for the held-out third draw.
        Missing or mismatched runs retain all species and pair denominators as unscorable.
        This function performs no new sampling, rule changes, or failure classification.
    """
    baseline = read_json(root / "results/recall_baseline.json")
    integrity = baseline_integrity(baseline, root)
    sample3_check = compare_proposal_samples(
        root / V2_SAMPLE3_EXTRACTION, root / V4_SAMPLE3_EXTRACTION, True
    )
    runs = {}
    reasons = [integrity["blocked_reason"]] if integrity["blocked_reason"] else []
    for variant, path in SAMPLE_PATHS.items():
        run_reasons = [integrity["blocked_reason"]] if integrity["blocked_reason"] else []
        if variant == "sample3_v4" and sample3_check["blocked_reason"]:
            run_reasons.append(sample3_check["blocked_reason"])
        run = score_variant(root / path, baseline, ";".join(run_reasons) or None)
        runs[variant] = run
        if run["blocked_reason"]:
            reasons.append(f"{variant}:{run['blocked_reason']}")
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
        "sample3_check": sample3_check,
        "variant_order": list(VARIANTS),
        "samples_pooled": False,
        "stage_yields": {variant: stage_yield(run) for variant, run in runs.items()},
        "sample_roles": {
            "sample1_v4": "informed_v4_rule_development",
            "sample2_v4": "informed_v4_rule_development",
            "sample3_v4": "held_out_draw_under_frozen_v4_rule",
        },
        "direction_scoring": baseline["direction_scoring"],
        "correctness_definition": "Every run uses the unchanged baseline score_species and "
        "summarise_group convention: correctness requires a surviving record whose structured "
        "species and outcome match the fixed reference pair. No semantic-review gate is added.",
        "sampling_caveat": "Samples 1 and 2 informed v4 rule development. Sample 3 is the "
        "held-out model draw under the frozen rule. Its result addresses a fresh response "
        "sample from the same request configuration; unseen-paper performance remains untested. "
        "Every sample is reported separately, with no selection or pooling of proposals.",
        "heldout_protocol": "Freeze the rule before sample 3 is drawn, score its complete "
        "saved proposals before inspecting failures, and keep the rule unchanged afterward. "
        "The separate run and preservation records establish compliance with this protocol.",
        "contamination_risk": "The curator matrix was produced by reading the same text blocks "
        "the extractor read, so shared blind spots would inflate apparent recall. The curator "
        "had the complete cached text including tables; the original extractor worked "
        "chunk-wise under a strict quote constraint. Implementers know the reference. This is "
        "one panel from one paper and is not a sample from any population.",
        "table_caveat": "The numerical table transcription was never visually verified against "
        "the PDF, so table-derived labels are weaker ground truth. Reference labels remain "
        "unchanged.",
        **runs,
    }


def render_heldout_tables(report: dict) -> str:
    """Render the three samples with separate PRIMARY and CONTEXT denominators.

    Args:
        report: A completed or explicitly blocked held-out comparison report.

    Returns:
        Markdown tables containing three data columns, stage counts, and candidate yields.
    """
    lines = []
    for group in ("PRIMARY", "CONTEXT"):
        denominator = ("six species-direction pairs" if group == "PRIMARY"
                       else "five species, ten species-direction pairs")
        lines += [
            f"## {group} — {denominator}", "",
            "| Sample 1: v4 | Sample 2: v4 | Sample 3: v4 (held out) |",
            "| --- | --- | --- |",
        ]
        for stage in STAGES:
            cells = [
                f"{stage.capitalize()}: "
                f"{stage_cell(report[variant]['groups'][group], stage, group == 'CONTEXT')}"
                for variant in VARIANTS
            ]
            lines.append(f"| {' | '.join(cells)} |")
        lines.append("")
    lines += [
        "## Candidate stage yield", "",
        "| Sample 1: v4 | Sample 2: v4 | Sample 3: v4 (held out) |",
        "| --- | --- | --- |",
    ]
    yields = []
    for variant in VARIANTS:
        value = report["stage_yields"][variant]
        yields.append(
            f"Blocked: {value['blocked_reason']}" if value["blocked_reason"] else
            f"{value['grounding_passes']} of {value['candidate_records']}"
        )
    lines.extend([f"| {' | '.join(yields)} |", ""])
    return "\n".join(lines)
