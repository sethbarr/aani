"""Report source-anchored glyph grounding on both saved development samples."""

from collections import Counter
from pathlib import Path

from src.common.io import read_json, read_jsonl, timestamp, write_json
from src.evaluation.generalized_glyph_comparison import VARIANTS, build_generalized_comparison
from src.evaluation.identity_comparison import STAGES, stage_cell

OUTPUT = Path("results/grounding_development_v4")
HEADERS = "| Sample 1: v3 | Sample 1: v4 | Sample 2: v3 | Sample 2: v4 |"


def glyph_usage(extraction: Path) -> dict:
    """Count recorded source-anchored routes and inferred code pairs.

    Args:
        extraction: Completed v4 output directory with per-record metadata.

    Returns:
        Counts of surviving records and mismatch occurrences for each inferred pair.
    """
    records = read_jsonl(extraction / "observations.jsonl")
    affected: Counter[tuple[str, str]] = Counter()
    occurrences: Counter[tuple[str, str]] = Counter()
    for record in records:
        pairs = [(entry["model_codepoint"], entry["source_codepoint"])
                 for span in record["grounded_source_spans"] for entry in span["replacements"]]
        affected.update(set(pairs))
        occurrences.update(pairs)
    return {
        "glyph_route_records": sum(record["quote_grounding_route"] == "source_anchored_control_glyph"
                                   for record in records),
        "exact_route_records": sum(record["quote_grounding_route"] == "exact" for record in records),
        "inferred_pairs": [{"model_codepoint": pair[0], "source_codepoint": pair[1],
                            "records": affected[pair], "span_occurrences": count}
                           for pair, count in sorted(occurrences.items())],
    }


def comparison_table(report: dict, group: str) -> list[str]:
    """Render all three stages with four separate fixed-denominator columns.

    Args:
        report: Four independently scored sample/rule combinations.
        group: PRIMARY or CONTEXT, retaining its original denominator.

    Returns:
        Markdown table lines with count-only measurement cells.
    """
    lines = [HEADERS, "| --- | --- | --- | --- |"]
    for stage in STAGES:
        cells = [f"{stage.capitalize()}: " + stage_cell(
            report[name]["groups"][group], stage, group == "CONTEXT"
        ) for name in VARIANTS]
        lines.append(f"| {' | '.join(cells)} |")
    return lines


def missing_proposals(run: dict) -> list[str]:
    """Identify reference pairs absent from structured model proposals.

    Args:
        run: Completed baseline-convention species measurement.

    Returns:
        Species-direction labels that grounding cannot recover from this sample.
    """
    return [f"{row['species']} — {direction}" for row in run["species"] if row["scorable"]
            for direction in sorted(set(row["reference_directions"]) - set(row["proposed_directions"]))]


def render_summary(report: dict, verification: dict, checks: dict) -> str:
    """Describe actual recoveries, broader control coverage, and remaining limits.

    Args:
        report: Scored saved samples with record transitions and glyph metadata counts.
        verification: Offline replay and preservation status.
        checks: Independent synthetic expected/actual comparison results.

    Returns:
        Markdown report containing both samples and bounded-generalization caveats.
    """
    lines = [
        "# V4 source-anchored control glyphs — DEVELOPMENT SET", "",
        "V4 infers a corrupted control character's cached glyph from a unique source span. "
        "The model-side codes can vary across records and samples. Cached targets remain "
        "limited to ± and ¼, and every other character must match exactly.", "",
        "## Two saved samples, unchanged proposals", "",
        "All three jobs from each sample were processed offline, with zero model requests. "
        "Requests, raw proposals, prompts, schema, identity context, and chunks are unchanged. "
        "Correctness uses the baseline structured-direction convention.", "",
        "### PRIMARY — six species-direction pairs", "", *comparison_table(report, "PRIMARY"), "",
        "### CONTEXT — five species, ten species-direction pairs", "",
        *comparison_table(report, "CONTEXT"), "", "### Candidate stage yield", "",
        HEADERS, "| --- | --- | --- | --- |",
    ]
    yields = [f"{report[name]['inventory']['grounding_passes']} of "
              f"{report[name]['inventory']['candidate_records']}" for name in VARIANTS]
    lines += [f"| {' | '.join(yields)} |", "", "## Recovered records and remaining failures", ""]
    for sample, transition in report["sample_transitions"].items():
        lines.append(f"- {sample}: {transition['recovered_count']} newly surviving records, "
                     f"{transition['retained_survivor_count']} previous survivors retained, "
                     f"{transition['lost_count']} previous survivors lost.")
    for sample in ("sample1", "sample2"):
        run = report[f"{sample}_v4"]
        failures = run["failure_reasons"]["all_candidates"]
        lines.append(f"- {sample} remaining rejection reasons: " + (
            "; ".join(f"`{reason}`: {count}" for reason, count in failures.items())
            if failures else "zero rejected records"
        ) + ".")
        missing = missing_proposals(run)
        if missing:
            lines.append(f"- {sample} missing structured proposals: {', '.join(missing)}. "
                         "Grounding preserves this detection gap.")
    lines += ["", "## Inferred glyph routes", "",
              "Mappings below are read from source matches and are local to each candidate. "
              "They are not a global replacement table.", ""]
    for sample, usage in report["glyph_usage"].items():
        lines.append(f"{sample}: {usage['glyph_route_records']} surviving records use the glyph "
                     f"route; {usage['exact_route_records']} use exact matching.")
        lines.append("")
        for pair in usage["inferred_pairs"]:
            lines.append(f"- `{pair['model_codepoint']}` → `{pair['source_codepoint']}`: "
                         f"{pair['records']} records, {pair['span_occurrences']} span occurrences.")
        lines.append("")
    lines += ["## Guardrails and generalization checks", "",
              "The fallback accepts only non-whitespace C0 controls aligned to cached ± or ¼, "
              "with literal printable context on both sides and one unique equal-length "
              "source match. Conflicting mappings within a record fail. Insertions, deletions, "
              "other cached glyphs, and changed digits, signs, words, or direction statements "
              "remain rejected. Existing literal source controls remain exact.", "",
              "Every job binds its own source ID and block hashes, so the rule has no fixed "
              "Saverschek identifier. Raw quotes and record digests stay unchanged. Each match "
              "logs source offsets, original text, cached text, and inferred substitutions.", "",
              f"Synthetic check status: {checks['status']}; {checks['counts']['passed']} of "
              f"{checks['counts']['case_count']} expectations passed. "
              "[generalization_checks.json](generalization_checks.json) records exhaustive "
              "non-whitespace C0 probes for the two permitted cached glyphs, using invented "
              "text and an unrelated source ID, plus adversarial rejections. These are "
              "algorithm checks and contain zero model samples.", "",
              f"Offline replay status: {verification['status']}; "
              f"{len(verification.get('protected_inputs', []))} protected files checked. "
              "[verification.json](verification.json) records identical response/proposal "
              "identities, scientific replay bytes, and unchanged frozen files at `98b5e09`.", "",
              "## Scope of the result", "",
              "The generalized rule covers the glyph failures observed in both saved samples. "
              "Its remaining source-glyph scope is ± and ¼; other Unicode and OCR errors "
              "are outside this implementation.", "", report["sampling_caveat"], "",
              report["contamination_risk"], "", report["table_caveat"], "",
              "This DEVELOPMENT SET is one panel from one paper and is not a sample from any "
              "population. Semantic support of table-derived directions remains unadjudicated. "
              "The default extractor and all earlier validators are preserved; select "
              "`--grounding multispan_v4` to use this mode. The biological feasibility-failure "
              "label is unchanged.", "",
              "The rule and reproduction commands are documented in "
              "[the dated amendment](../../docs/amendment_2026-09-13_generalized_glyph_grounding.md).", "",
              f"Blocked reason: {report['blocked_reason'] or verification['blocked_reason'] or checks.get('blocked_reason') or 'none'}.", ""]
    return "\n".join(lines)


def main() -> None:
    """Write new v4 reports once without replacing prior experiment artifacts."""
    destinations = [OUTPUT / "compare.json", OUTPUT / "summary.md"]
    if any(path.exists() for path in destinations):
        raise ValueError("v4_report_already_exists")
    report = build_generalized_comparison(Path.cwd())
    report["generated_at"] = timestamp()
    report["model_requests"] = 0
    report["glyph_usage"] = {
        sample: glyph_usage(Path(report[f"{sample}_v4"]["extraction"]))
        for sample in ("sample1", "sample2") if report[f"{sample}_v4"]["status"] == "complete"
    }
    verification = read_json(OUTPUT / "verification.json")
    checks = read_json(OUTPUT / "generalization_checks.json")
    write_json(destinations[0], report)
    destinations[1].write_text(render_summary(report, verification, checks), encoding="utf-8")
    print({"status": report["status"], "blocked_reason": report["blocked_reason"],
           "glyph_usage": report["glyph_usage"]})
    if report["blocked_reason"] or verification["blocked_reason"] or checks.get("blocked_reason"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
