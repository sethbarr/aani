"""Keep generalized glyph measurement on two separate, preserved proposal samples."""

from pathlib import Path
from shutil import copy2, copytree

import pytest

from src.common.io import digest, read_json, read_jsonl, write_json, write_jsonl
from src.evaluation.comparison import BASELINE_HASHES
from src.evaluation.generalized_glyph_comparison import (
    SAMPLE_PATHS,
    V4_REPEAT_EXTRACTION,
    VARIANTS,
    build_generalized_comparison,
)
from src.evaluation.identity_comparison import score_variant


@pytest.fixture
def measurement_root(tmp_path: Path) -> Path:
    """Copy preserved v3 inputs and initially reuse their outcomes as fixture v4 outputs."""
    baseline = read_json(Path("results/recall_baseline.json"))
    files = set(BASELINE_HASHES) | {row["path"] for row in baseline["inputs"]}
    for name in files:
        source = Path(name)
        if source.is_absolute():
            continue
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, target)
    for original, current in SAMPLE_PATHS.values():
        copytree(original, tmp_path / original)
        copytree(original, tmp_path / current)
    return tmp_path


def change_job_identifiers(extraction: Path) -> None:
    """Change only fixture job identifiers while preserving request and proposal identities."""
    manifest = read_json(extraction / "run_manifest.json")
    mapping = {value: f"v4-{value}" for value in manifest["input_hashes"]}
    manifest["input_hashes"] = [mapping[value] for value in manifest["input_hashes"]]
    write_json(extraction / "run_manifest.json", manifest)
    for path in sorted((extraction / "responses").glob("*.json")):
        response = read_json(path)
        response["input_hash"] = mapping[response["input_hash"]]
        write_json(path, response)
        path.rename(path.with_name(f"{response['input_hash']}.json"))
    for name in ("observations.jsonl", "rejections.jsonl"):
        rows = read_jsonl(extraction / name)
        for row in rows:
            row["input_hash"] = mapping[row["input_hash"]]
        write_jsonl(extraction / name, rows)


def recover_first_failure(extraction: Path) -> dict:
    """Promote one fixture candidate and keep its metrics and raw record digest reconciled."""
    rejections = read_jsonl(extraction / "rejections.jsonl")
    recovered = rejections.pop(0)
    observations = read_jsonl(extraction / "observations.jsonl")
    observations.append({
        **recovered["candidate"], "input_hash": recovered["input_hash"],
        "record_id": digest(recovered["candidate"]),
        "quote_grounding_route": "source_anchored_glyph_equivalence",
        "grounded_source_spans": [{"route": "source_anchored_glyph_equivalence"}],
    })
    write_jsonl(extraction / "observations.jsonl", observations)
    write_jsonl(extraction / "rejections.jsonl", rejections)
    metrics = read_json(extraction / "metrics.json")
    metrics["validated_candidates"] += 1
    metrics["rejected_candidates"] -= 1
    write_json(extraction / "metrics.json", metrics)
    return recovered


def test_four_variants_use_unchanged_baseline_convention(measurement_root: Path) -> None:
    """Match every group and species directly to the preserved structured-direction scorer."""
    baseline_path = measurement_root / "results/recall_baseline.json"
    before = baseline_path.read_bytes()
    baseline = read_json(baseline_path)
    report = build_generalized_comparison(measurement_root)
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
    assert baseline_path.read_bytes() == before


def test_identical_outcomes_retain_all_survivors_separately(measurement_root: Path) -> None:
    """Require per-sample identity checks without pooling the 26 and 18 raw proposals."""
    report = build_generalized_comparison(measurement_root)
    assert report["sample1_v3"]["inventory"]["candidate_records"] == 26
    assert report["sample2_v3"]["inventory"]["candidate_records"] == 18
    for sample in SAMPLE_PATHS:
        check = report["sample_checks"][sample]
        assert check["all_requests_identical"] is True
        assert check["all_raw_model_outputs_identical"] is True
        assert len(check["chunks"]) == 3
        transition = report["sample_transitions"][sample]
        assert transition["status"] == "complete"
        assert transition["recovered_count"] == 0
        assert transition["lost_count"] == 0
        assert transition["no_lost_v3_survivors"] is True
        assert transition["retained_survivor_count"] == report[
            f"{sample}_v3"
        ]["inventory"]["grounding_passes"]


def test_recovery_uses_chunk_mapping_and_raw_digest(measurement_root: Path) -> None:
    """Attribute a recovery across changed job hashes while preserving first-sample scores."""
    before = build_generalized_comparison(measurement_root)
    extraction = measurement_root / V4_REPEAT_EXTRACTION
    change_job_identifiers(extraction)
    recovered = recover_first_failure(extraction)
    report = build_generalized_comparison(measurement_root)
    assert report["status"] == "complete"
    assert report["sample1_v3"] == before["sample1_v3"]
    assert report["sample1_v4"] == before["sample1_v4"]
    transition = report["sample_transitions"]["sample2"]
    assert transition["recovered_count"] == 1
    assert transition["lost_count"] == 0
    row = transition["recovered_records"][0]
    assert row["record_digest"] == digest(recovered["candidate"])
    assert row["v4_input_hash"] == f"v4-{row['v3_input_hash']}"
    assert row["v3_grounding_status"] == "failed"
    assert row["v4_grounding_status"] == "passed"
    assert row["quote_grounding_route"] == "source_anchored_glyph_equivalence"
    assert row["grounded_source_spans"]


def test_lost_survivor_is_reported_with_measurable_counts(measurement_root: Path) -> None:
    """Expose a survivor regression and keep the observed scores available."""
    extraction = measurement_root / V4_REPEAT_EXTRACTION
    observations = read_jsonl(extraction / "observations.jsonl")
    lost = observations.pop(0)
    responses = [read_json(path) for path in (extraction / "responses").glob("*.json")]
    candidate = next(record for response in responses for record in response["output"]["records"]
                     if response["input_hash"] == lost["input_hash"]
                     and digest(record) == lost["record_id"])
    rejections = read_jsonl(extraction / "rejections.jsonl")
    rejections.append({"candidate": candidate, "input_hash": lost["input_hash"],
                       "reason": "test_regression"})
    write_jsonl(extraction / "observations.jsonl", observations)
    write_jsonl(extraction / "rejections.jsonl", rejections)
    metrics = read_json(extraction / "metrics.json")
    metrics["validated_candidates"] -= 1
    metrics["rejected_candidates"] += 1
    write_json(extraction / "metrics.json", metrics)
    report = build_generalized_comparison(measurement_root)
    assert report["status"] == "complete"
    transition = report["sample_transitions"]["sample2"]
    assert transition["no_lost_v3_survivors"] is False
    assert transition["lost_count"] == 1
    assert transition["recovered_count"] == 0
    assert transition["lost_records"][0]["v4_failure_reason"] == "test_regression"
    assert transition["lost_records"][0]["record_digest"] == lost["record_id"]


@pytest.mark.parametrize("changed_field", ["request_hash", "output"])
def test_mismatched_repeat_blocks_only_repeat_v4(
    measurement_root: Path, changed_field: str
) -> None:
    """Keep unaffected scores while refusing attribution on changed requests or proposals."""
    before = build_generalized_comparison(measurement_root)
    path = sorted((measurement_root / V4_REPEAT_EXTRACTION / "responses").glob("*.json"))[0]
    response = read_json(path)
    if changed_field == "request_hash":
        response[changed_field] = "changed-request"
        reason = "request_hash_changed_or_missing"
    else:
        response[changed_field]["records"].append({"plant_name_as_written": "changed-proposal"})
        reason = "raw_proposal_sample_changed"
    write_json(path, response)
    report = build_generalized_comparison(measurement_root)
    assert report["status"] == "partially_blocked"
    assert reason in report["sample2_v4"]["blocked_reason"]
    assert report["sample1_v3"] == before["sample1_v3"]
    assert report["sample1_v4"] == before["sample1_v4"]
    assert report["sample2_v3"] == before["sample2_v3"]
    assert report["sample_transitions"]["sample2"]["recovered_count"] is None
    assert report["sample_transitions"]["sample2"]["no_lost_v3_survivors"] is None
    assert all(row["correctness"] is None for row in report["sample2_v4"]["species"])


def test_missing_repeat_preserves_all_denominators(measurement_root: Path) -> None:
    """Keep all eleven species unscorable when saved responses are unavailable."""
    extraction = measurement_root / V4_REPEAT_EXTRACTION
    (extraction / "responses").rename(extraction / "unavailable-responses")
    report = build_generalized_comparison(measurement_root)
    assert report["status"] == "partially_blocked"
    run = report["sample2_v4"]
    assert "response_job_coverage_incomplete" in run["blocked_reason"]
    assert len(run["species"]) == 11
    for group, count in (("PRIMARY", 6), ("CONTEXT", 5)):
        assert len(run["groups"][group]["unscorable_species"]) == count
        assert run["groups"][group]["species_denominator"] == count


def test_changed_reference_blocks_all_variants(measurement_root: Path) -> None:
    """Require immutable baseline evidence for each sample and rule set."""
    path = measurement_root / "results/recall_baseline.json"
    baseline = read_json(path)
    baseline["unexpected_change"] = True
    write_json(path, baseline)
    report = build_generalized_comparison(measurement_root)
    for variant in VARIANTS:
        assert "baseline_or_original_input_changed" in report[variant]["blocked_reason"]
        assert all(row["survival"] is None for row in report[variant]["species"])
    assert report["sample_transitions"]["sample1"]["recovered_count"] is None
    assert report["sample_transitions"]["sample2"]["recovered_count"] is None


def test_known_sample_development_scope_is_explicit(measurement_root: Path) -> None:
    """State that both saved samples informed this rule's development."""
    report = build_generalized_comparison(measurement_root)
    assert report["set_type"] == "DEVELOPMENT SET"
    assert "Both existing samples informed development" in report["sampling_caveat"]
    assert "Neither sample is an independent test" in report["sampling_caveat"]
    assert "Implementers know the reference" in report["contamination_risk"]
    assert "shared blind spots would inflate apparent recall" in report["contamination_risk"]
    assert "one panel from one paper" in report["contamination_risk"]
    assert "not a sample from any population" in report["contamination_risk"]
    assert "Only structured outcome fields count" in report["direction_scoring"]
