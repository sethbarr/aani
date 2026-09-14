"""Exercise the predeclared v6 diagnostic audit entirely with synthetic input."""

from copy import deepcopy
from pathlib import Path

import pytest

from src.common.io import digest, read_json, timestamp, write_json, write_jsonl
from src.evaluation.cache_control_failures import (
    classify_failures,
    diagnose_span,
    diagnostic_kind,
    failure_category,
)
from src.evaluation.heldout_failures import file_sha256


def fixture_job(text: str) -> dict:
    """Create an unrelated source block without reference-panel content."""
    job = {"source_id": "INVENTED_SOURCE", "chunk_index": 0,
           "blocks": [{"block_id": "invented_block", "section": "Results", "text": text}]}
    return {**job, "input_hash": digest(job)}


def fixture_span(quote: str) -> dict:
    """Create a saved failed span with original emitted text."""
    return {"field": "evidence_quote", "index": None, "route": "rejected",
            "source_id": "INVENTED_SOURCE", "source_block": "invented_block",
            "section": "Results", "emitted_quote": quote, "rejection_reason": "ungrounded_quote"}


def score_fixture(folder: Path, copies: int = 1) -> tuple[list[dict], Path]:
    """Save synthetic proposals, failures, quote audits, and a completed hashed score."""
    job = fixture_job("prefix value \u0002 suffix")
    quote = "prefix value 7 suffix"
    candidate = {"source_id": job["source_id"], "plant_name_as_written": "Invented species",
                 "outcome": "rejected", "evidence_quote": quote}
    path = folder / "responses" / f"{job['input_hash']}.json"
    write_json(path, {"input_hash": job["input_hash"], "request_hash": "invented_request",
                      "output": {"records": [candidate] * copies}})
    write_json(folder / "run_manifest.json", {"input_hashes": [job["input_hash"]]})
    write_jsonl(folder / "observations.jsonl", [])
    write_jsonl(folder / "rejections.jsonl", [{"input_hash": job["input_hash"],
                                             "candidate": candidate,
                                             "reason": "ungrounded_quote"}] * copies)
    audit = [{"input_hash": job["input_hash"], "candidate_index": index,
              "raw_candidate_hash": digest(candidate), "survived": False,
              "rejection_reason": "ungrounded_quote", "spans": [fixture_span(quote)]}
             for index in range(copies)]
    write_jsonl(folder / "glyph_grounding_audit.jsonl", audit)
    files = [folder / name for name in ("run_manifest.json", "observations.jsonl", "rejections.jsonl")]
    files.append(path)
    score = {
        "status": "complete", "score_completed_at": timestamp(),
        "failure_candidates_inspected_before_scoring": False,
        "sample4_audit_sha256": file_sha256(folder / "glyph_grounding_audit.jsonl"),
        "sample4_v6": {
            "status": "complete", "files": [{"path": str(item), "sha256": file_sha256(item)}
                                            for item in files],
            "failure_reasons": {"all_candidates": {"ungrounded_quote": copies}},
            "inventory": {"candidate_records": copies, "grounding_failures": copies},
        },
    }
    marker = folder / "scores.json"
    write_json(marker, score)
    return [job], marker


@pytest.mark.parametrize(("model", "source", "kind"), [
    ("-", "\u0002", "unresolved_cache_control"),
    ("7", "\u0002", "unresolved_cache_control"),
    ("r", "\u0002", "unresolved_cache_control"),
    ("\u0007", "±", "unresolved_model_control"),
    ("\u0080", "1", "unresolved_model_control"),
    ("=", "¼", "printable_substitution"),
    ("－", "-", "printable_substitution"),
    ("1", "¼", "printable_substitution"),
    ("-", "+", None), ("1", "2", None), ("a", "b", None),
    ("\t", "±", None), ("-", "\n", None), ("-", "-", None),
])
def test_diagnostic_classes_grant_no_permission(model: str, source: str, kind: str | None) -> None:
    """Report excluded digits and letters as observations while preserving rule scope."""
    assert diagnostic_kind(model, source) == kind


def test_cache_control_evidence_preserves_exact_offsets_and_bytes() -> None:
    """Record raw cache controls and emitted glyph bytes through whitespace normalization."""
    job = fixture_job("Header\n word\u0002related\tvalue.")
    span = fixture_span("word-related value.")
    result = diagnose_span(span, job)
    assert result["status"] == "attributed"
    assert result["alignment_count"] == 1
    evidence = result["evidence"]
    change = evidence["replacements"][0]
    assert change["model_codepoint"] == "U+002D"
    assert change["source_codepoint"] == "U+0002"
    assert change["model_utf8_hex"] == "2d"
    assert change["source_utf8_hex"] == "02"
    assert span["emitted_quote"][change["model_offset"]] == "-"
    assert job["blocks"][0]["text"][change["source_offset"]] == "\u0002"
    assert evidence["matched_source_quote"] == "word\u0002related\tvalue."
    assert evidence["validator_permission_inferred"] is False
    assert evidence["all_other_normalized_characters_exact"] is True


def test_mixed_multiple_substitutions_are_diagnostic_only() -> None:
    """Count every observed mismatch without expanding the single-position validator."""
    result = diagnose_span(fixture_span("left-r \u0007 end"), fixture_job("left\u0002r ± end"))
    assert result["status"] == "attributed"
    assert result["evidence"]["differing_positions"] == 2
    assert result["evidence"]["applied_to_validator"] is False
    assert {row["kind"] for row in result["evidence"]["replacements"]} == {
        "unresolved_cache_control", "unresolved_model_control",
    }


@pytest.mark.parametrize(("quote", "source", "status"), [
    ("left-right", "left\u0002right left\u0003right", "ambiguous"),
    ("left-right 2", "left\u0002right 1", "unattributed"),
    ("left-right", "left-right", "unattributed"),
    ("left-right", "left\u0002right now", "attributed"),
])
def test_ambiguity_and_other_edits_prevent_attribution(quote: str, source: str, status: str) -> None:
    """Require a unique equal-length source alignment with exact other characters."""
    result = diagnose_span(fixture_span(quote), fixture_job(source))
    assert result["status"] == status
    if status != "attributed":
        assert result["evidence"] is None


def test_saved_score_and_audit_reconcile_and_preserve_all_inputs(tmp_path: Path) -> None:
    """Use existing audited fields without invoking the validator or changing raw proposals."""
    jobs, marker = score_fixture(tmp_path)
    original_jobs = deepcopy(jobs)
    hashes = {str(path): file_sha256(path) for path in tmp_path.rglob("*") if path.is_file()}
    report = classify_failures(tmp_path, jobs, marker)
    assert report["status"] == "complete"
    assert report["candidate_records_seen"] == report["rejected_records"] == 1
    assert report["category_counts"]["unresolved_cache_control"] == 1
    assert sum(report["category_counts"].values()) == 1
    assert report["ordered_failure_reason_counts"] == {"ungrounded_quote": 1}
    assert report["records"][0]["later_non_quote_gates_adjudicated"] is False
    assert report["validator_rerun"] is False
    assert report["records"][0]["first_failure_span"]["diagnostic"]["evidence"]["replacements"][0][
        "model_unicode_category"] == "Nd"
    assert report["score_completed_at"] <= report["audit_started_at"]
    assert report["score_sha256"] == file_sha256(marker)
    assert jobs == original_jobs
    assert all(file_sha256(Path(path)) == before for path, before in hashes.items())


def test_identical_raw_records_are_counted_once_per_proposal(tmp_path: Path) -> None:
    """Preserve two distinct candidate indices even when their raw record hashes match."""
    jobs, marker = score_fixture(tmp_path, copies=2)
    report = classify_failures(tmp_path, jobs, marker)
    assert report["status"] == "complete"
    assert report["rejected_records"] == 2
    assert [row["candidate_index"] for row in report["records"]] == [0, 1]


@pytest.mark.parametrize("mutation", [
    "status", "timestamp", "inspection", "missing_audit_hash", "changed_audit", "changed_response",
    "changed_job", "reason_count", "candidate_count",
])
def test_missing_or_changed_score_evidence_blocks_audit(tmp_path: Path, mutation: str) -> None:
    """Refuse classification whenever the saved score or any bound input is inconsistent."""
    jobs, marker = score_fixture(tmp_path)
    score = read_json(marker)
    if mutation == "status":
        score["status"] = "blocked"
    elif mutation == "timestamp":
        score.pop("score_completed_at")
    elif mutation == "inspection":
        score.pop("failure_candidates_inspected_before_scoring")
    elif mutation == "missing_audit_hash":
        score.pop("sample4_audit_sha256")
    elif mutation == "changed_audit":
        write_jsonl(tmp_path / "glyph_grounding_audit.jsonl", [])
    elif mutation == "changed_response":
        write_json(tmp_path / "responses" / f"{jobs[0]['input_hash']}.json", {})
    elif mutation == "changed_job":
        jobs[0]["blocks"][0]["text"] += "modified"
    elif mutation == "reason_count":
        score["sample4_v6"]["failure_reasons"]["all_candidates"] = {}
    else:
        score["sample4_v6"]["inventory"]["candidate_records"] = 2
    write_json(marker, score)
    report = classify_failures(tmp_path, jobs, marker)
    assert report["status"] == "blocked"
    assert report["blocked_reason"]
    assert report["records"] == []


@pytest.mark.parametrize(("reason", "category"), [
    ("invalid_exact_name_link", "identity"), ("ant_requires_review", "identity"),
    ("name_surface_not_in_quote", "name_surface"), ("low_confidence", "other"),
])
def test_recorded_identity_and_surface_gates_keep_their_classes(reason: str, category: str) -> None:
    """Classify each recorded first gate without inferring later outcomes."""
    assert failure_category(reason, None) == category
