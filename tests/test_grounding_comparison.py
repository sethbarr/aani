"""Protect independent semantic scoring and immutable development denominators."""

from copy import deepcopy
from pathlib import Path
from shutil import copytree

import pytest

from src.common.io import read_json, write_json, write_jsonl
from src.evaluation.comparison import (
    baseline_integrity,
    build_comparison,
    reference_rows,
    render_comparison,
    score_development_species,
    summarise_development_group,
    validate_adjudication,
)


def source() -> dict:
    """Supply exact scientific text and its experiment context."""
    return {"source_id": "SAVERSCHEK2010", "blocks": [
        {"block_id": "b1", "text": "Natural-leaf tests in a-habitat on day 1. "
         "Hymenaea courbaril was accepted. It was rejected on day 2."},
    ]}


def candidate(direction: str = "accepted", candidate_id: str = "run:1") -> dict:
    """Build one reconciled surviving structured candidate."""
    return {"candidate_id": candidate_id, "record_digest": f"digest-{candidate_id}",
            "grounding_status": "passed", "blocked_reason": None,
            "record": {"plant_name_as_written": "Hymenaea courbaril", "outcome": direction,
                       "source_id": "SAVERSCHEK2010"}}


def review(record: dict, decision: str = "correct", natural_panel: bool = True) -> dict:
    """Link an independent semantic decision to its candidate and exact source spans."""
    return {
        "record_digest": record["record_digest"], "species": record["record"]["plant_name_as_written"],
        "direction": record["record"]["outcome"], "decision": decision, "natural_panel": natural_panel,
        "context": "Natural-leaf series; a-habitat; day 1 or day 2 as stated in direction anchor.",
        "reason": "The quoted observation identifies the emitted direction in the stated context.",
        "source_anchors": [
            {"source_id": "SAVERSCHEK2010", "block_id": "b1", "role": "context",
             "evidence_quote": "Natural-leaf tests in a-habitat on day 1."},
            {"source_id": "SAVERSCHEK2010", "block_id": "b1", "role": "direction",
             "evidence_quote": "Hymenaea courbaril was accepted. It was rejected on day 2."},
        ],
    }


def reference() -> dict:
    """Read the fixed context-dependent reference without altering its labels."""
    baseline = read_json(Path("results/recall_baseline.json"))
    return next(row for row in reference_rows(baseline) if row["species"] == "Hymenaea courbaril")


def test_unreviewed_matches_are_provisional_and_detection_survival_remain_scored() -> None:
    """Prevent automatic outcome matching from receiving independent correctness credit."""
    row = score_development_species(reference(), [candidate()], {}, source())
    assert row["detection"] and row["survival"]
    assert row["correctness"] is None
    assert row["correct_directions"] == []
    assert row["provisional_direction_matches"] == ["accepted"]
    assert row["context_stages"] == {
        "detection": "collapsed_to_one", "survival": "collapsed_to_one", "correctness": "unscorable",
    }
    assert "semantic_adjudication_missing" in row["blocked_reason"]


def test_both_directions_require_two_reviewed_structured_records() -> None:
    """Give both-direction coverage only to two surviving reviewed outcome fields."""
    accepted = candidate()
    rejected = candidate("rejected", "run:2")
    single = score_development_species(reference(), [accepted], {"run:1": review(accepted)}, source())
    assert single["context_stages"]["correctness"] == "collapsed_to_one"
    both = score_development_species(reference(), [accepted, rejected], {
        "run:1": review(accepted), "run:2": review(rejected),
    }, source())
    assert both["context_stages"]["correctness"] == "both_directions_surfaced"
    assert both["correct_directions"] == ["accepted", "rejected"]


def test_one_missing_review_blocks_species_correctness_even_with_one_correct_review() -> None:
    """Require review completeness for each species while preserving raw counts."""
    accepted = candidate()
    row = score_development_species(reference(), [accepted, candidate("rejected", "run:2")],
                                    {"run:1": review(accepted)}, source())
    assert row["survival"]
    assert row["correctness"] is None
    assert row["correct_directions"] == []


def test_bad_anchor_or_digest_makes_review_unscorable() -> None:
    """Reject fabricated text spans and semantic reviews attached to different bytes."""
    record = candidate()
    damaged = review(record)
    damaged["source_anchors"][0]["evidence_quote"] = "This invented context is absent."
    damaged["record_digest"] = "other-record"
    decision = validate_adjudication(record, damaged, source())
    assert not decision["scorable"]
    assert "adjudication_record_digest_mismatch" in decision["blocked_reason"]
    assert "adjudication_anchor_unverified:1" in decision["blocked_reason"]


def test_other_experiment_does_not_receive_correctness_credit() -> None:
    """Keep full-name candidates outside the natural panel out of reviewed correctness."""
    record = candidate()
    row = score_development_species(reference(), [record], {
        "run:1": review(record, "out_of_scope", False),
    }, source())
    assert row["detection"] and row["survival"]
    assert row["correctness"] is False
    assert row["correct_directions"] == []


def test_unscorable_reference_keeps_detection_and_fixed_denominators() -> None:
    """Count raw proposals despite reference uncertainty and retain every panel species."""
    baseline = read_json(Path("results/recall_baseline.json"))
    references = reference_rows(baseline)
    hymenaea = next(row for row in references if row["species"] == "Hymenaea courbaril")
    hymenaea["scorable"] = False
    hymenaea["blocked_reason"] = "reference_anchor_unverified"
    record = candidate()
    rows = [score_development_species(row, [record], {"run:1": review(record)}, source())
            for row in references]
    context = summarise_development_group(rows, "CONTEXT")
    assert context["species_denominator"] == 5
    assert context["species_direction_pair_denominator"] == 10
    assert context["stages"]["detection"]["species_count"] == 1
    assert context["stages"]["survival"]["species_count"] == 1
    assert context["stages"]["correctness"]["unscorable_species"] == ["Hymenaea courbaril"]
    assert context["stages"]["correctness"]["direction_coverage"]["unscorable"] == 1
    assert summarise_development_group(rows, "PRIMARY")["species_denominator"] == 6


def test_comparison_preserves_saved_baseline_and_checks_original_hashes() -> None:
    """Verify the real saved run can be inspected without rewriting reference artifacts."""
    root = Path.cwd()
    original = read_json(root / "results/recall_baseline.json")
    snapshot = deepcopy(original)
    integrity = baseline_integrity(original, root)
    assert integrity["all_original_bytes_unchanged"]
    report = build_comparison(root / "data/interim/extraction_saverschek", root)
    assert report["baseline"]["groups"] == snapshot["groups"]
    assert report["panel_species_direction_pair_denominator"] == 16
    assert report["adjudication"]["required_surviving_panel_candidates"] == 3
    assert report["status"] == "partially_blocked"
    assert read_json(root / "results/recall_baseline.json") == snapshot


def test_missing_run_records_explicit_blocker_without_shrinking_denominators(tmp_path: Path) -> None:
    """Keep all species visible when extraction has not produced its required artifacts."""
    report = build_comparison(tmp_path / "missing-extraction", Path.cwd())
    assert report["status"] == "partially_blocked"
    assert "development_extraction_artifacts_missing" in report["blocked_reason"]
    assert report["development"]["inventory"]["candidate_records"] is None
    primary = report["development"]["groups"]["PRIMARY"]
    assert primary["species_denominator"] == 6
    assert len(primary["stages"]["detection"]["unscorable_species"]) == 6
    assert all(row["detection"] is None for row in report["development"]["species"])


@pytest.mark.parametrize(("field", "value"), [
    ("response_failures", 1), ("unattempted_chunks", 1), ("incomplete_papers", 1),
    ("blocked_reason", "provider_timeout"),
])
def test_incomplete_reconciled_run_blocks_every_stage(tmp_path: Path, field: str,
                                                    value: int | str) -> None:
    """Prevent partial model coverage from being scored as species detection failure."""
    extraction = tmp_path / "incomplete"
    copytree(Path("data/interim/extraction_saverschek"), extraction)
    metrics_path = extraction / "metrics.json"
    metrics = read_json(metrics_path)
    metrics[field] = value
    write_json(metrics_path, metrics)
    report = build_comparison(extraction, Path.cwd())
    assert report["development"]["inventory"]["reconciled_with_original_artifacts"]
    assert not report["development"]["inventory"]["run_complete"]
    assert "development_run_" in report["blocked_reason"]
    assert str(value) in report["blocked_reason"]
    assert len(report["development"]["species"]) == 11
    for row in report["development"]["species"]:
        assert row["detection"] is None
        assert row["survival"] is None
        assert row["correctness"] is None
    for group, denominator in (("PRIMARY", 6), ("CONTEXT", 5)):
        for stage in report["development"]["groups"][group]["stages"].values():
            assert len(stage["unscorable_species"]) == denominator
            assert not stage["complete"]


def test_completed_run_without_survivors_needs_no_adjudication(tmp_path: Path) -> None:
    """Explain zero correctness from grounding attrition without implying a semantic review."""
    extraction = tmp_path / "zero-survivors"
    record = candidate()["record"]
    write_json(extraction / "responses/run.json", {"input_hash": "run", "output": {"records": [record]}})
    write_jsonl(extraction / "observations.jsonl", [])
    write_jsonl(extraction / "rejections.jsonl", [
        {"input_hash": "run", "candidate": record, "reason": "ungrounded_quote"},
    ])
    write_json(extraction / "metrics.json", {
        "candidate_records": 1, "validated_candidates": 0, "rejected_candidates": 1,
        "response_failures": 0, "unattempted_chunks": 0, "incomplete_papers": 0,
        "blocked_reason": None,
    })
    write_json(extraction / "run_manifest.json", {"jobs": 1, "input_hashes": ["run"]})
    report = build_comparison(extraction, Path.cwd())
    assert report["status"] == "complete"
    assert report["blocked_reason"] is None
    assert report["adjudication"]["status"] == "not_required_no_surviving_panel_candidates"
    assert report["adjudication"]["blocked_reason"] is None
    assert report["adjudication"]["semantic_review_performed"] is False
    assert report["adjudication"]["required_surviving_panel_candidates"] == 0
    assert all(row["correctness"] is False for row in report["development"]["species"])
    assert "correctness counts are zero because no candidate survived grounding" in render_comparison(report)
    assert "adjudication was unnecessary and was not performed" in render_comparison(report)
