"""Source-grounding tests for the optional multi-span observation contract."""

import pytest

from src.common.io import digest
from src.extraction.multispan import (
    MultiSpanExtraction,
    MultiSpanObservation,
    validate_multispan_candidate,
)


def multispan_job() -> dict:
    """Return a source with independent prose, name and table blocks."""
    return {
        "source_id": "SOURCE1",
        "source_url": "https://example.org/paper",
        "input_hash": "multispan-input",
        "blocks": [
            {
                "block_id": "names",
                "section": "Methods",
                "text": "Plants tested included Cecropia peltata and Inga marginata.",
            },
            {
                "block_id": "prose",
                "section": "Results",
                "text": "Atta colombica rejected C. peltata after contact. Inga was accepted.",
            },
            {
                "block_id": "table",
                "section": "Table 1",
                "text": "Plant  Removed leaves\nCecropia peltata  0\nInga marginata  8",
            },
            {
                "block_id": "caption",
                "section": "Table 1 caption",
                "text": "Zero removed leaves indicates rejection after contact.",
            },
        ],
    }


def multispan_record(**updates: object) -> dict:
    """Return a supported abbreviation record with optional field overrides."""
    record = {
        "ant_species": "Atta colombica",
        "plant_name_as_written": "Cecropia peltata",
        "taxonomic_rank": "species",
        "outcome": "rejected",
        "evidence_type": "field_choice_assay",
        "quantitative_measure": None,
        "source_id": "SOURCE1",
        "section": "Results",
        "block_id": "prose",
        "evidence_quote": "Atta colombica rejected C. peltata after contact.",
        "extraction_confidence": 0.9,
        "substrate_treatment": "natural",
        "rejection_timing": "immediate",
        "behavioural_choice": True,
        "study_context": "contact choice",
        "original_source_id": None,
        "name_evidence": {
            "block_id": "names",
            "section": "Methods",
            "quote": "Plants tested included Cecropia peltata and Inga marginata.",
        },
        "name_surface_form": "C. peltata",
        "name_link": "abbreviated_binomial",
        "supporting_evidence": [],
    }
    record.update(updates)
    return record


def test_abbreviation_uses_independent_full_name_anchor() -> None:
    """Ground the abbreviation and preserve all original schema fields."""
    candidate = multispan_record()
    valid, reason = validate_multispan_candidate(candidate, multispan_job(), 0.8)
    assert reason is None
    assert valid is not None
    assert valid["record_id"] == digest(MultiSpanObservation.model_validate(candidate).model_dump())
    assert valid["name_evidence"] == candidate["name_evidence"]
    assert valid["source_url"] == "https://example.org/paper"
    assert valid["input_hash"] == "multispan-input"
    assert valid["grounding_review_reasons"] == ["direction_semantics"]


def test_table_row_keeps_heading_and_caption_as_independent_spans() -> None:
    """Ground a row and its context without stitching a composite quotation."""
    candidate = multispan_record(
        section="Table 1",
        block_id="table",
        evidence_quote="Cecropia peltata  0",
        name_surface_form="Cecropia peltata",
        name_link="exact",
        quantitative_measure="0",
        supporting_evidence=[
            {"block_id": "table", "section": "Table 1", "quote": "Plant  Removed leaves"},
            {
                "block_id": "caption",
                "section": "Table 1 caption",
                "quote": "Zero removed leaves indicates rejection after contact.",
            },
        ],
    )
    valid, reason = validate_multispan_candidate(candidate, multispan_job(), 0.8)
    assert reason is None
    assert valid is not None
    assert valid["evidence_quote"] == "Cecropia peltata  0"
    assert len(valid["supporting_evidence"]) == 2
    assert valid["grounding_review_required"] is True


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"source_id": "OTHER"}, "unknown_source_or_block"),
        ({"block_id": "unknown"}, "unknown_source_or_block"),
        ({"section": "Methods"}, "section_mismatch"),
        ({"evidence_quote": "Atta colombica accepted C. peltata"}, "ungrounded_quote"),
        ({"evidence_quote": "Atta colombica ... C. peltata"}, "ungrounded_quote"),
        ({"evidence_quote": "  "}, "ungrounded_quote"),
        ({"name_surface_form": "C. pelta"}, "name_surface_not_in_quote"),
        ({"name_surface_form": "Atta colombica"}, "invalid_abbreviated_binomial_link"),
        ({"plant_name_as_written": "Cecropia pelta"}, "plant_not_in_name_evidence"),
        ({"plant_name_as_written": "Trema micrantha"}, "plant_not_in_name_evidence"),
        ({"name_link": "exact"}, "invalid_exact_name_link"),
        ({"name_link": "genus_reference"}, "invalid_genus_reference_link"),
        ({"ant_species": "Atta"}, "ant_requires_review"),
        ({"ant_species": "Solenopsis invicta"}, "ant_requires_review"),
        ({"extraction_confidence": 0.79}, "low_confidence"),
    ],
)
def test_invalid_observation_is_rejected(updates: dict, reason: str) -> None:
    """Reject altered quotations, unsupported names and existing v1 exclusions."""
    valid, actual_reason = validate_multispan_candidate(
        multispan_record(**updates), multispan_job(), 0.8
    )
    assert valid is None
    assert actual_reason == reason


@pytest.mark.parametrize("field", ["name_evidence", "supporting_evidence"])
@pytest.mark.parametrize(
    ("span", "reason"),
    [
        (
            {"block_id": "other-job", "section": "Methods", "quote": "Cecropia peltata"},
            "unknown_block",
        ),
        (
            {"block_id": "names", "section": "Results", "quote": "Cecropia peltata"},
            "section_mismatch",
        ),
        (
            {"block_id": "names", "section": "Methods", "quote": "Cecropia peltata rejected"},
            "ungrounded_quote",
        ),
        (
            {"block_id": "names", "section": "Methods", "quote": "  "},
            "ungrounded_quote",
        ),
    ],
)
def test_each_extra_span_requires_its_own_grounding(
    field: str, span: dict, reason: str
) -> None:
    """Reject invalid extra spans even when the primary quote is exact."""
    update = {field: [span] if field == "supporting_evidence" else span}
    valid, actual_reason = validate_multispan_candidate(
        multispan_record(**update), multispan_job(), 0.8
    )
    prefix = "supporting_evidence[0]" if field == "supporting_evidence" else "name_evidence"
    assert valid is None
    assert actual_reason == f"{prefix}:{reason}"


def test_anchor_requires_full_name_even_when_primary_abbreviation_matches() -> None:
    """An abbreviation alone cannot establish the claimed full plant name."""
    candidate = multispan_record(
        name_evidence={
            "block_id": "prose",
            "section": "Results",
            "quote": "Atta colombica rejected C. peltata after contact.",
        }
    )
    valid, reason = validate_multispan_candidate(candidate, multispan_job(), 0.8)
    assert valid is None
    assert reason == "plant_not_in_name_evidence"


@pytest.mark.parametrize("name_link", ["exact", "abbreviated_binomial", "genus_reference"])
def test_abbreviated_genus_cannot_anchor_itself(name_link: str) -> None:
    """Require an unabbreviated genus for a species record under every link type."""
    job = multispan_job()
    job["blocks"][0]["text"] = "S. lindenianum was tested."
    job["blocks"][1]["text"] = "Atta colombica accepted S. lindenianum."
    candidate = multispan_record(
        plant_name_as_written="S. lindenianum",
        evidence_quote=job["blocks"][1]["text"],
        name_evidence={
            "block_id": "names",
            "section": "Methods",
            "quote": job["blocks"][0]["text"],
        },
        name_surface_form="S." if name_link == "genus_reference" else "S. lindenianum",
        name_link=name_link,
        outcome="accepted",
    )
    valid, reason = validate_multispan_candidate(candidate, job, 0.8)
    assert valid is None
    assert reason == "unabbreviated_genus_required"


@pytest.mark.parametrize(
    ("name_link", "surface"),
    [
        ("exact", "Spondias lindenianum"),
        ("abbreviated_binomial", "S. lindenianum"),
        ("abbreviated_binomial", "S.lindenianum"),
    ],
)
def test_full_name_anchor_preserves_supported_surface_forms(name_link: str, surface: str) -> None:
    """Retain exact and spaced or compact abbreviation links to a complete name."""
    job = multispan_job()
    job["blocks"][0]["text"] = "Spondias lindenianum was tested."
    job["blocks"][1]["text"] = f"Atta colombica accepted {surface}."
    candidate = multispan_record(
        plant_name_as_written="Spondias lindenianum",
        evidence_quote=job["blocks"][1]["text"],
        name_evidence={
            "block_id": "names",
            "section": "Methods",
            "quote": job["blocks"][0]["text"],
        },
        name_surface_form=surface,
        name_link=name_link,
        outcome="accepted",
    )
    valid, reason = validate_multispan_candidate(candidate, job, 0.8)
    assert reason is None
    assert valid is not None
    assert valid["name_surface_form"] == surface
    assert valid["plant_name_as_written"] == "Spondias lindenianum"


def test_genus_link_keeps_explicit_species_link_review() -> None:
    """A genus mention can pass lexical grounding while retaining semantic review."""
    candidate = multispan_record(
        plant_name_as_written="Inga marginata",
        evidence_quote="Inga was accepted.",
        name_surface_form="Inga",
        name_link="genus_reference",
        outcome="accepted",
    )
    valid, reason = validate_multispan_candidate(candidate, multispan_job(), 0.8)
    assert reason is None
    assert valid is not None
    assert valid["grounding_review_required"] is True
    assert "genus_reference_species_link" in valid["grounding_review_reasons"]


def test_control_glyph_must_be_preserved_in_quote() -> None:
    """Refuse repaired source glyphs while allowing an exact original quote."""
    job = multispan_job()
    job["blocks"][1]["text"] = "Atta colombica rejected\u0003 C. peltata after contact."
    valid, reason = validate_multispan_candidate(multispan_record(), job, 0.8)
    assert valid is None
    assert reason == "ungrounded_quote"
    exact = multispan_record(evidence_quote=job["blocks"][1]["text"])
    valid, reason = validate_multispan_candidate(exact, job, 0.8)
    assert reason is None
    assert valid is not None
    assert "\u0003" in valid["evidence_quote"]


def test_whitespace_normalization_keeps_record_text_unchanged() -> None:
    """Apply the existing whitespace rule without rewriting stored evidence."""
    candidate = multispan_record(evidence_quote="Atta colombica\nrejected C. peltata after contact.")
    valid, reason = validate_multispan_candidate(candidate, multispan_job(), 0.8)
    assert reason is None
    assert valid is not None
    assert valid["evidence_quote"] == candidate["evidence_quote"]


def test_schema_rejects_missing_name_anchor_and_unknown_links() -> None:
    """Require explicit anchors and the declared lexical link vocabulary."""
    candidate = multispan_record()
    del candidate["name_evidence"]
    valid, reason = validate_multispan_candidate(candidate, multispan_job(), 0.8)
    assert valid is None
    assert reason is not None and reason.startswith("schema:")
    valid, reason = validate_multispan_candidate(
        multispan_record(name_link="inferred"), multispan_job(), 0.8
    )
    assert valid is None
    assert reason is not None and reason.startswith("schema:")
    assert MultiSpanExtraction.model_validate({"records": []}).records == []
