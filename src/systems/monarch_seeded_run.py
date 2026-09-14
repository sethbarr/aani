"""Execute explicitly approved seeded-monarch jobs with exact discovery response reuse."""

import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from src.chemistry.export_cache import file_hash
from src.common.cache import CachedHTTP
from src.common.environment import load_local_environment
from src.common.io import digest, read_json, timestamp, write_json, write_jsonl
from src.extraction.errors import ExtractionServiceUnavailable
from src.extraction.pipeline import request_extraction
from src.systems.config import SystemConfig, load_system_config
from src.systems.downstream import SystemDeadlineExceeded, bounded_stage, isolated_path
from src.systems.extraction import make_system_jobs, run_system_extraction
from src.systems.monarch_seeded_downstream import seeded_paths
from src.systems.monarch_seeded_prepare import (
    MAXIMUM_CHARACTERS,
    adapter_compatibility,
    validate_preparation_contract,
    verified_copy,
)

ACQUISITION_ERRORS = (OSError, ValueError, KeyError, TypeError, RuntimeError, httpx.HTTPError)


def validate_job_selection(jobs: list[dict], limit: int) -> None:
    """Require unique intact payloads and complete source chunk groups below the cap."""
    if not jobs or len(jobs) > min(limit, 12):
        raise ValueError("seeded_selection_requires_one_to_twelve_jobs")
    hashes: set[str] = set()
    groups: dict[str, list[dict]] = {}
    for job in jobs:
        if job["input_hash"] in hashes or digest({
            key: value for key, value in job.items() if key != "input_hash"
        }) != job["input_hash"]:
            raise ValueError("duplicate_or_invalid_seeded_payload_hash")
        hashes.add(job["input_hash"])
        if job.get("system_slug") != "monarch" or job.get("grounding_version") != "single_quote_v1":
            raise ValueError("seeded_selection_requires_original_monarch_single_quote_adapter")
        groups.setdefault(job["source_id"], []).append(job)
    for chunks in groups.values():
        counts = {job["chunk_count"] for job in chunks}
        if len(counts) != 1 or counts != {len(chunks)} or {
            job["chunk_index"] for job in chunks
        } != set(range(len(chunks))):
            raise ValueError("seeded_selection_requires_complete_source_chunk_groups")


def approved_jobs(paths: dict[str, Path]) -> tuple[SystemConfig, list[dict], dict, dict[str, str], dict]:
    """Validate approval against every exact prepared payload before creating execution files."""
    approval_path = paths["root"] / "results/systems/monarch_seeded/payload_approval.json"
    if not approval_path.is_file() or read_json(approval_path).get("approved") is not True:
        raise ValueError("explicit_seeded_payload_export_approval_required")
    approval = read_json(approval_path)
    preparation = read_json(paths["root"] / "results/systems/monarch_seeded/preparation.json")
    if preparation.get("payloads_prepared") is not True or preparation.get("blocked_reason"):
        raise ValueError("seeded_preparation_must_be_complete_before_execution")
    config = load_system_config(paths["config"])
    validate_preparation_contract(config)
    compatibility = adapter_compatibility(paths["root"], config)
    if not compatibility["compatible"]:
        raise ValueError("original_adapter_compatibility_failed_at_execution")
    payloads = isolated_path(paths["live"] / "extraction_payloads", paths["live"])
    index = read_json(payloads / "index.json")
    jobs = []
    for item in index["jobs"]:
        path = isolated_path(payloads / f"{item['input_hash']}.json", paths["live"])
        job = read_json(path)
        if any(job[key] != item[key] for key in ("input_hash", "source_id", "chunk_index", "chunk_count")):
            raise ValueError("prepared_payload_index_does_not_match_job")
        jobs.append(job)
    validate_job_selection(jobs, config.extraction_job_limit)
    hashes = [job["input_hash"] for job in jobs]
    if approval.get("input_hashes") != hashes or preparation.get("input_hashes") != hashes:
        raise ValueError("approval_must_cover_exact_ordered_prepared_input_hashes")
    regenerated, _ = make_system_jobs(
        config, paths["live"] / "corpus", paths["live"] / "screening.json", MAXIMUM_CHARACTERS,
    )
    if [job["input_hash"] for job in regenerated] != hashes:
        raise ValueError("prepared_payloads_differ_from_current_corpus_and_adapter")
    provenance = read_json(paths["live"] / "corpus/provenance.json")["source_selection"]
    cohorts = {row["source_id"]: row["cohort"] for row in provenance if row["selected"]}
    if any(cohorts.get(job["source_id"]) not in {"targeted_seed", "original_discovery"}
           for job in jobs):
        raise ValueError("selected_job_requires_explicit_source_cohort")
    for field, cohort in (("reused_discovery_input_hashes", "original_discovery"),
                          ("new_seed_input_hashes", "targeted_seed")):
        expected = [job["input_hash"] for job in jobs if cohorts[job["source_id"]] == cohort]
        if field in approval and approval[field] != expected:
            raise ValueError("approval_source_cohort_subset_mismatch")
    return config, jobs, approval, cohorts, compatibility


def validate_envelope(envelope: dict, job: dict, model: str, provider: str) -> None:
    """Verify response identity and model provenance before importing or grounding."""
    if envelope.get("input_hash") != job["input_hash"]:
        raise ValueError("response_envelope_input_hash_mismatch")
    if envelope.get("engine") != model or envelope.get("provider") != provider:
        raise ValueError("response_envelope_model_or_provider_mismatch")
    if envelope.get("resolved_model", model) != model:
        raise ValueError("response_envelope_resolved_model_mismatch")
    if not isinstance(envelope.get("output"), dict) or not isinstance(
        envelope["output"].get("records"), list
    ):
        raise ValueError("response_envelope_records_array_required")
    request_hash = envelope.get("request_hash")
    if not isinstance(request_hash, str) or len(request_hash) != 64 or any(
        character not in "0123456789abcdef" for character in request_hash
    ):
        raise ValueError("response_envelope_request_hash_required")


def http_cache_snapshot(cache_path: Path) -> dict[str, int]:
    """Count persisted HTTP response attempts without exposing request bodies or credentials."""
    return {path.stem: len(read_json(path)["attempts"])
            for path in sorted((cache_path / "http").glob("*.json"))}


def import_discovery_response(
    job: dict, root: Path, cache_path: Path, model: str, provider: str,
) -> tuple[dict, dict]:
    """Copy an exact approved original envelope and raw cached response into the seeded cache."""
    original = root / "data/interim/systems/monarch"
    source = original / "extraction/responses" / f"{job['input_hash']}.json"
    original_job = read_json(original / "extraction_payloads" / f"{job['input_hash']}.json")
    if original_job != job:
        raise ValueError("discovery_response_reuse_requires_exact_original_payload")
    envelope = read_json(source)
    validate_envelope(envelope, job, model, provider)
    raw_source = original / "cache/http" / f"{envelope['request_hash']}.json"
    cached = read_json(raw_source)
    if cached.get("request_hash") != envelope["request_hash"] or digest(cached["request"]) != envelope["request_hash"]:
        raise ValueError("original_discovery_http_cache_hash_mismatch")
    raw_copy = verified_copy(raw_source, cache_path / "http" / raw_source.name, cache_path)
    envelope_copy = verified_copy(source, cache_path / "envelopes" / source.name, cache_path)
    return envelope, {
        "origin": "original_discovery_response", "envelope_copy": envelope_copy,
        "raw_response_copy": raw_copy, "original_request_hash": envelope["request_hash"],
        "new_model_request_function_called": False, "new_persisted_response_attempts": 0,
    }


def acquire_seeded_response(
    job: dict, cohort: str, paths: dict[str, Path], cache: CachedHTTP,
    model: str, provider: str, stop_new_requests: str | None,
) -> tuple[dict, dict]:
    """Load an approved isolated envelope or obtain one through the permitted cohort route."""
    envelope_path = isolated_path(cache.root / "envelopes" / f"{job['input_hash']}.json", paths["live"])
    if envelope_path.exists():
        envelope = read_json(envelope_path)
        validate_envelope(envelope, job, model, provider)
        return envelope, {
            "origin": "seeded_envelope_cache", "envelope_path": str(envelope_path),
            "envelope_sha256": file_hash(envelope_path),
            "new_model_request_function_called": False, "new_persisted_response_attempts": 0,
        }
    if cohort == "original_discovery":
        return import_discovery_response(job, paths["root"], cache.root, model, provider)
    if stop_new_requests:
        raise ExtractionServiceUnavailable(stop_new_requests)
    before = http_cache_snapshot(cache.root)
    envelope = request_extraction(job, cache, model, provider)
    validate_envelope(envelope, job, model, provider)
    write_json(envelope_path, envelope)
    after = http_cache_snapshot(cache.root)
    attempts = sum(max(count - before.get(key, 0), 0) for key, count in after.items())
    return envelope, {
        "origin": "seeded_http_cache" if not attempts else "seed_provider_response",
        "envelope_path": str(envelope_path), "envelope_sha256": file_hash(envelope_path),
        "new_model_request_function_called": True,
        "new_persisted_response_attempts": attempts,
    }


def seeded_execution_deadline(paths: dict[str, Path], config: SystemConfig) -> datetime:
    """Bound the live rerun from targeted retrieval start, preserving the original discovery date."""
    metrics = read_json(paths["live"] / "corpus_targeted_monarch/metrics.json")
    started = datetime.fromisoformat(metrics["started_at"])
    if started.tzinfo is None:
        raise ValueError("targeted_retrieval_start_requires_timezone")
    return started + timedelta(hours=config.time_limit_hours)


def run_seeded_extraction(
    root: Path, offline: bool = False, deadline: datetime | None = None,
) -> dict:
    """Acquire approved model responses and apply the unchanged single-quote extractor.

    Args:
        root: Repository root containing prepared seeded payloads and explicit approval.
        offline: Replay seeded/original cached envelopes without network access.
        deadline: Optional live bound; defaults to the first targeted retrieval plus four hours.

    Returns:
        Extraction counts, exact approval provenance, response-reuse records, and blockers.
    """
    paths = seeded_paths(root, offline)
    config, jobs, approval, cohorts, compatibility = approved_jobs(paths)
    model, provider = compatibility["model"], compatibility["provider"]
    if not offline:
        load_local_environment(paths["root"] / ".env")
        if os.environ.get("GEMINI_MODEL", model) != model:
            raise ValueError("environment_model_differs_from_original_monarch_run")
        if os.environ.get("EXTRACTION_PROVIDER", provider) != provider:
            raise ValueError("environment_provider_differs_from_original_monarch_run")
    deadline_source = "explicit_caller_override" if deadline else "targeted_retrieval_started_at"
    deadline = deadline or seeded_execution_deadline(paths, config)
    if deadline.tzinfo is None:
        raise ValueError("execution_deadline_requires_timezone")
    output = isolated_path(paths["interim"] / "extraction", paths["live"])
    cache_path = isolated_path(paths["cache"] / "extraction", paths["live"])
    responses = isolated_path(cache_path / "envelopes", paths["live"])
    approval_path = paths["root"] / "results/systems/monarch_seeded/payload_approval.json"
    confidence = read_json(paths["assay_config"])["extraction_confidence"]
    started_at = timestamp()
    approved_responses = isolated_path(
        output / "approved_responses" / digest({"started_at": started_at, "offline": offline}),
        paths["live"],
    )
    execution = {
        "system": "monarch_seeded", "adapter_system": "monarch", "offline": offline,
        "started_at": started_at, "deadline": deadline.isoformat(),
        "deadline_source": deadline_source,
        "deadline_scope": "Original targeted retrieval start; copied discovery dates are excluded.",
        "model": model, "provider": provider, "grounding_version": "single_quote_v1",
        "maximum_characters": MAXIMUM_CHARACTERS, "minimum_confidence": confidence,
        "approval_path": str(approval_path), "approval_sha256": file_hash(approval_path),
        "approved_input_hashes": approval["input_hashes"], "jobs": len(jobs),
        "complete_source_selection_verified": True, "compatibility": compatibility,
        "cache_path": str(cache_path), "envelope_path": str(responses),
        "approved_response_directory": str(approved_responses),
        "assay_config_sha256": file_hash(paths["assay_config"]), "analysis_performed": False,
    }
    write_json(output / "run_manifest.json", {**execution, "status": "running"})
    acquired, candidates = [], []
    stop_new_requests = None
    cache = CachedHTTP(cache_path, offline, client=httpx.Client(timeout=180, follow_redirects=True))
    try:
        for job in jobs:
            entry = {"input_hash": job["input_hash"], "source_id": job["source_id"],
                     "cohort": cohorts[job["source_id"]]}
            try:
                with bounded_stage(None if offline else deadline):
                    envelope, provenance = acquire_seeded_response(
                        job, entry["cohort"], paths, cache, model, provider, stop_new_requests,
                    )
                entry.update(status="complete", request_hash=envelope["request_hash"], **provenance)
                verified_copy(responses / f"{job['input_hash']}.json",
                              approved_responses / f"{job['input_hash']}.json", paths["live"])
                candidates.extend({
                    "source_id": job["source_id"], "input_hash": job["input_hash"],
                    "candidate_index": index, "candidate": candidate,
                } for index, candidate in enumerate(envelope["output"]["records"]))
                provenance_path = cache_path / "envelope_provenance" / f"{job['input_hash']}.json"
                if not provenance_path.exists():
                    write_json(provenance_path, entry)
                entry["initial_acquisition_provenance_path"] = str(provenance_path)
            except ACQUISITION_ERRORS as error:
                reason = f"{type(error).__name__}: {error}"
                entry.update(status="failed", blocked_reason=reason)
                if isinstance(error, (ExtractionServiceUnavailable, httpx.TransportError,
                                      SystemDeadlineExceeded)):
                    stop_new_requests = reason
            acquired.append(entry)
            write_jsonl(output / "response_acquisition.jsonl", acquired)
            write_jsonl(output / "candidates.jsonl", candidates)
        metrics = run_system_extraction(
            config, jobs, cache, output, responses=approved_responses, model=model, provider=provider,
            minimum_confidence=confidence, deadline=None if offline else deadline,
        )
    finally:
        cache.close()
    failed = [row for row in acquired if row["status"] != "complete"]
    status = "complete" if metrics["complete_jobs"] == len(jobs) else "partial" if metrics["complete_jobs"] else "blocked"
    metrics.update({
        "status": status,
        "blocked_reason": metrics.get("blocked_reason") or stop_new_requests
        or ("response_acquisition_failures" if failed else None),
        "response_acquisition_failures": len(failed),
        "reused_discovery_jobs": sum(row["status"] == "complete" and row["cohort"] == "original_discovery"
                                      for row in acquired),
        "seed_jobs_with_responses": sum(row["status"] == "complete" and row["cohort"] == "targeted_seed"
                                        for row in acquired),
        "persisted_new_response_attempts": sum(row.get("new_persisted_response_attempts", 0)
                                               for row in acquired),
        "request_count_caveat": "Transport failures can occur before an HTTP response is persisted.",
    })
    write_json(output / "metrics.json", metrics)
    report = {**execution, "status": status, "completed_at": timestamp(), "metrics": metrics,
              "response_acquisition": acquired, "output_path": str(output),
              "raw_candidates_path": str(output / "candidates.jsonl")}
    write_json(output / "run_manifest.json", report)
    write_json(paths["results"] / "extraction_manifest.json", report)
    return report
