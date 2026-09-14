"""Keep repeat glyph diagnostics separate from the unchanged v3 validator."""

from copy import deepcopy
from pathlib import Path

import pytest

from src.common.io import write_json, write_jsonl
from src.evaluation.repeat_failures import (
    classify_repeat_failures,
    diagnose_unpermitted_span,
    failure_category,
)
from src.extraction.multispan_v3 import validate_multispan_v3_candidate
from tests.test_glyph_grounding import glyph_job
from tests.test_multispan_v3 import table_candidate, table_job


def rejected_span(quote: str) -> dict:
    """Create a quote-audit entry for a synthetic rejected table span."""
    return {
        "field": "evidence_quote", "index": None, "route": "rejected",
        "source_id": "SAVERSCHEK2010", "source_block": "b00005", "section": "Results",
        "emitted_quote": quote, "rejection_reason": "ungrounded_quote",
    }


def extraction_fixture(destination: Path) -> list[dict]:
    """Write new temporary fixture artifacts with one independently rejected span."""
    job = table_job()
    job["chunk_index"] = 0
    candidate = table_candidate()
    candidate["evidence_quote"] = "Hiraea fagifolia 0.01 \u0011 0.00"
    _, reason = validate_multispan_v3_candidate(candidate, job, 0.8)
    write_json(destination / "run_manifest.json", {"input_hashes": [job["input_hash"]]})
    write_json(destination / "responses" / f"{job['input_hash']}.json", {
        "input_hash": job["input_hash"], "request_hash": "same-request",
        "output": {"records": [candidate]},
    })
    write_jsonl(destination / "rejections.jsonl", [{
        "input_hash": job["input_hash"], "candidate": candidate, "reason": reason,
    }])
    return [job]


def test_diagnostic_logs_raw_offsets_and_exact_codepoint_evidence() -> None:
    """Retain raw offsets through whitespace normalization and both observed pairs."""
    job = glyph_job("Header\n N ¼ 3;\tmean ± error.")
    span = rejected_span("N \u0010 3;\nmean \u0011 error.")
    result = diagnose_unpermitted_span(span, job)
    assert result is not None
    assert result["matched_source_quote"] == "N ¼ 3;\tmean ± error."
    assert result["start"] == 8
    assert result["permitted_by_v3"] is False
    assert result["applied_to_validator"] is False
    assert result["all_other_normalized_characters_exact"] is True
    first, second = result["replacements"]
    assert (first["model_codepoint"], first["source_codepoint"]) == ("U+0010", "U+00BC")
    assert (second["model_codepoint"], second["source_codepoint"]) == ("U+0011", "U+00B1")
    assert job["blocks"][0]["text"][first["source_offset"]] == "¼"
    assert span["emitted_quote"][second["model_offset"]] == "\u0011"
    assert first["model_utf8_hex"] == "10"
    assert second["source_utf8_hex"] == "c2b1"


@pytest.mark.parametrize("quote", [
    "N \u0010 4; mean \u0011 error.",
    "N \u0010 3; median \u0011 error.",
    "N \u0012 3; mean \u0011 error.",
    "N \u0003 3; mean \u0011 error.",
    "N ¼ 3; mean ± error.",
])
def test_other_changes_and_existing_policy_pairs_do_not_support_attribution(quote: str) -> None:
    """Permit no extra edit, broad fuzzy alignment, or silent policy union."""
    assert diagnose_unpermitted_span(rejected_span(quote), glyph_job("N ¼ 3; mean ± error.")) is None


def test_ambiguous_alignment_and_wrong_block_hash_remain_unattributed() -> None:
    """Require unique diagnostic correspondence within the hash-pinned block."""
    span = rejected_span("N \u0010 3")
    assert diagnose_unpermitted_span(span, glyph_job("N ¼ 3 and N ¼ 3")) is None
    job = glyph_job("N ¼ 3")
    job["blocks"][0]["text"] += " changed"
    assert diagnose_unpermitted_span(span, job) is None


def test_diagnostic_never_changes_candidate_job_or_validator_decision(tmp_path: Path) -> None:
    """Keep observed repeat substitutions unpermitted after diagnostic attribution."""
    jobs = extraction_fixture(tmp_path)
    original = deepcopy(jobs)
    report = classify_repeat_failures(tmp_path, jobs)
    assert jobs == original
    assert report["status"] == "complete"
    assert report["category_counts"] == {
        "glyph_substitution_not_covered": 1, "identity": 0, "name_surface": 0, "other": 0,
    }
    assert report["ordered_failure_reason_counts"] == {"ungrounded_quote": 1}
    assert report["unpermitted_substitutions"] == [{
        "model_codepoint": "U+0011", "source_codepoint": "U+00B1",
        "records": 1, "occurrences": 1, "permitted_by_v3": False,
    }]
    candidate = table_candidate()
    candidate["evidence_quote"] = "Hiraea fagifolia 0.01 \u0011 0.00"
    assert validate_multispan_v3_candidate(candidate, jobs[0], 0.8) == (None, "ungrounded_quote")


def test_missing_proposals_produce_explicit_blocked_reason(tmp_path: Path) -> None:
    """Return a blocked result for missing saved response artifacts."""
    report = classify_repeat_failures(tmp_path, [])
    assert report["status"] == "blocked"
    assert "FileNotFoundError" in report["blocked_reason"]


def test_job_mismatch_produces_explicit_blocked_reason(tmp_path: Path) -> None:
    """Reject an extraction whose manifest does not match supplied jobs."""
    jobs = extraction_fixture(tmp_path)
    jobs[0]["input_hash"] = "different-job"
    report = classify_repeat_failures(tmp_path, jobs)
    assert report["status"] == "blocked"
    assert "Manifest job order or input hashes differ" in report["blocked_reason"]


@pytest.mark.parametrize(("reason", "category"), [
    ("ant_identity_mismatch", "identity"),
    ("unabbreviated_genus_required", "identity"),
    ("plant_not_in_name_evidence", "name_surface"),
    ("name_surface_not_in_quote", "name_surface"),
    ("low_confidence", "other"),
    ("ungrounded_quote", "other"),
])
def test_non_glyph_categories_follow_the_first_ordered_reason(reason: str, category: str) -> None:
    """Classify an actual gate without making claims about unvisited later gates."""
    assert failure_category(reason, None) == category
