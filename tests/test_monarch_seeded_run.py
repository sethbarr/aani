"""Exercise approved seeded extraction using synthetic cached responses and zero network calls."""

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.chemistry.export_cache import file_hash
from src.common.cache import CachedHTTP
from src.common.io import digest, read_json, read_jsonl, write_json, write_jsonl
from src.systems import monarch_seeded_run as runner
from src.systems.config import load_system_config
from src.systems.extraction import export_system_jobs, make_system_jobs
from src.systems.monarch_seeded_prepare import prepare_seeded_monarch


def corpus_row(source_id: str) -> dict:
    """Create a source identifier and complete retrieval provenance for test payloads."""
    return {"source_id": source_id, "title": source_id, "status": "ready",
            "doi": f"10.1000/{source_id}", "source_url": f"https://example.org/{source_id}",
            "retrieved_at": datetime.now(UTC).isoformat()}


def corpus_text(row: dict) -> dict:
    """Provide a contiguous quote compatible with the existing single-quote schema."""
    return {"source_id": row["source_id"], "blocks": [{
        "source_id": row["source_id"], "block_id": "b00000", "section": "Body",
        "kind": "p", "text": "Females preferred Asclepias curassavica in the choice test.",
    }]}


def candidate_for_job(job: dict) -> dict:
    """Build a valid model candidate requiring no special grounding normalization."""
    return {
        "behaving_organism_as_written": "Danaus plexippus",
        "target_name_as_written": "Asclepias curassavica", "taxonomic_rank": "species",
        "direction": "accept", "evidence_type": "lab_choice_assay", "quantitative_measure": None,
        "compound_name_as_written": None, "activity_target_as_written": None,
        "activity_outcome": "unknown", "source_id": job["source_id"],
        "section": job["blocks"][0]["section"], "block_id": job["blocks"][0]["block_id"],
        "evidence_quote": "Females preferred Asclepias curassavica in the choice test.",
        "extraction_confidence": 0.95, "behavioural_choice": True,
        "study_context": "Explicit choice experiment", "original_source_id": None,
    }


def cached_envelope(job: dict, cache_path: Path) -> dict:
    """Create a synthetic response and its request-keyed raw HTTP cache entry."""
    descriptor = {"method": "POST", "url": "https://example.org/synthetic-model",
                  "params": {}, "json": {"input_hash": job["input_hash"]}}
    key = digest(descriptor)
    output = {"records": [candidate_for_job(job)]}
    write_json(cache_path / "http" / f"{key}.json", {
        "request": descriptor, "request_hash": key, "attempts": [{
            "status": 200, "body_base64": base64.b64encode(json.dumps(output).encode()).decode(),
        }],
    })
    return {"input_hash": job["input_hash"], "engine": "gemini-3.8-flash",
            "resolved_model": "gemini-3.8-flash", "provider": "gemini",
            "request_hash": key, "output": output}


def provider_stub(job: dict, cache: CachedHTTP, model: str, provider: str) -> dict:
    """Permit a provider invocation solely for the newly supplied seed test source."""
    assert job["source_id"] == "PMCseed"
    assert model == "gemini-3.8-flash" and provider == "gemini"
    assert cache.offline is False
    return cached_envelope(job, cache.root)


@pytest.fixture
def execution_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Prepare a twenty-source original corpus, two old responses, and one new seed job."""
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("EXTRACTION_PROVIDER", "gemini")
    config_path = tmp_path / "config/systems/monarch.json"
    write_json(config_path, read_json(Path("config/systems/monarch.json")))
    write_json(tmp_path / "config/analysis.json", read_json(Path("config/analysis.json")))
    original = tmp_path / "data/interim/systems/monarch"
    rows = [corpus_row(f"PMC{index}") for index in range(20)]
    write_jsonl(original / "corpus/manifest.jsonl", rows)
    for row in rows:
        write_json(original / "corpus/texts" / f"{row['source_id']}.json", corpus_text(row))
    write_json(original / "screening.json", {"decisions": [
        {"source_id": row["source_id"], "decision": "include" if index < 2 else "exclude",
         "reason": "Recorded original source decision."} for index, row in enumerate(rows)
    ]})
    config = load_system_config(config_path)
    jobs, metrics = make_system_jobs(config, original / "corpus", original / "screening.json")
    export_system_jobs(jobs, original / "extraction_payloads", metrics)
    for job in jobs:
        write_json(original / "extraction/responses" / f"{job['input_hash']}.json",
                   cached_envelope(job, original / "cache"))
    write_json(original / "extraction/run_manifest.json", {
        "model": "gemini-3.8-flash", "provider": "gemini", "grounding_version": "single_quote_v1",
    })
    write_json(tmp_path / "results/systems/monarch/run_manifest.json", {
        "config": {"sha256": file_hash(config_path)},
    })
    targeted = tmp_path / "data/interim/systems/monarch_seeded/corpus_targeted_monarch"
    seed = {**corpus_row("PMCseed"), "bibliography_verified": True,
            "indexed_doi": "10.1000/PMCseed"}
    write_jsonl(targeted / "manifest.jsonl", [seed])
    write_json(targeted / "texts/PMCseed.json", corpus_text(seed))
    write_json(targeted / "metrics.json", {"started_at": datetime.now(UTC).isoformat()})
    write_json(targeted / "screening.json", {"decisions": [
        {"source_id": "PMCseed", "decision": "include", "reason": "Focal choice design."},
    ]})
    prepare_seeded_monarch(tmp_path)
    return tmp_path


def approve(root: Path) -> list[dict]:
    """Approve the exact prepared job order and its explicit reuse/new-source subsets."""
    live = root / "data/interim/systems/monarch_seeded"
    index = read_json(live / "extraction_payloads/index.json")
    write_json(root / "results/systems/monarch_seeded/payload_approval.json", {
        "approved": True, "input_hashes": [row["input_hash"] for row in index["jobs"]],
        "new_seed_input_hashes": [row["input_hash"] for row in index["jobs"]
                                  if row["source_id"] == "PMCseed"],
        "reused_discovery_input_hashes": [row["input_hash"] for row in index["jobs"]
                                          if row["source_id"] != "PMCseed"],
    })
    return [read_json(live / "extraction_payloads" / f"{row['input_hash']}.json")
            for row in index["jobs"]]


def test_no_approval_prevents_all_requests_and_execution_writes(
    execution_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stop before cache acquisition or output creation unless export is explicitly approved."""
    provider = Mock(side_effect=AssertionError("Unapproved request"))
    monkeypatch.setattr(runner, "request_extraction", provider)
    with pytest.raises(ValueError, match="explicit_seeded_payload_export_approval_required"):
        runner.run_seeded_extraction(execution_root)
    provider.assert_not_called()
    assert not (execution_root / "data/interim/systems/monarch_seeded/extraction").exists()


def test_approval_must_match_exact_job_order(execution_root: Path) -> None:
    """Reject an approval that omits or reorders one prepared job."""
    approve(execution_root)
    path = execution_root / "results/systems/monarch_seeded/payload_approval.json"
    approval = read_json(path)
    approval["input_hashes"].reverse()
    write_json(path, approval)
    with pytest.raises(ValueError, match="exact_ordered_prepared_input_hashes"):
        runner.run_seeded_extraction(execution_root)


def test_only_seed_provider_call_and_exact_discovery_import(
    execution_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Import original discovery responses and ground all three jobs through the shared adapter."""
    jobs = approve(execution_root)
    provider = Mock(side_effect=provider_stub)
    monkeypatch.setattr(runner, "request_extraction", provider)
    original = execution_root / "data/interim/systems/monarch"
    original_bytes = (original / "extraction/run_manifest.json").read_bytes()
    report = runner.run_seeded_extraction(execution_root)
    assert report["status"] == "complete"
    assert report["metrics"]["complete_jobs"] == report["metrics"]["retained_records"] == 3
    assert report["metrics"]["reused_discovery_jobs"] == 2
    assert report["metrics"]["seed_jobs_with_responses"] == 1
    assert report["metrics"]["persisted_new_response_attempts"] == 1
    provider.assert_called_once()
    cache = Path(report["cache_path"])
    for job in jobs[1:]:
        name = f"{job['input_hash']}.json"
        assert (cache / "envelopes" / name).read_bytes() == (
            original / "extraction/responses" / name
        ).read_bytes()
    candidates = read_jsonl(Path(report["raw_candidates_path"]))
    assert len(candidates) == 3
    assert candidates[0]["candidate"] == candidate_for_job(jobs[0])
    assert (original / "extraction/run_manifest.json").read_bytes() == original_bytes


def test_offline_replay_reuses_envelopes_and_preserves_import_provenance(
    execution_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replay stable extraction records without provider calls or changing initial provenance."""
    jobs = approve(execution_root)
    monkeypatch.setattr(runner, "request_extraction", provider_stub)
    live = runner.run_seeded_extraction(execution_root)
    provenance = Path(live["cache_path"]) / "envelope_provenance" / f"{jobs[1]['input_hash']}.json"
    provenance_bytes = provenance.read_bytes()
    observations = Path(live["output_path"]) / "observations.jsonl"
    live_bytes = observations.read_bytes()
    provider = Mock(side_effect=AssertionError("Offline provider call"))
    monkeypatch.setattr(runner, "request_extraction", provider)
    replay = runner.run_seeded_extraction(execution_root, offline=True)
    assert replay["status"] == "complete"
    assert (Path(replay["output_path"]) / "observations.jsonl").read_bytes() == live_bytes
    assert observations.read_bytes() == live_bytes
    assert provenance.read_bytes() == provenance_bytes
    assert replay["metrics"]["persisted_new_response_attempts"] == 0
    provider.assert_not_called()


def test_invalid_cached_envelope_cannot_reach_shared_grounder(
    execution_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exclude a wrong-model envelope even when its source and input hash match."""
    jobs = approve(execution_root)
    cache = execution_root / "data/interim/systems/monarch_seeded/cache/extraction"
    bad = cached_envelope(jobs[0], cache)
    bad["engine"] = "different-model"
    write_json(cache / "envelopes" / f"{jobs[0]['input_hash']}.json", bad)
    provider = Mock(side_effect=AssertionError("Invalid cache must not trigger a new request"))
    monkeypatch.setattr(runner, "request_extraction", provider)
    report = runner.run_seeded_extraction(execution_root)
    assert report["status"] == "partial"
    assert report["metrics"]["retained_records"] == 2
    assert report["metrics"]["response_acquisition_failures"] == 1
    assert {row["source_id"] for row in read_jsonl(Path(report["output_path"]) / "observations.jsonl")} == {
        "PMC0", "PMC1",
    }
    provider.assert_not_called()


def test_missing_seed_offline_cache_preserves_discovery_results(
    execution_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep a missing seed response unavailable while importing approved discovery caches."""
    approve(execution_root)
    client = Mock(side_effect=AssertionError("Offline HTTP transport call"))
    monkeypatch.setattr(runner.httpx.Client, "request", client)
    report = runner.run_seeded_extraction(execution_root, offline=True)
    assert report["status"] == "partial"
    assert report["metrics"]["complete_jobs"] == 2
    assert report["metrics"]["seed_jobs_with_responses"] == 0
    assert "OfflineCacheMiss" in report["response_acquisition"][0]["blocked_reason"]
    client.assert_not_called()


def test_explicit_source_cohort_approval_is_validated(execution_root: Path) -> None:
    """Reject an approval that mislabels a new seed as a reused original response."""
    approve(execution_root)
    path = execution_root / "results/systems/monarch_seeded/payload_approval.json"
    approval = read_json(path)
    approval["new_seed_input_hashes"] = []
    write_json(path, approval)
    with pytest.raises(ValueError, match="approval_source_cohort_subset_mismatch"):
        runner.run_seeded_extraction(execution_root)


def test_whole_source_and_twelve_job_cap_guards(execution_root: Path) -> None:
    """Prevent partial papers and expanded extraction batches independently of preparation."""
    jobs = approve(execution_root)
    partial = {**jobs[0], "chunk_count": 2}
    partial["input_hash"] = digest({key: value for key, value in partial.items() if key != "input_hash"})
    with pytest.raises(ValueError, match="complete_source_chunk_groups"):
        runner.validate_job_selection([partial], 12)
    with pytest.raises(ValueError, match="one_to_twelve_jobs"):
        runner.validate_job_selection([jobs[0]] * 13, 20)


def test_environment_model_change_requires_explicit_resolution(
    execution_root: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep environment settings from silently changing the approved original model."""
    approve(execution_root)
    monkeypatch.setenv("GEMINI_MODEL", "different-model")
    with pytest.raises(ValueError, match="environment_model_differs"):
        runner.run_seeded_extraction(execution_root)
