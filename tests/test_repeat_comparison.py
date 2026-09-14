"""Keep the two saved model samples separate under the same scoring convention."""

from pathlib import Path
from shutil import copy2, copytree

import pytest

from src.common.io import read_json, write_json
from src.evaluation.comparison import BASELINE_HASHES
from src.evaluation.identity_comparison import score_variant
from src.evaluation.repeat_comparison import (
    SAMPLE_PATHS,
    V3_REPEAT_EXTRACTION,
    VARIANTS,
    build_repeat_comparison,
)


@pytest.fixture
def measurement_root(tmp_path: Path) -> Path:
    """Copy saved inputs and use unchanged repeat outcomes as the fixture's v3 rules."""
    baseline = read_json(Path("results/recall_baseline.json"))
    files = set(BASELINE_HASHES) | {row["path"] for row in baseline["inputs"]}
    for name in files:
        source = Path(name)
        if source.is_absolute():
            continue
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, target)
    for sample, (original, current) in SAMPLE_PATHS.items():
        copytree(original, tmp_path / original)
        copytree(current if sample == "sample1" else original, tmp_path / current)
    return tmp_path


def test_four_runs_use_unchanged_baseline_scoring(measurement_root: Path) -> None:
    """Match all four scored groups directly to the existing baseline scorer."""
    baseline_path = measurement_root / "results/recall_baseline.json"
    original_bytes = baseline_path.read_bytes()
    baseline = read_json(baseline_path)
    report = build_repeat_comparison(measurement_root)
    assert report["status"] == "complete"
    assert report["variant_order"] == list(VARIANTS)
    assert report["samples_pooled"] is False
    for variant in VARIANTS:
        run = report[variant]
        expected = score_variant(Path(run["extraction"]), baseline, None)
        assert run["groups"] == expected["groups"]
        assert run["species"] == expected["species"]
        assert run["groups"]["PRIMARY"]["species_direction_pair_denominator"] == 6
        assert run["groups"]["CONTEXT"]["species_direction_pair_denominator"] == 10
    assert baseline_path.read_bytes() == original_bytes


def test_request_and_raw_output_checks_are_per_sample(measurement_root: Path) -> None:
    """Require identical proposal bytes within each sample's two rule-set outcomes."""
    report = build_repeat_comparison(measurement_root)
    for sample in ("sample1", "sample2"):
        check = report["sample_checks"][sample]
        assert check["status"] == "complete"
        assert check["require_identical_raw_output"] is True
        assert check["all_requests_identical"] is True
        assert check["all_raw_model_outputs_identical"] is True
        assert len(check["chunks"]) == 3
    first = report["sample1_v2"]["inventory"]["candidate_records"]
    second = report["sample2_v2"]["inventory"]["candidate_records"]
    assert first == 26
    assert second == 18
    assert report["sample2_v3"]["groups"] == report["sample2_v2"]["groups"]
    assert report["sample2_v3"]["inventory"]["candidate_records"] == second


@pytest.mark.parametrize("changed_field", ["request_hash", "output"])
def test_repeat_mismatch_blocks_only_repeat_v3(
    measurement_root: Path, changed_field: str
) -> None:
    """Preserve first-sample scores and repeat v2 evidence when repeat v3 mismatches."""
    before = build_repeat_comparison(measurement_root)
    extraction = measurement_root / V3_REPEAT_EXTRACTION
    path = sorted((extraction / "responses").glob("*.json"))[0]
    response = read_json(path)
    if changed_field == "request_hash":
        response[changed_field] = "changed-request"
        expected_reason = "request_hash_changed_or_missing"
    else:
        response[changed_field]["records"].append({"plant_name_as_written": "changed-proposal"})
        expected_reason = "raw_proposal_sample_changed"
    write_json(path, response)
    report = build_repeat_comparison(measurement_root)
    assert report["status"] == "partially_blocked"
    assert expected_reason in report["sample2_v3"]["blocked_reason"]
    assert report["sample1_v2"] == before["sample1_v2"]
    assert report["sample1_v3"] == before["sample1_v3"]
    assert report["sample2_v2"] == before["sample2_v2"]
    assert all(row["correctness"] is None for row in report["sample2_v3"]["species"])


def test_missing_repeat_responses_keep_fixed_denominators(measurement_root: Path) -> None:
    """Retain all reference species as unscorable when the repeat cannot be loaded."""
    extraction = measurement_root / V3_REPEAT_EXTRACTION
    (extraction / "responses").rename(extraction / "unavailable-responses")
    report = build_repeat_comparison(measurement_root)
    run = report["sample2_v3"]
    assert report["status"] == "partially_blocked"
    assert "response_job_coverage_incomplete" in run["blocked_reason"]
    assert len(run["species"]) == 11
    assert all(row["detection"] is None for row in run["species"])
    for group, count in (("PRIMARY", 6), ("CONTEXT", 5)):
        assert len(run["groups"][group]["unscorable_species"]) == count
        assert run["groups"][group]["species_denominator"] == count


def test_changed_reference_bytes_block_every_run(measurement_root: Path) -> None:
    """Refuse derived counts when a preserved baseline artifact has changed."""
    path = measurement_root / "results/recall_baseline.json"
    baseline = read_json(path)
    baseline["unexpected_change"] = True
    write_json(path, baseline)
    report = build_repeat_comparison(measurement_root)
    assert report["baseline_integrity"]["all_original_bytes_unchanged"] is False
    for variant in VARIANTS:
        assert "baseline_or_original_input_changed" in report[variant]["blocked_reason"]
        assert all(row["survival"] is None for row in report[variant]["species"])


def test_scope_and_scoring_caveats_are_explicit(measurement_root: Path) -> None:
    """Carry count-only development-set scope and the existing correctness definition."""
    report = build_repeat_comparison(measurement_root)
    assert report["set_type"] == "DEVELOPMENT SET"
    assert report["unit"] == "species-direction pair"
    assert "Implementers know the reference" in report["contamination_risk"]
    assert "shared blind spots would inflate apparent recall" in report["contamination_risk"]
    assert "one panel from one paper" in report["contamination_risk"]
    assert "not a sample from any population" in report["contamination_risk"]
    assert "structured species and outcome" in report["correctness_definition"]
    assert "Only structured outcome fields count" in report["direction_scoring"]
