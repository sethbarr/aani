"""Measure additive v6 cache-side grounding with unchanged baseline scoring."""

from pathlib import Path

from src.common.io import read_json, read_jsonl
from src.evaluation.comparison import baseline_integrity
from src.evaluation.glyph_comparison import compare_proposal_samples
from src.evaluation.heldout_comparison import stage_yield
from src.evaluation.identity_comparison import STAGES, score_variant, stage_cell

V6_ROOT = Path("data/interim/extraction_saverschek_multispan_v6")
RAW_SAMPLES = {
    "sample1": Path("data/interim/extraction_saverschek_multispan_v2"),
    "sample2": Path("data/interim/extraction_saverschek_multispan_v2_repeat_for_v3"),
    "sample3": Path("data/interim/extraction_saverschek_multispan_v2_sample3"),
    "sample4": Path("data/interim/extraction_saverschek_multispan_v2_sample4"),
}
PRIOR_SAMPLES = {
    "sample1": {
        "v4": Path("data/interim/extraction_saverschek_multispan_v4"),
        "v5": Path("data/interim/extraction_saverschek_multispan_v5"),
    },
    "sample2": {
        "v4": Path("data/interim/extraction_saverschek_multispan_v4_repeat"),
        "v5": Path("data/interim/extraction_saverschek_multispan_v5_repeat"),
    },
    "sample3": {
        "v4": Path("data/interim/extraction_saverschek_multispan_v4_sample3"),
        "v5": Path("data/interim/extraction_saverschek_multispan_v5_sample3"),
    },
}


def regression_delta(previous: Path, current: Path) -> dict:
    """Compare every prior survivor identity and structured direction with v6.

    Args:
        previous: A saved v4 or v5 output directory.
        current: The corresponding v6 output from the same raw proposal sample.

    Returns:
        Survivor retention and direction changes, with explicit missing-input blockers.
    """
    paths = [previous / "observations.jsonl", current / "observations.jsonl"]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        return {
            "status": "blocked", "blocked_reason": "missing_survivor_files:" + ";".join(missing),
            "previous_survivors": None, "v6_survivors": None,
            "previous_survivors_retained": None, "lost_record_ids": None,
            "new_record_ids": None, "direction_changes": None,
        }
    before_rows, after_rows = [read_jsonl(path) for path in paths]
    before = {row["record_id"]: row for row in before_rows}
    after = {row["record_id"]: row for row in after_rows}
    duplicated = len(before) != len(before_rows) or len(after) != len(after_rows)
    shared = set(before) & set(after)
    lost = sorted(set(before) - set(after))
    changes = [
        {"record_id": record_id, "previous_outcome": before[record_id]["outcome"],
         "v6_outcome": after[record_id]["outcome"]}
        for record_id in sorted(shared)
        if before[record_id]["outcome"] != after[record_id]["outcome"]
    ]
    reasons = []
    if duplicated:
        reasons.append("duplicate_survivor_record_ids")
    if lost:
        reasons.append("previous_survivors_lost")
    if changes:
        reasons.append("previous_survivor_directions_changed")
    return {
        "status": "passed" if not reasons else "failed",
        "blocked_reason": ";".join(reasons) or None,
        "previous_survivors": len(before), "v6_survivors": len(after),
        "previous_survivors_retained": len(shared), "lost_record_ids": lost,
        "new_record_ids": sorted(set(after) - set(before)), "direction_changes": changes,
    }


def build_comparison(root: Path, include_sample4: bool = False) -> dict:
    """Score each complete sample separately under the fixed reference convention.

    Args:
        root: Repository containing baseline reference and saved extraction outputs.
        include_sample4: Include the fresh draw only when explicitly requested for scoring.

    Returns:
        Unchanged baseline-convention scores, proposal identity checks, and v4/v5 regressions.
        Missing or changed inputs remain in the denominator with unscorable reasons.
    """
    baseline = read_json(root / "results/recall_baseline.json")
    integrity = baseline_integrity(baseline, root)
    sample_names = ["sample1", "sample2", "sample3"]
    if include_sample4:
        sample_names.append("sample4")
    runs = {}
    checks = {}
    regressions = {}
    reasons = []
    for sample in sample_names:
        variant = f"{sample}_v6"
        extraction = root / V6_ROOT / sample
        check = compare_proposal_samples(root / RAW_SAMPLES[sample], extraction, True)
        checks[variant] = check
        run_reasons = [reason for reason in (integrity["blocked_reason"], check["blocked_reason"])
                       if reason]
        run = score_variant(extraction, baseline, ";".join(run_reasons) or None)
        runs[variant] = run
        if run["blocked_reason"]:
            reasons.append(f"{variant}:{run['blocked_reason']}")
        if sample in PRIOR_SAMPLES:
            regressions[variant] = {
                rule: regression_delta(root / path, extraction)
                for rule, path in PRIOR_SAMPLES[sample].items()
            }
            for rule, delta in regressions[variant].items():
                if delta["status"] != "passed":
                    reasons.append(f"{variant}:{rule}:{delta['blocked_reason']}")
    return {
        "schema_version": 1, "set_type": "DEVELOPMENT SET",
        "status": "complete" if not reasons else "partially_blocked",
        "blocked_reason": ";".join(reasons) or None,
        "unit": "species-direction pair", "source_id": baseline["source_id"],
        "panel_species_denominator": 11, "panel_species_direction_pair_denominator": 16,
        "sampling_scope": baseline["sampling_scope"], "samples_pooled": False,
        "baseline_integrity": integrity, "variant_order": list(runs),
        "sample_checks": checks, "regressions": regressions,
        "stage_yields": {variant: stage_yield(run) for variant, run in runs.items()},
        "sample_roles": {
            variant: ("held_out_draw_under_frozen_v6_rule" if variant == "sample4_v6"
                      else "informed_v6_rule_development") for variant in runs
        },
        "direction_scoring": baseline["direction_scoring"],
        "correctness_definition": "Correctness uses the unchanged baseline score_species and "
        "summarise_group functions: a surviving structured species and outcome must match the "
        "fixed reference pair. No semantic adjudication gate is added.",
        "sampling_caveat": "Samples 1–3 are DEVELOPMENT-SET evidence for v6; sample 3's failures "
        "informed the cache-side rule. Sample 4, if drawn, is a held-out model draw under the "
        "frozen rule. It measures a fresh draw of the same requests; unseen-paper performance "
        "remains untested. Every sample is separate and no proposals are pooled.",
        "contamination_risk": "This is one panel from one paper; implementers know the reference. "
        "It is not a sample from any population. The curator matrix used the same text blocks as "
        "the extractor, so shared blind spots would inflate apparent recall. The curator had "
        "the complete cache including tables; the original extractor worked chunk-wise under "
        "a strict quote constraint.",
        "table_caveat": "Directions were checked against Table 1 of the original PDF and the groupings are "
        "author-assigned, not our inference from numerical signs. What remains unverified "
        "is the semantic support for individual rows and captions. Reference labels remain "
        "unchanged.",
        **runs,
    }


def render_tables(report: dict) -> str:
    """Render count-only stages for each sample with the original group denominators.

    Args:
        report: Comparison built from three or four independently scored samples.

    Returns:
        Markdown tables with one data column per sample and explicit unscorable counts.
    """
    variants = report["variant_order"]
    labels = [f"Sample {name[6]}: v6" + (" (held out)" if name == "sample4_v6" else "")
              for name in variants]
    header = "| Stage | " + " | ".join(labels) + " |"
    divider = "| " + " | ".join(["---"] * (len(variants) + 1)) + " |"
    lines = []
    for group in ("PRIMARY", "CONTEXT"):
        denominator = "six pairs" if group == "PRIMARY" else "five species, ten pairs"
        lines.extend([f"## {group} — {denominator}", "", header, divider])
        for stage in STAGES:
            cells = [stage_cell(report[name]["groups"][group], stage, group == "CONTEXT")
                     for name in variants]
            lines.append(f"| {stage.capitalize()} | {' | '.join(cells)} |")
        unscorable = [str(len(report[name]["groups"][group]["unscorable_species"]))
                      for name in variants]
        lines.extend([f"| Unscorable species | {' | '.join(unscorable)} |", ""])
    lines.extend(["## Candidate stage yield", "", header, divider])
    cells = []
    for variant in variants:
        value = report["stage_yields"][variant]
        cells.append(f"Blocked: {value['blocked_reason']}" if value["blocked_reason"] else
                     f"{value['grounding_passes']} of {value['candidate_records']}")
    lines.extend([f"| Grounding survivors | {' | '.join(cells)} |", ""])
    return "\n".join(lines)
