"""V4 wrapper checks for raw-record preservation and unchanged v2 gates."""

import copy
import hashlib

import pytest

from src.common.io import digest
from src.extraction.adaptive_glyph_grounding import GLYPH_POLICY_V4
from src.extraction.multispan import MultiSpanObservation
from src.extraction.multispan_v2 import validate_multispan_v2_candidate
from src.extraction.multispan_v4 import (
    candidate_grounding_audit_v4,
    validate_multispan_v4_candidate,
)
from tests.test_multispan_v3 import table_candidate, table_job


def adaptive_table_job() -> dict:
    """Bind unchanged test source bytes to the v4 comparison-only policy."""
    job = table_job()
    job["glyph_policy"] = copy.deepcopy(GLYPH_POLICY_V4)
    job["glyph_source_hashes"] = {
        "source_id": job["source_id"],
        "blocks": {
            block["block_id"]: hashlib.sha256(block["text"].encode("utf-8")).hexdigest()
            for block in job["blocks"]
        },
    }
    return job


def adaptive_candidate() -> dict:
    """Create a proposal with C0 values absent from both observed samples."""
    candidate = table_candidate()
    candidate["evidence_quote"] = candidate["evidence_quote"].replace("\u0001", "\u0015")
    candidate["supporting_evidence"][1]["quote"] = (
        candidate["supporting_evidence"][1]["quote"].replace("\u0001", "\u0015").replace("\u0003", "\u0016")
    )
    return candidate


def test_v4_preserves_every_raw_schema_field_record_id_and_source_offsets() -> None:
    """Use matched source text solely for temporary v2 checks and provenance."""
    candidate = adaptive_candidate()
    job = adaptive_table_job()
    original = copy.deepcopy(candidate)
    original_job = copy.deepcopy(job)
    assert validate_multispan_v2_candidate(candidate, job, 0.8) == (None, "ungrounded_quote")
    record, reason = validate_multispan_v4_candidate(candidate, job, 0.8)
    assert reason is None
    assert record is not None
    schema_fields = MultiSpanObservation.model_validate(candidate).model_dump()
    assert {field: record[field] for field in schema_fields} == schema_fields
    assert record["record_id"] == digest(schema_fields)
    assert candidate == original
    assert job == original_job
    assert record["ant_identity_route"] == "source_identity_abbreviation"
    assert record["quote_grounding_route"] == "source_anchored_control_glyph"
    assert record["grounding_metadata_quote_representation"] == "matched_source_text"
    assert record["plant_name_surface_provenance"]["evidence_quote"] == "Hiraea fagifolia 0.01 ± 0.00"
    assert len(record["inferred_glyph_mapping"]) == 2
    for span in record["grounded_source_spans"]:
        text = job["blocks"][0]["text"]
        assert text[span["start"]:span["end"]] == span["matched_source_quote"]


@pytest.mark.parametrize(
    ("field", "value", "expected"),
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
def test_existing_v2_gates_remain(field: str, value: object, expected: str) -> None:
    """Retain identity, name, confidence, and source decisions after grounding."""
    candidate = adaptive_candidate()
    candidate[field] = value
    assert validate_multispan_v4_candidate(candidate, adaptive_table_job(), 0.8) == (None, expected)


@pytest.mark.parametrize("field", ["name_evidence", "supporting_evidence"])
@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"block_id": "missing"}, "unknown_block"),
        ({"section": "Methods"}, "section_mismatch"),
        ({"quote": "Hiraea fagifolia 0.02 \u0015 0.00"}, "ungrounded_quote"),
    ],
)
def test_every_existing_span_requirement_remains(field: str, updates: dict, reason: str) -> None:
    """Require independently grounded name and supporting spans."""
    candidate = adaptive_candidate()
    span = candidate[field][0] if field == "supporting_evidence" else candidate[field]
    span.update(updates)
    prefix = "supporting_evidence[0]" if field == "supporting_evidence" else field
    assert validate_multispan_v4_candidate(candidate, adaptive_table_job(), 0.8) == (None, f"{prefix}:{reason}")


def test_cross_span_mapping_conflict_rejects_the_later_span() -> None:
    """Detect one control assigned to two glyphs across independent spans."""
    candidate = adaptive_candidate()
    candidate["supporting_evidence"][1]["quote"] = "N \u0015 4."
    job = adaptive_table_job()
    record, reason = validate_multispan_v4_candidate(candidate, job, 0.8)
    assert record is None
    assert reason == "supporting_evidence[1]:conflicting_glyph_mapping"
    audit = candidate_grounding_audit_v4(candidate, job)
    assert audit["all_spans_grounded"] is False
    assert audit["spans"][3]["rejection_reason"] == reason
    assert audit["spans"][3]["conflicting_match_evidence"]["inferred_mapping"][0]["source_character"] == "¼"


def test_mapping_is_candidate_local_and_ignores_literal_controls() -> None:
    """Avoid carrying inferred substitutions into another proposed record."""
    first = adaptive_candidate()
    second = adaptive_candidate()
    second["evidence_quote"] = "Hiraea fagifolia 0.01 ± 0.00"
    second["supporting_evidence"][1]["quote"] = "Means are mean ± SE, N \u0015 4."
    job = adaptive_table_job()
    first_record, first_reason = validate_multispan_v4_candidate(first, job, 0.8)
    second_record, second_reason = validate_multispan_v4_candidate(second, job, 0.8)
    assert first_reason is None and second_reason is None
    assert first_record is not None and second_record is not None
    assert first_record["inferred_glyph_mapping"][0]["source_character"] == "±"
    assert second_record["inferred_glyph_mapping"][0]["source_character"] == "¼"


def test_name_evidence_uses_the_same_grounding_rule() -> None:
    """Include the independently quoted name anchor in candidate mapping checks."""
    candidate = adaptive_candidate()
    candidate["name_evidence"]["quote"] = candidate["evidence_quote"]
    record, reason = validate_multispan_v4_candidate(candidate, adaptive_table_job(), 0.8)
    assert reason is None
    assert record is not None
    assert record["grounded_source_spans"][1]["route"] == "source_anchored_control_glyph"
    assert record["name_evidence"]["quote"] == candidate["name_evidence"]["quote"]


def test_same_block_supporting_name_route_remains() -> None:
    """Preserve the existing pronoun and same-block supporting-name route."""
    candidate = adaptive_candidate()
    candidate["evidence_quote"] = "Immediate rejection"
    candidate["supporting_evidence"][0]["quote"] = "Hiraea fagifolia 0.01 \u0015 0.00"
    record, reason = validate_multispan_v4_candidate(candidate, adaptive_table_job(), 0.8)
    assert reason is None
    assert record is not None
    assert record["plant_name_surface_provenance"]["route"] == "supporting_evidence"
    assert record["plant_name_surface_provenance"]["index"] == 0


def test_exact_record_needs_no_glyph_policy() -> None:
    """Preserve exact-match acceptance when fallback is disabled."""
    candidate = adaptive_candidate()
    candidate["evidence_quote"] = "Hiraea fagifolia 0.01 ± 0.00"
    candidate["supporting_evidence"][1]["quote"] = "Means are mean ± SE, N ¼ 4."
    job = adaptive_table_job()
    del job["glyph_policy"]
    del job["glyph_source_hashes"]
    record, reason = validate_multispan_v4_candidate(candidate, job, 0.8)
    assert reason is None
    assert record is not None
    assert record["quote_grounding_route"] == "exact"
    assert record["inferred_glyph_mapping"] == []


def test_audit_keeps_matches_when_a_later_name_gate_fails() -> None:
    """Expose quote evidence independently of downstream identity decisions."""
    candidate = adaptive_candidate()
    candidate["name_surface_form"] = "Hiraea invented"
    job = adaptive_table_job()
    assert validate_multispan_v4_candidate(candidate, job, 0.8) == (None, "name_surface_not_in_quote")
    audit = candidate_grounding_audit_v4(candidate, job)
    assert audit["all_spans_grounded"] is True
    assert audit["glyph_span_count"] == 2
    assert audit["exact_span_count"] == 2


def test_audit_continues_after_unknown_spans() -> None:
    """Retain each span's route and declared-field rejection prefix."""
    candidate = adaptive_candidate()
    candidate["name_evidence"]["section"] = "wrong"
    candidate["supporting_evidence"][0]["block_id"] = "missing"
    audit = candidate_grounding_audit_v4(candidate, adaptive_table_job())
    assert audit["all_spans_grounded"] is False
    assert audit["spans"][1]["rejection_reason"] == "name_evidence:section_mismatch"
    assert audit["spans"][2]["rejection_reason"] == "supporting_evidence[0]:unknown_block"
    assert audit["spans"][3]["route"] == "source_anchored_control_glyph"


def test_schema_and_source_failures_remain_explicit_in_audit() -> None:
    """Retain required name schema and candidate source binding."""
    candidate = adaptive_candidate()
    del candidate["name_evidence"]
    record, reason = validate_multispan_v4_candidate(candidate, adaptive_table_job(), 0.8)
    assert record is None
    assert reason is not None and reason.startswith("schema:")
    audit = candidate_grounding_audit_v4(candidate, adaptive_table_job())
    assert audit["schema_valid"] is False
    assert audit["all_spans_grounded"] is None
    assert audit["spans"] == []
    candidate = adaptive_candidate()
    candidate["source_id"] = "OTHER"
    audit = candidate_grounding_audit_v4(candidate, adaptive_table_job())
    assert audit["blocked_reason"] == "unknown_source_or_block"
    assert all(entry["route"] == "rejected" for entry in audit["spans"])


def test_audit_span_metadata_matches_the_surviving_record() -> None:
    """Keep the accepted-record audit and independent quote audit consistent."""
    candidate = adaptive_candidate()
    job = adaptive_table_job()
    record, reason = validate_multispan_v4_candidate(candidate, job, 0.8)
    audit = candidate_grounding_audit_v4(candidate, job)
    assert reason is None
    assert record is not None
    assert audit["spans"] == record["grounded_source_spans"]
    assert audit["inferred_mapping"] == record["inferred_glyph_mapping"]
