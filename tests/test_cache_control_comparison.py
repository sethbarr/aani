"""Test v6 measurement with copied development fixtures and invented held-out input."""

from pathlib import Path
from shutil import copy2, copytree

import pytest

from scripts.report_grounding_v6 import render_summary, write_reports
from src.common.io import read_json, read_jsonl, write_json, write_jsonl
from src.evaluation.cache_control_comparison import (
    PRIOR_SAMPLES,
    RAW_SAMPLES,
    V6_ROOT,
    build_comparison,
    regression_delta,
    render_tables,
)
from src.evaluation.comparison import BASELINE_HASHES
from src.evaluation.identity_comparison import score_variant


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    """Copy sample 2 into invented variants without reading a live sample 4."""
    baseline = read_json(Path("results/recall_baseline.json"))
    files = set(BASELINE_HASHES) | {row["path"] for row in baseline["inputs"]}
    for name in files:
        source = Path(name)
        if source.is_absolute():
            continue
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, target)
    original = RAW_SAMPLES["sample2"]
    current = PRIOR_SAMPLES["sample2"]["v5"]
    for sample in RAW_SAMPLES:
        copytree(original, tmp_path / RAW_SAMPLES[sample])
        copytree(current, tmp_path / V6_ROOT / sample)
        for prior in PRIOR_SAMPLES.get(sample, {}).values():
            copytree(current, tmp_path / prior)
    return tmp_path


def test_default_excludes_heldout_sample(fixture_root: Path) -> None:
    """Keep held-out files untouched unless their scoring is explicitly requested."""
    heldout = fixture_root / V6_ROOT / "sample4" / "metrics.json"
    heldout.write_text("deliberately invalid fixture", encoding="utf-8")
    report = build_comparison(fixture_root)
    assert report["status"] == "complete"
    assert report["variant_order"] == ["sample1_v6", "sample2_v6", "sample3_v6"]
    assert "sample4_v6" not in report
    assert report["samples_pooled"] is False


def test_all_samples_use_unchanged_baseline_scorer(fixture_root: Path) -> None:
    """Compare per-species and grouped output with the existing scorer directly."""
    baseline_path = fixture_root / "results/recall_baseline.json"
    previous = baseline_path.read_bytes()
    baseline = read_json(baseline_path)
    report = build_comparison(fixture_root, include_sample4=True)
    assert report["status"] == "complete"
    for variant in report["variant_order"]:
        run = report[variant]
        expected = score_variant(Path(run["extraction"]), baseline, None)
        assert run["species"] == expected["species"]
        assert run["groups"] == expected["groups"]
        assert run["groups"]["PRIMARY"]["species_direction_pair_denominator"] == 6
        assert run["groups"]["CONTEXT"]["species_direction_pair_denominator"] == 10
        assert report["sample_checks"][variant]["all_raw_model_outputs_identical"] is True
    assert baseline_path.read_bytes() == previous


def test_regressions_cover_both_prior_rules(fixture_root: Path) -> None:
    """Check retained identities and outcomes separately against v4 and v5."""
    report = build_comparison(fixture_root)
    assert len(report["regressions"]) == 3
    for comparisons in report["regressions"].values():
        assert set(comparisons) == {"v4", "v5"}
        for delta in comparisons.values():
            assert delta["status"] == "passed"
            assert delta["previous_survivors_retained"] == delta["previous_survivors"]
            assert delta["lost_record_ids"] == []
            assert delta["direction_changes"] == []


@pytest.mark.parametrize("mutation", ["lost", "direction", "duplicate", "missing"])
def test_regression_detects_bad_survivor_changes(fixture_root: Path, mutation: str) -> None:
    """Reject missing, lost, duplicated, or relabeled survivor records."""
    previous = fixture_root / PRIOR_SAMPLES["sample1"]["v4"]
    current = fixture_root / V6_ROOT / "sample1"
    path = current / "observations.jsonl"
    rows = read_jsonl(path)
    if mutation == "lost":
        rows.pop()
    elif mutation == "direction":
        rows[0]["outcome"] = "fixture_changed_direction"
    elif mutation == "duplicate":
        rows.append(rows[0])
    if mutation == "missing":
        path.rename(current / "fixture_saved_observations.jsonl")
    else:
        write_jsonl(path, rows)
    delta = regression_delta(previous, current)
    assert delta["status"] != "passed"
    assert delta["blocked_reason"]


def test_changed_proposal_blocks_only_affected_sample(fixture_root: Path) -> None:
    """Keep fixed proposals enforced while retaining each unaffected sample score."""
    before = build_comparison(fixture_root)
    path = sorted((fixture_root / V6_ROOT / "sample3" / "responses").glob("*.json"))[0]
    response = read_json(path)
    response["request_hash"] = "fixture_changed_request"
    write_json(path, response)
    report = build_comparison(fixture_root)
    assert report["status"] == "partially_blocked"
    assert report["sample1_v6"] == before["sample1_v6"]
    assert report["sample2_v6"] == before["sample2_v6"]
    assert "request_hash_changed_or_missing" in report["sample3_v6"]["blocked_reason"]
    assert len(report["sample3_v6"]["groups"]["PRIMARY"]["unscorable_species"]) == 6
    assert len(report["sample3_v6"]["groups"]["CONTEXT"]["unscorable_species"]) == 5
    assert report["stage_yields"]["sample3_v6"]["grounding_passes"] is None


def test_count_tables_and_scope(fixture_root: Path) -> None:
    """Render four separate sample columns, fixed denominators, and contamination caveats."""
    report = build_comparison(fixture_root, include_sample4=True)
    table = render_tables(report)
    assert "Sample 4: v6 (held out)" in table
    assert table.count("Sample 1: v6") == 3
    assert "Unscorable species | 0 | 0 | 0 | 0" in table
    assert "unscorable 0; pairs 9 of 10" in table
    assert "%" not in table
    assert report["sample_roles"]["sample3_v6"] == "informed_v6_rule_development"
    assert report["sample_roles"]["sample4_v6"] == "held_out_draw_under_frozen_v6_rule"
    assert "shared blind spots" in report["contamination_risk"]
    assert "one panel from one paper" in report["contamination_risk"]


def test_report_uses_saved_scores_and_preserves_files(fixture_root: Path) -> None:
    """Write each summary once using scored artifacts and retain existing report bytes."""
    report = build_comparison(fixture_root)
    folder = fixture_root / "results/grounding_development_v6"
    write_json(folder / "development_scores.json", report)
    write_json(folder / "development_verification.json", {"status": "passed", "blocked_reason": None})
    written = write_reports(fixture_root)
    assert written == [folder / "summary.md"]
    text = written[0].read_text(encoding="utf-8")
    assert "Sample 3 is DEVELOPMENT-SET" in text
    assert "Offline replay and preservation status: passed" in text
    assert write_reports(fixture_root) == []
    assert written[0].read_text(encoding="utf-8") == text


def test_heldout_report_requires_score_marker_and_audit(fixture_root: Path) -> None:
    """Keep missing held-out evidence visible and print only saved ordered reason counts."""
    report = build_comparison(fixture_root, include_sample4=True)
    rendered = render_summary(report, {"status": "passed", "blocked_reason": None})
    assert "sample4_score_completion_marker_missing" in rendered
    assert "sample4_failure_audit_missing" in rendered
    report["score_completed_at"] = "2026-09-13T19:30:00+00:00"
    audit = {"status": "complete", "blocked_reason": None, "category_counts": {"other": 0},
             "generalization_verdict": "The fixture draw has complete recorded glyph grounding."}
    sampling = {"status": "complete", "network_attempts": 3, "retries": 0}
    rendered = render_summary(report, {"status": "passed", "blocked_reason": None}, sampling, audit)
    assert "network attempts: 3; retries: 0" in rendered
    assert "| other | 0 |" in rendered
    assert audit["generalization_verdict"] in rendered
    assert "%" not in rendered
