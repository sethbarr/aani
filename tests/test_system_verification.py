"""Bounded local fixtures for replay integrity and scientific comparison failures."""

import base64
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.common.io import digest, read_json, write_json, write_jsonl
from src.systems import verification
from src.systems.config import load_system_config
from src.systems.extraction import validate_system_candidate
from src.systems.schema import SystemExtraction


def test_scientific_comparison_ignores_provenance_and_detects_count_drift(tmp_path: Path) -> None:
    """Permit documented offline metadata changes while failing changed scientific counts."""
    live, replay = tmp_path / "live.json", tmp_path / "replay.json"
    write_json(live, {"active": 2, "offline": False, "input_path": "live/rows",
                      "completed_at": "first", "nested": {"unknown": 3}})
    write_json(replay, {"active": 2, "offline": True, "input_path": "replay/rows",
                        "completed_at": "second", "nested": {"unknown": 3}})
    audit = verification.Audit(tmp_path)
    audit.compare(live, replay, "counts", scientific=True)
    assert audit.checks[-1]["status"] == "passed"
    value = read_json(replay)
    value["nested"]["unknown"] = 4
    write_json(replay, value)
    audit.compare(live, replay, "counts", scientific=True)
    assert audit.checks[-1]["status"] == "failed"


def test_missing_replay_cannot_equal_completed_empty_output(tmp_path: Path) -> None:
    """Distinguish a missing offline artifact from an actual empty JSONL result."""
    live, replay = tmp_path / "live.jsonl", tmp_path / "replay.jsonl"
    write_jsonl(live, [])
    audit = verification.Audit(tmp_path)
    audit.compare(live, replay, "records")
    assert audit.checks[-1]["status"] == "unavailable"
    write_jsonl(replay, [])
    audit.compare(live, replay, "records")
    assert audit.checks[-1]["status"] == "passed"
    assert audit.checks[-1]["live_records"] == audit.checks[-1]["replay_records"] == 0


def test_cache_filename_must_match_request_descriptor(tmp_path: Path) -> None:
    """Catch a cache whose filename and stored hash agree while its request was altered."""
    request = {"method": "GET", "url": "https://example.org/data", "params": {}, "json": None}
    key = digest(request)
    cache = tmp_path / "cache"
    write_json(cache / "http" / f"{key}.json", {
        "request": {**request, "url": "https://example.org/other"}, "request_hash": key,
        "attempts": [{"status": 200, "body_base64": base64.b64encode(b"{}").decode()}],
    })
    audit = verification.Audit(tmp_path)
    inventory, _ = verification.cache_inventory(audit, cache)
    assert len(inventory) == 1
    assert inventory[0]["sha256"]
    assert any(c["check"] == "cached_request_hash" and c["status"] == "failed"
               for c in audit.checks)


def test_corpus_detects_changed_text_despite_identical_manifest(tmp_path: Path) -> None:
    """Recompute text equality instead of trusting a previous replay assertion."""
    live, replay = tmp_path / "corpus", tmp_path / "replay"
    manifest = [{"source_id": "ONE", "status": "ready"}]
    for folder in (live, replay):
        write_jsonl(folder / "manifest.jsonl", manifest)
        write_json(folder / "texts/ONE.json", {
            "source_id": "ONE", "blocks": [{"block_id": "b1", "text": "Original"}],
        })
    write_json(replay / "texts/ONE.json", {
        "source_id": "ONE", "blocks": [{"block_id": "b1", "text": "Changed"}],
    })
    audit = verification.Audit(tmp_path)
    counts = verification.verify_corpus(audit, live, replay)
    assert counts["texts_compared"] == 1
    assert any(c["check"] == "corpus_text:ONE" and c["status"] == "failed"
               for c in audit.checks)


def source_fixture() -> tuple[dict, dict, object]:
    """Supply a fully valid quote-grounded system record for integrity mutations."""
    config = load_system_config(Path("config/systems/propolis.json"))
    candidate = {
        "behaving_organism_as_written": "Apis mellifera", "target_name_as_written": "Populus nigra",
        "taxonomic_rank": "species", "direction": "accept", "evidence_type": "observational",
        "quantitative_measure": None, "compound_name_as_written": None,
        "activity_target_as_written": None, "activity_outcome": "unknown", "source_id": "ONE",
        "section": "Results", "block_id": "b1", "evidence_quote": "Bees collected Populus nigra.",
        "extraction_confidence": 0.9, "behavioural_choice": True, "study_context": "field",
        "original_source_id": None,
    }
    job = {
        "system_slug": "propolis", "source_id": "ONE", "title": "Field study",
        "source_url": "https://example.org/one", "prompt": "Extract observations",
        "schema": SystemExtraction.model_json_schema(), "chunk_index": 0, "chunk_count": 1,
        "blocks": [{"block_id": "b1", "section": "Results", "text": candidate["evidence_quote"]}],
    }
    job["input_hash"] = digest(job)
    record, reason = validate_system_candidate(candidate, job, config, 0.8)
    assert reason is None
    return job, record, config


def test_semantic_copy_mutation_fails_without_repairing_raw(tmp_path: Path) -> None:
    """A reviewer may append fields but cannot silently rewrite model evidence."""
    job, record, config = source_fixture()
    original = tmp_path / "extraction/observations.jsonl"
    write_jsonl(original, [record])
    before = original.read_bytes()
    write_jsonl(tmp_path / "semantic_review/observations.jsonl", [
        {**record, "semantic_decision": "include", "direction": "unknown"},
    ])
    audit = verification.Audit(tmp_path)
    verification.verify_semantics(audit, tmp_path, [job], config)
    assert any(c["check"] == "retained_quote_grounding" and c["status"] == "passed"
               for c in audit.checks)
    assert any(c["check"] == "semantic_raw_fields_unchanged" and c["status"] == "failed"
               for c in audit.checks)
    assert original.read_bytes() == before


def test_payload_approval_cannot_cover_modified_source_blocks(tmp_path: Path) -> None:
    """Detect a payload with a valid digest and approval that differs from its source."""
    job, _, config = source_fixture()
    interim, results = tmp_path / "interim", tmp_path / "results"
    write_json(interim / "extraction_payloads/index.json", {"jobs": [{"input_hash": job["input_hash"]}]})
    write_json(interim / "extraction_payloads" / f"{job['input_hash']}.json", job)
    write_json(results / "payload_approval.json", {"approved": True, "input_hashes": [job["input_hash"]]})
    write_json(interim / "corpus/texts/ONE.json", {
        "source_id": "ONE", "blocks": [{"block_id": "b1", "section": "Results", "text": "Different."}],
    })
    audit = verification.Audit(tmp_path)
    verification.approved_jobs(audit, interim, results, config)
    assert any(c["check"] == "payload_hash" and c["status"] == "passed" for c in audit.checks)
    assert any(c["check"] == "payload_blocks_match_source" and c["status"] == "failed"
               for c in audit.checks)


def test_primary_checksum_drift_is_reported_and_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Report a changed primary input while leaving its bytes untouched."""
    for name in verification.FROZEN_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"frozen")
    target = tmp_path / "primary.json"
    target.write_bytes(b"changed")
    write_json(tmp_path / "results/funnel.json", {
        "input_manifests": [{"path": "primary.json", "sha256": hashlib.sha256(b"original").hexdigest()}],
    })
    monkeypatch.setattr(verification.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=0, stdout=b"frozen"))
    audit = verification.Audit(tmp_path)
    verification.verify_primary(audit)
    assert any(c["check"] == "primary_recorded_input_checksum" and c["status"] == "failed"
               for c in audit.checks)
    assert target.read_bytes() == b"changed"
