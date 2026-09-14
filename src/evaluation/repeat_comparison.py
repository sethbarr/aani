"""Score both saved model samples under their v2 and v3 grounding outcomes."""

from pathlib import Path

from src.common.io import read_json
from src.evaluation.comparison import baseline_integrity
from src.evaluation.glyph_comparison import (
    V2_EXTRACTION,
    V2_REPEAT_EXTRACTION,
    V3_EXTRACTION,
    compare_proposal_samples,
)
from src.evaluation.identity_comparison import score_variant

V3_REPEAT_EXTRACTION = Path("data/interim/extraction_saverschek_multispan_v3_repeat")
SAMPLE_PATHS = {
    "sample1": (V2_EXTRACTION, V3_EXTRACTION),
    "sample2": (V2_REPEAT_EXTRACTION, V3_REPEAT_EXTRACTION),
}
VARIANTS = ("sample1_v2", "sample1_v3", "sample2_v2", "sample2_v3")


def build_repeat_comparison(root: Path) -> dict:
    """Measure each preserved sample with the unchanged baseline scoring convention.

    Args:
        root: Repository containing the fixed reference and four saved run directories.

    Returns:
        Four separate run inventories and scores, within-sample request and proposal
        preservation checks, and explicit blockers for incomplete comparisons.
    """
    baseline = read_json(root / "results/recall_baseline.json")
    integrity = baseline_integrity(baseline, root)
    runs = {}
    checks = {}
    reasons = []
    if integrity["blocked_reason"]:
        reasons.append(integrity["blocked_reason"])
    for sample, paths in SAMPLE_PATHS.items():
        original, current = (root / path for path in paths)
        check = compare_proposal_samples(original, current, True)
        checks[sample] = check
        v3_reasons = [reason for reason in (
            integrity["blocked_reason"], check["blocked_reason"]
        ) if reason]
        runs[f"{sample}_v2"] = score_variant(original, baseline, integrity["blocked_reason"])
        runs[f"{sample}_v3"] = score_variant(current, baseline, ";".join(v3_reasons) or None)
        for rules in ("v2", "v3"):
            key = f"{sample}_{rules}"
            if runs[key]["blocked_reason"]:
                reasons.append(f"{key}:{runs[key]['blocked_reason']}")
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
        "table_caveat": "The numerical table transcription was never visually verified against "
        "the PDF, so table-derived labels are weaker ground truth. Reference labels remain "
        "unchanged.",
        **runs,
    }
