"""Keep source-identity comparisons on the frozen baseline scoring convention."""

from copy import deepcopy
from pathlib import Path
from shutil import copytree

import pytest

from src.common.io import read_json, write_json
from src.evaluation.comparison import reference_rows
from src.evaluation.identity_comparison import (
    V1_EXTRACTION,
    assess_primary_change,
    build_identity_comparison,
    check_job_coverage,
    count_failure_reasons,
    render_identity_summary,
    score_variant,
)
from src.evaluation.recall import score_species, summarise_group


def test_original_extraction_reproduces_every_baseline_group_count() -> None:
    """Use the saved baseline as a byte-preserved structured-scoring regression check."""
    root = Path.cwd()
    baseline = read_json(root / "results/recall_baseline.json")
    snapshot = deepcopy(baseline)
    measured = score_variant(root / "data/interim/extraction_saverschek", baseline, None)
    assert measured["status"] == "complete"
    assert measured["groups"] == baseline["groups"]
    assert baseline == snapshot


def test_v1_recomputed_with_identical_scorer_and_no_semantic_review_gate() -> None:
    """Confirm v1 and v2 correctness use the existing baseline score_species function."""
    root = Path.cwd()
    baseline = read_json(root / "results/recall_baseline.json")
    run = score_variant(root / V1_EXTRACTION, baseline, None)
    rows = [score_species(row, run["candidates"]) for row in reference_rows(baseline)]
    assert run["species"] == rows
    assert run["groups"] == {group: summarise_group(rows, group)
                             for group in ("PRIMARY", "CONTEXT")}
    assert run["groups"]["PRIMARY"]["stages"]["detection"]["species_count"] == 2
    assert run["groups"]["PRIMARY"]["stages"]["survival"]["species_count"] == 0
    assert run["groups"]["CONTEXT"]["stages"]["detection"]["direction_coverage"] == {
        "both_directions_surfaced": 1, "collapsed_to_one": 1, "absent": 3, "unscorable": 0,
    }


def test_structure_matching_gives_correctness_credit_without_reviews() -> None:
    """Credit a matching surviving structured label exactly as the baseline does."""
    baseline = read_json(Path("results/recall_baseline.json"))
    reference = next(row for row in reference_rows(baseline) if row["species"] == "Hymenaea courbaril")
    candidates = [{
        "candidate_id": "run:1", "grounding_status": "passed", "blocked_reason": None,
        "record": {"plant_name_as_written": "Hymenaea courbaril", "outcome": "accepted",
                   "evidence_quote": "It was accepted first and rejected later."},
    }]
    result = score_species(reference, candidates)
    assert result["correctness"] is True
    assert result["correct_directions"] == ["accepted"]
    assert result["context_stages"]["correctness"] == "collapsed_to_one"


def test_missing_v2_blocks_all_species_with_fixed_denominators(tmp_path: Path) -> None:
    """Keep an absent rerun explicitly blocked without fabricating negative detections."""
    report = build_identity_comparison(tmp_path / "absent", Path.cwd())
    assert report["status"] == "partially_blocked"
    assert "development_extraction_artifacts_missing" in report["blocked_reason"]
    assert report["primary_change"]["v2_beats_baseline_survival"] is None
    assert report["v2"]["inventory"]["candidate_records"] is None
    assert len(report["v2"]["species"]) == 11
    assert all(row[stage] is None for row in report["v2"]["species"]
               for stage in ("detection", "survival", "correctness"))
    for group, species, pairs in (("PRIMARY", 6, 6), ("CONTEXT", 5, 10)):
        result = report["v2"]["groups"][group]
        assert result["species_denominator"] == species
        assert result["species_direction_pair_denominator"] == pairs
        assert len(result["unscorable_species"]) == species


@pytest.mark.parametrize(("field", "value"), [
    ("response_failures", 1), ("unattempted_chunks", 1), ("incomplete_papers", 1),
    ("blocked_reason", "provider_timeout"),
])
def test_incomplete_v2_is_unscorable(tmp_path: Path, field: str, value: int | str) -> None:
    """Block all stages when provider failures leave only a partial source run."""
    extraction = tmp_path / "incomplete"
    copytree(Path("data/interim/extraction_saverschek"), extraction)
    metrics = read_json(extraction / "metrics.json")
    metrics[field] = value
    write_json(extraction / "metrics.json", metrics)
    report = build_identity_comparison(extraction, Path.cwd())
    assert report["v2"]["status"] == "blocked"
    assert "development_run_" in report["v2"]["blocked_reason"]
    assert all(row["correctness"] is None for row in report["v2"]["species"])


def test_missing_response_blocks_nominally_complete_metrics(tmp_path: Path) -> None:
    """Check response coverage independently of a claimed complete run."""
    extraction = tmp_path / "manifest-only"
    write_json(extraction / "run_manifest.json", {"jobs": 3, "input_hashes": ["a", "b", "c"]})
    result = check_job_coverage(extraction)
    assert result["response_input_hashes"] == []
    assert result["blocked_reason"] == "development_response_job_coverage_incomplete"


def test_baseline_integrity_failure_blocks_derived_counts() -> None:
    """Prevent scoring against inputs that failed the frozen byte-integrity check."""
    baseline = read_json(Path("results/recall_baseline.json"))
    run = score_variant(Path("data/interim/extraction_saverschek"), baseline, "frozen_input_changed")
    assert run["status"] == "blocked"
    assert all(row["detection"] is None for row in run["species"])
    assert run["groups"]["PRIMARY"]["species_denominator"] == 6


def test_v1_failure_reasons_and_provenance_are_preserved() -> None:
    """Record dominant attrition and the unchanged weaker-reference split."""
    report = build_identity_comparison(Path("data/interim/extraction_saverschek"), Path.cwd())
    reasons = report["v1"]["failure_reasons"]
    assert reasons["all_candidates"] == {"ant_requires_review": 6, "name_surface_not_in_quote": 1}
    assert reasons["dominant_reasons"] == ["ant_requires_review"]
    assert reasons["dominant_reason_count"] == 6
    assert report["reference_provenance_species"] == {
        "author_prose": 6, "author_table_grouping": 5,
    }
    assert report["baseline_integrity"]["all_original_bytes_unchanged"]


def test_tied_failure_counts_are_reported_without_arbitrary_selection() -> None:
    """Keep every equally frequent grounding failure visible."""
    candidates = [
        {"grounding_status": "failed", "grounding_failure_reason": reason,
         "record": {"plant_name_as_written": name}}
        for reason, name in (("bad_quote", "Spondias mombin"), ("bad_identity", "Other species"))
    ]
    counts = count_failure_reasons(candidates, {"Spondias mombin"})
    assert counts["dominant_reasons"] == ["bad_identity", "bad_quote"]
    assert counts["panel_name_candidates"] == {"bad_quote": 1}


def test_survival_tie_is_explicitly_not_an_improvement() -> None:
    """Require greater survival before declaring that v2 beats the baseline."""
    baseline = read_json(Path("results/recall_baseline.json"))
    run = score_variant(Path("data/interim/extraction_saverschek"), baseline, None)
    result = assess_primary_change(baseline, run)
    assert result["v2_survival"] == 2
    assert result["v2_beats_baseline_survival"] is False
    assert result["proposal_suppression_investigation_required"] is False


def test_renderer_has_three_variant_columns_and_development_caveats() -> None:
    """Render directly comparable count tables and retain the known-reference caveats."""
    report = build_identity_comparison(Path("data/interim/extraction_saverschek"), Path.cwd())
    text = render_identity_summary(report)
    assert text.count("| Stage | baseline | v1 | v2 |") == 2
    assert "## PRIMARY" in text and "## CONTEXT" in text
    assert "DEVELOPMENT SET" in text
    assert "implementers know the reference" in text
    assert "shared blind spots would inflate apparent recall" in text
    assert "does not beat the baseline 2 of 6" in text
    assert "%" not in text
    assert "precision" not in text
    assert "validation" not in text.lower()
