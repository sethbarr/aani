"""Post-score diagnostics for an untouched draw under frozen v4 rules."""

import hashlib
from collections import Counter
from pathlib import Path

from src.common.io import digest, read_json, read_jsonl
from src.extraction.adaptive_glyph_grounding import (
    SOURCE_GLYPHS,
    glyph_policy_allows_v4,
    is_substitutable_control,
)
from src.extraction.glyph_grounding import match_provenance, normalise_with_offsets
from src.extraction.multispan_v4 import candidate_grounding_audit_v4

CATEGORIES = (
    "unresolved_control_glyph", "printable_unicode_substitution", "identity",
    "name_surface", "other",
)


def file_sha256(path: Path) -> str:
    """Return the SHA-256 of unchanged file bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_score_marker(extraction: Path, jobs: list[dict], score_path: Path) -> dict:
    """Require a completed score and unchanged inputs before reading failures.

    Args:
        extraction: Directory of the previously scored v4 extraction.
        jobs: Previously scored jobs in their original order.
        score_path: Saved score with status and sample3_v4.files fields.

    Returns:
        The completed score marker, after verifying all required input hashes.

    Raises:
        ValueError: The score is incomplete or an input is missing or changed.
    """
    score = read_json(score_path)
    if score.get("status") != "complete":
        raise ValueError("Failure diagnostics require a completed saved score")
    run_score = score.get("sample3_v4", {})
    if run_score.get("status") != "complete":
        raise ValueError("Failure diagnostics require complete sample3_v4 scores")
    scored_files = run_score.get("files")
    if not isinstance(scored_files, list):
        raise ValueError("Saved score lacks sample3_v4.files")
    hashes = {str(Path(item["path"]).resolve()): item["sha256"] for item in scored_files}
    names = ["run_manifest.json", "rejections.jsonl", "observations.jsonl"]
    names.extend(f"responses/{job['input_hash']}.json" for job in jobs)
    for job in jobs:
        payload = {key: value for key, value in job.items() if key != "input_hash"}
        if digest(payload) != job["input_hash"]:
            raise ValueError("Supplied job contents differ from their input hash")
    for name in names:
        path = extraction / name
        expected = hashes.get(str(path.resolve()))
        if expected is None or file_sha256(path) != expected:
            raise ValueError(f"Scored input missing from marker or changed: {name}")
    return score


def is_control(character: str) -> bool:
    """Identify C0, DEL, and C1 controls independently of the frozen policy."""
    return ord(character) < 32 or 127 <= ord(character) < 160


def diagnostic_mismatch_kind(model: str, source: str) -> str | None:
    """Identify conservative diagnostic mismatches without permitting repair.

    Args:
        model: One emitted character at an equal-length alignment.
        source: One cached character at the same alignment position.

    Returns:
        A diagnostic class for controls or printable Unicode substitutions.
        Changes involving ASCII letters or digits cannot support attribution.
    """
    if model == source:
        return None
    if any(character.isascii() and character.isalnum() for character in (model, source)):
        return None
    if is_control(model) and not model.isspace() and source.isprintable():
        return "unresolved_control_glyph"
    if all(character.isprintable() for character in (model, source)) and any(
        not character.isascii() for character in (model, source)
    ):
        return "printable_unicode_substitution"
    return None


def diagnostic_alignment(model: str, source: str, start: int) -> list[int] | None:
    """Return mismatched positions when every other normalized character agrees."""
    replacements: list[int] = []
    for index, character in enumerate(model):
        cached = source[start + index]
        if character == cached:
            continue
        if diagnostic_mismatch_kind(character, cached) is None:
            return None
        replacements.append(index)
    return replacements or None


def policy_exclusions(replacement: dict, span: dict, job: dict, block: dict) -> list[str]:
    """Describe policy exclusions and the stored guard that rejected this span."""
    reasons: list[str] = []
    if not glyph_policy_allows_v4(job, block):
        reasons.append("glyph_policy_or_source_hash_binding_disallows_fallback")
    if not is_substitutable_control(replacement["model_character"]):
        reasons.append("model_character_outside_non_whitespace_c0")
    if replacement["source_character"] not in SOURCE_GLYPHS:
        reasons.append("cached_glyph_outside_source_whitelist")
    reasons.append(span["rejection_reason"])
    return reasons


def diagnose_span(span: dict, job: dict) -> dict:
    """Find unique diagnostic source evidence for a rejected quotation.

    Args:
        span: A rejected span from the unchanged v4 quote audit.
        job: Original source blocks and the frozen v4 policy.

    Returns:
        Unique source coordinates and observed code points, or an explicit
        ambiguous or unattributed result. This function never validates a quote.
    """
    result = {
        "status": "unattributed", "applied_to_validator": False,
        "unique_source_alignment": False, "alignment_count": 0,
        "blocked_reason": None, "evidence": None,
    }
    block = next(
        (item for item in job["blocks"] if item["block_id"] == span["source_block"]), None
    )
    if block is None or span["source_id"] != job["source_id"]:
        result["blocked_reason"] = "source_or_block_mismatch"
        return result
    if span["section"] != block["section"]:
        result["blocked_reason"] = "section_mismatch"
        return result
    model = normalise_with_offsets(span["emitted_quote"])
    source = normalise_with_offsets(block["text"])
    if not model.text or model.text in source.text:
        result["blocked_reason"] = "empty_or_exact_quote_has_no_substitution_attribution"
        return result
    alignments: list[tuple[int, list[int]]] = []
    for start in range(len(source.text) - len(model.text) + 1):
        replacements = diagnostic_alignment(model.text, source.text, start)
        if replacements:
            alignments.append((start, replacements))
    result["alignment_count"] = len(alignments)
    if len(alignments) != 1:
        result["status"] = "ambiguous" if alignments else "unattributed"
        result["blocked_reason"] = "multiple_source_alignments" if alignments else "no_exact_other_characters_alignment"
        return result
    start, replacements = alignments[0]
    evidence = match_provenance(
        span["emitted_quote"], block, job["source_id"], model, source, start, replacements
    )
    evidence.update({
        "route": "diagnostic_only_observed_substitution",
        "applied_to_validator": False,
        "all_other_normalized_characters_exact": True,
        "block_text_sha256": hashlib.sha256(block["text"].encode("utf-8")).hexdigest(),
        "emitted_quote_utf8_sha256": hashlib.sha256(span["emitted_quote"].encode("utf-8")).hexdigest(),
        "field": span["field"], "index": span["index"],
        "ordered_span_rejection_reason": span["rejection_reason"],
    })
    for replacement in evidence["replacements"]:
        replacement.update({
            "kind": diagnostic_mismatch_kind(
                replacement["model_character"], replacement["source_character"]
            ),
            "model_utf8_hex": replacement["model_character"].encode("utf-8").hex(),
            "source_utf8_hex": replacement["source_character"].encode("utf-8").hex(),
            "v4_policy_or_guard_reasons": policy_exclusions(replacement, span, job, block),
        })
    result.update({"status": "attributed", "unique_source_alignment": True, "evidence": evidence})
    return result


def failure_category(reason: str, ordered_span: dict | None) -> str:
    """Assign one category to the stored first failure, leaving later gates unscored."""
    if ordered_span:
        evidence = ordered_span["diagnostic"].get("evidence")
        kinds = {entry["kind"] for entry in evidence["replacements"]} if evidence else set()
        for category in CATEGORIES[:2]:
            if category in kinds:
                return category
    if reason.startswith("ant_") or reason in {
        "unabbreviated_genus_required", "invalid_abbreviated_binomial_link",
        "invalid_genus_reference_link", "invalid_exact_name_link",
    }:
        return "identity"
    if reason in {"plant_not_in_name_evidence", "name_surface_not_in_quote"}:
        return "name_surface"
    return "other"


def failure_record(rejection: dict, job: dict, response: dict, path: Path, index: int, order: int) -> dict:
    """Retain one ordered failure with diagnostic evidence for every rejected span."""
    candidate = rejection["candidate"]
    reason = rejection["reason"]
    audit = candidate_grounding_audit_v4(candidate, job)
    spans = [
        {**span, "diagnostic": diagnose_span(span, job)}
        for span in audit["spans"] if span["route"] == "rejected"
    ]
    ordered_span = next((span for span in spans if span["rejection_reason"] == reason), None)
    return {
        "record_id": digest(candidate), "raw_candidate_hash": digest(candidate),
        "input_hash": job["input_hash"], "request_hash": response.get("request_hash"),
        "source_id": candidate.get("source_id"), "chunk_index": job["chunk_index"],
        "candidate_index": index, "proposal_order": order,
        "plant_name_as_written": candidate.get("plant_name_as_written"),
        "outcome": candidate.get("outcome"), "ordered_failure_reason": reason,
        "category": failure_category(reason, ordered_span),
        "response_envelope_path": str(path), "response_envelope_sha256": file_sha256(path),
        "first_failure_span": ordered_span,
        "rejected_spans_in_validator_order": spans,
        "later_non_quote_gates_adjudicated": False,
    }


def substitution_counts(records: list[dict], first_only: bool) -> list[dict]:
    """Count code-point pairs by distinct affected records and quote occurrences."""
    occurrences: Counter[tuple[str, str, str]] = Counter()
    affected: Counter[tuple[str, str, str]] = Counter()
    for record in records:
        spans = [record["first_failure_span"]] if first_only else record["rejected_spans_in_validator_order"]
        pairs: list[tuple[str, str, str]] = []
        for span in spans:
            evidence = span["diagnostic"].get("evidence") if span else None
            if evidence:
                pairs.extend(
                    (entry["model_codepoint"], entry["source_codepoint"], entry["kind"])
                    for entry in evidence["replacements"]
                )
        occurrences.update(pairs)
        affected.update(set(pairs))
    return [
        {"model_codepoint": pair[0], "source_codepoint": pair[1], "kind": pair[2],
         "records": affected[pair], "occurrences": count, "applied_to_validator": False}
        for pair, count in sorted(occurrences.items())
    ]


def classify_heldout_failures(extraction: Path, jobs: list[dict], score_path: Path) -> dict:
    """Diagnose saved held-out failures only after immutable score verification.

    Args:
        extraction: Complete saved held-out extraction under unchanged v4 rules.
        jobs: Corresponding v4 jobs in manifest order.
        score_path: Completed score marker with hashes of every inspected input.

    Returns:
        First-failure counts and per-record diagnostic evidence. Missing inputs,
        an incomplete score or changed artifacts yield an explicit blocked reason.
    """
    report = {
        "status": "blocked", "blocked_reason": None, "model_requests": 0,
        "applied_to_validator": False, "score_path": str(score_path),
        "classification_unit": "first_ordered_failure_per_rejected_record",
        "candidate_records_seen": 0, "rejected_records": 0,
        "category_counts": dict.fromkeys(CATEGORIES, 0),
        "ordered_failure_reason_counts": {}, "first_failure_substitutions": [],
        "all_rejected_span_substitutions": [], "records": [],
    }
    try:
        verify_score_marker(extraction, jobs, score_path)
        report["score_sha256"] = file_sha256(score_path)
        manifest = read_json(extraction / "run_manifest.json")
        if manifest["input_hashes"] != [job["input_hash"] for job in jobs]:
            raise ValueError("Manifest job order or input hashes differ from scored jobs")
        remaining: dict[tuple[str, str], list[dict]] = {}
        for rejection in read_jsonl(extraction / "rejections.jsonl"):
            key = rejection["input_hash"], digest(rejection["candidate"])
            remaining.setdefault(key, []).append(rejection)
        records: list[dict] = []
        order = 0
        for job in jobs:
            path = extraction / "responses" / f"{job['input_hash']}.json"
            response = read_json(path)
            if response["input_hash"] != job["input_hash"]:
                raise ValueError("Response input hash differs from its manifest job")
            for index, candidate in enumerate(response["output"]["records"]):
                key = job["input_hash"], digest(candidate)
                if remaining.get(key):
                    records.append(failure_record(remaining[key].pop(0), job, response, path, index, order))
                order += 1
        if any(remaining.values()):
            raise ValueError("Saved rejection has no matching raw proposal")
        report.update({
            "status": "complete", "candidate_records_seen": order,
            "rejected_records": len(records), "records": records,
            "category_counts": {
                category: sum(record["category"] == category for record in records)
                for category in CATEGORIES
            },
            "ordered_failure_reason_counts": dict(Counter(record["ordered_failure_reason"] for record in records)),
            "first_failure_substitutions": substitution_counts(records, True),
            "all_rejected_span_substitutions": substitution_counts(records, False),
        })
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        report["blocked_reason"] = f"{type(error).__name__}: {error}"
    return report
