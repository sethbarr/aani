"""Measure bounded glyph grounding on the unchanged saved proposal sample."""

from pathlib import Path

from src.common.io import digest, read_json, read_jsonl
from src.evaluation.identity_comparison import (
    EXPECTED_JOBS,
    STAGES,
    V2_EXTRACTION,
    build_identity_comparison,
    check_job_coverage,
    score_variant,
    stage_cell,
)

V3_EXTRACTION = Path("data/interim/extraction_saverschek_multispan_v3")
V2_REPEAT_EXTRACTION = Path("data/interim/extraction_saverschek_multispan_v2_repeat_for_v3")
VARIANTS = ("baseline", "v1", "v2", "v3")


def ordered_responses(extraction: Path) -> tuple[list[dict], str | None]:
    """Read responses in manifest chunk order with explicit completeness checks.

    Args:
        extraction: Saved extraction directory containing a three-job manifest.

    Returns:
        Ordered response envelopes and any reason that prevents comparison.
    """
    coverage = check_job_coverage(extraction)
    if coverage["blocked_reason"]:
        return [], coverage["blocked_reason"]
    responses = {row["input_hash"]: row for row in (
        read_json(path) for path in sorted((extraction / "responses").glob("*.json"))
    )}
    return [responses[value] for value in coverage["manifest"]["input_hashes"]], None


def compare_proposal_samples(original: Path, current: Path, require_same_output: bool) -> dict:
    """Check identical requests and optionally identical raw model output per chunk.

    Args:
        original: Original v2 extraction directory.
        current: Glyph rerun or independent v2 repeat directory.
        require_same_output: Require the fixed v2 sample for the glyph-only comparison.

    Returns:
        Per-chunk request and output hashes with an explicit mismatch blocker.
    """
    before, before_reason = ordered_responses(original)
    after, after_reason = ordered_responses(current)
    reasons = [f"{name}:{reason}" for name, reason in (
        ("original", before_reason), ("current", after_reason)
    ) if reason]
    chunks = []
    for index, (old, new) in enumerate(zip(before, after, strict=False), start=1):
        request_matches = bool(old.get("request_hash")) and (
            old.get("request_hash") == new.get("request_hash")
        )
        output_matches = old.get("output") == new.get("output")
        engine_matches = all(old.get(key) == new.get(key) for key in (
            "engine", "resolved_model", "provider"
        ))
        if not request_matches:
            reasons.append(f"chunk_{index}:request_hash_changed_or_missing")
        if not engine_matches:
            reasons.append(f"chunk_{index}:model_identity_changed")
        if require_same_output and not output_matches:
            reasons.append(f"chunk_{index}:raw_proposal_sample_changed")
        chunks.append({
            "chunk_index": index,
            "v2_input_hash": old["input_hash"], "current_input_hash": new["input_hash"],
            "v2_request_hash": old.get("request_hash"),
            "current_request_hash": new.get("request_hash"),
            "request_hash_matches": request_matches, "model_identity_matches": engine_matches,
            "v2_output_hash": digest(old.get("output")),
            "current_output_hash": digest(new.get("output")),
            "raw_model_output_matches": output_matches,
            "v2_candidate_count": len(old.get("output", {}).get("records", [])),
            "current_candidate_count": len(new.get("output", {}).get("records", [])),
        })
    complete = len(chunks) == EXPECTED_JOBS and not reasons
    return {
        "status": "complete" if complete else "blocked",
        "blocked_reason": ";".join(reasons) or (None if complete else "three_chunks_required"),
        "require_identical_raw_output": require_same_output,
        "all_requests_identical": complete and all(row["request_hash_matches"] for row in chunks),
        "all_raw_model_outputs_identical": (
            all(row["raw_model_output_matches"] for row in chunks)
            if len(chunks) == EXPECTED_JOBS else None
        ),
        "chunks": chunks,
    }


def recovered_records(v2: dict, v3: dict, sample_check: dict) -> dict:
    """List newly surviving fixed-sample records and their recorded quote routes.

    Args:
        v2: Original v2 candidate inventory and scores.
        v3: Glyph-only candidate inventory and scores.
        sample_check: Per-chunk identity check mapping the two job identifiers.

    Returns:
        Newly surviving records with unchanged raw identities and glyph audit metadata.
    """
    reason = sample_check["blocked_reason"] or v2["blocked_reason"] or v3["blocked_reason"]
    if reason:
        return {"records": [], "count": None, "glyph_route_count": None,
                "blocked_reason": reason}
    input_map = {row["current_input_hash"]: row["v2_input_hash"]
                 for row in sample_check["chunks"]}
    before = {(row["input_hash"], row["record_digest"]): row for row in v2["candidates"]}
    observations = {(row["input_hash"], row["record_id"]): row for row in read_jsonl(
        Path(v3["extraction"]) / "observations.jsonl"
    )}
    records = []
    for candidate in v3["candidates"]:
        original = before[(input_map[candidate["input_hash"]], candidate["record_digest"])]
        if candidate["grounding_status"] != "passed" or original["grounding_status"] == "passed":
            continue
        observation = observations[(candidate["input_hash"], candidate["record_digest"])]
        records.append({
            "candidate_id": candidate["candidate_id"],
            "v2_candidate_id": original["candidate_id"],
            "record_digest": candidate["record_digest"],
            "species": candidate["record"]["plant_name_as_written"],
            "direction": candidate["record"]["outcome"],
            "v2_failure_reason": original["grounding_failure_reason"],
            "quote_grounding_route": observation.get("quote_grounding_route"),
            "grounded_source_spans": observation.get("grounded_source_spans", []),
        })
    glyph_count = sum(row["quote_grounding_route"] == "bounded_glyph_equivalence"
                      for row in records)
    reason = "recovered_record_glyph_provenance_missing" if glyph_count != len(records) else None
    return {"records": records, "count": len(records), "glyph_route_count": glyph_count,
            "blocked_reason": reason}


def score_repeat_sample(repeat: Path | None, root: Path, baseline: dict,
                        integrity_reason: str | None) -> dict:
    """Measure the independent repeat separately without selecting or pooling records.

    Args:
        repeat: Optional independently cached v2 repeat sample directory.
        root: Repository containing the original v2 extraction.
        baseline: Saved fixed reference and scoring definitions.
        integrity_reason: Any blocker from checking the saved reference artifacts.

    Returns:
        Repeat-only scores and whether PRIMARY detection again reaches six species.
    """
    if repeat is None:
        return {
            "label": "repeat sample", "status": "not_run",
            "blocked_reason": "repeat_sample_not_requested", "run": None,
            "primary_detection_six_of_six_again": None, "pooled_with_v3": False,
        }
    sample_check = compare_proposal_samples(root / V2_EXTRACTION, repeat, False)
    reasons = [reason for reason in (integrity_reason, sample_check["blocked_reason"]) if reason]
    run = score_variant(repeat, baseline, ";".join(reasons) or None)
    primary = run["groups"]["PRIMARY"]
    detection = primary["stages"]["detection"]["species_count"]
    complete = run["status"] == "complete" and not primary["unscorable_species"]
    return {
        "label": "repeat sample", "status": run["status"],
        "blocked_reason": run["blocked_reason"], "run": run,
        "request_configuration_check": sample_check,
        "primary_detection_six_of_six_again": detection == 6 if complete else None,
        "pooled_with_v3": False,
    }


def build_glyph_comparison(extraction: Path, root: Path, repeat: Path | None = None) -> dict:
    """Build four-variant baseline-convention counts plus a separate optional repeat.

    Args:
        extraction: Saved v3 output using the unchanged v2 raw proposal sample.
        root: Repository containing the preserved baseline, v1, and v2 artifacts.
        repeat: Optional independent repeat of the original v2 request configuration.

    Returns:
        Four separate measurements, glyph recoveries, and repeat-only results.
    """
    report = build_identity_comparison(root / V2_EXTRACTION, root)
    baseline = read_json(root / "results/recall_baseline.json")
    integrity_reason = report["baseline_integrity"]["blocked_reason"]
    sample_check = compare_proposal_samples(root / V2_EXTRACTION, extraction, True)
    v3_reasons = [reason for reason in (integrity_reason, sample_check["blocked_reason"]) if reason]
    v3 = score_variant(extraction, baseline, ";".join(v3_reasons) or None)
    reasons = [reason for reason in (report["blocked_reason"], v3["blocked_reason"]) if reason]
    report.update({
        "schema_version": 1, "status": "complete" if not reasons else "partially_blocked",
        "blocked_reason": ";".join(reasons) or None,
        "v3": v3, "fixed_sample_check": sample_check,
        "glyph_recoveries": recovered_records(report["v2"], v3, sample_check),
        "repeat_sample": score_repeat_sample(repeat, root, baseline, integrity_reason),
        "experiment_change": "v3 changes only quote comparison through the two observed "
        "control-character/glyph equivalences; the v2 requests and raw model proposals are reused.",
    })
    report.pop("primary_change")
    report.pop("live_run_status")
    return report


def repeat_summary(repeat: dict) -> str:
    """Describe the optional sample independently from the four-variant comparison."""
    if repeat["status"] != "complete":
        return f"The v2 repeat sample is {repeat['status']}: {repeat['blocked_reason']}."
    primary = repeat["run"]["groups"]["PRIMARY"]["stages"]
    detection = primary["detection"]["species_count"]
    survival = primary["survival"]["species_count"]
    correctness = primary["correctness"]["species_count"]
    return (f"The independent v2 repeat sample detected {detection} of 6 PRIMARY species, "
            f"retained {survival} of 6, and carried the reference direction for {correctness} "
            "of 6. Its records are reported separately and are never pooled with v3.")


def render_glyph_summary(report: dict) -> str:
    """Render four data columns with fixed denominators and development-set caveats."""
    lines = [
        "# Bounded glyph grounding — DEVELOPMENT SET", "",
        "This is one panel from one paper; implementers know the reference. It is not a sample "
        "from any population. All variants use the unchanged baseline structured-direction "
        "matching convention for correctness.", "", report["experiment_change"], "",
    ]
    for group in ("PRIMARY", "CONTEXT"):
        lines += [f"## {group}", "", "| baseline | v1 | v2 | v3 |", "| --- | --- | --- | --- |"]
        for stage in STAGES:
            cells = [f"{stage}: {stage_cell(report[name]['groups'][group], stage, group == 'CONTEXT')}"
                     for name in VARIANTS]
            lines.append(f"| {' | '.join(cells)} |")
        lines.append("")
    failures = report["v3"]["failure_reasons"]
    if report["v3"]["blocked_reason"]:
        lines.append(f"The v3 measurement is blocked: {report['v3']['blocked_reason']}.")
    elif failures["dominant_reasons"]:
        lines.append(f"The dominant remaining grounding failure is "
                     f"{', '.join(failures['dominant_reasons'])}: "
                     f"{failures['dominant_reason_count']} of "
                     f"{failures['failed_candidate_count']} failed candidates per listed reason.")
    else:
        lines.append("v3 has zero recorded grounding failures.")
    lines += ["", "## Recovered records", ""]
    recoveries = report["glyph_recoveries"]
    if recoveries["blocked_reason"]:
        lines.append(f"Recovery attribution is blocked: {recoveries['blocked_reason']}.")
    elif recoveries["records"]:
        for row in recoveries["records"]:
            lines.append(f"- {row['species']} — {row['direction']}; "
                         f"route `{row['quote_grounding_route']}`; "
                         f"candidate `{row['candidate_id']}`.")
    else:
        lines.append("There are zero newly surviving records in the fixed proposal sample.")
    lines += ["", "## Repeat sample", "", repeat_summary(report["repeat_sample"]), "",
              report["contamination_risk"], "", report["table_caveat"], "",
              "Candidate pass/failure counts are stage yields.", "",
              f"Comparison status: {report['status']}. "
              f"Blocked reason: {report['blocked_reason'] or 'none'}.", ""]
    return "\n".join(lines)
