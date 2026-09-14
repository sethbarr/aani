"""Verify seeded isolation, infection groups, missingness, and independent assay scope."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from src.common.io import read_json, read_jsonl, write_json, write_jsonl
from src.systems import monarch_seeded_downstream as seeded
from src.systems.config import SystemConfig, load_system_config


@pytest.fixture
def seeded_root(tmp_path: Path) -> Path:
    """Create a repository-shaped test root with original read-only configurations."""
    write_json(tmp_path / "config/systems/monarch.json",
               read_json(Path("config/systems/monarch.json")))
    write_json(tmp_path / "config/analysis.json", read_json(Path("config/analysis.json")))
    return tmp_path


def observation(record_id: str, infection_status: str, direction: str = "accept") -> dict:
    """Build independently reviewed infection-group records with shared source text."""
    return {
        "record_id": record_id, "source_id": "PMC1", "source_url": "https://example.org/PMC1",
        "target_name_as_written": "Asclepias curassavica", "taxonomic_rank": "species",
        "accepted_name": "Asclepias curassavica", "accepted_usage_key": "123",
        "genus": "Asclepias", "family": "Apocynaceae",
        "direction": direction, "evidence_quote": "Females preferred Asclepias curassavica.",
        "behaving_organism_as_written": "Danaus plexippus", "study_context": "Choice test",
        "behavioural_choice": True, "evidence_type": "lab_choice_assay",
        "semantic_decision": "include", "infection_status": infection_status,
        "infection_status_evidence": [{"source_id": "PMC1", "block_id": "B1",
                                       "evidence_quote": "Choosing females were infected."}],
        "focal_eligible": False, "infection_comparison_eligible": False,
    }


def assay_scope_stub(
    config: SystemConfig, output: Path, cache_path: Path,
    assay_config_path: Path, offline: bool = False,
) -> dict:
    """Write an independent synthetic inventory without network activity."""
    metrics = {"status": "complete", "primary_fungal_assays": 3,
               "parasite_assays_all_types": 0, "offline": offline}
    write_json(output / "metrics.json", metrics)
    return metrics


def taxonomy_stub(
    config: SystemConfig, observations_path: Path, output: Path,
    cache_path: Path, offline: bool = False,
) -> dict:
    """Copy already-resolved test records through the taxonomy boundary."""
    rows = read_jsonl(observations_path)
    write_jsonl(output / "observations.jsonl", rows)
    write_jsonl(output / "review.jsonl", [])
    metrics = {"status": "complete", "resolved_taxa": 1}
    write_json(output / "metrics.json", metrics)
    return metrics


def activity_stub(
    config: SystemConfig, occurrences_path: Path, genera_path: Path,
    chemistry_metrics_path: Path, output: Path, cache_path: Path,
    assay_config_path: Path, offline: bool = False,
) -> dict:
    """Complete an empty eligible compound cohort without requesting ChEMBL."""
    assert read_jsonl(genera_path) == []
    assert read_jsonl(occurrences_path) == []
    metrics = {"status": "complete", "classified_compounds": 0,
               "genera_with_classified_compounds": 0, "unknown": 0}
    write_json(output / "metrics.json", metrics)
    return metrics


def test_paths_use_new_namespace_and_original_config(seeded_root: Path) -> None:
    """Keep caches in the seeded namespace and original configuration read-only."""
    paths = seeded.seeded_paths(seeded_root)
    replay = seeded.seeded_paths(seeded_root, offline=True)
    assert paths["cache"] == seeded_root / "data/interim/systems/monarch_seeded/cache"
    assert paths["config"] == seeded_root / "config/systems/monarch.json"
    assert replay["cache"] == paths["cache"]
    assert replay["interim"] == paths["live"] / "offline_replay"
    assert replay["results"] == paths["results"] / "offline_replay"


def test_seeded_namespace_cannot_redirect_into_first_run(seeded_root: Path) -> None:
    """Reject a seeded root symlink that would overwrite original-run artifacts."""
    original = seeded_root / "data/interim/systems/monarch"
    original.mkdir(parents=True)
    (original.parent / "monarch_seeded").symlink_to(original, target_is_directory=True)
    with pytest.raises(ValueError, match="cannot be redirected"):
        seeded.seeded_paths(seeded_root)


def test_semantic_input_requires_infection_status(tmp_path: Path) -> None:
    """Reject records whose required choosing-female infection annotation is absent."""
    row = observation("one", "infected")
    row.pop("infection_status")
    source = tmp_path / "records.jsonl"
    write_jsonl(source, [row])
    with pytest.raises(ValueError, match="infection_status_required"):
        seeded.validate_semantic_input(source)


def test_unreported_infection_retained_and_flagged(tmp_path: Path) -> None:
    """Preserve an unreported infection group without claiming focal recovery."""
    source = tmp_path / "records.jsonl"
    row = observation("one", "unreported")
    write_jsonl(source, [row])
    metrics = seeded.validate_semantic_input(source)
    assert metrics["records"] == 1
    assert metrics["unreported_infection_records"] == 1
    row["focal_eligible"] = True
    write_jsonl(source, [row])
    with pytest.raises(ValueError, match="cannot_satisfy_focal_design"):
        seeded.validate_semantic_input(source)


def test_distinct_infection_groups_survive_shared_deduplication(tmp_path: Path) -> None:
    """Preserve same-quote records assigned to distinct choosing-female groups."""
    source = tmp_path / "observations.jsonl"
    rows = [observation("one", "infected"), observation("two", "uninfected"),
            observation("three", "unreported")]
    write_jsonl(source, rows)
    before = source.read_bytes()
    config = load_system_config(Path("config/systems/monarch.json"))
    output = tmp_path / "behaviour"
    metrics = seeded.build_seeded_genus_coverage(source, output, config)
    retained = read_jsonl(output / "observations.jsonl")
    genus = read_jsonl(output / "genera.jsonl")[0]
    assert source.read_bytes() == before
    assert metrics["resolved_observations"] == 3
    assert metrics["duplicate_observations"] == 0
    assert genus["infection_statuses"] == ["infected", "uninfected", "unreported"]
    assert genus["unreported_infection_records"] == 1
    assert {row["study_context"] for row in retained} == {"Choice test"}
    assert retained[0]["infection_status_evidence"] == rows[0]["infection_status_evidence"]


def test_context_discriminator_preserves_treatment_groups(tmp_path: Path) -> None:
    """Keep infection-identical records with separate treatment contexts distinct."""
    source, output = tmp_path / "observations.jsonl", tmp_path / "behaviour"
    rows = [observation("one", "infected"), observation("two", "infected")]
    rows[0]["treatment_context"] = "treatment A"
    rows[1]["treatment_context"] = "treatment B"
    write_jsonl(source, rows)
    config = load_system_config(Path("config/systems/monarch.json"))
    metrics = seeded.build_seeded_genus_coverage(source, output, config)
    genus = read_jsonl(output / "genera.jsonl")[0]
    assert metrics["resolved_observations"] == 2
    assert genus["infection_status_groups"][0]["treatment_contexts"] == [
        "treatment A", "treatment B",
    ]


def test_experiment_and_model_context_origins_remain_explicit(tmp_path: Path) -> None:
    """Preserve experiment identity and distinguish model records from added contexts."""
    source, output = tmp_path / "observations.jsonl", tmp_path / "behaviour"
    rows = [observation("one", "infected"), observation("two", "infected")]
    rows[0].update(experiment_id="experiment A", record_origin="model_record")
    rows[1].update(experiment_id="experiment B", record_origin="curator_context_expansion")
    write_jsonl(source, rows)
    config = load_system_config(Path("config/systems/monarch.json"))
    metrics = seeded.build_seeded_genus_coverage(source, output, config)
    group = read_jsonl(output / "genera.jsonl")[0]["infection_status_groups"][0]
    assert metrics["resolved_observations"] == 2
    assert group["experiment_ids"] == ["experiment A", "experiment B"]
    assert group["record_origin_counts"] == {"curator_context_expansion": 1, "model_record": 1}
    assert group["model_record_ids"] == ["one"]
    assert group["curator_context_record_ids"] == ["two"]


def test_cross_group_genus_conflict_remains_excluded(tmp_path: Path) -> None:
    """Apply original genus unanimity even when direction differs by infection group."""
    source, output = tmp_path / "observations.jsonl", tmp_path / "behaviour"
    write_jsonl(source, [observation("one", "infected", "accept"),
                        observation("two", "uninfected", "reject")])
    config = load_system_config(Path("config/systems/monarch.json"))
    metrics = seeded.build_seeded_genus_coverage(source, output, config)
    assert metrics["eligible_genera"] == 0
    assert metrics["conflict_genera"] == 1
    assert read_jsonl(output / "genera.jsonl") == []
    assert read_jsonl(output / "conflicts.jsonl")[0]["infection_statuses"] == [
        "infected", "uninfected",
    ]


def test_missing_input_blocks_join_and_still_queries_scope(
    seeded_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measure organism inventory independently while unavailable joins remain null."""
    scope = Mock(side_effect=assay_scope_stub)
    taxonomy = Mock(side_effect=AssertionError("Missing input cannot enter taxonomy"))
    monkeypatch.setattr(seeded, "run_assay_scope_check", scope)
    monkeypatch.setattr(seeded, "run_system_taxonomy", taxonomy)
    result = seeded.run_seeded_downstream(seeded_root)
    assert result["status"] == "partial"
    assert result["stages"]["taxonomy"]["resolved_taxa"] is None
    assert result["stages"]["chemistry"]["unique_compounds"] is None
    assert result["stages"]["assay_scope"]["parasite_assays_all_types"] == 0
    assert result["cache_imported_from_first_monarch_run"] is False
    assert all(row["count"] is None for row in result["funnel"]["stages"])
    taxonomy.assert_not_called()
    scope.assert_called_once()
    assert scope.call_args.args[2] == (
        seeded_root / "data/interim/systems/monarch_seeded/cache/chembl"
    )


def test_empty_reviewed_cohort_preserves_unavailable_counts(
    seeded_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep empty model input distinct from a successfully measured empty downstream join."""
    write_jsonl(seeded_root / "data/interim/systems/monarch_seeded/semantic_review/observations.jsonl",
                [])
    monkeypatch.setattr(seeded, "run_assay_scope_check", assay_scope_stub)
    result = seeded.run_seeded_downstream(seeded_root)
    assert "no_reviewed_model_records_available" in result["errors"]["semantic_input"]
    assert result["stages"]["taxonomy"]["resolved_taxa"] is None
    assert result["stages"]["bioactivity"]["classified_compounds"] is None


def test_conflicted_only_cohort_skips_pinned_export_and_replays_isolated(
    seeded_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A measured genus conflict yields an empty chemistry join and preserves originals."""
    paths = seeded.seeded_paths(seeded_root)
    write_jsonl(paths["reviewed"], [observation("one", "infected", "accept"),
                                   observation("two", "uninfected", "reject")])
    original = seeded_root / "results/systems/monarch/untouched.json"
    write_json(original, {"preserved": True})
    original_bytes = original.read_bytes()
    export = Mock(side_effect=AssertionError("Conflicted genera cannot request the export"))
    monkeypatch.setattr(seeded, "materialize_lotus_cache", export)
    monkeypatch.setattr(seeded, "run_assay_scope_check", assay_scope_stub)
    monkeypatch.setattr(seeded, "run_system_taxonomy", taxonomy_stub)
    monkeypatch.setattr(seeded, "run_system_bioactivity", activity_stub)
    live = seeded.run_seeded_downstream(seeded_root)
    live_manifest = (paths["results"] / "downstream_manifest.json").read_bytes()
    replay = seeded.run_seeded_downstream(seeded_root, offline=True)
    assert live["status"] == replay["status"] == "complete"
    assert live["stages"]["behaviour"]["conflict_genera"] == 1
    assert live["stages"]["chemistry"]["unique_compounds"] == 0
    assert original.read_bytes() == original_bytes
    assert (paths["results"] / "downstream_manifest.json").read_bytes() == live_manifest
    assert Path(replay["funnel_path"]).is_relative_to(paths["results"] / "offline_replay")
    export.assert_not_called()


def test_standalone_scope_reuses_only_seeded_cache(
    seeded_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permit an assay-only run while seed text or model-payload approval is pending."""
    scope = Mock(side_effect=assay_scope_stub)
    monkeypatch.setattr(seeded, "run_assay_scope_check", scope)
    metrics = seeded.run_seeded_assay_scope(seeded_root, offline=True)
    assert metrics["parasite_assays_all_types"] == 0
    assert scope.call_args.kwargs["offline"] is True
    manifest = read_json(seeded_root / "results/systems/monarch_seeded/offline_replay/"
                         "assay_scope_manifest.json")
    assert manifest["cache_imported_from_first_monarch_run"] is False
    assert "monarch_seeded/cache/chembl" in manifest["cache_path"]
