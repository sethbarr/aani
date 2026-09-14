"""Replay v5 grounding on immutable single-quote system proposals."""

from copy import deepcopy
from hashlib import sha256

from pydantic import ValidationError

from src.common.io import digest, normalise_space
from src.extraction.adaptive_glyph_grounding import inferred_mapping
from src.extraction.multispan_v4 import merge_span_mapping
from src.extraction.printable_confusable_grounding import (
    GLYPH_POLICY_V5,
    ground_quote_v5,
    ground_section_v5,
)
from src.systems.config import SystemConfig
from src.systems.extraction import validate_system_candidate
from src.systems.grounding_v4 import audit_system_candidate_v4, bind_system_job_v4
from src.systems.schema import SystemObservation


def bind_system_job_v5(job: dict) -> dict:
    """Bind unchanged system source blocks to the fixed v5 policy."""
    original = {key: value for key, value in job.items() if key != "input_hash"}
    if digest(original) != job["input_hash"]:
        raise ValueError("original_system_payload_hash_mismatch")
    bound = deepcopy(original)
    bound.update({
        "source_job_input_hash": job["input_hash"],
        "validation_mode": "printable_confusables_v5_on_system_single_quote_v1",
        "glyph_policy": deepcopy(GLYPH_POLICY_V5),
        "glyph_source_hashes": {
            "source_id": job["source_id"],
            "blocks": {
                block["block_id"]: sha256(block["text"].encode("utf-8")).hexdigest()
                for block in job["blocks"]
            },
        },
    })
    bound["input_hash"] = digest(bound)
    return bound


def complete_route(quote_match: dict, section_match: dict) -> str:
    """Summarize the most permissive source-grounding route used."""
    routes = {quote_match["route"], section_match["route"]}
    if "source_anchored_printable_confusable" in routes:
        return "source_anchored_printable_confusable"
    if "source_anchored_control_glyph" in routes:
        return "source_anchored_control_glyph"
    return "exact"


def audit_system_candidate_v5(
    candidate: dict,
    job: dict,
    bound: dict,
    config: SystemConfig,
    minimum_confidence: float,
) -> tuple[dict | None, dict]:
    """Apply v5 grounding and preserve every other system validator check."""
    if bound != bind_system_job_v5(job):
        raise ValueError("v5_job_binding_mismatch")
    _, v4_audit = audit_system_candidate_v4(
        candidate, job, bind_system_job_v4(job), config, minimum_confidence,
    )
    audit = {
        "source_id": job["source_id"],
        "input_hash": job["input_hash"],
        "v5_input_hash": bound["input_hash"],
        "candidate_hash": digest(candidate),
        "baseline_accepted": v4_audit["baseline_accepted"],
        "baseline_reason": v4_audit["baseline_reason"],
        "v4_accepted": v4_audit["v4_accepted"],
        "v4_reason": v4_audit["v4_reason"],
        "quote_match": None,
        "quote_reason": None,
        "section_match": None,
        "section_reason": None,
        "v5_accepted": False,
        "v5_reason": v4_audit["v4_reason"],
        "candidate": deepcopy(candidate),
    }
    try:
        original = SystemObservation.model_validate(candidate).model_dump()
    except ValidationError:
        return None, audit
    audit["record_id"] = digest(original)
    blocks = {block["block_id"]: block for block in job["blocks"]}
    block = blocks.get(original["block_id"])
    if original["source_id"] != job["source_id"] or block is None:
        audit["quote_reason"] = "unknown_source_or_block"
        audit["section_reason"] = "unknown_source_or_block"
        audit["v5_reason"] = "unknown_source_or_block"
        return None, audit
    audit.update(
        declared_section=original["section"],
        source_section=block["section"],
        target_in_emitted_quote=normalise_space(original["target_name_as_written"])
        in normalise_space(original["evidence_quote"]),
    )
    mapping: dict[str, str] = {}
    section_match, section_reason = ground_section_v5(original["section"], block, bound)
    audit.update(section_match=section_match, section_reason=section_reason)
    if section_match is None:
        audit["v5_reason"] = section_reason
        return None, audit
    if not merge_span_mapping(mapping, section_match):
        audit["v5_reason"] = "conflicting_glyph_mapping"
        return None, audit
    quote_match, quote_reason = ground_quote_v5(original["evidence_quote"], block, bound)
    audit.update(quote_match=quote_match, quote_reason=quote_reason)
    if quote_match is None:
        audit["v5_reason"] = quote_reason
        return None, audit
    if not merge_span_mapping(mapping, quote_match):
        audit["v5_reason"] = "conflicting_glyph_mapping"
        return None, audit
    canonical = {
        **original,
        "section": section_match["matched_source_section"],
        "evidence_quote": quote_match["matched_source_quote"],
    }
    record, reason = validate_system_candidate(canonical, job, config, minimum_confidence)
    audit.update(v5_accepted=record is not None, v5_reason=reason)
    if record is None:
        return None, audit
    record.update(original)
    record["record_id"] = digest(original)
    record["v5_input_hash"] = bound["input_hash"]
    record["quote_grounding_route"] = complete_route(quote_match, section_match)
    record["grounded_source_quote"] = quote_match
    record["grounded_source_section"] = section_match
    record["inferred_character_mapping"] = inferred_mapping(
        section_match["replacements"] + quote_match["replacements"]
    )
    return record, audit
