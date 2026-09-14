"""Protect source-specific recall and exact semantic-field grounding."""

from copy import deepcopy

import pytest

from src.systems.control_review import (
    apply_adjudications,
    reference_components,
    score_reference_set,
)


def record(source: str = "PMC2748230", **changes: object) -> dict:
    """Create a complete producer-compound-activity observation."""
    return {
        "record_id": "record",
        "source_id": source,
        "input_hash": "oh",
        "block_id": "b1",
        "section": "Results",
        "behaving_organism_as_written": "Apterostigma dentigerum",
        "target_name_as_written": "Pseudonocardia",
        "taxonomic_rank": "genus",
        "compound_name_as_written": "dentigerumycin",
        "activity_target_as_written": "Escovopsis",
        "activity_outcome": "suppresses",
        "direction": "accept",
        "behavioural_choice": False,
        "evidence_type": "compound_activity_assay",
        "evidence_role": "direct_primary",
        "evidence_quote": "Pseudonocardia from Apterostigma dentigerum produces dentigerumycin that inhibits Escovopsis.",
        **changes,
    }


def judgment(**changes: object) -> dict:
    """Return an explicit relation review for the complete fixture."""
    return {
        "decision": "include",
        "reason_codes": [],
        "evidence_role": "direct_primary",
        "host_identity_grounding": "quote",
        "producer_relation_supported": True,
        "compound_relation_supported": True,
        "activity_relation_supported": True,
        "direction_supported": True,
        "note": "The quote states the complete relation.",
        **changes,
    }


def jobs_for(row: dict) -> dict:
    """Ground a fixture in a selected source block."""
    return {
        row["input_hash"]: {
            "input_hash": row["input_hash"],
            "source_id": row["source_id"],
            "chunk_index": 0,
            "chunk_count": 1,
            "blocks": [{"block_id": "b1", "section": "Results", "text": row["evidence_quote"]}],
        }
    }


def reference_set() -> dict:
    """Keep both prospectively fixed reference identities in every recall test."""
    return {
        "scoring": {"recall_denominator": 2},
        "reference_items": [
            {
                "reference_id": "currie",
                "doi": "10.1038/19519",
                "producer_as_written": "Streptomyces",
                "compound_as_written": "antibiotics",
                "activity_target_as_written": "Escovopsis",
            },
            {
                "reference_id": "oh",
                "doi": "10.1038/nchembio.159",
                "producer_as_written": "Pseudonocardia spp.",
                "compound_as_written": "dentigerumycin",
                "activity_target_as_written": "Escovopsis sp.",
            },
        ],
    }


def exposure() -> tuple[dict, list[dict]]:
    """Expose both full reference sources with completed jobs."""
    jobs = {
        "currie": {
            "input_hash": "currie",
            "source_id": "CURRIE1999",
            "chunk_index": 0,
            "chunk_count": 1,
        },
        "oh": {"input_hash": "oh", "source_id": "PMC2748230", "chunk_index": 0, "chunk_count": 1},
    }
    return jobs, [{"input_hash": key, "status": "complete"} for key in jobs]


def test_activity_field_requires_same_quote_even_when_review_approves() -> None:
    """Grounded producer mentions cannot validate an absent activity target."""
    row = record(
        evidence_quote="Pseudonocardia from Apterostigma dentigerum produces dentigerumycin."
    )
    with pytest.raises(ValueError, match="activity_target_not_in_quote"):
        apply_adjudications([row], jobs_for(row), {"record": judgment()})


def test_analog_identity_requires_explicit_relation_review() -> None:
    """A parent compound substring in an analog name cannot override adjudication."""
    row = record(
        evidence_quote="Pseudonocardia from Apterostigma dentigerum produces dentigerumycin F that inhibits Escovopsis."
    )
    reviewed = judgment(
        decision="exclude",
        compound_relation_supported=False,
        reason_codes=["compound_identity_overstated"],
    )
    retained, decisions = apply_adjudications([row], jobs_for(row), {"record": reviewed})
    assert retained == []
    assert "compound_relation_unsupported" in decisions[0]["checks"]["issues"]


def test_source_block_host_identity_is_explicit_and_verified() -> None:
    """A broader host identity must actually occur in the cited source block."""
    row = record(behaving_organism_as_written="fungus-growing ants")
    review = judgment(host_identity_grounding="same_source_block")
    jobs = jobs_for(row)
    with pytest.raises(ValueError, match="host_not_in_source_block"):
        apply_adjudications([row], jobs, {"record": review})
    jobs["oh"]["blocks"][0]["text"] = "These are fungus-growing ants. " + row["evidence_quote"]
    retained, _ = apply_adjudications([row], jobs, {"record": review})
    assert retained[0]["host_identity_grounding"] == "same_source_block"


def test_historical_producer_and_all_raw_fields_remain_unchanged() -> None:
    """The review cannot replace historical Streptomyces with an inferred genus."""
    row = record(
        "CURRIE1999",
        target_name_as_written="Streptomyces",
        compound_name_as_written="antibiotics",
        evidence_quote="Streptomyces from Apterostigma dentigerum produces antibiotics that inhibit Escovopsis.",
    )
    original = deepcopy(row)
    retained, _ = apply_adjudications([row], jobs_for(row), {"record": judgment()})
    assert row == original
    assert {key: retained[0][key] for key in original} == original
    assert retained[0]["taxonomy_query_name"] == "Streptomyces"


def test_empty_currie_and_recovered_oh_keep_two_item_denominator() -> None:
    """An empty completed reference response is measured as a recall miss."""
    jobs, statuses = exposure()
    row = record()
    result = score_reference_set(
        reference_set(), [row], [row], [], jobs, statuses, {"currie": 0, "oh": 1}
    )
    assert result["status"] == "complete"
    assert result["fixed_reference_denominator"] == 2
    assert result["reference_recall"] == 0.5
    assert result["items"][0]["outcome"] == "empty_model_output"
    assert result["historical_taxonomy_annotation"]["taxonomy_query_changed"] is False


def test_secondary_complete_match_never_rescues_primary_recall() -> None:
    """A later paper's matching statement is reported separately from direct recall."""
    jobs, statuses = exposure()
    secondary = record("PMC_SECONDARY", evidence_role="secondary")
    result = score_reference_set(reference_set(), [secondary], [secondary], [], jobs, statuses, {})
    assert result["reference_recall"] == 0
    assert result["items"][1]["primary_match_record_ids"] == []
    assert result["items"][1]["secondary_content_match_record_ids"] == ["record"]


def test_failed_grounding_is_visible_and_cannot_enter_recall() -> None:
    """A complete-looking candidate remains excluded after a grounding failure."""
    jobs, statuses = exposure()
    rejected = {
        "source_id": "PMC2748230",
        "input_hash": "oh",
        "candidate": record(),
        "reason": "ungrounded_quote",
    }
    result = score_reference_set(reference_set(), [], [], [rejected], jobs, statuses, {"oh": 1})
    assert result["reference_recall"] == 0
    oh = result["items"][1]
    assert oh["outcome"] == "no_complete_grounded_semantic_match"
    assert all(oh["failed_grounding_candidate_comparison"][0]["components"].values())


def test_missing_source_chunk_retains_fixed_denominator_and_partial_status() -> None:
    """An unexposed chunk prevents complete-source recovery, even with a matching row."""
    jobs, statuses = exposure()
    jobs["oh"]["chunk_count"] = 2
    row = record()
    result = score_reference_set(reference_set(), [row], [row], [], jobs, statuses, {"oh": 1})
    assert result["status"] == "partial"
    assert result["fixed_reference_denominator"] == 2
    assert result["reference_recall"] == 0
    assert result["items"][1]["outcome"] == "source_exposure_incomplete"


def test_adjudications_require_complete_unique_record_coverage() -> None:
    """New or omitted model records cannot silently inherit an older review."""
    row = record()
    with pytest.raises(ValueError, match="exactly"):
        apply_adjudications([row], jobs_for(row), {})


def test_denominator_and_reference_source_identities_cannot_drift() -> None:
    """Changing either fixed source prevents scoring against a revised denominator."""
    jobs, statuses = exposure()
    changed = reference_set()
    changed["reference_items"][0]["doi"] = "replacement"
    with pytest.raises(ValueError, match="identities changed"):
        score_reference_set(changed, [], [], [], jobs, statuses, {})


@pytest.mark.parametrize(
    "producer", ["Pseudonocardiafoo", "Pseudonocardia_foo", "Pseudonocardia-foo"]
)
def test_taxon_prefix_is_not_an_exact_genus_token(producer: str) -> None:
    """A longer first token cannot match the explicit reference producer genus."""
    components = reference_components(
        record(target_name_as_written=producer), reference_set()["reference_items"][1]
    )
    assert components["producer"] is False


def test_activity_target_prefix_does_not_match_reference_genus() -> None:
    """Escovopsisi is distinct from the fixed Escovopsis target token."""
    components = reference_components(
        record(activity_target_as_written="Escovopsisi"), reference_set()["reference_items"][1]
    )
    assert components["activity_target"] is False


@pytest.mark.parametrize(
    "producer,target",
    [
        ("Pseudonocardia spp.", "Escovopsis sp."),
        ("Pseudonocardia, spp.", "Escovopsis(sp.)"),
        ("Pseudonocardia", "Escovopsis"),
    ],
)
def test_explicit_genus_tokens_allow_species_suffixes_and_punctuation(
    producer: str, target: str
) -> None:
    """Species qualifiers preserve the exact explicit genus at the start."""
    components = reference_components(
        record(target_name_as_written=producer, activity_target_as_written=target),
        reference_set()["reference_items"][1],
    )
    assert components["producer"] is True
    assert components["activity_target"] is True
