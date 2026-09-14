"""Identity-link tests for the opt-in v2 multi-span validator."""

import pytest

from src.common.io import digest
from src.extraction.multispan import MultiSpanObservation
from src.extraction.multispan_v2 import validate_multispan_v2_candidate


def identity_job() -> dict:
    """Build one extraction chunk with an independently resolved source ant."""
    return {
        "source_id": "SOURCE1",
        "source_url": "https://example.org/paper",
        "input_hash": "v2-job",
        "source_ant_identity": {
            "source_id": "SOURCE1",
            "status": "resolved",
            "scientific_name": "Atta colombica",
            "abbreviated_forms": ["A. colombica", "A.colombica"],
            "provenance": {
                "method": "full_binomial_in_block",
                "block_id": "intro",
                "section": "Introduction",
                "evidence_quote": "We studied Atta colombica colonies.",
            },
            "blocked_reason": None,
        },
        "blocks": [
            {
                "block_id": "names",
                "section": "Methods",
                "text": "We offered Hymenaea courbaril and Spondias mombin leaves.",
            },
            {
                "block_id": "results",
                "section": "Results",
                "text": (
                    "A. colombica accepted Spondias mombin. "
                    "Hymenaea courbaril was offered next. "
                    "They rejected its leaves on day two."
                ),
            },
        ],
    }


def identity_candidate(**updates: object) -> dict:
    """Build an exact plant record whose ant name needs source context."""
    candidate = {
        "ant_species": "A. colombica",
        "plant_name_as_written": "Spondias mombin",
        "taxonomic_rank": "species",
        "outcome": "accepted",
        "evidence_type": "field_choice_assay",
        "quantitative_measure": None,
        "source_id": "SOURCE1",
        "section": "Results",
        "block_id": "results",
        "evidence_quote": "A. colombica accepted Spondias mombin.",
        "extraction_confidence": 0.9,
        "substrate_treatment": "natural",
        "rejection_timing": "immediate",
        "behavioural_choice": True,
        "study_context": "natural-leaf choice",
        "original_source_id": None,
        "name_evidence": {
            "block_id": "names",
            "section": "Methods",
            "quote": "We offered Hymenaea courbaril and Spondias mombin leaves.",
        },
        "name_surface_form": "Spondias mombin",
        "name_link": "exact",
        "supporting_evidence": [],
    }
    candidate.update(updates)
    return candidate


def pronoun_candidate() -> dict:
    """Build the same-block supporting-name shape of the Hymenaea record."""
    return identity_candidate(
        plant_name_as_written="Hymenaea courbaril",
        outcome="rejected",
        evidence_quote="They rejected its leaves on day two.",
        name_surface_form="Hymenaea courbaril",
        supporting_evidence=[
            {
                "block_id": "results",
                "section": "Results",
                "quote": "Hymenaea courbaril was offered next.",
            }
        ],
    )


@pytest.mark.parametrize("surface", ["A. colombica", "A.colombica", "Atta colombica"])
def test_source_identity_supplies_ant_context_to_the_chunk(surface: str) -> None:
    """Ground compatible fields without rewriting the emitted ant name."""
    candidate = identity_candidate(ant_species=surface)
    valid, reason = validate_multispan_v2_candidate(candidate, identity_job(), 0.8)
    assert reason is None
    assert valid is not None
    assert valid["ant_species"] == surface
    assert valid["resolved_ant_species"] == "Atta colombica"
    route = "source_identity_full_name" if surface == "Atta colombica" else "source_identity_abbreviation"
    assert valid["ant_identity_route"] == route
    assert valid["ant_identity_provenance"]["block_id"] == "intro"
    assert valid["plant_name_surface_provenance"]["route"] == "primary_quote"
    assert valid["record_id"] == digest(MultiSpanObservation.model_validate(candidate).model_dump())


@pytest.mark.parametrize("surface", ["A. cephalotes", "Atta cephalotes", "Acromyrmex colombica"])
def test_different_ant_identity_is_rejected(surface: str) -> None:
    """Reject wrong epithets and full names from the other eligible genus."""
    valid, reason = validate_multispan_v2_candidate(
        identity_candidate(ant_species=surface), identity_job(), 0.8
    )
    assert valid is None
    assert reason == "ant_identity_mismatch"


@pytest.mark.parametrize("surface", ["Atta", "Solenopsis invicta", "A. colombica invented"])
def test_unsupported_ant_field_still_requires_review(surface: str) -> None:
    """Keep an unsupported or incomplete ant field outside automatic grounding."""
    valid, reason = validate_multispan_v2_candidate(
        identity_candidate(ant_species=surface), identity_job(), 0.8
    )
    assert valid is None
    assert reason == "ant_requires_review"


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"source_id": "OTHER"}, "ant_identity_source_mismatch"),
        ({"status": "blocked", "blocked_reason": "absent"}, "ant_identity_unresolved"),
        ({"status": "blocked", "blocked_reason": "ambiguous"}, "ant_identity_unresolved"),
        ({"scientific_name": None}, "ant_identity_unresolved"),
        ({"scientific_name": "Solenopsis invicta"}, "ant_identity_unresolved"),
        ({"abbreviated_forms": []}, "ant_identity_mismatch"),
    ],
)
def test_source_identity_must_be_resolved_and_source_specific(updates: dict, reason: str) -> None:
    """Reject foreign, unresolved, ambiguous or incompatible identity contexts."""
    job = identity_job()
    job["source_ant_identity"].update(updates)
    valid, actual_reason = validate_multispan_v2_candidate(identity_candidate(), job, 0.8)
    assert valid is None
    assert actual_reason == reason


def test_abbreviation_without_source_identity_is_unresolved() -> None:
    """Require a supplied identity when no record span contains its full name."""
    job = identity_job()
    del job["source_ant_identity"]
    valid, reason = validate_multispan_v2_candidate(identity_candidate(), job, 0.8)
    assert valid is None
    assert reason == "ant_identity_unresolved"


@pytest.mark.parametrize("surface", ["A. colombica", "Atta colombica"])
def test_full_binomial_in_grounded_primary_quote_is_sufficient(surface: str) -> None:
    """Accept a directly quoted identity without source-level resolution."""
    job = identity_job()
    del job["source_ant_identity"]
    quote = "Atta colombica accepted Spondias mombin."
    job["blocks"][1]["text"] = quote
    candidate = identity_candidate(ant_species=surface, evidence_quote=quote)
    valid, reason = validate_multispan_v2_candidate(candidate, job, 0.8)
    assert reason is None
    assert valid is not None
    assert valid["ant_identity_route"] == "full_binomial_in_quote"
    assert valid["ant_identity_provenance"]["route"] == "primary_quote"
    assert valid["ant_identity_provenance"]["evidence_quote"] == quote


def test_full_binomial_in_grounded_supporting_quote_is_sufficient() -> None:
    """Record which additional span supplied the direct ant identity."""
    job = identity_job()
    del job["source_ant_identity"]
    quote = "Atta colombica colonies were observed."
    job["blocks"][0]["text"] += " " + quote
    candidate = identity_candidate(
        supporting_evidence=[{"block_id": "names", "section": "Methods", "quote": quote}]
    )
    valid, reason = validate_multispan_v2_candidate(candidate, job, 0.8)
    assert reason is None
    assert valid is not None
    assert valid["ant_identity_route"] == "full_binomial_in_quote"
    assert valid["ant_identity_provenance"]["route"] == "supporting_evidence"
    assert valid["ant_identity_provenance"]["index"] == 0


def test_same_block_support_can_supply_plant_surface_for_pronoun() -> None:
    """Keep the pronoun quote and record the same-block supporting name span."""
    candidate = pronoun_candidate()
    valid, reason = validate_multispan_v2_candidate(candidate, identity_job(), 0.8)
    assert reason is None
    assert valid is not None
    assert valid["evidence_quote"] == candidate["evidence_quote"]
    assert valid["supporting_evidence"] == candidate["supporting_evidence"]
    assert valid["record_id"] == digest(MultiSpanObservation.model_validate(candidate).model_dump())
    assert valid["plant_name_surface_provenance"] == {
        "route": "supporting_evidence",
        "index": 0,
        "block_id": "results",
        "section": "Results",
        "evidence_quote": "Hymenaea courbaril was offered next.",
    }
    assert valid["ant_identity_route"] == "source_identity_abbreviation"


def test_other_block_support_cannot_supply_plant_surface_for_pronoun() -> None:
    """Keep the same-block restriction on the plant-name fallback."""
    candidate = pronoun_candidate()
    candidate["supporting_evidence"] = [candidate["name_evidence"]]
    valid, reason = validate_multispan_v2_candidate(candidate, identity_job(), 0.8)
    assert valid is None
    assert reason == "name_surface_not_in_quote"


def test_supporting_surface_retains_existing_lexical_check() -> None:
    """Reject an incorrect name-link declaration even in a matching support span."""
    candidate = pronoun_candidate()
    candidate["name_link"] = "abbreviated_binomial"
    valid, reason = validate_multispan_v2_candidate(candidate, identity_job(), 0.8)
    assert valid is None
    assert reason == "invalid_abbreviated_binomial_link"


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"block_id": "unseen"}, "unknown_block"),
        ({"section": "Methods"}, "section_mismatch"),
        ({"quote": "Hymenaea courbaril was rejected."}, "ungrounded_quote"),
    ],
)
def test_supporting_span_must_ground_before_name_fallback(updates: dict, reason: str) -> None:
    """Reject invalid supporting spans before using their plant name."""
    candidate = pronoun_candidate()
    candidate["supporting_evidence"][0].update(updates)
    valid, actual_reason = validate_multispan_v2_candidate(candidate, identity_job(), 0.8)
    assert valid is None
    assert actual_reason == f"supporting_evidence[0]:{reason}"


@pytest.mark.parametrize("field", ["name_evidence", "supporting_evidence", "name_surface_form"])
def test_required_multispan_fields_are_unchanged(field: str) -> None:
    """Retain each existing required schema field in the v2 validator."""
    candidate = identity_candidate()
    del candidate[field]
    valid, reason = validate_multispan_v2_candidate(candidate, identity_job(), 0.8)
    assert valid is None
    assert reason is not None and reason.startswith("schema:")


def test_source_identity_cannot_bypass_confidence_threshold() -> None:
    """Retain the existing minimum-confidence check after identity grounding."""
    valid, reason = validate_multispan_v2_candidate(
        identity_candidate(extraction_confidence=0.79), identity_job(), 0.8
    )
    assert valid is None
    assert reason == "low_confidence"


def test_source_identity_cannot_bypass_exact_primary_quote() -> None:
    """Retain exact quote matching independently of ant resolution."""
    valid, reason = validate_multispan_v2_candidate(
        identity_candidate(evidence_quote="A. colombica rejected Spondias mombin."),
        identity_job(),
        0.8,
    )
    assert valid is None
    assert reason == "ungrounded_quote"
