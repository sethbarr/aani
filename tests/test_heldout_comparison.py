"""Exercise held-out scoring using only previously observed sample fixtures."""

from pathlib import Path
from shutil import copy2, copytree

import pytest

from src.common.io import read_json, write_json
from src.evaluation.comparison import BASELINE_HASHES
from src.evaluation.generalized_glyph_comparison import V4_EXTRACTION, V4_REPEAT_EXTRACTION
from src.evaluation.glyph_comparison import V2_REPEAT_EXTRACTION
from src.evaluation.heldout_comparison import (
    V2_SAMPLE3_EXTRACTION,
    V4_SAMPLE3_EXTRACTION,
    VARIANTS,
    build_heldout_comparison,
    render_heldout_tables,
)
from src.evaluation.identity_comparison import score_variant


@pytest.fixture
def heldout_root(tmp_path: Path) -> Path:
    """Use sample 2 copies for fixture sample 3 without reading the live held-out draw."""
    baseline = read_json(Path("results/recall_baseline.json"))
    files = set(BASELINE_HASHES) | {row["path"] for row in baseline["inputs"]}
    for name in files:
        source = Path(name)
        if source.is_absolute():
            continue
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, target)
    pairs = (
        (V4_EXTRACTION, V4_EXTRACTION),
        (V4_REPEAT_EXTRACTION, V4_REPEAT_EXTRACTION),
        (V2_REPEAT_EXTRACTION, V2_SAMPLE3_EXTRACTION),
        (V4_REPEAT_EXTRACTION, V4_SAMPLE3_EXTRACTION),
    )
    for source, target in pairs:
        copytree(source, tmp_path / target)
    return tmp_path


def test_three_variants_use_baseline_scoring(heldout_root: Path) -> None:
    """Keep the original species, pair, provenance, and direction conventions."""
    baseline_path = heldout_root / "results/recall_baseline.json"
    before = baseline_path.read_bytes()
    baseline = read_json(baseline_path)
    report = build_heldout_comparison(heldout_root)
    assert report["status"] == "complete"
    assert report["variant_order"] == list(VARIANTS)
    assert report["samples_pooled"] is False
    assert report["sample3_check"]["all_requests_identical"] is True
    assert report["sample3_check"]["all_raw_model_outputs_identical"] is True
    for variant in VARIANTS:
        run = report[variant]
        expected = score_variant(Path(run["extraction"]), baseline, None)
        assert run["groups"] == expected["groups"]
        assert run["species"] == expected["species"]
        assert run["groups"]["PRIMARY"]["species_direction_pair_denominator"] == 6
        assert run["groups"]["CONTEXT"]["species_direction_pair_denominator"] == 10
    assert baseline_path.read_bytes() == before


def test_stage_yield_retains_separate_candidate_counts(heldout_root: Path) -> None:
    """Keep all proposals within their sample, including outside-panel records."""
    report = build_heldout_comparison(heldout_root)
    for variant, passes, candidates in (
        ("sample1_v4", 23, 26), ("sample2_v4", 18, 18), ("sample3_v4", 18, 18)
    ):
        assert report["stage_yields"][variant]["grounding_passes"] == passes
        assert report["stage_yields"][variant]["candidate_records"] == candidates
        assert report["stage_yields"][variant]["grounding_failures"] == candidates - passes


@pytest.mark.parametrize("changed_field", ["request_hash", "output"])
def test_changed_heldout_sample_blocks_only_sample3(
    heldout_root: Path, changed_field: str
) -> None:
    """Reject a changed sample-3 identity while retaining both earlier measurements."""
    before = build_heldout_comparison(heldout_root)
    path = sorted((heldout_root / V4_SAMPLE3_EXTRACTION / "responses").glob("*.json"))[0]
    response = read_json(path)
    if changed_field == "request_hash":
        response[changed_field] = "fixture-changed-request"
        reason = "request_hash_changed_or_missing"
    else:
        response[changed_field]["fixture_change"] = True
        reason = "raw_proposal_sample_changed"
    write_json(path, response)
    report = build_heldout_comparison(heldout_root)
    assert report["status"] == "partially_blocked"
    assert reason in report["sample3_v4"]["blocked_reason"]
    assert report["sample1_v4"] == before["sample1_v4"]
    assert report["sample2_v4"] == before["sample2_v4"]
    assert report["stage_yields"]["sample3_v4"]["grounding_passes"] is None
    assert all(row["correctness"] is None for row in report["sample3_v4"]["species"])


def test_missing_heldout_output_retains_denominators(heldout_root: Path) -> None:
    """Report an unavailable third sample explicitly without removing reference pairs."""
    extraction = heldout_root / V4_SAMPLE3_EXTRACTION
    (extraction / "responses").rename(extraction / "fixture-unavailable-responses")
    report = build_heldout_comparison(heldout_root)
    assert report["status"] == "partially_blocked"
    run = report["sample3_v4"]
    assert "response_job_coverage_incomplete" in run["blocked_reason"]
    assert len(run["species"]) == 11
    for group, species, pairs in (("PRIMARY", 6, 6), ("CONTEXT", 5, 10)):
        assert run["groups"][group]["species_denominator"] == species
        assert run["groups"][group]["species_direction_pair_denominator"] == pairs
        assert len(run["groups"][group]["unscorable_species"]) == species
    assert "unscorable 5" in render_heldout_tables(report)
    assert "Blocked:" in render_heldout_tables(report)


def test_changed_reference_blocks_all_samples(heldout_root: Path) -> None:
    """Require unchanged reference labels and baseline inputs for every sample."""
    path = heldout_root / "results/recall_baseline.json"
    baseline = read_json(path)
    baseline["fixture_change"] = True
    write_json(path, baseline)
    report = build_heldout_comparison(heldout_root)
    for variant in VARIANTS:
        assert "baseline_or_original_input_changed" in report[variant]["blocked_reason"]
        assert all(row["survival"] is None for row in report[variant]["species"])
        assert report["stage_yields"][variant]["grounding_passes"] is None


def test_heldout_scope_and_count_only_tables(heldout_root: Path) -> None:
    """Separate rule-development draws from the same-paper held-out draw."""
    report = build_heldout_comparison(heldout_root)
    assert report["sample_roles"]["sample1_v4"] == "informed_v4_rule_development"
    assert report["sample_roles"]["sample2_v4"] == "informed_v4_rule_development"
    assert report["sample_roles"]["sample3_v4"] == "held_out_draw_under_frozen_v4_rule"
    assert report["set_type"] == "DEVELOPMENT SET"
    assert "Samples 1 and 2 informed v4 rule development" in report["sampling_caveat"]
    assert "unseen-paper performance remains untested" in report["sampling_caveat"]
    assert "Implementers know the reference" in report["contamination_risk"]
    assert "shared blind spots would inflate apparent recall" in report["contamination_risk"]
    assert "one panel from one paper" in report["contamination_risk"]
    assert "not a sample from any population" in report["contamination_risk"]
    assert "Only structured outcome fields count" in report["direction_scoring"]
    rendered = render_heldout_tables(report)
    assert rendered.count("| Sample 1: v4 | Sample 2: v4 | Sample 3: v4 (held out) |") == 3
    assert "unscorable 0; pairs 9 of 10" in rendered
    assert "| 23 of 26 | 18 of 18 | 18 of 18 |" in rendered
    assert "%" not in rendered
