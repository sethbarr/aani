"""Candidate mapping, raw preservation and unchanged downstream v2 checks."""

import copy
from hashlib import sha256

import pytest

from src.common.io import digest
from src.extraction.cache_control_grounding import CACHE_CONTROL_ROUTE, GLYPH_POLICY_V6
from src.extraction.multispan import MultiSpanObservation
from src.extraction.multispan_v6 import (
    candidate_grounding_audit_v6,
    validate_multispan_v6_candidate,
)
from tests.test_multispan_v3 import table_candidate, table_job


def cache_table_job() -> dict:
    """Create a bound fixture with earlier glyph classes and cached controls."""
    job = table_job()
    job["blocks"][0]["text"] += (
        "\nHiraea fagifolia shows habitat\u0002related rejection."
        "\nThe second habitat\u0002related passage."
        "\nA third habitat\u0005related passage."
        "\nOne other habitat–related passage."
    )
    job["glyph_policy"] = copy.deepcopy(GLYPH_POLICY_V6)
    job["glyph_source_hashes"] = {
        "source_id": job["source_id"],
        "blocks": {
            block["block_id"]: sha256(block["text"].encode("utf-8")).hexdigest()
            for block in job["blocks"]
        },
    }
    return job


def cache_candidate() -> dict:
    """Create a record requiring both cache-side and existing control inference."""
    candidate = table_candidate()
    candidate["evidence_quote"] = "Hiraea fagifolia shows habitat-related rejection."
    return candidate


def test_original_schema_digest_directions_and_source_fields_are_preserved() -> None:
    """Use cached text only for temporary v2 checks and explicit provenance."""
    candidate = cache_candidate()
    job = cache_table_job()
    original_candidate = copy.deepcopy(candidate)
    original_job = copy.deepcopy(job)
    record, reason = validate_multispan_v6_candidate(candidate, job, 0.8)
    assert reason is None
    assert record is not None
    schema = MultiSpanObservation.model_validate(candidate).model_dump()
    assert {field: record[field] for field in schema} == schema
    assert record["record_id"] == digest(schema)
    assert record["outcome"] == candidate["outcome"]
    assert record["quote_grounding_route"] == CACHE_CONTROL_ROUTE
    assert record["inferred_cache_control_mapping"] == [{
        "source_character": "\u0002", "model_character": "-",
        "source_codepoint": "U+0002", "model_codepoint": "U+002D",
    }]
    assert record["ant_identity_route"] == "source_identity_abbreviation"
    assert candidate == original_candidate
    assert job == original_job
    audit = candidate_grounding_audit_v6(candidate, job)
    assert audit["spans"] == record["grounded_source_spans"]
    assert audit["cache_control_span_count"] == 1
    assert audit["control_glyph_span_count"] == 1


@pytest.mark.parametrize(
    ("quote", "reason"),
    [
        ("The second habitat—related passage.", "conflicting_cache_control_mapping"),
        ("A third habitat-related passage.", "conflicting_glyph_mapping"),
        ("One other habitat-related passage.", "conflicting_glyph_mapping"),
    ],
)
def test_cross_span_conflicts_fail_with_logged_evidence(quote: str, reason: str) -> None:
    """Enforce forward mappings across all classes and mirrored cache mappings."""
    candidate = cache_candidate()
    candidate["supporting_evidence"][0]["quote"] = quote
    job = cache_table_job()
    expected = f"supporting_evidence[0]:{reason}"
    assert validate_multispan_v6_candidate(candidate, job, 0.8) == (None, expected)
    audit = candidate_grounding_audit_v6(candidate, job)
    failure = audit["spans"][2]
    assert failure["route"] == "rejected"
    assert failure["rejection_reason"] == expected
    assert failure["conflicting_match_evidence"]["replacements"]
    assert audit["spans"][3]["route"] == "source_anchored_control_glyph"


def test_consistent_repeated_mapping_and_literal_control_are_eligible() -> None:
    """Permit repeated evidence and ignore controls matched literally."""
    candidate = cache_candidate()
    candidate["supporting_evidence"][0]["quote"] = "The second habitat-related passage."
    job = cache_table_job()
    record, reason = validate_multispan_v6_candidate(candidate, job, 0.8)
    assert reason is None
    assert record is not None
    assert len(record["inferred_cache_control_mapping"]) == 1
    candidate["supporting_evidence"][0]["quote"] = "The second habitat\u0002related passage."
    record, reason = validate_multispan_v6_candidate(candidate, job, 0.8)
    assert reason is None
    assert record is not None
    assert record["grounded_source_spans"][2]["route"] == "exact"


def test_cache_mapping_does_not_leak_across_candidates() -> None:
    """Infer one cache mapping independently within each proposed record."""
    first = cache_candidate()
    second = cache_candidate()
    second["evidence_quote"] = second["evidence_quote"].replace("-", "—")
    job = cache_table_job()
    first_record, first_reason = validate_multispan_v6_candidate(first, job, 0.8)
    second_record, second_reason = validate_multispan_v6_candidate(second, job, 0.8)
    assert first_reason is None and second_reason is None
    assert first_record is not None and second_record is not None
    assert first_record["inferred_cache_control_mapping"][0]["model_character"] == "-"
    assert second_record["inferred_cache_control_mapping"][0]["model_character"] == "—"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("ant_species", "A. cephalotes", "ant_identity_mismatch"),
        ("name_surface_form", "Hiraea invented", "name_surface_not_in_quote"),
        ("plant_name_as_written", "Hiraea invented", "plant_not_in_name_evidence"),
        ("extraction_confidence", 0.79, "low_confidence"),
        ("source_id", "OTHER", "unknown_source_or_block"),
        ("block_id", "OTHER", "unknown_source_or_block"),
        ("section", "Methods", "section_mismatch"),
    ],
)
def test_existing_gates_remain(field: str, value: object, reason: str) -> None:
    """Retain existing identity, name, confidence and source gates."""
    candidate = cache_candidate()
    candidate[field] = value
    assert validate_multispan_v6_candidate(candidate, cache_table_job(), 0.8) == (None, reason)


def test_schema_failures_remain_explicit() -> None:
    """Keep the independent name-span schema requirement and audit status."""
    candidate = cache_candidate()
    del candidate["name_evidence"]
    record, reason = validate_multispan_v6_candidate(candidate, cache_table_job(), 0.8)
    assert record is None
    assert reason is not None and reason.startswith("schema:")
    audit = candidate_grounding_audit_v6(candidate, cache_table_job())
    assert audit["schema_valid"] is False
    assert audit["blocked_reason"] == "schema_error"
