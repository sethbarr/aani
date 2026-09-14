"""V2 identity and span checks with narrowly scoped glyph quote comparison."""

from pydantic import ValidationError

from src.common.io import digest
from src.extraction.glyph_grounding import ground_quote
from src.extraction.multispan import EvidenceSpan, MultiSpanObservation
from src.extraction.multispan_v2 import validate_multispan_v2_candidate


def observation_spans(observation: MultiSpanObservation) -> list[tuple[str, int | None, EvidenceSpan]]:
    """Enumerate the existing required and supporting quote fields.

    Args:
        observation: Schema-checked, unchanged model observation.

    Returns:
        Field names, optional supporting indices and individual source spans.
    """
    spans = [
        (
            "evidence_quote",
            None,
            EvidenceSpan(
                block_id=observation.block_id,
                section=observation.section,
                quote=observation.evidence_quote,
            ),
        ),
        ("name_evidence", None, observation.name_evidence),
    ]
    spans.extend(
        ("supporting_evidence", index, span)
        for index, span in enumerate(observation.supporting_evidence)
    )
    return spans


def field_reason(field: str, index: int | None, reason: str) -> str:
    """Apply the existing field-specific rejection prefixes.

    Args:
        field: Observation field containing the rejected quote.
        index: Supporting-span index, when applicable.
        reason: Unprefixed grounding rejection reason.

    Returns:
        A rejection reason with the original multi-span field convention.
    """
    if field == "evidence_quote":
        return reason
    prefix = f"{field}[{index}]" if index is not None else field
    return f"{prefix}:{reason}"


def canonical_candidate(observation: MultiSpanObservation, grounded_spans: list[dict]) -> dict:
    """Create an internal v2-check copy using only matched source quotations.

    Args:
        observation: Original, unchanged model observation.
        grounded_spans: Accepted exact or bounded-equivalence source matches.

    Returns:
        A transient schema dictionary whose quote fields are source text. This
        dictionary is never emitted as the model's original record.
    """
    candidate = observation.model_dump()
    for span in grounded_spans:
        field = span["field"]
        source_quote = span["matched_source_quote"]
        if field == "evidence_quote":
            candidate[field] = source_quote
        elif field == "name_evidence":
            candidate[field]["quote"] = source_quote
        else:
            candidate[field][span["index"]]["quote"] = source_quote
    return candidate


def candidate_grounding_audit(candidate: dict, job: dict) -> dict:
    """Audit every original quote independently without changing a candidate.

    Args:
        candidate: Original proposed record, including candidates later rejected
            by identity, plant-name or confidence checks.
        job: Exact extraction context and comparison-only glyph policy.

    Returns:
        Explicit schema status and one match or rejection entry per available
        schema span. This quote-only audit does not make a validator decision.
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
            "spans": [],
        }
    blocks = {block["block_id"]: block for block in job["blocks"]}
    source_matches = observation.source_id == job["source_id"]
    entries: list[dict] = []
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
            match, reason = ground_quote(span.quote, block, job)
        if match is not None:
            entries.append({"field": field, "index": index, **match})
        else:
            entries.append(
                {
                    "field": field,
                    "index": index,
                    "route": "rejected",
                    "source_id": observation.source_id,
                    "source_block": span.block_id,
                    "section": span.section,
                    "emitted_quote": span.quote,
                    "rejection_reason": field_reason(field, index, reason or "ungrounded_quote"),
                }
            )
    return {
        "schema_valid": True,
        "schema_error": None,
        "blocked_reason": None if source_matches else "unknown_source_or_block",
        "all_spans_grounded": all(entry["route"] != "rejected" for entry in entries),
        "exact_span_count": sum(entry["route"] == "exact" for entry in entries),
        "glyph_span_count": sum(entry["route"] == "bounded_glyph_equivalence" for entry in entries),
        "spans": entries,
    }


def validate_multispan_v3_candidate(
    candidate: dict, job: dict, minimum_confidence: float
) -> tuple[dict | None, str | None]:
    """Run unchanged v2 checks after exact or bounded glyph span grounding.

    Args:
        candidate: Proposed record under the unchanged multi-span schema.
        job: Unchanged extraction context plus comparison-only glyph policy.
        minimum_confidence: Existing frozen extraction-confidence threshold.

    Returns:
        Original schema fields and original digest with per-span grounding
        provenance, or a rejection reason. All v2 identity and name checks are
        delegated to v2 using matched source spans after every span is checked.
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
    for field, index, span in spans:
        match, reason = ground_quote(span.quote, blocks[span.block_id], job)
        if reason is not None:
            return None, field_reason(field, index, reason)
        assert match is not None
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
    record["quote_grounding_route"] = (
        "bounded_glyph_equivalence"
        if any(span["route"] == "bounded_glyph_equivalence" for span in grounded_spans)
        else "exact"
    )
    return record, None
