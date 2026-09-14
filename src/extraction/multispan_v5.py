"""Candidate-local v5 control and printable-confusable grounding."""

from pydantic import ValidationError

from src.common.io import digest
from src.extraction.adaptive_glyph_grounding import inferred_mapping
from src.extraction.multispan import EvidenceSpan, MultiSpanObservation
from src.extraction.multispan_v2 import validate_multispan_v2_candidate
from src.extraction.multispan_v3 import field_reason, observation_spans
from src.extraction.multispan_v4 import merge_span_mapping
from src.extraction.printable_confusable_grounding import ground_quote_v5, ground_section_v5


def canonical_candidate_v5(observation: MultiSpanObservation, grounded_spans: list[dict]) -> dict:
    """Create a transient v2 candidate from matched source quotes and sections."""
    candidate = observation.model_dump()
    for span in grounded_spans:
        field = span["field"]
        source_quote = span["matched_source_quote"]
        source_section = span["section_match"]["matched_source_section"]
        if field == "evidence_quote":
            candidate["evidence_quote"] = source_quote
            candidate["section"] = source_section
        elif field == "name_evidence":
            candidate[field]["quote"] = source_quote
            candidate[field]["section"] = source_section
        else:
            index = span["index"]
            candidate[field][index]["quote"] = source_quote
            candidate[field][index]["section"] = source_section
    return candidate


def combined_replacements(grounded_spans: list[dict]) -> list[dict]:
    """Collect quote and section substitutions in deterministic span order."""
    replacements: list[dict] = []
    for span in grounded_spans:
        replacements.extend(span["replacements"])
        replacements.extend(span["section_match"]["replacements"])
    return replacements


def span_grounding_v5(
    field: str,
    index: int | None,
    span: EvidenceSpan,
    block: dict,
    job: dict,
    mapping: dict[str, str],
) -> tuple[dict | None, str | None]:
    """Ground one schema span and merge its section and quote mappings."""
    local_mapping = mapping.copy()
    section_match, reason = ground_section_v5(span.section, block, job)
    if section_match is None:
        return None, field_reason(field, index, reason or "section_mismatch")
    if not merge_span_mapping(local_mapping, section_match):
        return None, field_reason(field, index, "conflicting_glyph_mapping")
    quote_match, reason = ground_quote_v5(span.quote, block, job)
    if quote_match is None:
        return None, field_reason(field, index, reason or "ungrounded_quote")
    if not merge_span_mapping(local_mapping, quote_match):
        return None, field_reason(field, index, "conflicting_glyph_mapping")
    mapping.clear()
    mapping.update(local_mapping)
    return {"field": field, "index": index, **quote_match, "section_match": section_match}, None


def candidate_grounding_audit_v5(candidate: dict, job: dict) -> dict:
    """Audit all v5 quote and section matches without changing a proposal."""
    try:
        observation = MultiSpanObservation.model_validate(candidate)
    except ValidationError as error:
        return {
            "schema_valid": False,
            "schema_error": str(error),
            "blocked_reason": "schema_error",
            "all_spans_grounded": None,
            "exact_span_count": 0,
            "control_glyph_span_count": 0,
            "printable_confusable_span_count": 0,
            "inferred_mapping": [],
            "spans": [],
        }
    blocks = {block["block_id"]: block for block in job["blocks"]}
    source_matches = observation.source_id == job["source_id"]
    entries: list[dict] = []
    mapping: dict[str, str] = {}
    for field, index, span in observation_spans(observation):
        block = blocks.get(span.block_id)
        if not source_matches:
            reason = field_reason(field, index, "unknown_source_or_block")
            match = None
        elif block is None:
            reason = field_reason(field, index, "unknown_block")
            match = None
        else:
            match, reason = span_grounding_v5(field, index, span, block, job, mapping)
        if match is not None:
            entries.append(match)
        else:
            entries.append({
                "field": field,
                "index": index,
                "route": "rejected",
                "source_id": observation.source_id,
                "source_block": span.block_id,
                "section": span.section,
                "emitted_quote": span.quote,
                "rejection_reason": reason,
            })
    replacements = combined_replacements([
        entry for entry in entries if entry["route"] != "rejected"
    ])
    return {
        "schema_valid": True,
        "schema_error": None,
        "blocked_reason": None if source_matches else "unknown_source_or_block",
        "all_spans_grounded": all(entry["route"] != "rejected" for entry in entries),
        "exact_span_count": sum(
            entry["route"] == "exact"
            and entry["section_match"]["route"] == "exact"
            for entry in entries if entry["route"] != "rejected"
        ),
        "control_glyph_span_count": sum(
            entry["route"] == "source_anchored_control_glyph"
            for entry in entries if entry["route"] != "rejected"
        ),
        "printable_confusable_span_count": sum(
            entry["route"] == "source_anchored_printable_confusable"
            or entry["section_match"]["route"] == "source_anchored_printable_confusable"
            for entry in entries if entry["route"] != "rejected"
        ),
        "inferred_mapping": inferred_mapping(replacements),
        "spans": entries,
    }


def validate_multispan_v5_candidate(
    candidate: dict, job: dict, minimum_confidence: float,
) -> tuple[dict | None, str | None]:
    """Run unchanged v2 checks after v5 source-anchored inference."""
    try:
        observation = MultiSpanObservation.model_validate(candidate)
    except ValidationError as error:
        return None, f"schema: {error}"
    blocks = {block["block_id"]: block for block in job["blocks"]}
    if observation.source_id != job["source_id"] or observation.block_id not in blocks:
        return None, "unknown_source_or_block"
    grounded_spans: list[dict] = []
    mapping: dict[str, str] = {}
    for field, index, span in observation_spans(observation):
        block = blocks.get(span.block_id)
        if block is None:
            return None, field_reason(field, index, "unknown_block")
        match, reason = span_grounding_v5(field, index, span, block, job, mapping)
        if match is None:
            return None, reason
        grounded_spans.append(match)
    record, reason = validate_multispan_v2_candidate(
        canonical_candidate_v5(observation, grounded_spans), job, minimum_confidence,
    )
    if record is None:
        return None, reason
    original = observation.model_dump()
    replacements = combined_replacements(grounded_spans)
    record.update(original)
    record["record_id"] = digest(original)
    record["grounded_source_spans"] = grounded_spans
    record["grounding_metadata_quote_representation"] = "matched_source_text"
    record["inferred_character_mapping"] = inferred_mapping(replacements)
    routes = {
        span["route"] for span in grounded_spans
    } | {
        span["section_match"]["route"] for span in grounded_spans
    }
    if "source_anchored_printable_confusable" in routes:
        record["quote_grounding_route"] = "source_anchored_printable_confusable"
    elif "source_anchored_control_glyph" in routes:
        record["quote_grounding_route"] = "source_anchored_control_glyph"
    else:
        record["quote_grounding_route"] = "exact"
    return record, None
