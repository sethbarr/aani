import json

from src.analysis.dataset import aggregate_behaviour, build_dataset


def observation(genus: str, outcome: str, record_id: str, family: str = "Fabaceae") -> dict:
    """Return a minimal taxonomically resolved natural-substrate observation."""
    return {
        "genus": genus,
        "family": family,
        "accepted_name": f"{genus} species",
        "plant_name_as_written": f"{genus} species",
        "source_id": f"source-{record_id}",
        "source_url": "https://example.org/paper",
        "record_id": record_id,
        "outcome": outcome,
        "substrate_treatment": "natural",
        "behavioural_choice": True,
        "evidence_type": "field_choice_assay",
        "rejection_timing": "immediate",
    }


def occurrence(genus: str, compound: str) -> dict:
    """Return a traceable occurrence for a genus and compound."""
    return {
        "genus": genus,
        "compound_id": compound,
        "occurrence_id": f"occ-{genus}-{compound}",
        "aggregation_level": "species",
        "plant_name": f"{genus} species",
        "reference_url": "https://example.org/occurrence",
    }


def test_unknown_only_genus_is_reported_in_review() -> None:
    """Keep zero-classified genera out of inference while reporting them."""
    observations = [observation("Rejected", "rejected", "r1"), observation("Unknown", "accepted", "u1", "Myrtaceae")]
    occurrences = [occurrence("Rejected", "A"), occurrence("Unknown", "B")]
    labels = [{"compound_id": "A", "label": "active"}, {"compound_id": "B", "label": "unknown"}]
    genera, compounds, review = build_dataset(observations, occurrences, labels)
    assert list(genera["genus"]) == ["Rejected"]
    assert list(compounds["compound_id"]) == ["A"]
    assert any(row["exclusion_reason"] == "no_classified_compounds" for row in review)


def test_species_match_covariate_is_invariant_to_duplicate_order() -> None:
    """Any exact species support qualifies a distinct occurrence regardless of row order."""
    observations = [observation("Plant", "rejected", "r1")]
    matching = occurrence("Plant", "A")
    other_species = {**matching, "plant_name": "Plant other_species"}
    labels = [{"compound_id": "A", "label": "active"}]
    first, _, _ = build_dataset(observations, [other_species, matching], labels)
    second, _, _ = build_dataset(observations, [matching, other_species], labels)
    assert first.iloc[0]["species_match_fraction"] == 1.0
    assert first.iloc[0]["phytochemistry_records"] == 1
    assert first.iloc[0]["species_match_fraction"] == second.iloc[0]["species_match_fraction"]


def test_missing_chemistry_is_separate_from_unknown_activity() -> None:
    """Distinguish no occurrence records from occurrences with no classified assays."""
    observations = [observation("Missing", "rejected", "r1"), observation("Unknown", "accepted", "a1")]
    genera, _, review = build_dataset(observations, [occurrence("Unknown", "A")], [])
    assert genera.empty
    reasons = {row["genus"]: row for row in review}
    assert reasons["Missing"]["exclusion_reason"] == "no_chemistry"
    assert "n_compounds" not in reasons["Missing"]
    assert reasons["Unknown"]["exclusion_reason"] == "no_classified_compounds"
    assert reasons["Unknown"]["n_compounds"] == 1


def test_conflicts_preserve_source_dictionaries_without_nan() -> None:
    """Do not invent pandas NaNs when sources have different optional metadata."""
    rows = [
        {**observation("Conflict", "accepted", "a1"), "model_metadata": {"provider": "test"}},
        {**observation("Conflict", "rejected", "r1"), "manual_audit_id": "audit-1"},
    ]
    genera, review = aggregate_behaviour(rows)
    assert genera == []
    assert len(review) == 2
    json.dumps(review, allow_nan=False)
    assert "manual_audit_id" not in review[0]
