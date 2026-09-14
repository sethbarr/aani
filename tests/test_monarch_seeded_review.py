"""Verify deterministic seeded review, source-bound names and raw-record preservation."""

from copy import deepcopy
from pathlib import Path

import pytest

from src.common.io import digest, read_json, read_jsonl, write_json, write_jsonl
from src.systems.monarch_infection import Record, validate_source_design_annotations
from src.systems.monarch_seeded_review import (
    apply_seeded_adjudications,
    run_seeded_semantic_review,
    summarize_seeded_focal_recovery,
)


@pytest.fixture
def fixture_review() -> tuple[list[Record], dict[str, Record], dict[str, Record]]:
    """Provide exact synthetic female choice, infection and expanded-name evidence."""
    text = (
        "Infected adult females preferred A. curassavica. "
        "Uninfected adult females showed no preference. "
        "The same experiment offered Asclepias curassavica and Asclepias incarnata."
    )
    job: Record = {"source_id": "SEED", "blocks": [
        {"block_id": "b1", "section": "Results", "text": text}
    ]}
    job["input_hash"] = digest(job)
    row: Record = {
        "record_id": "raw_id", "input_hash": job["input_hash"], "source_id": "SEED",
        "block_id": "b1", "section": "Results", "direction": "accept",
        "target_name_as_written": "A. curassavica", "taxonomic_rank": "species",
        "evidence_quote": "Infected adult females preferred A. curassavica.",
    }
    evidence = {key: row[key] for key in ("input_hash", "source_id", "block_id", "section")}
    evidence["evidence_quote"] = text
    review: Record = {
        "decision": "include", "note": "Synthetic primary choice experiment.",
        "infection_status": "infected", "infection_subject": "choosing_adult_female",
        "infection_evidence": [evidence], "primary_oviposition_choice": True,
        "between_milkweed_species": True, "choosing_adult_female": True,
        "design_evidence": [evidence], "experiment_id": "experiment1",
        "same_experiment_comparison": True,
        "compared_infection_groups": ["infected", "uninfected"],
        "comparison_evidence": [evidence], "direction_supported": True,
        "taxonomy_query": {"name": "Asclepias curassavica", "rank": "species",
                           "reason": "Expand the source-grounded genus abbreviation.",
                           "evidence": [evidence]},
    }
    return [row], {job["input_hash"]: job}, {"raw_id": review}


def write_review_fixture(
    root: Path, inputs: tuple[list[Record], dict[str, Record], dict[str, Record]],
) -> None:
    """Materialize isolated synthetic extraction and independent source-design evidence."""
    records, jobs, reviews = inputs
    live = root / "data/interim/systems/monarch_seeded"
    results = root / "results/systems/monarch_seeded"
    write_json(live / "extraction/metrics.json", {
        "status": "complete", "incomplete_papers": 0, "retained_records": len(records),
    })
    write_jsonl(live / "extraction/observations.jsonl", records)
    write_json(live / "extraction_payloads/index.json", {
        "jobs": [{"input_hash": key} for key in jobs],
    })
    for key, job in jobs.items():
        write_json(live / f"extraction_payloads/{key}.json", job)
    source = {key: deepcopy(value) for key, value in reviews["raw_id"].items()
              if key not in {"decision", "note", "taxonomy_query"}}
    source.update(source_id="SEED", infection_status="unreported",
                  infection_subject="unreported", infection_evidence=[])
    source_reviews = {"experiment1": source}
    write_json(results / "semantic_adjudications.json", reviews)
    write_json(results / "source_design_adjudications.json", source_reviews)
    write_json(results / "source_design_review.json", {
        "designs": validate_source_design_annotations(source_reviews, jobs),
    })


def test_taxonomy_expansion_preserves_raw_fields_and_origin(
    fixture_review: tuple[list[Record], dict[str, Record], dict[str, Record]],
) -> None:
    """Add query metadata while preserving the original model name, quote and identity."""
    before = deepcopy(fixture_review)
    rows, decisions = apply_seeded_adjudications(*fixture_review)
    row = rows[0]
    assert all(row[key] == value for key, value in fixture_review[0][0].items())
    assert row["raw_model_record"] == fixture_review[0][0]
    assert row["taxonomy_query_name"] == "Asclepias curassavica"
    assert row["record_origin"] == "model_record"
    assert row["curator_added_context"] is False
    assert decisions[0]["validated_taxonomy_query"]["taxonomy_query_evidence"] == row[
        "taxonomy_query_evidence"
    ]
    assert fixture_review == before


@pytest.mark.parametrize("name", ["Asclepias incarnata", "Araujia curassavica", "Asclepias"])
def test_name_expansion_requires_matching_epithet_and_source_support(
    fixture_review: tuple[list[Record], dict[str, Record], dict[str, Record]], name: str,
) -> None:
    """Refuse a changed epithet, an unsupported genus or a non-binomial override."""
    fixture_review[2]["raw_id"]["taxonomy_query"]["name"] = name
    with pytest.raises(ValueError):
        apply_seeded_adjudications(*fixture_review)


def test_expanded_name_cannot_use_another_source(
    fixture_review: tuple[list[Record], dict[str, Record], dict[str, Record]],
) -> None:
    """Keep taxonomy expansion tied to the record's original source."""
    fixture_review[2]["raw_id"]["taxonomy_query"]["evidence"] = [
        {**fixture_review[2]["raw_id"]["taxonomy_query"]["evidence"][0], "source_id": "OTHER"}
    ]
    with pytest.raises(ValueError):
        apply_seeded_adjudications(*fixture_review)


def test_context_expansions_are_disabled_for_this_rerun(
    fixture_review: tuple[list[Record], dict[str, Record], dict[str, Record]],
) -> None:
    """Prevent curator-created infection-group rows from entering model recovery."""
    original = fixture_review[2]["raw_id"]
    expansion = {key: deepcopy(value) for key, value in original.items()
                 if key not in {"decision", "note", "taxonomy_query"}}
    original["context_expansions"] = [expansion]
    with pytest.raises(ValueError):
        apply_seeded_adjudications(*fixture_review)


def test_live_and_offline_review_have_identical_records_and_preserve_first_run(
    fixture_review: tuple[list[Record], dict[str, Record], dict[str, Record]], tmp_path: Path,
) -> None:
    """Regenerate exact retained records and decisions without changing earlier outputs."""
    write_review_fixture(tmp_path, fixture_review)
    original = tmp_path / "results/systems/monarch/untouched.json"
    write_json(original, {"original": True})
    original_bytes = original.read_bytes()
    live = run_seeded_semantic_review(tmp_path)
    interim = tmp_path / "data/interim/systems/monarch_seeded"
    before = {name: (interim / "semantic_review" / name).read_bytes()
              for name in ("observations.jsonl", "decisions.jsonl", "metrics.json")}
    replay = run_seeded_semantic_review(tmp_path, offline=True)
    assert original.read_bytes() == original_bytes
    assert live["included"] == replay["included"] == 1
    assert live["focal_recovery"] == replay["focal_recovery"]
    assert live["focal_recovery"]["source_design_recovered"] is True
    assert live["focal_recovery"]["model_infected_uninfected_pair_recovered"] is False
    assert live["focal_recovery"]["same_target_model_panel_count"] == 0
    assert live["focal_recovery"]["same_target_model_panel_recovered"] is False
    for name in ("observations.jsonl", "decisions.jsonl"):
        assert before[name] == (interim / "offline_replay/semantic_review" / name).read_bytes()
    assert before == {name: (interim / "semantic_review" / name).read_bytes() for name in before}
    assert read_jsonl(interim / "semantic_review/observations.jsonl")[0]["record_id"] == "raw_id"


@pytest.fixture
def fixture_paired_model_records() -> list[Record]:
    """Provide same-experiment infection groups with distinct retained target species."""
    common: Record = {
        "source_id": "SEED", "experiment_id": "experiment1", "record_origin": "model_record",
        "focal_eligible": True, "curator_added_context": False,
    }
    return [
        {**common, "record_id": "infected", "infection_status": "infected", "direction": "accept",
         "target_name_as_written": "A. curassavica", "taxonomy_query_name": "Asclepias curassavica"},
        {**common, "record_id": "uninfected", "infection_status": "uninfected", "direction": "unknown",
         "target_name_as_written": "A. incarnata", "taxonomy_query_name": "Asclepias incarnata"},
    ]


def test_experiment_pair_does_not_imply_a_same_target_panel(
    fixture_paired_model_records: list[Record],
) -> None:
    """Count different-target infection coverage only at the experiment level."""
    before = deepcopy(fixture_paired_model_records)
    metrics = summarize_seeded_focal_recovery(fixture_paired_model_records, [])
    assert metrics["model_pairing_unit"] == "source_id + experiment_id"
    assert metrics["model_infected_uninfected_pair_recovered"] is True
    assert metrics["paired_model_experiments"] == [{"source_id": "SEED", "experiment_id": "experiment1"}]
    assert metrics["same_target_model_panel_count"] == 0
    assert metrics["same_target_model_panel_recovered"] is False
    assert metrics["same_target_model_panels"] == []
    assert fixture_paired_model_records == before


@pytest.mark.parametrize("expanded_query", [True, False])
def test_same_target_panel_uses_validated_query_or_exact_raw_name(
    fixture_paired_model_records: list[Record], expanded_query: bool,
) -> None:
    """Join source-validated names across spelling forms or fall back to exact raw names."""
    rows = fixture_paired_model_records
    rows[1].update(target_name_as_written="Asclepias curassavica",
                   taxonomy_query_name="Asclepias curassavica")
    if not expanded_query:
        for row in rows:
            del row["taxonomy_query_name"]
            row["target_name_as_written"] = "A. curassavica"
    rows.append(deepcopy(rows[0]))
    metrics = summarize_seeded_focal_recovery(rows, [])
    assert metrics["same_target_model_panel_count"] == 1
    assert metrics["same_target_model_panel_recovered"] is True
    assert metrics["same_target_model_panels"] == [{
        "source_id": "SEED", "experiment_id": "experiment1",
        "target_name": "Asclepias curassavica" if expanded_query else "A. curassavica",
    }]
    assert rows[1]["direction"] == "unknown"


@pytest.mark.parametrize("field,value", [
    ("source_id", "OTHER"), ("experiment_id", "experiment2"),
    ("infection_status", "unreported"), ("record_origin", "curator_context_expansion"),
    ("focal_eligible", False),
])
def test_same_target_panels_require_eligible_original_groups_in_one_source_and_experiment(
    fixture_paired_model_records: list[Record], field: str, value: str | bool,
) -> None:
    """Prevent cross-source, cross-experiment, unknown-status and curator-created panels."""
    rows = fixture_paired_model_records
    rows[1]["taxonomy_query_name"] = "Asclepias curassavica"
    rows[1][field] = value
    metrics = summarize_seeded_focal_recovery(rows, [])
    assert metrics["same_target_model_panel_count"] == 0
    assert metrics["same_target_model_panel_recovered"] is False


@pytest.mark.parametrize("damage", ["payload", "raw_count", "incomplete", "source_design"])
def test_runner_rejects_stale_or_incomplete_inputs(
    fixture_review: tuple[list[Record], dict[str, Record], dict[str, Record]],
    tmp_path: Path, damage: str,
) -> None:
    """Fail before writing review outputs if provenance or cohort checks disagree."""
    write_review_fixture(tmp_path, fixture_review)
    live = tmp_path / "data/interim/systems/monarch_seeded"
    if damage == "payload":
        key = next(iter(fixture_review[1]))
        job = deepcopy(fixture_review[1][key])
        job["blocks"][0]["text"] += " Added text."
        write_json(live / f"extraction_payloads/{key}.json", job)
    elif damage == "source_design":
        write_json(tmp_path / "results/systems/monarch_seeded/source_design_review.json", {
            "designs": [],
        })
    else:
        metrics = read_json(live / "extraction/metrics.json")
        metrics["retained_records" if damage == "raw_count" else "incomplete_papers"] = 2
        write_json(live / "extraction/metrics.json", metrics)
    with pytest.raises(ValueError):
        run_seeded_semantic_review(tmp_path)
    assert not (live / "semantic_review/observations.jsonl").exists()
