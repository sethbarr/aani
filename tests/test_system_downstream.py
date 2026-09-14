"""Check exploratory joins and preserve behavioural and assay missingness."""

import base64
import json
import signal
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.common.cache import CachedHTTP
from src.common.io import digest, read_json, read_jsonl, write_json, write_jsonl
from src.systems import downstream
from src.systems.config import load_system_config
from src.taxonomy.gbif import CHECKLIST


def observation(record_id: str, genus: str, direction: str = "accept", **extra: object) -> dict:
    """Build a reviewed target record with complete taxonomy and provenance."""
    return {
        "record_id": record_id, "source_id": "PMC1", "source_url": "https://example.org/PMC1",
        "target_name_as_written": f"{genus} species", "accepted_name": f"{genus} species",
        "accepted_usage_key": genus, "genus": genus, "family": "Exampleaceae",
        "taxonomic_rank": "species", "direction": direction,
        "evidence_quote": f"The organism used {genus} species.",
        "behaving_organism_as_written": "Apis mellifera", "study_context": "observed collection",
        "behavioural_choice": True, "evidence_type": "observational",
        "semantic_decision": "include", **extra,
    }


def genus_row(genus: str, status: str = "accepted") -> dict:
    """Build an eligible genus selection for chemistry and bioactivity."""
    return {
        "genus": genus, "status": status, "primary_eligible": True,
        "directional_behaviour_records": 1, "accepted_names": [f"{genus} species"],
    }


def test_taxonomy_uses_configured_bacterial_kingdom_and_target(tmp_path: Path) -> None:
    """Replay a bacterial matcher request through the shared GBIF implementation."""
    config = load_system_config(Path("config/systems/attine_actino.json"))
    rows = [observation("one", "Pseudonocardia", "unknown", taxonomic_rank="genus",
                        target_name_as_written="Pseudonocardia")]
    source = tmp_path / "reviewed.jsonl"
    write_jsonl(source, rows)
    cache_path = tmp_path / "cache"
    request = {
        "method": "GET", "url": "https://api.gbif.org/v2/species/match", "json": None,
        "params": {"scientificName": "Pseudonocardia", "taxonRank": "GENUS",
                   "kingdom": "Bacteria", "checklistKey": CHECKLIST},
    }
    key = digest(request)
    payload = {
        "usage": {"key": "123", "rank": "GENUS", "canonicalName": "Pseudonocardia"},
        "diagnostics": {"matchType": "EXACT", "confidence": 99},
        "classification": [
            {"rank": "KINGDOM", "name": "Bacteria"},
            {"rank": "FAMILY", "name": "Pseudonocardiaceae"},
            {"rank": "GENUS", "name": "Pseudonocardia"},
        ],
    }
    write_json(cache_path / "http" / f"{key}.json", {
        "request": request, "request_hash": key,
        "attempts": [{"status": 200,
                      "body_base64": base64.b64encode(json.dumps(payload).encode()).decode()}],
    })
    metrics = downstream.run_system_taxonomy(config, source, tmp_path / "taxonomy", cache_path,
                                             offline=True)
    assert metrics["resolved_taxa"] == 1
    assert metrics["kingdom"] == "Bacteria"
    assert read_jsonl(tmp_path / "taxonomy/observations.jsonl")[0]["direction"] == "unknown"


def test_taxonomy_requires_applied_semantic_review(tmp_path: Path) -> None:
    """Refuse raw model outputs before any taxonomy lookup."""
    source = tmp_path / "records.jsonl"
    write_jsonl(source, [observation("one", "Example", semantic_decision="exclude")])
    config = load_system_config(Path("config/systems/propolis.json"))
    with pytest.raises(ValueError, match="semantic-review"):
        downstream.run_system_taxonomy(config, source, tmp_path / "out", tmp_path / "cache")


def test_taxonomy_offline_cache_miss_preserves_unknown_resolution(tmp_path: Path) -> None:
    """Distinguish unavailable taxonomy retrieval from a completed empty match."""
    source = tmp_path / "records.jsonl"
    write_jsonl(source, [observation("one", "Example")])
    config = load_system_config(Path("config/systems/propolis.json"))
    metrics = downstream.run_system_taxonomy(config, source, tmp_path / "out", tmp_path / "cache",
                                             offline=True)
    assert metrics["status"] == "blocked"
    assert metrics["resolved_taxa"] is None
    assert metrics["failed_observations"] == 1
    assert read_jsonl(tmp_path / "out/review.jsonl")[0]["taxonomy_request_hash"] is None


def test_genus_coverage_preserves_unknown_and_excludes_conflicts_and_named_sources(
    tmp_path: Path,
) -> None:
    """Keep direction evidence distinct from plant identity and compound activity."""
    rows = [
        observation("one", "Conflict", "accept"), observation("two", "Conflict", "reject"),
        observation("three", "Unknown", "unknown"),
        observation("four", "Named", behavioural_choice=False),
        observation("five", "Accepted"), observation("six", "Accepted", "unknown"),
        observation("seven", "Review", evidence_type="review_secondary"),
        observation("eight", "Compound", evidence_type="compound_activity_assay"),
        observation("duplicate", "Accepted"),
    ]
    source, output = tmp_path / "taxonomy.jsonl", tmp_path / "behaviour"
    write_jsonl(source, rows)
    metrics = downstream.build_genus_coverage(source, output)
    eligible = read_jsonl(output / "genera.jsonl")
    coverage = {row["genus"]: row for row in read_jsonl(output / "genus_coverage.jsonl")}
    assert [row["genus"] for row in eligible] == ["Accepted"]
    assert eligible[0]["status"] == "accepted"
    assert coverage["Accepted"]["all_directions"] == ["accept", "unknown"]
    assert coverage["Conflict"]["status"] == "conflict"
    assert coverage["Unknown"]["status"] == "unknown"
    assert coverage["Named"]["status"] == "unknown"
    assert coverage["Compound"]["status"] == "unknown"
    assert metrics["duplicate_observations"] == 1
    assert metrics["direct_directional_observations"] == 3
    assert metrics["unknown_direction_observations"] == 2


def test_same_quote_different_target_taxa_remain_distinct(tmp_path: Path) -> None:
    """Preserve species distinctions when a source sentence names several plants."""
    source = tmp_path / "observations.jsonl"
    rows = [
        observation("one", "Example", evidence_quote="Example one and Example two were used.",
                    accepted_usage_key="one", target_name_as_written="Example one"),
        observation("two", "Example", evidence_quote="Example one and Example two were used.",
                    accepted_usage_key="two", target_name_as_written="Example two"),
    ]
    write_jsonl(source, rows)
    metrics = downstream.build_genus_coverage(source, tmp_path / "behaviour")
    assert metrics["resolved_observations"] == 2
    assert metrics["duplicate_observations"] == 0


def test_ancillary_monarch_scope_survives_genus_aggregation(tmp_path: Path) -> None:
    """Preserve treatment context and the absent infection comparison in genus outputs."""
    config = load_system_config(Path("config/systems/monarch.json"))
    path, output = tmp_path / "observations.jsonl", tmp_path / "behaviour"
    write_jsonl(path, [observation(
        "one", "Asclepias", behaving_organism_as_written="Danaus plexippus",
        focal_eligible=False, infection_comparison_eligible=False,
        treatment_context="reduced-water versus well-watered plants of the same species",
        direction_scope="preference for reduced-water plants",
        semantic_scope="adjacent_within_species_water_treatment",
    )])
    metrics = downstream.build_genus_coverage(path, output, config)
    genus = read_jsonl(output / "genera.jsonl")[0]
    assert genus["primary_eligible"] is True
    assert genus["focal_eligible"] is False
    assert genus["infection_comparison_eligible"] is False
    assert genus["evaluation_scope"] == "ancillary_oviposition_coverage"
    assert genus["source_record_ids"] == ["one"]
    assert genus["direction_scopes"] == ["preference for reduced-water plants"]
    assert genus["treatment_contexts"] == [
        "reduced-water versus well-watered plants of the same species",
    ]
    assert metrics["eligible_genera"] == 1
    assert metrics["focal_eligible_genera"] == 0
    assert metrics["ancillary_oviposition_genera"] == 1
    assert read_jsonl(output / "genus_coverage.jsonl")[0]["focal_eligible"] is False


def test_focal_eligibility_is_propagated_from_reviewed_directional_records(tmp_path: Path) -> None:
    """Preserve positive mechanism-eligibility flags when an explicit review supplies them."""
    config = load_system_config(Path("config/systems/monarch.json"))
    path, output = tmp_path / "observations.jsonl", tmp_path / "behaviour"
    write_jsonl(path, [observation("one", "Asclepias", focal_eligible=True,
                                   infection_comparison_eligible=True)])
    metrics = downstream.build_genus_coverage(path, output, config)
    genus = read_jsonl(output / "genera.jsonl")[0]
    assert genus["focal_eligible"] is True
    assert genus["infection_comparison_eligible"] is True
    assert genus["evaluation_scope"] == "focal_mechanism_coverage"
    assert metrics["focal_eligible_genera"] == 1


def test_empty_chemistry_records_measured_zero_without_loading_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Avoid export retrieval when the reviewed directional cohort is empty."""
    def forbidden(*args: object, **kwargs: object) -> dict:
        """Fail if the export function is called for an empty selection."""
        pytest.fail("Empty chemistry selection must not read an export")

    monkeypatch.setattr(downstream, "acquire_lotus", forbidden)
    path = tmp_path / "genera.jsonl"
    write_jsonl(path, [])
    config = load_system_config(Path("config/systems/monarch.json"))
    metrics = downstream.run_system_chemistry(config, path, tmp_path / "raw",
                                              tmp_path / "transform", tmp_path / "chemistry")
    assert metrics["status"] == "complete"
    assert metrics["unique_compounds"] == 0
    assert metrics["export_scanned"] is False


def test_conflict_cannot_enter_chemistry(tmp_path: Path) -> None:
    """Reject an incorrectly supplied conflict row before export retrieval."""
    path = tmp_path / "genera.jsonl"
    write_jsonl(path, [genus_row("Example", "conflict")])
    config = load_system_config(Path("config/systems/propolis.json"))
    with pytest.raises(ValueError, match="direct directional"):
        downstream.run_system_chemistry(config, path, tmp_path / "raw",
                                       tmp_path / "transform", tmp_path / "chemistry")


def test_attine_chemistry_and_assays_are_unconfigured(tmp_path: Path) -> None:
    """Record omitted positive-control stages with null counts and no input reads."""
    config = load_system_config(Path("config/systems/attine_actino.json"))
    missing = tmp_path / "missing"
    chemistry = downstream.run_system_chemistry(config, missing, missing, missing,
                                               tmp_path / "chemistry")
    activity = downstream.run_system_bioactivity(config, missing, missing, missing,
                                                tmp_path / "bioactivity", missing, missing)
    assert chemistry["status"] == activity["status"] == "not_applicable"
    assert chemistry["unique_compounds"] is None
    assert activity["classified_compounds"] is None


def test_bioactivity_reuses_frozen_assays_and_excludes_unknown_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Limit exact structure retrieval to eligible genera and classify known labels."""
    config = load_system_config(Path("config/systems/monarch.json"))
    genera, occurrences, chemistry = [tmp_path / name for name in
                                     ("genera.jsonl", "occurrences.jsonl", "chemistry.json")]
    write_jsonl(genera, [genus_row("First"), genus_row("Second", "rejected")])
    write_jsonl(occurrences, [
        {"genus": "First", "compound_id": "A"}, {"genus": "First", "compound_id": "U"},
        {"genus": "Second", "compound_id": "I"}, {"genus": "Conflict", "compound_id": "X"},
    ])
    write_json(chemistry, {"status": "completed"})

    def retrieve(compounds: list[str], cache: CachedHTTP, output: Path, assay: dict) -> dict:
        """Check the downstream API contract with deterministic labelled fixtures."""
        assert compounds == ["A", "I", "U"]
        assert assay == read_json(Path("config/analysis.json"))
        assert cache.root == tmp_path / "cache"
        write_jsonl(output / "labels.jsonl", [
            {"compound_id": "A", "label": "active", "retrieval_status": "complete"},
            {"compound_id": "I", "label": "inactive", "retrieval_status": "complete"},
            {"compound_id": "U", "label": "unknown", "retrieval_status": "complete"},
        ])
        return {"status": "complete", "active": 1, "inactive": 1, "unknown": 1,
                "failed_compounds": 0, "blocked_reason": None}

    monkeypatch.setattr(downstream, "retrieve_labels", retrieve)
    metrics = downstream.run_system_bioactivity(
        config, occurrences, genera, chemistry, tmp_path / "bioactivity", tmp_path / "cache",
        Path("config/analysis.json"), offline=True,
    )
    assert metrics["classified_compounds"] == 2
    assert metrics["genera_with_classified_compounds"] == 2
    assert metrics["excluded_occurrences"] == 1
    assert metrics["assay_mismatch"] == config.assay_mismatch


def test_unavailable_chemistry_cannot_become_zero_classified_activity(tmp_path: Path) -> None:
    """Retain nulls when the upstream stage has no measured coverage."""
    config = load_system_config(Path("config/systems/propolis.json"))
    missing = tmp_path / "missing"
    metrics = downstream.run_system_bioactivity(config, missing, missing, missing,
                                                tmp_path / "out", tmp_path / "cache", missing)
    assert metrics["status"] == "blocked"
    assert metrics["classified_compounds"] is None


def test_funnel_distinguishes_missing_from_completed_empty_stages(tmp_path: Path) -> None:
    """Report observed zero only after the corresponding stage was completed."""
    config = load_system_config(Path("config/systems/propolis.json"))
    write_json(tmp_path / "chemistry/metrics.json", {
        "status": "complete", "unique_compounds": 0, "genera_with_chemistry": 0,
    })
    result = downstream.build_system_funnel(config, tmp_path, tmp_path / "funnel.json")
    stages = {row["stage"]: row for row in result["stages"]}
    assert stages["model_candidates"]["count"] is None
    assert stages["model_candidates"]["status"] == "not_run"
    assert stages["mapped_compounds"]["count"] == 0
    assert stages["classified_compounds"]["count"] is None
    assert result["analysis_performed"] is False


def prepare_empty_system(root: Path, hours_old: int = 0) -> tuple[Path, Path]:
    """Prepare a local empty reviewed cohort with a controlled retrieval time."""
    live = root / "data/interim/systems/propolis"
    write_jsonl(live / "corpus/manifest.jsonl", [{
        "source_id": "PMC1",
        "retrieved_at": (datetime.now(UTC) - timedelta(hours=hours_old)).isoformat(),
    }])
    write_jsonl(live / "semantic_review/observations.jsonl", [])
    write_json(live / "semantic_review/metrics.json", {"status": "complete", "included": 0})
    write_json(root / "config/analysis.json", read_json(Path("config/analysis.json")))
    return Path("config/systems/propolis.json").resolve(), live


def test_orchestration_empty_cohort_uses_no_export_and_records_zero_queries(tmp_path: Path) -> None:
    """Run actual empty join stages without any external service request."""
    config, live = prepare_empty_system(tmp_path)
    result = downstream.run_system_downstream(config, tmp_path)
    assert result["status"] == "complete"
    assert result["lotus_cache_copy"] is None
    assert result["stages"]["bioactivity"]["query_count"] == 0
    assert not (live / "cache/chemistry_export").exists()
    assert (tmp_path / "results/systems/propolis/funnel.json").is_file()


def test_offline_replay_has_separate_outputs_and_can_verify_after_live_deadline(
    tmp_path: Path,
) -> None:
    """Preserve live outputs while replaying completed evidence without networking."""
    config, live = prepare_empty_system(tmp_path, hours_old=5)
    write_json(live / "taxonomy/metrics.json", {"status": "complete", "resolved_taxa": 123})
    result = downstream.run_system_downstream(config, tmp_path, offline=True)
    assert result["status"] == "complete"
    assert read_json(live / "taxonomy/metrics.json")["resolved_taxa"] == 123
    assert read_json(live / "offline_replay/taxonomy/metrics.json")["resolved_taxa"] == 0
    assert result["semantic_input_path"] == str(live / "semantic_review/observations.jsonl")
    assert (tmp_path / "results/systems/propolis/offline_replay/funnel.json").is_file()


def test_elapsed_deadline_blocks_new_live_stages(tmp_path: Path) -> None:
    """Stop before external requests when four hours have already elapsed."""
    config, live = prepare_empty_system(tmp_path, hours_old=5)
    result = downstream.run_system_downstream(config, tmp_path)
    assert result["status"] == "blocked"
    assert result["stages"]["taxonomy"]["status"] == "blocked"
    assert not (live / "cache").exists()
    assert all(row["count"] is None for row in result["funnel"]["stages"][3:])


def test_deadline_interrupts_a_running_stage_and_restores_handler() -> None:
    """Exercise the actual timeout handler without waiting for wall-clock expiry."""
    previous = signal.getsignal(signal.SIGALRM)
    with pytest.raises(downstream.SystemDeadlineExceeded):
        with downstream.bounded_stage(datetime.now(UTC) + timedelta(seconds=60)):
            signal.raise_signal(signal.SIGALRM)
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_orchestration_rejects_output_symlink_escape(tmp_path: Path) -> None:
    """Reject a stage directory redirected beyond its system root."""
    config, live = prepare_empty_system(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (live / "taxonomy").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="isolation root"):
        downstream.run_system_downstream(config, tmp_path)
    assert not list(outside.iterdir())


def test_lotus_cache_copy_is_reusable_and_refuses_mismatched_existing_files(tmp_path: Path) -> None:
    """Copy shared cached artifacts once and protect existing system evidence."""
    source, destination = tmp_path / "shared", tmp_path / "system"
    write_json(source / "http/record.json", {"fixture": 1})
    first = downstream.materialize_lotus_cache(source, destination)
    second = downstream.materialize_lotus_cache(source, destination)
    assert first["files_copied"] == 1
    assert second["files_copied"] == 0
    write_json(source / "http/record.json", {"fixture": 2})
    with pytest.raises(ValueError, match="differs from shared source"):
        downstream.materialize_lotus_cache(source, destination)


def test_monarch_assay_scope_queries_fungi_and_separate_parasite_even_without_compounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measure actual assay inventory separately from absent compound coverage."""
    config = load_system_config(Path("config/systems/monarch.json"))

    def service(cache: CachedHTTP, requests: list[dict]) -> dict:
        """Provide a verified fixture service without network access."""
        requests.append({"request_hash": "service"})
        return {"status": {"chembl_db_version": "fixture"}}

    def primary(cache: CachedHTTP, assay: dict, requests: list[dict]) -> dict:
        """Check that the frozen functional fungal panel is requested."""
        assert assay["organisms"] == config.assay_organisms
        requests.append({"request_hash": "primary"})
        return {"A": {"assay_chembl_id": "A", "assay_organism": "Candida albicans",
                      "assay_type": "F"}}

    def parasite(cache: CachedHTTP, resource: str, collection: str, params: dict,
                 requests: list[dict]) -> list[dict]:
        """Check the exact parasite organism across all assay types."""
        assert resource == "assay" and collection == "assays"
        assert params == {"assay_organism": "Ophryocystis elektroscirrha"}
        requests.append({"request_hash": "parasite"})
        return []

    monkeypatch.setattr(downstream, "verified_service", service)
    monkeypatch.setattr(downstream, "eligible_assays", primary)
    monkeypatch.setattr(downstream, "pages", parasite)
    result = downstream.run_assay_scope_check(config, tmp_path / "assays", tmp_path / "cache",
                                             Path("config/analysis.json"), offline=True)
    assert result["primary_fungal_assays"] == 1
    assert result["parasite_assays_all_types"] == 0
    assert result["parasite_absent_from_complete_inventory"] is True
    assert result["query_count"] == 3
    assert (tmp_path / "assays/assay_scope_check.json").is_file()
