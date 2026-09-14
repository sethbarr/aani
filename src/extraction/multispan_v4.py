"""Candidate-local inferred glyph mappings with unchanged v2 identity checks."""

from pydantic import ValidationError

from src.common.io import digest
from src.extraction.adaptive_glyph_grounding import ground_quote_v4, inferred_mapping
from src.extraction.multispan import MultiSpanObservation
from src.extraction.multispan_v2 import validate_multispan_v2_candidate
from src.extraction.multispan_v3 import canonical_candidate, field_reason, observation_spans


def merge_span_mapping(mapping: dict[str, str], match: dict) -> bool:
    """Merge one grounded span's mismatches if the candidate mapping agrees.

    Args:
        mapping: Candidate-local control-to-glyph mapping, updated on agreement.
        match: Exact or source-anchored match with per-position replacements.

    Returns:
        Whether every inferred substitution agrees with earlier span evidence.
        Conflicting spans leave the accumulated mapping unchanged.
    """
    pairs = {
        entry["model_character"]: entry["source_character"]
        for entry in match["replacements"]
    }
    if any(character in mapping and mapping[character] != glyph for character, glyph in pairs.items()):
        return False
    mapping.update(pairs)
    return True


def candidate_grounding_audit_v4(candidate: dict, job: dict) -> dict:
    """Audit every span and candidate-local mapping without changing a proposal.

    Args:
        candidate: Original proposed record, including later rejected records.
        job: Source blocks, identity context and comparison-only v4 policy.

    Returns:
        Schema status, quote-match evidence, and ordered span failures. This
        quote audit leaves subsequent identity and confidence checks unscored.
    """
    try:
        observation = MultiSpanObservation.model_validate(candidate)
    except ValidationError as error:
        return {
            "schema_valid": False,
            "schema_error": str(error),
            "blocked_reason": "schema_error",
            "all_spans_grounded": None,
            "exact_span_count": 0,
            "glyph_span_count": 0,
            "inferred_mapping": [],
            "spans": [],
        }
    blocks = {block["block_id"]: block for block in job["blocks"]}
    source_matches = observation.source_id == job["source_id"]
    entries: list[dict] = []
    mapping: dict[str, str] = {}
    for field, index, span in observation_spans(observation):
        block = blocks.get(span.block_id)
        match: dict | None = None
        if not source_matches:
            reason = "unknown_source_or_block"
        elif block is None:
            reason = "unknown_block"
        elif span.section != block["section"]:
            reason = "section_mismatch"
        else:
            match, reason = ground_quote_v4(span.quote, block, job)
            if match is not None and not merge_span_mapping(mapping, match):
                reason = "conflicting_glyph_mapping"
        if match is not None and reason is None:
            entries.append({"field": field, "index": index, **match})
        else:
            entries.append({
                "field": field,
                "index": index,
                "route": "rejected",
                "source_id": observation.source_id,
                "source_block": span.block_id,
                "section": span.section,
                "emitted_quote": span.quote,
                "rejection_reason": field_reason(field, index, reason or "ungrounded_quote"),
                "conflicting_match_evidence": match,
            })
    replacements = [
        replacement
        for entry in entries
        for replacement in entry.get("replacements", [])
    ]
    return {
        "schema_valid": True,
        "schema_error": None,
        "blocked_reason": None if source_matches else "unknown_source_or_block",
        "all_spans_grounded": all(entry["route"] != "rejected" for entry in entries),
        "exact_span_count": sum(entry["route"] == "exact" for entry in entries),
        "glyph_span_count": sum(entry["route"] == "source_anchored_control_glyph" for entry in entries),
        "inferred_mapping": inferred_mapping(replacements),
        "spans": entries,
    }


def validate_multispan_v4_candidate(
    candidate: dict, job: dict, minimum_confidence: float
) -> tuple[dict | None, str | None]:
    """Run unchanged v2 checks after source-anchored, candidate-consistent repair.

    Args:
        candidate: Proposed record under the unchanged multi-span schema.
        job: Original extraction context with v4 policy and source bindings.
        minimum_confidence: Existing frozen extraction-confidence threshold.

    Returns:
        Original schema fields and digest plus quote-grounding evidence, or an
        ordered rejection reason. Matched cached quotes exist only in the
        temporary copy passed to v2 and the explicit provenance fields.
    """
    try:
        observation = MultiSpanObservation.model_validate(candidate)
    except ValidationError as error:
        return None, f"schema: {error}"
    blocks = {block["block_id"]: block for block in job["blocks"]}
    if observation.source_id != job["source_id"] or observation.block_id not in blocks:
        return None, "unknown_source_or_block"
    spans = observation_spans(observation)
    for field, index, span in spans:
        block = blocks.get(span.block_id)
        if block is None:
            return None, field_reason(field, index, "unknown_block")
        if span.section != block["section"]:
            return None, field_reason(field, index, "section_mismatch")
    grounded_spans: list[dict] = []
    mapping: dict[str, str] = {}
    for field, index, span in spans:
        match, reason = ground_quote_v4(span.quote, blocks[span.block_id], job)
        if reason is not None:
            return None, field_reason(field, index, reason)
        assert match is not None
        if not merge_span_mapping(mapping, match):
            return None, field_reason(field, index, "conflicting_glyph_mapping")
        grounded_spans.append({"field": field, "index": index, **match})
    record, reason = validate_multispan_v2_candidate(
        canonical_candidate(observation, grounded_spans), job, minimum_confidence
    )
    if reason is not None:
        return None, reason
    assert record is not None
    original = observation.model_dump()
    record.update(original)
    record["record_id"] = digest(original)
    record["grounded_source_spans"] = grounded_spans
    record["grounding_metadata_quote_representation"] = "matched_source_text"
    record["inferred_glyph_mapping"] = inferred_mapping([
        replacement for span in grounded_spans for replacement in span["replacements"]
    ])
    record["quote_grounding_route"] = (
        "source_anchored_control_glyph"
        if record["inferred_glyph_mapping"] else "exact"
    )
    return record, None
