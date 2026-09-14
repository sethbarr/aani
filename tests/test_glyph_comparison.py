"""Keep glyph-only comparisons on fixed proposals and separate repeat samples."""

from pathlib import Path
from shutil import copytree

from src.common.io import digest, read_json, read_jsonl, write_json, write_jsonl
from src.evaluation.glyph_comparison import (
    V2_EXTRACTION,
    build_glyph_comparison,
    compare_proposal_samples,
    render_glyph_summary,
)


def test_identical_v2_sample_reproduces_every_v2_group() -> None:
    """Require the same baseline scorer for the unchanged proposal sample."""
    report = build_glyph_comparison(V2_EXTRACTION, Path.cwd())
    assert report["status"] == "complete"
    assert report["v3"]["groups"] == report["v2"]["groups"]
    assert report["fixed_sample_check"]["all_requests_identical"] is True
    assert report["fixed_sample_check"]["all_raw_model_outputs_identical"] is True
    assert report["glyph_recoveries"]["count"] == 0


def test_missing_v3_keeps_all_eleven_species_unscorable(tmp_path: Path) -> None:
    """Retain fixed denominators when the glyph rerun has no saved responses."""
    report = build_glyph_comparison(tmp_path / "absent", Path.cwd())
    assert report["status"] == "partially_blocked"
    assert len(report["v3"]["species"]) == 11
    assert all(row["detection"] is None for row in report["v3"]["species"])
    assert len(report["v3"]["groups"]["PRIMARY"]["unscorable_species"]) == 6
    assert len(report["v3"]["groups"]["CONTEXT"]["unscorable_species"]) == 5
    assert report["glyph_recoveries"]["count"] is None


def test_unexpected_raw_proposal_pool_blocks_v3(tmp_path: Path) -> None:
    """Block a changed model proposal sample before attributing effects to glyphs."""
    extraction = tmp_path / "changed-pool"
    copytree(V2_EXTRACTION, extraction)
    response_path = sorted((extraction / "responses").glob("*.json"))[0]
    response = read_json(response_path)
    response["output"]["records"].append({"plant_name_as_written": "unexpected"})
    write_json(response_path, response)
    report = build_glyph_comparison(extraction, Path.cwd())
    assert "raw_proposal_sample_changed" in report["v3"]["blocked_reason"]
    assert all(row["correctness"] is None for row in report["v3"]["species"])


def test_request_configuration_change_blocks_v3(tmp_path: Path) -> None:
    """Require request identity even if a changed request has identical proposals."""
    extraction = tmp_path / "changed-request"
    copytree(V2_EXTRACTION, extraction)
    response_path = sorted((extraction / "responses").glob("*.json"))[0]
    response = read_json(response_path)
    response["request_hash"] = "different-request"
    write_json(response_path, response)
    report = build_glyph_comparison(extraction, Path.cwd())
    assert "request_hash_changed_or_missing" in report["v3"]["blocked_reason"]
    assert all(row["survival"] is None for row in report["v3"]["species"])


def test_repeat_sample_stays_separate_and_never_changes_v3_counts() -> None:
    """Expose independent repeat scores without merging the candidate inventories."""
    ordinary = build_glyph_comparison(V2_EXTRACTION, Path.cwd())
    repeated = build_glyph_comparison(V2_EXTRACTION, Path.cwd(), V2_EXTRACTION)
    assert repeated["v3"] == ordinary["v3"]
    assert repeated["repeat_sample"]["status"] == "complete"
    assert repeated["repeat_sample"]["pooled_with_v3"] is False
    assert repeated["repeat_sample"]["primary_detection_six_of_six_again"] is True


def test_recovery_links_changed_job_hash_to_original_record(tmp_path: Path) -> None:
    """Identify a glyph recovery from raw record digest across new job identifiers."""
    extraction = tmp_path / "glyph-recovery"
    copytree(V2_EXTRACTION, extraction)
    manifest = read_json(extraction / "run_manifest.json")
    input_map = {value: f"v3-{value}" for value in manifest["input_hashes"]}
    manifest["input_hashes"] = [input_map[value] for value in manifest["input_hashes"]]
    write_json(extraction / "run_manifest.json", manifest)
    for response_path in sorted((extraction / "responses").glob("*.json")):
        response = read_json(response_path)
        response["input_hash"] = input_map[response["input_hash"]]
        write_json(response_path, response)
        response_path.rename(response_path.with_name(f"{response['input_hash']}.json"))
    observations = read_jsonl(extraction / "observations.jsonl")
    rejections = read_jsonl(extraction / "rejections.jsonl")
    for row in observations + rejections:
        row["input_hash"] = input_map[row["input_hash"]]
    recovered = rejections.pop(0)
    observations.append({
        **recovered["candidate"], "input_hash": recovered["input_hash"],
        "record_id": digest(recovered["candidate"]),
        "quote_grounding_route": "bounded_glyph_equivalence",
        "grounded_source_spans": [{"route": "bounded_glyph_equivalence", "replacements": [
            {"model_codepoint": "U+0001", "source_codepoint": "U+00B1"}
        ]}],
    })
    write_jsonl(extraction / "observations.jsonl", observations)
    write_jsonl(extraction / "rejections.jsonl", rejections)
    metrics = read_json(extraction / "metrics.json")
    metrics["validated_candidates"] += 1
    metrics["rejected_candidates"] -= 1
    write_json(extraction / "metrics.json", metrics)
    report = build_glyph_comparison(extraction, Path.cwd())
    assert report["status"] == "complete"
    result = report["glyph_recoveries"]
    assert result["count"] == 1
    assert result["glyph_route_count"] == 1
    assert result["blocked_reason"] is None
    assert result["records"][0]["candidate_id"].startswith("v3-")
    assert not result["records"][0]["v2_candidate_id"].startswith("v3-")
    assert result["records"][0]["grounded_source_spans"][0]["replacements"][0] == {
        "model_codepoint": "U+0001", "source_codepoint": "U+00B1"
    }


def test_missing_repeat_does_not_block_completed_glyph_comparison(tmp_path: Path) -> None:
    """Keep quota-blocked optional repeat work separate from the completed experiment."""
    report = build_glyph_comparison(V2_EXTRACTION, Path.cwd(), tmp_path / "absent-repeat")
    assert report["status"] == "complete"
    assert report["repeat_sample"]["status"] == "blocked"
    assert report["repeat_sample"]["blocked_reason"]
    assert report["repeat_sample"]["primary_detection_six_of_six_again"] is None


def test_repeat_allows_new_raw_output_with_identical_configuration(tmp_path: Path) -> None:
    """Permit model variation in the separate repeat while keeping requests fixed."""
    extraction = tmp_path / "repeat"
    copytree(V2_EXTRACTION, extraction)
    response_path = sorted((extraction / "responses").glob("*.json"))[0]
    response = read_json(response_path)
    response["output"]["records"].append({"plant_name_as_written": "repeat-only"})
    write_json(response_path, response)
    result = compare_proposal_samples(V2_EXTRACTION, extraction, False)
    assert result["status"] == "complete"
    assert result["all_requests_identical"] is True
    assert result["all_raw_model_outputs_identical"] is False


def test_renderer_has_four_columns_and_development_caveats() -> None:
    """Keep count-only output and the four data columns in each separate group."""
    report = build_glyph_comparison(V2_EXTRACTION, Path.cwd())
    text = render_glyph_summary(report)
    assert text.count("| baseline | v1 | v2 | v3 |") == 2
    assert "## PRIMARY" in text and "## CONTEXT" in text
    assert "implementers know the reference" in text
    assert "shared blind spots would inflate apparent recall" in text
    assert "repeat_sample_not_requested" in text
    assert "%" not in text
    assert "precision" not in text
    assert "validation" not in text.lower()
