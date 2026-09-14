"""Report both saved samples and diagnose the unchanged v3 repeat failures."""

from pathlib import Path

from src.common.io import read_json, timestamp, write_json
from src.evaluation.identity_comparison import STAGES, stage_cell
from src.evaluation.repeat_comparison import (
    V3_REPEAT_EXTRACTION,
    VARIANTS,
    build_repeat_comparison,
)
from src.evaluation.repeat_failures import classify_repeat_failures
from src.extraction.pipeline import make_jobs

OUTPUT = Path("results/grounding_development_v3")
HEADERS = "| Sample 1: v2 rules | Sample 1: v3 rules | Sample 2: v2 rules | Sample 2: v3 rules |"


def comparison_table(report: dict, group: str) -> list[str]:
    """Render four separate count columns with baseline scoring semantics.

    Args:
        report: Complete four-run comparison or explicit per-run blockers.
        group: PRIMARY or CONTEXT, preserving its fixed denominator.

    Returns:
        Markdown table lines with all three measurement stages.
    """
    lines = [HEADERS, "| --- | --- | --- | --- |"]
    for stage in STAGES:
        cells = [f"{stage.capitalize()}: " + stage_cell(
            report[name]["groups"][group], stage, group == "CONTEXT"
        ) for name in VARIANTS]
        lines.append(f"| {' | '.join(cells)} |")
    return lines


def generalization_verdict(report: dict, failures: dict) -> str:
    """State the observed cross-sample result without a population claim.

    Args:
        report: Separate baseline-convention measurements for both samples.
        failures: Mutually exclusive first-failure classifications for sample two.

    Returns:
        One sentence identifying whether this fixed policy covers the repeat failures.
    """
    if report["blocked_reason"] or failures["blocked_reason"]:
        return "The cross-sample conclusion is blocked by incomplete measurement or failure evidence."
    original = report["sample2_v2"]["inventory"]["grounding_passes"]
    changed = report["sample2_v3"]["inventory"]["grounding_passes"]
    glyph_failures = failures["category_counts"]["glyph_substitution_not_covered"]
    if changed == original and glyph_failures:
        return ("The pinned v3 fix fails to generalize across these two samples: sample 2 gains "
                f"zero survivors and retains {glyph_failures} failures caused by different, "
                "unpermitted glyph substitutions.")
    return (f"Across these two samples, sample 2 changes from {original} to {changed} surviving "
            f"records and retains {glyph_failures} uncovered glyph failures under the fixed policy.")


def render_summary(report: dict, failures: dict, verification: dict) -> str:
    """Render the requested side-by-side measurement and ordered failure evidence.

    Args:
        report: Four independently scored run inventories.
        failures: Diagnostic-only attribution of saved sample-two rejections.
        verification: Byte-preservation and offline replay result.

    Returns:
        A count-only DEVELOPMENT SET report with explicit evidence limits.
    """
    lines = [
        "# Repeat sample under unchanged v3 rules — DEVELOPMENT SET", "",
        "The saved sample 2 proposals were processed with the unchanged v3 validator and glyph "
        "policy, offline with zero model requests. Within each sample, both rule sets use the "
        "same request hashes and raw proposals. Both samples are reported separately; none of "
        "their records are pooled or selected across draws.", "",
        "This DEVELOPMENT SET is one panel from one paper, implementers know the reference, "
        "and it is not a sample from any population. Correctness uses the unchanged baseline "
        "structured-direction convention.", "", "## PRIMARY — six species-direction pairs", "",
        *comparison_table(report, "PRIMARY"), "",
        "## CONTEXT — five species, ten species-direction pairs", "",
        "Both means both directions surfaced; collapsed means one direction surfaced. "
        "Each cell retains absent and unscorable species explicitly.", "",
        *comparison_table(report, "CONTEXT"), "", "## Candidate stage yield", "",
        HEADERS, "| --- | --- | --- | --- |",
    ]
    yields = [f"{report[name]['inventory']['grounding_passes']} of "
              f"{report[name]['inventory']['candidate_records']}" for name in VARIANTS]
    lines += [f"| {' | '.join(yields)} |", "", "## Sample 2 failures under v3", "",
              "Each record is classified by its first returned reason in validator order. "
              "Later gates are not adjudicated after an earlier rejection.", ""]
    labels = {
        "glyph_substitution_not_covered": "Glyph substitution outside the two pinned equivalences",
        "identity": "Identity", "name_surface": "Name surface", "other": "Other",
    }
    for category, count in failures["category_counts"].items():
        lines.append(f"- {labels[category]}: {count} records.")
    lines += ["", "Observed, unpermitted substitutions in the first-failing spans:", ""]
    for item in failures["unpermitted_substitutions"]:
        glyph = chr(int(item["source_codepoint"][2:], 16))
        lines.append(f"- Emitted `{item['model_codepoint']}` replaces cached "
                     f"`{item['source_codepoint']}` ({glyph}): {item['records']} records, "
                     f"{item['occurrences']} character occurrences.")
    lines += ["", "The diagnostic establishes a unique source match with every other "
              "whitespace-normalized character unchanged. These observed substitutions "
              "were never applied to the validator, proposals, or scores. The permitted "
              "policy remains U+0001→± and U+0003→¼ in the original hash-pinned table block.", "",
              "### Every failed record, in proposal order", "",
              "Indices are zero-based. Full raw candidate hashes, response hashes, original quotes, "
              "source offsets, and UTF-8 evidence are in [repeat_failures.json](repeat_failures.json).", "",
              "| Chunk:record | Species | Direction | First ordered failure | Observed substitution |",
              "| --- | --- | --- | --- | --- |"]
    for row in failures["records"]:
        span = row["first_failure_span"]
        evidence = span.get("unpermitted_substitution_evidence") if span else None
        pairs = sorted({f"{item['model_codepoint']}→{item['source_codepoint']}"
                        for item in evidence["replacements"]}) if evidence else []
        lines.append(f"| {row['chunk_index']}:{row['candidate_index']} | "
                     f"{row['plant_name_as_written']} | {row['outcome']} | "
                     f"`{row['ordered_failure_reason']}` | {', '.join(pairs) or row['category']} |")
    lines += ["", "## Cross-sample verdict", "", generalization_verdict(report, failures), "",
              "All observed sample 2 rejections are glyph failures at the first failing gate; "
              "this run makes no claim that later identity or name checks would pass after "
              "a future repair.", "", "## Preservation and limits", "",
              f"Offline replay: {verification['status']}. "
              f"Protected files checked: {len(verification.get('protected_inputs', []))}. "
              "[repeat_verification.json](repeat_verification.json) records identical scientific "
              "output bytes, unchanged source caches and validators, the identical glyph policy, "
              "and frozen-file checks against `98b5e09`.", "",
              report["contamination_risk"], "", report["table_caveat"], "",
              "Structured-direction agreement leaves the semantic interpretation of table rows "
              "and captions unadjudicated. The biological feasibility-failure label is unchanged.", "",
              f"Blocked reason: {report['blocked_reason'] or failures['blocked_reason'] or verification['blocked_reason'] or 'none'}.", ""]
    return "\n".join(lines)


def main() -> None:
    """Write new repeat-only artifacts while refusing to replace any saved report."""
    paths = [OUTPUT / name for name in (
        "repeat_comparison.json", "repeat_failures.json", "repeat_summary.md"
    )]
    if any(path.exists() for path in paths):
        raise ValueError("refusing_to_overwrite_existing_repeat_report")
    root = Path.cwd()
    report = build_repeat_comparison(root)
    jobs = make_jobs(Path("data/interim/corpus_targeted_saverschek"),
                     grounding_version="multispan_v3")
    failures = classify_repeat_failures(V3_REPEAT_EXTRACTION, jobs)
    verification = read_json(OUTPUT / "repeat_verification.json")
    report["generated_at"] = timestamp()
    report["model_requests"] = 0
    report["generalization_verdict"] = generalization_verdict(report, failures)
    write_json(paths[0], report)
    write_json(paths[1], failures)
    paths[2].write_text(render_summary(report, failures, verification), encoding="utf-8")
    print({"comparison": report["status"], "classification": failures["status"],
           "verification": verification["status"], "category_counts": failures["category_counts"]})
    if report["blocked_reason"] or failures["blocked_reason"] or verification["blocked_reason"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
