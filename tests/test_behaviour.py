"""Regression checks for grounded-context deduplication and genus conflicts."""

from pathlib import Path

from src.behaviour.aggregation import aggregate, deduplicate, verify_miconia
from src.behaviour.pipeline import load_inputs


def record(record_id: str, outcome: str, day: int = 1) -> dict:
    """Build a minimal directional context with explicit repeated-test identity."""
    return {
        "record_id": record_id, "source_id": "SOURCE", "source_url": "https://example.org",
        "genus": "Miconia", "family": "Melastomataceae", "accepted_name": "Miconia argentea",
        "plant_name_as_written": "Miconia argentea", "outcome": outcome,
        "evidence_quote": "Miconia argentea was tested.", "ant_species": "Atta colombica",
        "study_context": "field study", "test_day": day, "habitat": "p",
        "experiment_id": "individual_pickup", "choice_design": "individual_pickup",
        "substrate_treatment": "natural", "behavioural_choice": True,
        "evidence_type": "field_choice_assay", "rejection_timing": "immediate",
    }


def test_deduplicate_whitespace_not_record_ids() -> None:
    """Collapse repeat grounded claims even when extractor IDs differ."""
    first = record("first", "rejected")
    duplicate = {**first, "record_id": "second", "evidence_quote": "Miconia  argentea\nwas tested."}
    observations, duplicates = deduplicate([first, duplicate])
    assert len(observations) == 1
    assert observations[0]["merged_record_ids"] == ["first", "second"]
    assert len(duplicates) == 1


def test_different_days_and_directions_remain_distinct() -> None:
    """Preserve repeat contexts and opposite directions without majority voting."""
    observations, duplicates = deduplicate([
        record("a", "accepted"), record("r", "rejected", day=2),
        record("r2", "rejected", day=3),
    ])
    genera, conflicts, review = aggregate(observations)
    assert not duplicates and not genera and not review
    assert conflicts[0]["n_observations"] == 3
    assert conflicts[0]["n_sources"] == 1
    assert conflicts[0]["n_ant_species"] == 1
    assert conflicts[0]["directions"] == ["accepted", "rejected"]


def test_artificial_rejection_cannot_create_natural_conflict() -> None:
    """Keep treatment and secondary claims outside natural directional aggregation."""
    rows = [record("natural", "accepted"),
            {**record("treated", "rejected"), "substrate_treatment": "experimentally_treated"},
            {**record("review", "rejected"), "evidence_type": "review_secondary"}]
    genera, conflicts, review = aggregate(rows)
    assert genera[0]["outcome"] == "accepted"
    assert not conflicts and len(review) == 2


def test_real_miconia_conflict_and_explicit_saverschek_replacement() -> None:
    """Verify both real Miconia species and avoid double-counting old Saverschek rows."""
    root = Path(__file__).resolve().parents[1]
    rows, replacements, inputs, lineage = load_inputs(root)
    observations, duplicates = deduplicate(rows)
    genera, conflicts, review = aggregate(observations)
    verification = verify_miconia(observations, conflicts)
    assert verification["verified"]
    assert lineage["baseline_taxonomy_records"] == 12
    assert len(replacements) == 3 and len(inputs) == 5
    assert not duplicates and not review
    assert len(observations) == 89 and len(genera) == 10 and len(conflicts) == 5
    assert "Miconia" not in {row["genus"] for row in genera}
    miconia = next(row for row in conflicts if row["genus"] == "Miconia")
    assert miconia["accepted_names"] == ["Miconia argentea", "Miconia microphysca"]
    assert miconia["n_sources"] == 2
    superseded_ids = {row["superseded_record_id"] for row in replacements}
    assert not superseded_ids.intersection(row["record_id"] for row in observations)
