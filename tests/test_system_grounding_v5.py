"""System-adapter checks for printable quote and section substitutions."""

from pathlib import Path

from src.common.io import digest
from src.systems.config import SystemConfig, load_system_config
from src.systems.grounding_v5 import audit_system_candidate_v5, bind_system_job_v5


def source_job(text: str, section: str) -> dict:
    """Create one original system job with its approved payload hash."""
    job = {
        "system_slug": "propolis",
        "source_id": "TEST_SOURCE",
        "source_url": "https://example.org/test-source",
        "blocks": [{"block_id": "b1", "section": section, "text": text}],
    }
    job["input_hash"] = digest(job)
    return job


def candidate(quote: str, section: str) -> dict:
    """Create a schema-valid propolis proposal."""
    return {
        "behaving_organism_as_written": "Apis mellifera",
        "target_name_as_written": "Populus nigra",
        "taxonomic_rank": "species",
        "direction": "accept",
        "evidence_type": "review_secondary",
        "quantitative_measure": None,
        "compound_name_as_written": None,
        "activity_target_as_written": None,
        "activity_outcome": "unknown",
        "source_id": "TEST_SOURCE",
        "section": section,
        "block_id": "b1",
        "evidence_quote": quote,
        "extraction_confidence": 0.9,
        "behavioural_choice": True,
        "study_context": "Secondary resin-source statement.",
        "original_source_id": None,
    }


def propolis_config() -> SystemConfig:
    """Load the saved propolis semantics."""
    root = Path(__file__).resolve().parents[1]
    return load_system_config(root / "config/systems/propolis.json")


def test_printable_quote_and_section_pass_with_complete_logs() -> None:
    """Recover the observed propolis failure while preserving candidate identity."""
    cached_quote = "Apis mellifera used phenolic‐rich Populus nigra resin."
    emitted_quote = cached_quote.replace("‐", "‑")
    cached_section = "Origin‐ and Species‐Specific"
    emitted_section = cached_section.replace("‐", "‑")
    job = source_job(cached_quote, cached_section)
    proposal = candidate(emitted_quote, emitted_section)
    record, audit = audit_system_candidate_v5(
        proposal, job, bind_system_job_v5(job), propolis_config(), 0.8,
    )
    assert record is not None
    assert audit["v4_accepted"] is False
    assert audit["v5_accepted"] is True
    assert record["record_id"] == digest(proposal)
    assert record["evidence_quote"] == emitted_quote
    assert record["section"] == emitted_section
    assert record["quote_grounding_route"] == "source_anchored_printable_confusable"
    assert audit["quote_match"]["replacements"][0]["model_codepoint"] == "U+2011"
    assert audit["section_match"]["replacements"][0]["source_codepoint"] == "U+2010"


def test_quote_and_section_mapping_conflict_rejects() -> None:
    """Reject one emitted hyphen that maps to two cached hyphens in a record."""
    cached_quote = "Apis mellifera used phenolic‒rich Populus nigra resin."
    emitted_quote = cached_quote.replace("‒", "‑")
    cached_section = "Origin‐ specific"
    emitted_section = cached_section.replace("‐", "‑")
    job = source_job(cached_quote, cached_section)
    proposal = candidate(emitted_quote, emitted_section)
    record, audit = audit_system_candidate_v5(
        proposal, job, bind_system_job_v5(job), propolis_config(), 0.8,
    )
    assert record is None
    assert audit["v5_reason"] == "conflicting_glyph_mapping"
