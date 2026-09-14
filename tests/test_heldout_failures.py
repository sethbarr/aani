"""Synthetic tests for post-score diagnostics without changing the v4 rule."""

from copy import deepcopy
from pathlib import Path

import pytest

from src.common.io import digest, read_json, write_json, write_jsonl
from src.evaluation.heldout_failures import (
    classify_heldout_failures,
    diagnose_span,
    diagnostic_mismatch_kind,
    failure_category,
    file_sha256,
)
from src.extraction.multispan_v4 import validate_multispan_v4_candidate
from tests.test_adaptive_glyph_grounding import adaptive_job
from tests.test_multispan_v4 import adaptive_candidate, adaptive_table_job


def rejected_span(quote: str) -> dict:
    """Return a synthetic primary quotation that the unchanged rule rejected."""
    return {
        "field": "evidence_quote", "index": None, "route": "rejected",
        "source_id": "GENERIC_SOURCE", "source_block": "table_17", "section": "Results",
        "emitted_quote": quote, "rejection_reason": "ungrounded_quote",
    }


def score_fixture(destination: Path) -> tuple[list[dict], Path]:
    """Create temporary saved proposals and a completed immutable score marker."""
    job = adaptive_table_job()
    job["chunk_index"] = 0
    job["input_hash"] = digest({key: value for key, value in job.items() if key != "input_hash"})
    candidate = adaptive_candidate()
    candidate["evidence_quote"] = "Hiraea fagifolia 0.01 \u0080 0.00"
    _, reason = validate_multispan_v4_candidate(candidate, job, 0.8)
    assert reason == "ungrounded_quote"
    write_json(destination / "run_manifest.json", {"input_hashes": [job["input_hash"]]})
    write_json(destination / "responses" / f"{job['input_hash']}.json", {
        "input_hash": job["input_hash"], "request_hash": "unchanged-request",
        "output": {"records": [candidate]},
    })
    write_jsonl(destination / "rejections.jsonl", [{
        "input_hash": job["input_hash"], "candidate": candidate, "reason": reason,
    }])
    write_jsonl(destination / "observations.jsonl", [])
    marker = destination / "score.json"
    names = ["run_manifest.json", "rejections.jsonl", "observations.jsonl", f"responses/{job['input_hash']}.json"]
    write_json(marker, {
        "status": "complete",
        "sample3_v4": {"status": "complete", "files": [
            {"path": str(destination / name), "sha256": file_sha256(destination / name)}
            for name in names
        ]},
    })
    return [job], marker


@pytest.mark.parametrize(("model", "source", "kind"), [
    ("\u0080", "±", "unresolved_control_glyph"),
    ("\u0007", "∓", "unresolved_control_glyph"),
    ("∓", "±", "printable_unicode_substitution"),
    ("=", "¼", "printable_unicode_substitution"),
    ("1", "¼", None), ("q", "±", None), ("∓", "a", None),
    ("\u0007", "7", None), ("-", "+", None), ("\t", "±", None),
])
def test_diagnostic_mismatch_scope(model: str, source: str, kind: str | None) -> None:
    """Exclude changes to ASCII numbers, letters, and unrelated ASCII symbols."""
    assert diagnostic_mismatch_kind(model, source) == kind


def test_unique_source_evidence_has_codepoints_and_raw_offsets() -> None:
    """Retain exact cached glyphs through the existing whitespace normalization."""
    job = adaptive_job("Header\n N ¼ 3;\tmean ± error.")
    span = rejected_span("N = 3;\nmean \u0080 error.")
    result = diagnose_span(span, job)
    assert result["status"] == "attributed"
    evidence = result["evidence"]
    assert evidence["matched_source_quote"] == "N ¼ 3;\tmean ± error."
    assert evidence["emitted_quote"] == span["emitted_quote"]
    assert evidence["applied_to_validator"] is False
    first, second = evidence["replacements"]
    assert (first["model_codepoint"], first["source_codepoint"]) == ("U+003D", "U+00BC")
    assert (second["model_codepoint"], second["source_codepoint"]) == ("U+0080", "U+00B1")
    assert span["emitted_quote"][second["model_offset"]] == "\u0080"
    assert job["blocks"][0]["text"][second["source_offset"]] == "±"
    assert "model_character_outside_non_whitespace_c0" in second["v4_policy_or_guard_reasons"]


@pytest.mark.parametrize("quote", ["N = 4", "N a 3", "M = 3", "N ¼ 3"])
def test_changed_numbers_words_or_exact_quotes_have_no_attribution(quote: str) -> None:
    """Avoid claiming a glyph defect where additional edits prevent exact alignment."""
    assert diagnose_span(rejected_span(quote), adaptive_job("N ¼ 3"))["evidence"] is None


def test_ambiguous_alignment_does_not_claim_an_exact_replacement() -> None:
    """Report both possible alignments without choosing their different glyphs."""
    result = diagnose_span(rejected_span("N \u0080 3"), adaptive_job("N ¼ 3 and N ± 3"))
    assert result["status"] == "ambiguous"
    assert result["alignment_count"] == 2
    assert result["evidence"] is None


def test_policy_guard_diagnostic_preserves_frozen_rule() -> None:
    """Identify a cached glyph outside the whitelist without granting equivalence."""
    job = adaptive_job("N ∓ 3")
    result = diagnose_span(rejected_span("N \u0007 3"), job)
    replacement = result["evidence"]["replacements"][0]
    assert "cached_glyph_outside_source_whitelist" in replacement["v4_policy_or_guard_reasons"]


def test_classification_requires_score_and_preserves_every_input(tmp_path: Path) -> None:
    """Read only scored bytes and retain candidate order and downstream uncertainty."""
    jobs, score_path = score_fixture(tmp_path)
    original_jobs = deepcopy(jobs)
    original_hashes = {str(path): file_sha256(path) for path in tmp_path.rglob("*") if path.is_file()}
    report = classify_heldout_failures(tmp_path, jobs, score_path)
    assert report["status"] == "complete"
    assert report["candidate_records_seen"] == report["rejected_records"] == 1
    assert report["category_counts"] == {
        "unresolved_control_glyph": 1, "printable_unicode_substitution": 0,
        "identity": 0, "name_surface": 0, "other": 0,
    }
    assert report["records"][0]["later_non_quote_gates_adjudicated"] is False
    assert report["first_failure_substitutions"][0]["model_codepoint"] == "U+0080"
    assert jobs == original_jobs
    assert all(file_sha256(Path(path)) == value for path, value in original_hashes.items())


@pytest.mark.parametrize("mutation", ["status", "missing_hash", "changed_input", "missing_response"])
def test_missing_or_changed_scored_inputs_block_diagnostics(tmp_path: Path, mutation: str) -> None:
    """Refuse post-score inspection when the saved score is absent or inconsistent."""
    jobs, score_path = score_fixture(tmp_path)
    marker = read_json(score_path)
    if mutation == "status":
        marker["status"] = "blocked"
    elif mutation == "missing_hash":
        marker["sample3_v4"]["files"] = [
            item for item in marker["sample3_v4"]["files"]
            if not item["path"].endswith("rejections.jsonl")
        ]
    elif mutation == "changed_input":
        write_jsonl(tmp_path / "rejections.jsonl", [])
    else:
        (tmp_path / "responses" / f"{jobs[0]['input_hash']}.json").unlink()
    write_json(score_path, marker)
    report = classify_heldout_failures(tmp_path, jobs, score_path)
    assert report["status"] == "blocked"
    assert report["blocked_reason"]
    assert report["records"] == []


@pytest.mark.parametrize(("reason", "category"), [
    ("ant_identity_mismatch", "identity"),
    ("unabbreviated_genus_required", "identity"),
    ("name_surface_not_in_quote", "name_surface"),
    ("plant_not_in_name_evidence", "name_surface"),
    ("low_confidence", "other"), ("unknown_source_or_block", "other"),
])
def test_first_failure_category_does_not_infer_later_gates(reason: str, category: str) -> None:
    """Follow the recorded ordered gate even when no quote diagnostic is applicable."""
    assert failure_category(reason, None) == category
