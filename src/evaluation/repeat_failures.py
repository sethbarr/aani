"""Attribute saved repeat failures without changing grounding or score rules."""

import hashlib
from collections import Counter
from pathlib import Path

from src.common.io import digest, read_json, read_jsonl
from src.extraction.glyph_grounding import (
    glyph_policy_allows,
    match_provenance,
    normalise_with_offsets,
)
from src.extraction.multispan_v3 import candidate_grounding_audit

OBSERVED_UNPERMITTED_SUBSTITUTIONS = {"\u0010": "¼", "\u0011": "±"}
CATEGORIES = (
    "glyph_substitution_not_covered",
    "identity",
    "name_surface",
    "other",
)


def diagnose_unpermitted_span(span: dict, job: dict) -> dict | None:
    """Attribute an exact source alignment using only observed repeat defects.

    Args:
        span: A rejected quote entry from the unchanged v3 quote audit.
        job: Original blocks and unchanged hash-pinned v3 policy.

    Returns:
        Diagnostic-only source and code-point evidence for a unique match, or
        None if any other mismatch or ambiguity prevents this attribution.
        The diagnostic never changes a candidate, validator, or score.
    """
    block = next(
        (item for item in job["blocks"] if item["block_id"] == span["source_block"]), None
    )
    if block is None or not glyph_policy_allows(job, block):
        return None
    if span["source_id"] != job["source_id"] or span["section"] != block["section"]:
        return None
    model = normalise_with_offsets(span["emitted_quote"])
    source = normalise_with_offsets(block["text"])
    replacements = [
        index for index, character in enumerate(model.text)
        if character in OBSERVED_UNPERMITTED_SUBSTITUTIONS
    ]
    if not replacements:
        return None
    diagnostic_text = "".join(
        OBSERVED_UNPERMITTED_SUBSTITUTIONS.get(character, character)
        for character in model.text
    )
    start = source.text.find(diagnostic_text)
    if start < 0 or source.text.find(diagnostic_text, start + 1) >= 0:
        return None
    evidence = match_provenance(
        span["emitted_quote"], block, job["source_id"], model, source, start, replacements
    )
    evidence.update({
        "route": "observed_unpermitted_substitution",
        "permitted_by_v3": False,
        "applied_to_validator": False,
        "all_other_normalized_characters_exact": True,
        "unique_source_alignment": True,
        "block_text_sha256": hashlib.sha256(block["text"].encode("utf-8")).hexdigest(),
        "emitted_quote_utf8_sha256": hashlib.sha256(
            span["emitted_quote"].encode("utf-8")
        ).hexdigest(),
        "field": span["field"],
        "index": span["index"],
    })
    for replacement in evidence["replacements"]:
        replacement["model_utf8_hex"] = replacement["model_character"].encode("utf-8").hex()
        replacement["source_utf8_hex"] = replacement["source_character"].encode("utf-8").hex()
        replacement["permitted_by_v3"] = False
    return evidence


def failure_category(reason: str, ordered_span: dict | None) -> str:
    """Classify only the validator's first returned failure.

    Args:
        reason: Stored ordered rejection reason from the unchanged validator.
        ordered_span: Quote audit entry corresponding to that returned reason.

    Returns:
        One of the four requested mutually exclusive failure categories.
    """
    if ordered_span and ordered_span.get("unpermitted_substitution_evidence"):
        return "glyph_substitution_not_covered"
    if reason.startswith("ant_") or reason in {
        "unabbreviated_genus_required", "invalid_abbreviated_binomial_link",
        "invalid_genus_reference_link", "invalid_exact_name_link",
    }:
        return "identity"
    if reason in {"plant_not_in_name_evidence", "name_surface_not_in_quote"}:
        return "name_surface"
    return "other"


def failure_record(
    rejection: dict, job: dict, response: dict, response_path: Path,
    candidate_index: int, proposal_order: int,
) -> dict:
    """Audit one saved rejection and retain its source proposal coordinates.

    Args:
        rejection: Existing v3 rejection row with unchanged raw candidate.
        job: Corresponding extraction job.
        response: Existing response envelope.
        response_path: Location of that unchanged envelope.
        candidate_index: Zero-based index inside the chunk's proposals.
        proposal_order: Zero-based index across the manifest's ordered jobs.

    Returns:
        First-failure classification and all rejected quote spans in audit order.
    """
    candidate = rejection["candidate"]
    reason = rejection["reason"]
    audit = candidate_grounding_audit(candidate, job)
    rejected_spans = []
    for span in audit["spans"]:
        if span["route"] == "rejected":
            rejected_spans.append({
                **span,
                "unpermitted_substitution_evidence": diagnose_unpermitted_span(span, job),
            })
    ordered_span = next(
        (span for span in rejected_spans if span["rejection_reason"] == reason), None
    )
    return {
        "record_id": digest(candidate),
        "raw_candidate_hash": digest(candidate),
        "source_id": candidate.get("source_id"),
        "input_hash": job["input_hash"],
        "request_hash": response.get("request_hash"),
        "response_envelope_path": str(response_path),
        "response_envelope_sha256": hashlib.sha256(response_path.read_bytes()).hexdigest(),
        "chunk_index": job["chunk_index"],
        "candidate_index": candidate_index,
        "proposal_order": proposal_order,
        "plant_name_as_written": candidate.get("plant_name_as_written"),
        "outcome": candidate.get("outcome"),
        "ordered_failure_reason": reason,
        "category": failure_category(reason, ordered_span),
        "first_failure_span": ordered_span,
        "rejected_spans_in_validator_order": rejected_spans,
        "later_non_quote_gates_adjudicated": False,
    }


def substitution_counts(records: list[dict]) -> list[dict]:
    """Count diagnostic substitutions in first-failing spans by exact pair.

    Args:
        records: Mutually exclusive first-failure record classifications.

    Returns:
        Distinct affected records and occurrences for each observed code pair.
    """
    occurrences: Counter[tuple[str, str]] = Counter()
    affected_records: Counter[tuple[str, str]] = Counter()
    for record in records:
        span = record["first_failure_span"]
        evidence = span.get("unpermitted_substitution_evidence") if span else None
        if evidence is None:
            continue
        pairs = [
            (entry["model_codepoint"], entry["source_codepoint"])
            for entry in evidence["replacements"]
        ]
        occurrences.update(pairs)
        affected_records.update(set(pairs))
    return [
        {"model_codepoint": pair[0], "source_codepoint": pair[1],
         "records": affected_records[pair], "occurrences": count, "permitted_by_v3": False}
        for pair, count in sorted(occurrences.items())
    ]


def classify_repeat_failures(extraction: Path, jobs: list[dict]) -> dict:
    """Classify saved v3 repeat rejections without requests or rule changes.

    Args:
        extraction: Complete repeat-under-v3 artifacts to read without mutation.
        jobs: Exact v3 jobs in manifest order, including the unchanged glyph policy.

    Returns:
        Counts, source evidence and per-record first-failure classifications.
        Missing or inconsistent artifacts produce an explicit blocked reason.
    """
    report = {
        "status": "blocked", "blocked_reason": None,
        "classification_unit": "first_ordered_failure_per_rejected_record",
        "model_requests": 0, "applied_to_validator": False,
        "candidate_records_seen": 0, "rejected_records": 0,
        "category_counts": dict.fromkeys(CATEGORIES, 0),
        "ordered_failure_reason_counts": {}, "unpermitted_substitutions": [], "records": [],
    }
    try:
        manifest = read_json(extraction / "run_manifest.json")
        if manifest["input_hashes"] != [job["input_hash"] for job in jobs]:
            raise ValueError("Manifest job order or input hashes differ from supplied v3 jobs")
        rejections = read_jsonl(extraction / "rejections.jsonl")
        remaining: dict[tuple[str, str], list[dict]] = {}
        for rejection in rejections:
            key = rejection["input_hash"], digest(rejection["candidate"])
            remaining.setdefault(key, []).append(rejection)
        records: list[dict] = []
        proposal_order = 0
        for job in jobs:
            path = extraction / "responses" / f"{job['input_hash']}.json"
            response = read_json(path)
            if response["input_hash"] != job["input_hash"]:
                raise ValueError("Response input hash differs from its manifest job")
            for candidate_index, candidate in enumerate(response["output"]["records"]):
                key = job["input_hash"], digest(candidate)
                if remaining.get(key):
                    records.append(failure_record(
                        remaining[key].pop(0), job, response, path, candidate_index, proposal_order
                    ))
                proposal_order += 1
        if any(remaining.values()):
            raise ValueError("Saved rejection has no matching raw proposal in the responses")
        report.update({
            "status": "complete", "candidate_records_seen": proposal_order,
            "rejected_records": len(records), "records": records,
            "category_counts": {
                category: sum(record["category"] == category for record in records)
                for category in CATEGORIES
            },
            "ordered_failure_reason_counts": dict(Counter(
                record["ordered_failure_reason"] for record in records
            )),
            "unpermitted_substitutions": substitution_counts(records),
        })
    except (OSError, ValueError, KeyError, TypeError) as error:
        report["blocked_reason"] = f"{type(error).__name__}: {error}"
    return report
