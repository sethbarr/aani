"""Diagnose scored v6 rejections without changing or rerunning grounding rules."""

import hashlib
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

from src.common.io import digest, read_json, read_jsonl, timestamp
from src.evaluation.heldout_failures import file_sha256, substitution_counts
from src.extraction.glyph_grounding import match_provenance, normalise_with_offsets

CATEGORIES = (
    "unresolved_cache_control", "unresolved_model_control", "printable_substitution",
    "identity", "name_surface", "other",
)


def verify_score_marker(extraction: Path, jobs: list[dict], completed_score_path: Path) -> dict:
    """Require completed scores and byte-identical inputs before inspecting rejections.

    Args:
        extraction: Saved sample-4 v6 output directory.
        jobs: Frozen v6 jobs in manifest order.
        completed_score_path: Saved completed baseline-convention score artifact.

    Returns:
        Completed score after checking its timestamp, candidate files, and stored glyph audit.

    Raises:
        ValueError: A required score marker or hashed input is missing or changed.
    """
    score = read_json(completed_score_path)
    run = score.get("sample4_v6", {})
    if score.get("status") != "complete" or run.get("status") != "complete":
        raise ValueError("completed_sample4_v6_scores_required_before_failure_audit")
    completed_at = score.get("score_completed_at")
    if not isinstance(completed_at, str):
        raise ValueError("sample4_score_completion_marker_missing")
    completed_time = datetime.fromisoformat(completed_at)
    now = datetime.fromisoformat(timestamp())
    if completed_time.tzinfo is None or completed_time > now:
        raise ValueError("sample4_score_completion_marker_invalid")
    if score.get("failure_candidates_inspected_before_scoring") is not False:
        raise ValueError("sample4_score_before_inspection_declaration_missing")
    files = run.get("files")
    if not isinstance(files, list):
        raise ValueError("sample4_scored_file_hashes_missing")
    hashes = {str(Path(row["path"]).resolve()): row["sha256"] for row in files}
    names = ["run_manifest.json", "observations.jsonl", "rejections.jsonl"]
    names.extend(f"responses/{job['input_hash']}.json" for job in jobs)
    for name in names:
        path = extraction / name
        expected = hashes.get(str(path.resolve()))
        if expected is None or file_sha256(path) != expected:
            raise ValueError(f"sample4_scored_input_changed_or_missing:{name}")
    audit_path = extraction / "glyph_grounding_audit.jsonl"
    expected_audit = score.get("sample4_audit_sha256")
    if not expected_audit or file_sha256(audit_path) != expected_audit:
        raise ValueError("sample4_saved_glyph_audit_changed_or_missing")
    for job in jobs:
        if digest({key: value for key, value in job.items() if key != "input_hash"}) != job["input_hash"]:
            raise ValueError("frozen_job_contents_differ_from_input_hash")
    return score


def diagnostic_kind(model: str, source: str) -> str | None:
    """Describe a character mismatch without authorizing any substitution.

    Args:
        model: Single emitted character.
        source: Single cached character at the same alignment position.

    Returns:
        Cache-control, model-control, or printable-Unicode class; unrelated ASCII edits
        and whitespace remain unattributed. Digits and letters are allowed as diagnostic
        observations when the other side is a control, and never gain validator permission.
    """
    if model == source or model.isspace() or source.isspace():
        return None
    if ord(source) < 32 and model.isprintable():
        return "unresolved_cache_control"
    if (ord(model) < 32 or 127 <= ord(model) < 160) and source.isprintable():
        return "unresolved_model_control"
    if model.isprintable() and source.isprintable() and (
        not model.isascii() or not source.isascii()
    ):
        return "printable_substitution"
    return None


def aligned_differences(model: str, source: str, start: int) -> list[int] | None:
    """Find diagnostic differences while requiring exact agreement everywhere else.

    Args:
        model: Whitespace-normalized emitted quote.
        source: Whitespace-normalized cached block.
        start: Source alignment offset.

    Returns:
        All character mismatch offsets when each has a diagnostic class, otherwise None.
    """
    differences = []
    for index, character in enumerate(model):
        cached = source[start + index]
        if character == cached:
            continue
        if diagnostic_kind(character, cached) is None:
            return None
        differences.append(index)
    return differences or None


def diagnose_span(span: dict, job: dict) -> dict:
    """Find unique equal-length source evidence for a saved rejected quote.

    Args:
        span: Stored rejected span from the frozen validator audit.
        job: Unchanged source blocks bound in the frozen job.

    Returns:
        Diagnostic-only code points, UTF-8 bytes, and raw offsets, or an explicit
        ambiguity or attribution blocker. Multiple differences are logged without repair.
    """
    result = {"status": "unattributed", "applied_to_validator": False,
              "alignment_count": 0, "unique_source_alignment": False,
              "blocked_reason": None, "evidence": None}
    block = next((row for row in job["blocks"] if row["block_id"] == span["source_block"]), None)
    if block is None or span["source_id"] != job["source_id"]:
        result["blocked_reason"] = "source_or_block_mismatch"
        return result
    model = normalise_with_offsets(span["emitted_quote"])
    source = normalise_with_offsets(block["text"])
    if not model.text or model.text in source.text:
        result["blocked_reason"] = "empty_or_exact_quote_has_no_substitution_attribution"
        return result
    alignments = []
    for start in range(len(source.text) - len(model.text) + 1):
        differences = aligned_differences(model.text, source.text, start)
        if differences:
            alignments.append((start, differences))
    result["alignment_count"] = len(alignments)
    if len(alignments) != 1:
        result["status"] = "ambiguous" if alignments else "unattributed"
        result["blocked_reason"] = ("multiple_source_alignments" if alignments
                                    else "no_exact_other_characters_alignment")
        return result
    start, differences = alignments[0]
    evidence = match_provenance(span["emitted_quote"], block, job["source_id"],
                                model, source, start, differences)
    evidence.update({
        "route": "diagnostic_only_observed_substitution", "applied_to_validator": False,
        "all_other_normalized_characters_exact": True, "differing_positions": len(differences),
        "block_text_sha256": hashlib.sha256(block["text"].encode("utf-8")).hexdigest(),
        "emitted_quote_utf8_sha256": hashlib.sha256(span["emitted_quote"].encode("utf-8")).hexdigest(),
        "field": span["field"], "index": span["index"],
        "section_label_matches": span["section"] == block["section"],
        "ordered_span_rejection_reason": span["rejection_reason"],
        "validator_permission_inferred": False,
    })
    for replacement in evidence["replacements"]:
        model_character = replacement["model_character"]
        source_character = replacement["source_character"]
        replacement.update({
            "kind": diagnostic_kind(model_character, source_character),
            "model_utf8_hex": model_character.encode("utf-8").hex(),
            "source_utf8_hex": source_character.encode("utf-8").hex(),
            "model_unicode_category": unicodedata.category(model_character),
            "source_unicode_category": unicodedata.category(source_character),
            "applied_to_validator": False,
            "observed_rejected_substitution": True,
        })
    result.update({"status": "attributed", "unique_source_alignment": True, "evidence": evidence})
    return result


def failure_category(reason: str, first_span: dict | None) -> str:
    """Classify the recorded first gate with deterministic diagnostic precedence.

    Args:
        reason: Recorded first ordered rejection.
        first_span: Matching rejected span with optional unique source evidence.

    Returns:
        One mutually exclusive category; all observed substitutions remain in the audit.
    """
    evidence = first_span["diagnostic"].get("evidence") if first_span else None
    kinds = {row["kind"] for row in evidence["replacements"]} if evidence else set()
    for category in CATEGORIES[:3]:
        if category in kinds:
            return category
    if reason.startswith("ant_") or reason in {
        "unabbreviated_genus_required", "invalid_abbreviated_binomial_link",
        "invalid_genus_reference_link", "invalid_exact_name_link",
    }:
        return "identity"
    if reason in {"name_surface_not_in_quote", "plant_not_in_name_evidence"}:
        return "name_surface"
    return "other"


def failure_record(candidate: dict, rejection: dict, audit: dict, job: dict,
                   response: dict, response_path: Path, index: int, order: int) -> dict:
    """Describe one rejected raw record using the saved frozen-rule audit only.

    Args:
        candidate: Original raw proposal.
        rejection: Corresponding stored ordered failure.
        audit: Saved per-candidate quote audit.
        job: Original frozen source job.
        response: Original response envelope.
        response_path: Saved response path for byte provenance.
        index: Candidate index within its response.
        order: Candidate order across all jobs.

    Returns:
        One rejection and all saved rejected-span diagnostics without running a validator.
    """
    spans = [{**span, "diagnostic": diagnose_span(span, job)}
             for span in audit["spans"] if span["route"] == "rejected"]
    reason = rejection["reason"]
    first = next((span for span in spans if span["rejection_reason"] == reason), None)
    return {
        "record_id": digest(candidate), "raw_candidate_hash": digest(candidate),
        "input_hash": job["input_hash"], "request_hash": response.get("request_hash"),
        "chunk_index": job["chunk_index"], "candidate_index": index, "proposal_order": order,
        "source_id": candidate.get("source_id"),
        "plant_name_as_written": candidate.get("plant_name_as_written"),
        "outcome": candidate.get("outcome"), "ordered_failure_reason": reason,
        "category": failure_category(reason, first), "first_failure_span": first,
        "rejected_spans_in_validator_order": spans,
        "response_envelope_path": str(response_path),
        "response_envelope_sha256": file_sha256(response_path),
        "later_non_quote_gates_adjudicated": False,
        "validator_rerun": False,
    }


def classify_failures(extraction: Path, jobs: list[dict], completed_score_path: Path) -> dict:
    """Classify every sample-4 rejection after verifying a completed immutable score.

    Args:
        extraction: Saved sample-4 v6 output.
        jobs: Frozen source jobs in manifest order.
        completed_score_path: Already saved baseline-convention sample-4 score artifact.

    Returns:
        Ordered rejection counts, diagnostic-only glyph evidence, and exact reconciliation,
        or an explicit blocker. This function makes zero model calls and performs no repair.
    """
    report = {
        "status": "blocked", "blocked_reason": None, "model_requests": 0,
        "applied_to_validator": False, "validator_rerun": False,
        "completed_score_path": str(completed_score_path), "audit_started_at": timestamp(),
        "classification_unit": "first_ordered_failure_per_rejected_record",
        "category_precedence": list(CATEGORIES), "candidate_records_seen": 0,
        "rejected_records": 0, "category_counts": dict.fromkeys(CATEGORIES, 0),
        "ordered_failure_reason_counts": {}, "first_failure_substitutions": [],
        "all_rejected_span_substitutions": [], "records": [],
        "scope": "Diagnostic character classes include excluded letters, digits, and multiple "
        "positions. Attribution records observed bytes and grants no grounding permission.",
    }
    try:
        score = verify_score_marker(extraction, jobs, completed_score_path)
        report["score_sha256"] = file_sha256(completed_score_path)
        report["score_completed_at"] = score["score_completed_at"]
        report["sample4_audit_sha256"] = score["sample4_audit_sha256"]
        manifest = read_json(extraction / "run_manifest.json")
        if manifest["input_hashes"] != [job["input_hash"] for job in jobs]:
            raise ValueError("manifest_job_order_differs_from_frozen_jobs")
        saved_audit = read_jsonl(extraction / "glyph_grounding_audit.jsonl")
        audits = {(row["input_hash"], row["candidate_index"], row["raw_candidate_hash"]): row
                  for row in saved_audit}
        if len(audits) != len(saved_audit):
            raise ValueError("duplicate_saved_candidate_audit")
        remaining: dict[tuple[str, str], list[dict]] = {}
        for rejection in read_jsonl(extraction / "rejections.jsonl"):
            key = rejection["input_hash"], digest(rejection["candidate"])
            remaining.setdefault(key, []).append(rejection)
        records = []
        order = 0
        for job in jobs:
            path = extraction / "responses" / f"{job['input_hash']}.json"
            response = read_json(path)
            if response["input_hash"] != job["input_hash"]:
                raise ValueError("response_input_hash_differs_from_manifest_job")
            for index, candidate in enumerate(response["output"]["records"]):
                key = job["input_hash"], digest(candidate)
                audit_key = job["input_hash"], index, digest(candidate)
                if audit_key not in audits:
                    raise ValueError("raw_candidate_missing_saved_quote_audit")
                audit = audits.pop(audit_key)
                if remaining.get(key):
                    rejection = remaining[key].pop(0)
                    if audit["survived"] or audit["rejection_reason"] != rejection["reason"]:
                        raise ValueError("saved_quote_audit_disagrees_with_ordered_rejection")
                    records.append(failure_record(candidate, rejection, audit, job,
                                                  response, path, index, order))
                elif not audit["survived"] or audit["rejection_reason"] is not None:
                    raise ValueError("failed_quote_audit_missing_saved_rejection")
                order += 1
        if any(remaining.values()) or audits:
            raise ValueError("saved_rejection_or_audit_has_no_matching_raw_proposal")
        run = score["sample4_v6"]
        reasons = dict(Counter(row["ordered_failure_reason"] for row in records))
        if reasons != run["failure_reasons"]["all_candidates"]:
            raise ValueError("rejection_reason_counts_differ_from_saved_scores")
        if len(records) != run["inventory"]["grounding_failures"]:
            raise ValueError("rejection_count_differs_from_saved_scores")
        if order != run["inventory"]["candidate_records"]:
            raise ValueError("raw_candidate_count_differs_from_saved_scores")
        report.update({
            "status": "complete", "candidate_records_seen": order,
            "rejected_records": len(records), "records": records,
            "category_counts": {category: sum(row["category"] == category for row in records)
                                for category in CATEGORIES},
            "ordered_failure_reason_counts": reasons,
            "first_failure_substitutions": substitution_counts(records, True),
            "all_rejected_span_substitutions": substitution_counts(records, False),
        })
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        report["blocked_reason"] = f"{type(error).__name__}: {error}"
    report["audit_completed_at"] = timestamp()
    return report
