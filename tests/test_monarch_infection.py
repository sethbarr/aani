"""Regression checks for explicit seeded-monarch infection annotations."""

from copy import deepcopy
from typing import Any

import pytest

from src.common.io import digest
from src.systems.monarch_infection import (
    apply_explicit_infection_annotations,
    summarize_focal_recovery,
    validate_source_design_annotations,
)

type Record = dict[str, Any]


@pytest.fixture
def inputs() -> tuple[list[Record], dict[str, Record], dict[str, Record]]:
    """Provide a synthetic experiment with explicit adult choice and infection groups."""
    text = (
        "Adult female monarchs chose between Asclepias curassavica and Asclepias incarnata. "
        "Infected females preferred Asclepias curassavica. "
        "The same choice experiment compared infected and uninfected females."
    )
    job: Record = {"source_id": "source", "blocks": [
        {"block_id": "b1", "section": "Results", "text": text}
    ]}
    job["input_hash"] = digest(job)
    record: Record = {
        "record_id": "r1", "input_hash": job["input_hash"], "source_id": "source",
        "section": "Results", "block_id": "b1",
        "evidence_quote": "Infected females preferred Asclepias curassavica.",
        "direction": "accept", "target_name_as_written": "Asclepias curassavica",
    }
    evidence = {"input_hash": job["input_hash"], "source_id": "source",
                "section": "Results", "block_id": "b1", "evidence_quote": text}
    review: Record = {
        "decision": "include", "note": "Synthetic explicit primary experiment.",
        "infection_status": "infected", "infection_subject": "choosing_adult_female",
        "infection_evidence": [evidence], "design_evidence": [evidence],
        "primary_oviposition_choice": True, "between_milkweed_species": True,
        "choosing_adult_female": True, "direction_supported": True,
        "experiment_id": "choice_1", "same_experiment_comparison": True,
        "compared_infection_groups": ["infected", "uninfected"],
        "comparison_evidence": [evidence],
    }
    return [record], {job["input_hash"]: job}, {"r1": review}


def test_reported_status_preserves_raw_record_and_exact_source(
    inputs: tuple[list[Record], dict[str, Record], dict[str, Record]],
) -> None:
    """Preserve model fields and bind review evidence to exact original text."""
    before = deepcopy(inputs)
    records, decisions = apply_explicit_infection_annotations(*inputs)
    row = records[0]
    assert all(row[key] == value for key, value in inputs[0][0].items())
    assert row["raw_model_record"] == inputs[0][0]
    assert row["infection_status"] == "infected"
    assert row["focal_eligible"] is True
    anchor = row["infection_evidence"][0]
    text = inputs[1][anchor["input_hash"]]["blocks"][0]["text"]
    assert text[anchor["start"]:anchor["end"]] == anchor["evidence_quote"]
    assert decisions[0]["validated_annotation"]["source_design_eligible"] is True
    assert inputs == before


def test_unreported_records_remain_flagged_and_nonfocal(
    inputs: tuple[list[Record], dict[str, Record], dict[str, Record]],
) -> None:
    """Separate source-level experimental design from a record's unreported status."""
    review = inputs[2]["r1"]
    review.update(infection_status="unreported", infection_subject="unreported",
                  infection_evidence=[])
    records, decisions = apply_explicit_infection_annotations(*inputs)
    assert records[0]["focal_eligible"] is False
    assert records[0]["infection_comparison_eligible"] is False
    assert "choosing_female_infection_unreported" in records[0]["infection_flags"]
    summary = summarize_focal_recovery(records, decisions)
    assert summary["source_design_recovered"] is True
    assert summary["focal_model_record_count"] == 0
    assert summary["model_infected_uninfected_pair_recovered"] is False


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate"])
def test_requires_exact_unique_record_coverage(
    inputs: tuple[list[Record], dict[str, Record], dict[str, Record]], change: str,
) -> None:
    """Refuse missing, extraneous or duplicate record adjudications."""
    if change == "missing":
        inputs[2].clear()
    elif change == "extra":
        inputs[2]["extra"] = deepcopy(inputs[2]["r1"])
    else:
        inputs[0].append(deepcopy(inputs[0][0]))
    with pytest.raises(ValueError, match="cover exactly"):
        apply_explicit_infection_annotations(*inputs)


@pytest.mark.parametrize("field,value", [
    ("source_id", "other_source"), ("input_hash", "other_hash"),
    ("block_id", "other_block"), ("section", "Discussion"),
    ("evidence_quote", "Invented infection quote."),
])
def test_rejects_unbound_infection_evidence(
    inputs: tuple[list[Record], dict[str, Record], dict[str, Record]], field: str, value: str,
) -> None:
    """Reject source, job, block, section and exact-quote mismatches."""
    inputs[2]["r1"]["infection_evidence"] = [
        {**inputs[2]["r1"]["infection_evidence"][0], field: value}
    ]
    with pytest.raises(ValueError):
        apply_explicit_infection_annotations(*inputs)


@pytest.mark.parametrize("field,value", [
    ("infection_subject", "unreported"), ("infection_evidence", []),
    ("choosing_adult_female", False), ("design_evidence", []),
    ("compared_infection_groups", ["infected"]), ("experiment_id", None),
    ("comparison_evidence", []), ("same_experiment_comparison", False),
    ("between_milkweed_species", False), ("primary_oviposition_choice", False),
    ("direction_supported", False),
])
def test_positive_claims_require_explicit_subject_design_and_comparison(
    inputs: tuple[list[Record], dict[str, Record], dict[str, Record]],
    field: str, value: str | bool | list[str] | None,
) -> None:
    """Prevent isolated infection, larval or watering context from establishing focal choice."""
    inputs[2]["r1"][field] = value
    with pytest.raises(ValueError):
        apply_explicit_infection_annotations(*inputs)


def test_context_expansions_do_not_count_as_model_recovery(
    inputs: tuple[list[Record], dict[str, Record], dict[str, Record]],
) -> None:
    """Keep curator-added group records auditable and outside model recovery counts."""
    expansion = {key: deepcopy(value) for key, value in inputs[2]["r1"].items()
                 if key not in {"decision", "note"}}
    expansion["infection_status"] = "uninfected"
    inputs[2]["r1"]["context_expansions"] = [expansion]
    records, decisions = apply_explicit_infection_annotations(*inputs)
    assert len(records) == 2
    assert records[1]["record_id"] != "r1"
    assert records[1]["parent_record_id"] == "r1"
    assert records[1]["raw_model_record"]["record_id"] == "r1"
    assert records[1]["record_origin"] == "curator_context_expansion"
    summary = summarize_focal_recovery(records, decisions)
    assert summary["focal_model_record_count"] == 1
    assert summary["curator_context_expansion_count"] == 1
    assert summary["model_infected_uninfected_pair_recovered"] is False
    repeated, _ = apply_explicit_infection_annotations(*inputs)
    assert repeated == records


def test_exclusion_keeps_required_status_and_raw_record_in_decisions(
    inputs: tuple[list[Record], dict[str, Record], dict[str, Record]],
) -> None:
    """Retain the full audit of excluded model proposals."""
    inputs[2]["r1"]["decision"] = "exclude"
    records, decisions = apply_explicit_infection_annotations(*inputs)
    assert records == []
    assert decisions[0]["infection_status"] == "infected"
    assert decisions[0]["raw_model_record"] == inputs[0][0]


def test_duplicate_contexts_fail_and_unknown_status_is_invalid(
    inputs: tuple[list[Record], dict[str, Record], dict[str, Record]],
) -> None:
    """Prevent duplicate context rows and statuses outside the declared three values."""
    inputs[2]["r1"]["infection_status"] = "unknown"
    with pytest.raises(ValueError):
        apply_explicit_infection_annotations(*inputs)
    inputs[2]["r1"]["infection_status"] = "infected"
    expansion = {key: deepcopy(value) for key, value in inputs[2]["r1"].items()
                 if key not in {"decision", "note"}}
    inputs[2]["r1"]["context_expansions"] = [expansion, deepcopy(expansion)]
    with pytest.raises(ValueError, match="Duplicate retained"):
        apply_explicit_infection_annotations(*inputs)


def test_source_design_recovery_is_independent_of_model_records(
    inputs: tuple[list[Record], dict[str, Record], dict[str, Record]],
) -> None:
    """Measure available primary design evidence when extraction yielded no candidate."""
    source_review = {key: deepcopy(value) for key, value in inputs[2]["r1"].items()
                     if key not in {"decision", "note"}}
    source_review.update(source_id="source", infection_status="unreported",
                         infection_subject="unreported", infection_evidence=[])
    designs = validate_source_design_annotations({"design1": source_review}, inputs[1])
    summary = summarize_focal_recovery([], [], designs)
    assert summary["source_design_recovered"] is True
    assert summary["source_design_sources"] == ["source"]
    assert summary["focal_model_record_count"] == 0
    assert summary["model_infected_uninfected_pair_recovered"] is False


def test_model_comparison_requires_two_groups_within_one_experiment(
    inputs: tuple[list[Record], dict[str, Record], dict[str, Record]],
) -> None:
    """Keep identical labels from different experiments outside paired recovery."""
    second_record = {**inputs[0][0], "record_id": "r2"}
    inputs[0].append(second_record)
    inputs[2]["r2"] = deepcopy(inputs[2]["r1"])
    inputs[2]["r2"].update(infection_status="uninfected", experiment_id="choice_2")
    records, decisions = apply_explicit_infection_annotations(*inputs)
    assert summarize_focal_recovery(records, decisions)[
        "model_infected_uninfected_pair_recovered"
    ] is False
    inputs[2]["r2"]["experiment_id"] = "choice_1"
    records, decisions = apply_explicit_infection_annotations(*inputs)
    summary = summarize_focal_recovery(records, decisions)
    assert summary["model_infected_uninfected_pair_recovered"] is True
    assert summary["paired_model_experiments"] == [
        {"source_id": "source", "experiment_id": "choice_1"}
    ]
