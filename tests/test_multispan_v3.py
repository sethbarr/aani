"""V3 wrapper checks preserving the v2 extraction schema and other gates."""

import copy

import pytest

from src.common.io import digest
from src.extraction.multispan import MultiSpanObservation
from src.extraction.multispan_v2 import validate_multispan_v2_candidate
from src.extraction.multispan_v3 import candidate_grounding_audit, validate_multispan_v3_candidate
from tests.test_glyph_grounding import glyph_job


def table_job() -> dict:
    """Create an identity-grounded test source with independently quoted spans."""
    job = glyph_job(
        "Immediate rejection\nHiraea fagifolia 0.01 ± 0.00\n"
        "Means are mean ± SE, N ¼ 4.\nPlants included Hiraea fagifolia."
    )
    job.update(
        {
            "source_url": "https://example.org/paper",
            "input_hash": "v3-test-job",
            "source_ant_identity": {
                "source_id": "SAVERSCHEK2010",
                "status": "resolved",
                "scientific_name": "Atta colombica",
                "abbreviated_forms": ["A. colombica"],
                "provenance": {"method": "full_binomial_in_block", "block_id": "b00000"},
            },
        }
    )
    return job


def table_candidate() -> dict:
    """Create one unchanged-schema proposal with observed glyph substitutions."""
    return {
        "ant_species": "A. colombica",
        "plant_name_as_written": "Hiraea fagifolia",
        "taxonomic_rank": "species",
        "outcome": "rejected",
        "evidence_type": "field_choice_assay",
        "quantitative_measure": "0.01 \u0001 0.00",
        "source_id": "SAVERSCHEK2010",
        "section": "Results",
        "block_id": "b00005",
        "evidence_quote": "Hiraea fagifolia 0.01 \u0001 0.00",
        "extraction_confidence": 0.9,
        "substrate_treatment": "natural",
        "rejection_timing": "immediate",
        "behavioural_choice": True,
        "study_context": "natural-leaf choice",
        "original_source_id": None,
        "name_evidence": {
            "block_id": "b00005",
            "section": "Results",
            "quote": "Plants included Hiraea fagifolia.",
        },
        "name_surface_form": "Hiraea fagifolia",
        "name_link": "exact",
        "supporting_evidence": [
            {
                "block_id": "b00005",
                "section": "Results",
                "quote": "Immediate rejection",
            },
            {
                "block_id": "b00005",
                "section": "Results",
                "quote": "Means are mean \u0001 SE, N \u0003 4.",
            },
        ],
    }


def test_v3_recovers_only_quote_comparison_and_preserves_every_raw_schema_field() -> None:
    """Keep emitted controls, source-ant route and original record digest."""
    candidate = table_candidate()
    original = copy.deepcopy(candidate)
    v2_record, v2_reason = validate_multispan_v2_candidate(candidate, table_job(), 0.8)
    assert v2_record is None
    assert v2_reason == "ungrounded_quote"
    record, reason = validate_multispan_v3_candidate(candidate, table_job(), 0.8)
    assert reason is None
    assert record is not None
    assert candidate == original
    schema_fields = MultiSpanObservation.model_validate(candidate).model_dump()
    assert {field: record[field] for field in schema_fields} == schema_fields
    assert record["record_id"] == digest(schema_fields)
    assert record["ant_identity_route"] == "source_identity_abbreviation"
    assert record["quote_grounding_route"] == "bounded_glyph_equivalence"
    assert record["grounding_metadata_quote_representation"] == "matched_source_text"
    assert record["plant_name_surface_provenance"]["evidence_quote"] == (
        "Hiraea fagifolia 0.01 ± 0.00"
    )
    assert [(span["field"], span["index"], span["route"]) for span in record["grounded_source_spans"]] == [
        ("evidence_quote", None, "bounded_glyph_equivalence"),
        ("name_evidence", None, "exact"),
        ("supporting_evidence", 0, "exact"),
        ("supporting_evidence", 1, "bounded_glyph_equivalence"),
    ]


def test_name_evidence_can_use_the_same_bounded_quote_comparison() -> None:
    """Ground every existing quote field with individually logged evidence."""
    candidate = table_candidate()
    candidate["name_evidence"]["quote"] = candidate["evidence_quote"]
    record, reason = validate_multispan_v3_candidate(candidate, table_job(), 0.8)
    assert reason is None
    assert record is not None
    name_span = record["grounded_source_spans"][1]
    assert name_span["field"] == "name_evidence"
    assert name_span["route"] == "bounded_glyph_equivalence"
    assert record["name_evidence"]["quote"] == candidate["name_evidence"]["quote"]


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("ant_species", "A. cephalotes", "ant_identity_mismatch"),
        ("name_surface_form", "Hiraea invented", "name_surface_not_in_quote"),
        ("plant_name_as_written", "Hiraea invented", "plant_not_in_name_evidence"),
        ("extraction_confidence", 0.79, "low_confidence"),
        ("source_id", "OTHER", "unknown_source_or_block"),
        ("block_id", "b00006", "unknown_source_or_block"),
        ("section", "Methods", "section_mismatch"),
    ],
)
def test_existing_v2_identity_name_confidence_and_source_gates_remain(
    field: str, value: object, reason: str
) -> None:
    """Leave all non-glyph eligibility and source checks unchanged."""
    candidate = table_candidate()
    candidate[field] = value
    record, actual = validate_multispan_v3_candidate(candidate, table_job(), 0.8)
    assert record is None
    assert actual == reason


@pytest.mark.parametrize("field", ["name_evidence", "supporting_evidence"])
@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"block_id": "unknown"}, "unknown_block"),
        ({"section": "Methods"}, "section_mismatch"),
        ({"quote": "Hiraea fagifolia 0.02 \u0001 0.00"}, "ungrounded_quote"),
    ],
)
def test_every_span_must_pass_all_existing_requirements(
    field: str, updates: dict, reason: str
) -> None:
    """Retain independent grounding for required name and supporting spans."""
    candidate = table_candidate()
    span = candidate[field][0] if field == "supporting_evidence" else candidate[field]
    span.update(updates)
    record, actual = validate_multispan_v3_candidate(candidate, table_job(), 0.8)
    prefix = "supporting_evidence[0]" if field == "supporting_evidence" else field
    assert record is None
    assert actual == f"{prefix}:{reason}"


def test_missing_name_evidence_remains_a_schema_failure() -> None:
    """Keep the independent-name-span schema requirement unchanged."""
    candidate = table_candidate()
    del candidate["name_evidence"]
    record, reason = validate_multispan_v3_candidate(candidate, table_job(), 0.8)
    assert record is None
    assert reason is not None
    assert reason.startswith("schema:")


def test_same_block_supporting_name_route_from_v2_is_preserved() -> None:
    """Allow the v2 pronoun route using an individually matched support span."""
    candidate = table_candidate()
    candidate["evidence_quote"] = "Immediate rejection"
    candidate["supporting_evidence"][0]["quote"] = "Hiraea fagifolia 0.01 \u0001 0.00"
    record, reason = validate_multispan_v3_candidate(candidate, table_job(), 0.8)
    assert reason is None
    assert record is not None
    assert record["plant_name_surface_provenance"]["route"] == "supporting_evidence"
    assert record["plant_name_surface_provenance"]["index"] == 0
    assert record["evidence_quote"] == "Immediate rejection"


def test_exact_record_works_without_a_glyph_policy() -> None:
    """Preserve v2 exact matching when the opt-in policy is unavailable."""
    candidate = table_candidate()
    candidate["evidence_quote"] = "Hiraea fagifolia 0.01 ± 0.00"
    candidate["supporting_evidence"][1]["quote"] = "Means are mean ± SE, N ¼ 4."
    job = table_job()
    del job["glyph_policy"]
    record, reason = validate_multispan_v3_candidate(candidate, job, 0.8)
    assert reason is None
    assert record is not None
    assert record["quote_grounding_route"] == "exact"
    assert all(span["replacements"] == [] for span in record["grounded_source_spans"])


def test_audit_preserves_glyph_routes_for_a_later_name_gate_failure() -> None:
    """Expose all quote comparisons when the record fails a separate v2 check."""
    candidate = table_candidate()
    candidate["name_surface_form"] = "Hiraea invented"
    original = copy.deepcopy(candidate)
    job = table_job()
    original_job = copy.deepcopy(job)
    record, reason = validate_multispan_v3_candidate(candidate, job, 0.8)
    audit = candidate_grounding_audit(candidate, job)
    assert record is None
    assert reason == "name_surface_not_in_quote"
    assert audit["schema_valid"] is True
    assert audit["schema_error"] is None
    assert audit["blocked_reason"] is None
    assert audit["all_spans_grounded"] is True
    assert audit["exact_span_count"] == 2
    assert audit["glyph_span_count"] == 2
    assert len(audit["spans"]) == 4
    assert audit["spans"][0]["replacements"][0]["model_codepoint"] == "U+0001"
    assert candidate == original
    assert job == original_job


def test_audit_reports_each_failed_span_and_continues_to_later_matches() -> None:
    """Record independent rejection reasons without hiding later glyph matches."""
    candidate = table_candidate()
    candidate["name_evidence"]["section"] = "wrong"
    candidate["supporting_evidence"][0]["block_id"] = "missing"
    audit = candidate_grounding_audit(candidate, table_job())
    assert audit["all_spans_grounded"] is False
    assert audit["glyph_span_count"] == 2
    assert audit["exact_span_count"] == 0
    assert audit["spans"][1]["rejection_reason"] == "name_evidence:section_mismatch"
    assert audit["spans"][2]["rejection_reason"] == "supporting_evidence[0]:unknown_block"
    assert audit["spans"][3]["route"] == "bounded_glyph_equivalence"


def test_audit_rejects_every_span_for_a_foreign_candidate_source() -> None:
    """Keep source-identity failure explicit even when source text matches."""
    candidate = table_candidate()
    candidate["source_id"] = "OTHER"
    audit = candidate_grounding_audit(candidate, table_job())
    assert audit["blocked_reason"] == "unknown_source_or_block"
    assert audit["all_spans_grounded"] is False
    assert audit["glyph_span_count"] == 0
    assert audit["exact_span_count"] == 0
    assert len(audit["spans"]) == 4
    assert all(entry["route"] == "rejected" for entry in audit["spans"])


def test_audit_reports_schema_errors_without_claiming_empty_span_success() -> None:
    """Keep malformed schema candidates explicitly unscorable by this helper."""
    candidate = table_candidate()
    del candidate["name_evidence"]
    audit = candidate_grounding_audit(candidate, table_job())
    assert audit["schema_valid"] is False
    assert "name_evidence" in audit["schema_error"]
    assert audit["blocked_reason"] == "schema_error"
    assert audit["all_spans_grounded"] is None
    assert audit["spans"] == []


def test_audit_span_metadata_equals_the_surviving_record_metadata() -> None:
    """Use one comparison implementation for audit and accepted record routes."""
    candidate = table_candidate()
    job = table_job()
    record, reason = validate_multispan_v3_candidate(candidate, job, 0.8)
    audit = candidate_grounding_audit(candidate, job)
    assert reason is None
    assert record is not None
    assert audit["spans"] == record["grounded_source_spans"]
