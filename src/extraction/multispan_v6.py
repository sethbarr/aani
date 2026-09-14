"""Candidate-local cache-side control inference with unchanged v2 gates."""

from pydantic import ValidationError

from src.common.io import digest
from src.extraction.adaptive_glyph_grounding import inferred_mapping
from src.extraction.cache_control_grounding import (
    CACHE_CONTROL_ROUTE,
    ground_quote_v6,
    ground_section_v6,
)
from src.extraction.multispan import EvidenceSpan, MultiSpanObservation
from src.extraction.multispan_v2 import validate_multispan_v2_candidate
from src.extraction.multispan_v3 import field_reason, observation_spans
from src.extraction.multispan_v4 import merge_span_mapping
from src.extraction.multispan_v5 import canonical_candidate_v5, combined_replacements


def merge_cache_mapping(mapping: dict[str, str], match: dict) -> bool:
    """Require one emitted printable per cached control within a candidate."""
    if match["route"] != CACHE_CONTROL_ROUTE:
        return True
    pairs = {
        entry["source_character"]: entry["model_character"]
        for entry in match["replacements"]
    }
    if any(cached in mapping and mapping[cached] != emitted for cached, emitted in pairs.items()):
        return False
    mapping.update(pairs)
    return True


def span_grounding_v6(
    field: str,
    index: int | None,
    span: EvidenceSpan,
    block: dict,
    job: dict,
    mapping: dict[str, str],
    cache_mapping: dict[str, str],
) -> tuple[dict | None, str | None]:
    """Ground a span transactionally and enforce both candidate-local maps."""
    local_mapping = mapping.copy()
    local_cache_mapping = cache_mapping.copy()
    section_match, reason = ground_section_v6(span.section, block, job)
    if section_match is None:
        return None, field_reason(field, index, reason or "section_mismatch")
    if not merge_span_mapping(local_mapping, section_match):
        return {"section_match": section_match}, field_reason(field, index, "conflicting_glyph_mapping")
    quote_match, reason = ground_quote_v6(span.quote, block, job)
    if quote_match is None:
        return None, field_reason(field, index, reason or "ungrounded_quote")
    match = {"field": field, "index": index, **quote_match, "section_match": section_match}
    if not merge_span_mapping(local_mapping, quote_match):
        return match, field_reason(field, index, "conflicting_glyph_mapping")
    if not merge_cache_mapping(local_cache_mapping, quote_match):
        return match, field_reason(field, index, "conflicting_cache_control_mapping")
    mapping.clear()
    mapping.update(local_mapping)
    cache_mapping.clear()
    cache_mapping.update(local_cache_mapping)
    return match, None


def cache_mapping_evidence(mapping: dict[str, str]) -> list[dict]:
    """Describe candidate-local cached-control-to-emitted-printable mappings."""
    return [
        {
            "source_character": cached,
            "model_character": emitted,
            "source_codepoint": f"U+{ord(cached):04X}",
            "model_codepoint": f"U+{ord(emitted):04X}",
        }
        for cached, emitted in sorted(mapping.items())
    ]


def candidate_grounding_audit_v6(candidate: dict, job: dict) -> dict:
    """Audit all spans under v6 without changing raw candidate fields."""
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
            "cache_control_span_count": 0,
            "inferred_mapping": [],
            "inferred_cache_mapping": [],
            "spans": [],
        }
    blocks = {block["block_id"]: block for block in job["blocks"]}
    source_matches = observation.source_id == job["source_id"]
    entries: list[dict] = []
    mapping: dict[str, str] = {}
    cache_mapping: dict[str, str] = {}
    for field, index, span in observation_spans(observation):
        block = blocks.get(span.block_id)
        match = None
        if not source_matches:
            reason = field_reason(field, index, "unknown_source_or_block")
        elif block is None:
            reason = field_reason(field, index, "unknown_block")
        else:
            match, reason = span_grounding_v6(
                field, index, span, block, job, mapping, cache_mapping,
            )
        if match is not None and reason is None:
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
                "conflicting_match_evidence": match,
            })
    grounded = [entry for entry in entries if entry["route"] != "rejected"]
    return {
        "schema_valid": True,
        "schema_error": None,
        "blocked_reason": None if source_matches else "unknown_source_or_block",
        "all_spans_grounded": all(entry["route"] != "rejected" for entry in entries),
        "exact_span_count": sum(
            entry["route"] == "exact" and entry["section_match"]["route"] == "exact"
            for entry in grounded
        ),
        "control_glyph_span_count": sum(
            entry["route"] == "source_anchored_control_glyph" for entry in grounded
        ),
        "printable_confusable_span_count": sum(
            entry["route"] == "source_anchored_printable_confusable"
            or entry["section_match"]["route"] == "source_anchored_printable_confusable"
            for entry in grounded
        ),
        "cache_control_span_count": sum(entry["route"] == CACHE_CONTROL_ROUTE for entry in grounded),
        "inferred_mapping": inferred_mapping(combined_replacements(grounded)),
        "inferred_cache_mapping": cache_mapping_evidence(cache_mapping),
        "spans": entries,
    }


def validate_multispan_v6_candidate(
    candidate: dict, job: dict, minimum_confidence: float,
) -> tuple[dict | None, str | None]:
    """Run unchanged v2 identity and eligibility gates after v6 comparison.

    Args:
        candidate: Original proposal under the unchanged multi-span schema.
        job: Bound source context and immutable v6 comparison policy.
        minimum_confidence: Existing frozen extraction confidence threshold.

    Returns:
        Original schema fields and digest with source-match evidence, or an
        ordered rejection. Canonical source text exists only in a temporary
        candidate used for the existing v2 checks and provenance fields.
    """
    try:
        observation = MultiSpanObservation.model_validate(candidate)
    except ValidationError as error:
        return None, f"schema: {error}"
    blocks = {block["block_id"]: block for block in job["blocks"]}
    if observation.source_id != job["source_id"] or observation.block_id not in blocks:
        return None, "unknown_source_or_block"
    grounded_spans: list[dict] = []
    mapping: dict[str, str] = {}
    cache_mapping: dict[str, str] = {}
    for field, index, span in observation_spans(observation):
        block = blocks.get(span.block_id)
        if block is None:
            return None, field_reason(field, index, "unknown_block")
        match, reason = span_grounding_v6(field, index, span, block, job, mapping, cache_mapping)
        if reason is not None:
            return None, reason
        assert match is not None
        grounded_spans.append(match)
    record, reason = validate_multispan_v2_candidate(
        canonical_candidate_v5(observation, grounded_spans), job, minimum_confidence,
    )
    if record is None:
        return None, reason
    original = observation.model_dump()
    record.update(original)
    record["record_id"] = digest(original)
    record["grounded_source_spans"] = grounded_spans
    record["grounding_metadata_quote_representation"] = "matched_source_text"
    record["inferred_character_mapping"] = inferred_mapping(combined_replacements(grounded_spans))
    record["inferred_cache_control_mapping"] = cache_mapping_evidence(cache_mapping)
    routes = {span["route"] for span in grounded_spans} | {
        span["section_match"]["route"] for span in grounded_spans
    }
    record["quote_grounding_route"] = "exact"
    for route in (
        CACHE_CONTROL_ROUTE, "source_anchored_printable_confusable", "source_anchored_control_glyph",
    ):
        if route in routes:
            record["quote_grounding_route"] = route
            break
    return record, None
