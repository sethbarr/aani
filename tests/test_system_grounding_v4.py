"""Independent regression checks for the single-quote v4 replay adapter."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from src.common.io import digest
from src.systems.config import SystemConfig, load_system_config
from src.systems.extraction import validate_system_candidate
from src.systems.grounding_v4 import audit_system_candidate_v4, bind_system_job_v4


def source_job(text: str) -> dict:
    """Create an independently hashed source job for a supplied text block.

    Args:
        text: Unmodified source text used in the fixture.

    Returns:
        A single-block system job with a valid original input hash.
    """
    job = {
        "system_slug": "propolis",
        "source_id": "TEST_SOURCE",
        "source_url": "https://example.org/test-source",
        "blocks": [{"block_id": "b00001", "section": "Results", "text": text}],
    }
    job["input_hash"] = digest(job)
    return job


@pytest.fixture
def propolis_config() -> SystemConfig:
    """Load the existing prospective propolis contract.

    Returns:
        The validated repository configuration with reject unavailable.
    """
    root = Path(__file__).resolve().parents[1]
    return load_system_config(root / "config" / "systems" / "propolis.json")


@pytest.fixture
def candidate() -> dict:
    """Provide a complete schema-valid single-quote proposal.

    Returns:
        A propolis observation with an exact target occurrence.
    """
    return {
        "behaving_organism_as_written": "Apis mellifera",
        "target_name_as_written": "Populus nigra",
        "taxonomic_rank": "species",
        "direction": "accept",
        "evidence_type": "observational",
        "quantitative_measure": None,
        "compound_name_as_written": None,
        "activity_target_as_written": None,
        "activity_outcome": "unknown",
        "source_id": "TEST_SOURCE",
        "section": "Results",
        "block_id": "b00001",
        "evidence_quote": "Apis mellifera collected Populus nigra resin at 2 ± 1 units.",
        "extraction_confidence": 0.9,
        "behavioural_choice": True,
        "study_context": "Direct resin-collection observation.",
        "original_source_id": None,
    }


def test_exact_record_keeps_original_identity_and_fields(
    candidate: dict, propolis_config: SystemConfig,
) -> None:
    """Preserve baseline scientific fields and provenance for an exact match."""
    job = source_job(candidate["evidence_quote"])
    bound = bind_system_job_v4(job)
    baseline, reason = validate_system_candidate(candidate, job, propolis_config, 0.8)
    record, audit = audit_system_candidate_v4(candidate, job, bound, propolis_config, 0.8)
    assert reason is None
    assert baseline is not None
    assert record is not None
    assert all(record[key] == value for key, value in baseline.items())
    assert record["record_id"] == digest(candidate)
    assert record["input_hash"] == job["input_hash"]
    assert record["v4_input_hash"] == bound["input_hash"]
    assert record["quote_grounding_route"] == "exact"
    assert audit["baseline_accepted"] is True
    assert audit["v4_accepted"] is True
    assert audit["quote_match"]["replacements"] == []


@pytest.mark.parametrize("glyph", ["±", "¼"])
def test_control_recovery_preserves_original_quote_identity_and_source(
    candidate: dict, propolis_config: SystemConfig, glyph: str,
) -> None:
    """Retain original payloads and raw offsets for an authorized glyph match."""
    cached_quote = f"Apis mellifera collected Populus nigra resin at 2 {glyph} 1 units."
    candidate["evidence_quote"] = cached_quote.replace(glyph, "\u0015")
    source_text = f"Prefix.\n\t{cached_quote}\nSuffix."
    job = source_job(source_text)
    original_job = deepcopy(job)
    original_candidate = deepcopy(candidate)
    bound = bind_system_job_v4(job)
    original_bound = deepcopy(bound)
    record, audit = audit_system_candidate_v4(candidate, job, bound, propolis_config, 0.8)
    assert record is not None
    assert record["record_id"] == digest(original_candidate)
    assert record["evidence_quote"] == original_candidate["evidence_quote"]
    assert record["quote_grounding_route"] == "source_anchored_control_glyph"
    match = record["grounded_source_quote"]
    assert match["emitted_quote"] == candidate["evidence_quote"]
    assert match["matched_source_quote"] == cached_quote
    assert source_text[match["start"]:match["end"]] == cached_quote
    assert match["block_text_sha256"] == sha256(source_text.encode("utf-8")).hexdigest()
    replacement = match["replacements"][0]
    assert candidate["evidence_quote"][replacement["model_offset"]] == "\u0015"
    assert source_text[replacement["source_offset"]] == glyph
    assert audit["baseline_accepted"] is False
    assert audit["baseline_reason"] == "ungrounded_quote"
    assert audit["v4_accepted"] is True
    assert audit["v4_reason"] is None
    assert candidate == original_candidate
    assert job == original_job
    assert bound == original_bound


def test_printable_hyphen_substitution_remains_rejected(
    candidate: dict, propolis_config: SystemConfig,
) -> None:
    """Keep the observed propolis printable-hyphen failure outside v4 policy."""
    candidate["evidence_quote"] = "Apis mellifera collected phenolic\u2011rich Populus nigra resin."
    job = source_job(candidate["evidence_quote"].replace("\u2011", "\u2010"))
    record, audit = audit_system_candidate_v4(
        candidate, job, bind_system_job_v4(job), propolis_config, 0.8,
    )
    assert record is None
    assert audit["baseline_reason"] == "ungrounded_quote"
    assert audit["v4_reason"] == "ungrounded_quote"
    assert audit["quote_match"] is None


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("section", "Discussion", "section_mismatch"),
        ("target_name_as_written", "Pseudonocardia", "target_not_in_quote"),
        ("extraction_confidence", 0.7, "low_confidence"),
        ("direction", "reject", "reject_direction_unavailable"),
    ],
)
@pytest.mark.parametrize("glyph_match", [False, True])
def test_remaining_validator_checks_survive_quote_matching(
    candidate: dict, propolis_config: SystemConfig, field: str, value: str | float,
    reason: str, glyph_match: bool,
) -> None:
    """Separate a successful quote match from later eligibility failures."""
    job = source_job(candidate["evidence_quote"])
    if glyph_match:
        candidate["evidence_quote"] = candidate["evidence_quote"].replace("±", "\u0015")
    candidate[field] = value
    record, audit = audit_system_candidate_v4(
        candidate, job, bind_system_job_v4(job), propolis_config, 0.8,
    )
    assert record is None
    assert audit["quote_reason"] is None
    assert audit["quote_match"] is not None
    assert audit["v4_reason"] == reason
    assert audit["v4_accepted"] is False


def test_ambiguous_glyph_alignment_stays_rejected(
    candidate: dict, propolis_config: SystemConfig,
) -> None:
    """Require one source alignment when a control needs substitution."""
    cached_quote = candidate["evidence_quote"]
    job = source_job(f"{cached_quote} {cached_quote}")
    candidate["evidence_quote"] = cached_quote.replace("±", "\u0015")
    record, audit = audit_system_candidate_v4(
        candidate, job, bind_system_job_v4(job), propolis_config, 0.8,
    )
    assert record is None
    assert audit["v4_reason"] == "ambiguous_glyph_match"


@pytest.mark.parametrize("field", ["source_id", "block_id"])
def test_foreign_source_or_block_never_matches(
    candidate: dict, propolis_config: SystemConfig, field: str,
) -> None:
    """Reject unknown source and block identifiers before matching text."""
    job = source_job(candidate["evidence_quote"])
    candidate[field] = "OTHER"
    record, audit = audit_system_candidate_v4(
        candidate, job, bind_system_job_v4(job), propolis_config, 0.8,
    )
    assert record is None
    assert audit["v4_reason"] == "unknown_source_or_block"
    assert audit["quote_reason"] == "unknown_source_or_block"
    assert audit["quote_match"] is None


def test_stale_original_payload_hash_prevents_binding(candidate: dict) -> None:
    """Reject source edits that retain an approved original payload hash."""
    job = source_job(candidate["evidence_quote"])
    job["blocks"][0]["text"] += " changed"
    with pytest.raises(ValueError) as error:
        bind_system_job_v4(job)
    assert str(error.value) == "original_system_payload_hash_mismatch"


@pytest.mark.parametrize("change", ["source_text", "source_hash", "policy", "input_hash"])
def test_stale_or_modified_v4_binding_is_rejected(
    candidate: dict, propolis_config: SystemConfig, change: str,
) -> None:
    """Prevent a validator job from weakening its original source binding."""
    job = source_job(candidate["evidence_quote"])
    bound = bind_system_job_v4(job)
    if change == "source_text":
        bound["blocks"][0]["text"] += " changed"
    elif change == "source_hash":
        bound["glyph_source_hashes"]["blocks"]["b00001"] = "0" * 64
    elif change == "policy":
        bound["glyph_policy"]["source_glyphs"].append("\u2010")
    else:
        bound["input_hash"] = "0" * 64
    with pytest.raises(ValueError) as error:
        audit_system_candidate_v4(candidate, job, bound, propolis_config, 0.8)
    assert str(error.value) == "v4_job_binding_mismatch"


def test_schema_failure_preserves_original_rejection(
    candidate: dict, propolis_config: SystemConfig,
) -> None:
    """Keep malformed proposals outside the quotation matcher."""
    job = source_job(candidate["evidence_quote"])
    del candidate["study_context"]
    record, audit = audit_system_candidate_v4(
        candidate, job, bind_system_job_v4(job), propolis_config, 0.8,
    )
    assert record is None
    assert audit["baseline_reason"].startswith("schema: ")
    assert audit["v4_reason"] == audit["baseline_reason"]
    assert audit["quote_match"] is None
