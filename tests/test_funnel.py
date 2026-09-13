"""Check coverage units and distinguish unrun stages from measured empty joins."""

from pathlib import Path

from scripts.funnel import current_stages, historical_stages
from src.common.io import read_json, read_jsonl, write_json, write_jsonl


def stage_map(stages: list[dict]) -> dict[str, dict]:
    """Index reported stages by their stable machine-readable names."""
    return {row["stage"]: row for row in stages}


def prepare_behaviour(root: Path) -> tuple[Path, Path]:
    """Create a small resolved fixture with accepted, rejected and conflicted genera."""
    processed, results = root / "processed", root / "results"
    eligible = [{"genus": "Accepted", "status": "accepted"},
                {"genus": "Rejected", "status": "rejected"}]
    conflicts = [{"genus": "Miconia", "status": "conflict"}]
    observations = [
        {"genus": "Accepted", "accepted_usage_key": "A", "accepted_name": "Accepted species",
         "source_id": "SOURCE_A", "outcome": "accepted", "record_id": "a"},
        {"genus": "Rejected", "accepted_usage_key": "R", "accepted_name": "Rejected species",
         "source_id": "SOURCE_R", "outcome": "rejected", "record_id": "r"},
        {"genus": "Miconia", "accepted_usage_key": "M1", "accepted_name": "Miconia microphysca",
         "source_id": "PMC11543716", "outcome": "accepted", "record_id": "m1"},
        {"genus": "Miconia", "accepted_usage_key": "M2", "accepted_name": "Miconia argentea",
         "source_id": "SAVERSCHEK2010", "outcome": "rejected", "record_id": "m2"},
    ]
    for name, rows in [("observations", observations), ("genera", eligible),
                       ("conflicts", conflicts)]:
        write_jsonl(processed / "behaviour" / f"{name}.jsonl", rows)
    write_json(processed / "behaviour/metrics.json", {"status": "complete", "blocked_reason": None})
    return processed, results


def prepare_chemistry(processed: Path, rows: list[dict]) -> None:
    """Record a completed occurrence import, including a legitimately empty one."""
    write_jsonl(processed / "chemistry/occurrences.jsonl", rows)
    write_json(processed / "chemistry/metrics.json", {"status": "complete", "blocked_reason": None})


def prepare_activity(processed: Path, rows: list[dict], failed: int = 0) -> None:
    """Record completed activity retrieval without converting unknowns into inactive labels."""
    write_jsonl(processed / "bioactivity/labels.jsonl", rows)
    write_json(processed / "bioactivity/metrics.json", {
        "status": "partial" if failed else "complete", "blocked_reason": None,
        "compounds": len(rows), "failed_compounds": failed,
    })


def test_historical_model_funnel_and_unique_source_counts() -> None:
    """Keep repeated source retrieval and curator rows outside model denominators."""
    stages, cohorts, _ = historical_stages()
    counts = {name: row["count"] for name, row in stage_map(stages).items()}
    assert counts == {
        "papers_retrieved": 33, "screened_in": 13, "extraction_jobs": 23,
        "candidate_records": 61, "grounding_passed": 41, "semantically_retained": 9,
    }
    assert len(cohorts["retrieved_source_ids"]) == 33
    assert len(set(cohorts["retrieved_source_ids"])) == 33
    assert cohorts["source_following_recovery"]["additional_retrieved_sources"] == [
        "PMC3140513", "PMC5710599",
    ]
    assert cohorts["included_source_ids"].count("PMC9965205") == 1


def test_curation_bridge_uses_context_units_and_reports_taxonomy_loss() -> None:
    """Verify 96 retained contexts become 89 matched contexts, independently of 61 candidates."""
    audit = read_json(Path("results/saverschek_audit/summary.json"))
    pilot = read_jsonl(Path("data/interim/taxonomy_pilot/observations.jsonl"))
    recovered = read_jsonl(Path("data/interim/taxonomy_recovered/observations.jsonl"))
    matched = read_jsonl(Path("results/saverschek_audit/taxonomy_matched_directional.jsonl"))
    assert len(pilot) + len(recovered) + audit["directional_context_cells"] == 96
    assert len(pilot) + len(recovered) + len(matched) == 89
    assert audit["directional_context_cells"] - len(matched) == 7


def test_missing_stages_are_unavailable_not_zero(tmp_path: Path) -> None:
    """Do not assign observed-zero activity metrics to an unrun stage."""
    processed, results = prepare_behaviour(tmp_path)
    stages, _, miconia, _ = current_stages(processed, results)
    named = stage_map(stages)
    assert named["genera_with_chemistry"]["count"] is None
    assert named["genera_with_classified_compounds"]["count"] is None
    assert named["genera_with_classified_compounds"]["classified_structures_observed"] is None
    assert named["genera_with_classified_compounds"]["failed_compounds"] is None
    assert named["genera_available_for_primary_test"]["count"] is None
    assert miconia["status"] == "conflict"


def test_missing_primary_summary_is_blocked_even_after_activity(tmp_path: Path) -> None:
    """A completed activity stage does not imply that analysis has executed."""
    processed, results = prepare_behaviour(tmp_path)
    prepare_chemistry(processed, [{"genus": "Accepted", "compound_id": "C1"}])
    prepare_activity(processed, [{"compound_id": "C1", "label": "active"}])
    stages, _, _, _ = current_stages(processed, results)
    primary = stage_map(stages)["genera_available_for_primary_test"]
    assert primary["count"] is None
    assert primary["status"] == "blocked"
    assert primary["blocked_reason"]


def test_unknown_activity_excludes_denominator_and_missing_chemistry_separately(tmp_path: Path) -> None:
    """Report a real zero-classified genus while distinguishing a genus without chemistry."""
    processed, results = prepare_behaviour(tmp_path)
    prepare_chemistry(processed, [{"genus": "Accepted", "compound_id": "C1"}])
    prepare_activity(processed, [{"compound_id": "C1", "label": "unknown",
                                  "retrieval_status": "complete"}])
    write_json(results / "primary/summary.json", {
        "n_genera": 0, "status": "feasibility_failure", "estimable": False,
    })
    stages, _, _, _ = current_stages(processed, results)
    named = stage_map(stages)
    assert named["genera_with_chemistry"]["count"] == 1
    assert named["genera_with_chemistry"]["missing_chemistry_genera"] == ["Rejected"]
    classified = named["genera_with_classified_compounds"]
    assert classified["count"] == 0 and classified["status"] == "complete"
    assert classified["zero_classified_genera"] == ["Accepted"]
    assert classified["zero_classified_genera_count"] == 1
    assert named["genera_available_for_primary_test"]["count"] == 0


def test_failed_activity_and_conflicted_genus_never_enter_primary_count(tmp_path: Path) -> None:
    """Exclude apparent hits from failed retrievals and from conflicted genera."""
    processed, results = prepare_behaviour(tmp_path)
    prepare_chemistry(processed, [{"genus": "Accepted", "compound_id": "C1"},
                                 {"genus": "Miconia", "compound_id": "C2"}])
    prepare_activity(processed, [
        {"compound_id": "C1", "label": "active", "retrieval_status": "failed"},
        {"compound_id": "C2", "label": "active", "retrieval_status": "complete"},
    ], failed=1)
    stages, _, _, _ = current_stages(processed, results)
    classified = stage_map(stages)["genera_with_classified_compounds"]
    assert classified["count"] == 0
    assert classified["status"] == "partial"
    assert classified["failed_compounds"] == 1
    assert classified["conflict_genera_excluded_from_primary"] == 1


def test_completed_empty_behaviour_is_zero_not_blocked(tmp_path: Path) -> None:
    """Differentiate a successful empty eligible-evidence result from an absent stage."""
    processed, results = prepare_behaviour(tmp_path)
    for name in ["observations", "genera", "conflicts"]:
        write_jsonl(processed / "behaviour" / f"{name}.jsonl", [])
    stages, _, _, _ = current_stages(processed, results)
    named = stage_map(stages)
    assert named["names_resolved"]["count"] == 0
    assert named["names_resolved"]["status"] == "complete"
    assert named["genera_after_aggregation"]["count"] == 0


def test_real_current_behaviour_reports_five_conflicts_and_miconia() -> None:
    """Verify actual resolved species and excluded-genus counts from the merged evidence."""
    stages, _, miconia, _ = current_stages(Path("data/processed"), Path("results"))
    named = stage_map(stages)
    assert named["names_resolved"]["count"] == 16
    assert named["names_resolved"]["observation_contexts"] == 89
    assert named["names_resolved"]["species_in_conflicted_genera"] == 6
    assert named["genera_after_aggregation"]["count"] == 10
    assert named["genera_after_aggregation"]["conflict_genera"] == 5
    assert miconia["accepted_names"] == ["Miconia argentea", "Miconia microphysca"]
    assert miconia["directions"] == ["accepted", "rejected"]
    assert miconia["sources"] == ["PMC11543716", "SAVERSCHEK2010"]
