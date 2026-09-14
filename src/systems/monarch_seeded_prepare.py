"""Prepare seeded-monarch payloads through the original single-quote adapter."""

import shutil
from pathlib import Path

from src.chemistry.export_cache import file_hash
from src.common.io import digest, read_json, read_jsonl, timestamp, write_json, write_jsonl
from src.extraction.gemini import DEFAULT_MODEL
from src.systems import extraction
from src.systems.config import SystemConfig, load_system_config
from src.systems.downstream import isolated_path
from src.systems.extraction import export_system_jobs, make_system_jobs
from src.systems.monarch_seeded_downstream import seeded_paths
from src.systems.schema import SystemExtraction

MAXIMUM_CHARACTERS = 24000
DISCOVERY_READY_COUNT = 20


def validate_preparation_contract(config: SystemConfig) -> None:
    """Enforce this rerun's adapter and job boundary independently of config validation."""
    if config.slug != "monarch" or config.extraction_grounding != "single_quote_v1":
        raise ValueError("seeded_rerun_requires_original_monarch_single_quote_adapter")
    if not 1 <= config.extraction_job_limit <= 12:
        raise ValueError("seeded_rerun_extraction_job_cap_exceeds_twelve")


def canonical_doi(value: str | None) -> str | None:
    """Normalize a DOI for identity matching without changing stored source metadata."""
    if not value:
        return None
    normalized = value.strip().casefold()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/",
                   "http://dx.doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
            break
    return normalized or None


def source_text(corpus: Path, source_id: str) -> Path:
    """Resolve an ordinary source identifier within its corpus text directory."""
    if not source_id or any(not (character.isalnum() or character in "_-")
                            for character in source_id):
        raise ValueError("unsafe_corpus_source_identifier")
    return isolated_path(corpus / "texts" / f"{source_id}.json", corpus)


def verified_copy(source: Path, destination: Path, allowed_root: Path) -> dict:
    """Copy bytes into the seeded namespace and reject conflicting existing copies."""
    target = isolated_path(destination, allowed_root)
    checksum = file_hash(source)
    if target.exists() and file_hash(target) != checksum:
        raise ValueError(f"Existing isolated copy differs from source: {target}")
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    if file_hash(target) != checksum:
        raise ValueError("copied_source_checksum_mismatch")
    return {"source_path": str(source), "copy_path": str(target), "sha256": checksum}


def screening_decisions(path: Path, source_ids: set[str]) -> dict[str, dict]:
    """Validate a complete screening document with one recorded decision per source."""
    decisions = read_json(path)["decisions"]
    by_source = {row["source_id"]: row for row in decisions}
    if len(by_source) != len(decisions) or set(by_source) != source_ids:
        raise ValueError("screening_must_cover_exact_source_set")
    if any(row.get("decision") not in {"include", "exclude"} or not row.get("reason")
           for row in decisions):
        raise ValueError("screening_requires_explicit_decision_and_reason")
    return by_source


def adapter_compatibility(root: Path, config: SystemConfig) -> dict:
    """Verify prompt, schema, model and regenerated old payload hashes before reuse."""
    original = root / "data/interim/systems/monarch"
    config_path = root / "config/systems/monarch.json"
    execution = read_json(original / "extraction/run_manifest.json")
    run = read_json(root / "results/systems/monarch/run_manifest.json")
    index = read_json(original / "extraction_payloads/index.json")
    regenerated, _ = make_system_jobs(
        config, original / "corpus", original / "screening.json", MAXIMUM_CHARACTERS,
    )
    current_prompt = extraction.system_prompt(config)
    current_schema = SystemExtraction.model_json_schema()
    hashes = [job["input_hash"] for job in regenerated]
    checks = {
        "model_matches_original": execution.get("model") == DEFAULT_MODEL,
        "provider_matches_original": execution.get("provider") == "gemini",
        "config_sha256_matches_original": run["config"]["sha256"] == file_hash(config_path),
        "grounding_matches_original": execution.get("grounding_version") == "single_quote_v1",
        "regenerated_original_input_hashes_match": hashes == [row["input_hash"]
                                                               for row in index["jobs"]],
        "prompt_matches_all_original_payloads": True,
        "schema_matches_all_original_payloads": True,
        "original_payload_hashes_valid": True,
    }
    for item in index["jobs"]:
        job = read_json(original / "extraction_payloads" / f"{item['input_hash']}.json")
        checks["prompt_matches_all_original_payloads"] &= job["prompt"] == current_prompt
        checks["schema_matches_all_original_payloads"] &= job["schema"] == current_schema
        checks["original_payload_hashes_valid"] &= digest({
            key: value for key, value in job.items() if key != "input_hash"
        }) == job["input_hash"] == item["input_hash"]
    return {
        "compatible": all(checks.values()), "checks": checks,
        "model": execution.get("model"), "provider": execution.get("provider"),
        "grounding_version": "single_quote_v1", "maximum_characters": MAXIMUM_CHARACTERS,
        "config_sha256": file_hash(config_path),
        "prompt_digest": digest(current_prompt), "schema_digest": digest(current_schema),
        "adapter_module_sha256": file_hash(Path(extraction.__file__)),
        "adapter_file_comparison": (
            "The original module-file hash was unrecorded. Original complete payloads "
            "are regenerated and compared by hash; prompt and schema are compared directly."
        ),
        "original_payload_index_sha256": file_hash(original / "extraction_payloads/index.json"),
        "original_payload_count": len(index["jobs"]),
    }


def merge_ready_sources(seeds: list[dict], discovery: list[dict]) -> tuple[list[dict], list[dict]]:
    """Prioritize seeds and deduplicate source identifiers and canonical DOIs."""
    selected, provenance = [], []
    identifiers: dict[str, str] = {}
    dois: dict[str, str] = {}
    for cohort, rows in (("targeted_seed", seeds), ("original_discovery", discovery)):
        for row in rows:
            source_id, doi = row["source_id"], canonical_doi(row.get("doi"))
            retained = identifiers.get(source_id) or (dois.get(doi) if doi else None)
            if retained:
                provenance.append({
                    "source_id": source_id, "cohort": cohort, "doi": row.get("doi"),
                    "selected": False, "deduplicated_to": retained,
                    "reason": "duplicate_source_id_or_doi",
                })
                continue
            selected.append(row)
            identifiers[source_id] = source_id
            if doi:
                dois[doi] = source_id
            provenance.append({"source_id": source_id, "cohort": cohort, "doi": row.get("doi"),
                               "selected": True, "deduplicated_to": None})
    return selected, provenance


def prepare_seeded_monarch(root: Path, offline: bool = False) -> dict:
    """Materialize a seeded corpus and prepare locally approved-boundary payloads.

    Args:
        root: Repository root containing the original monarch run and verified seed inputs.
        offline: Write deterministic preparation replay below seeded offline-replay roots.

    Returns:
        Preparation status, source counts, compatibility checks, and the pending approval gate.

    Raises:
        ValueError: Source identities, prior artifacts, or screening decisions are inconsistent.
    """
    paths = seeded_paths(root, offline)
    config = load_system_config(paths["config"])
    validate_preparation_contract(config)
    original = paths["root"] / "data/interim/systems/monarch"
    targeted = isolated_path(paths["live"] / "corpus_targeted_monarch", paths["live"])
    corpus = isolated_path(paths["interim"] / "corpus", paths["live"])
    screening_path = isolated_path(paths["interim"] / "screening.json", paths["live"])
    payloads = isolated_path(paths["interim"] / "extraction_payloads", paths["live"])
    approval_path = paths["results"] / "payload_approval.json"
    if approval_path.exists() and read_json(approval_path).get("approved") is True:
        raise ValueError("approved_seeded_payloads_cannot_be_reprepared")
    if (paths["interim"] / "extraction/run_manifest.json").exists():
        raise ValueError("executed_seeded_run_cannot_be_reprepared")
    original_rows = read_jsonl(original / "corpus/manifest.jsonl")
    discovery = [row for row in original_rows if row.get("status") == "ready"]
    if len(discovery) != DISCOVERY_READY_COUNT:
        raise ValueError("original_discovery_must_have_exactly_twenty_ready_sources")
    old_screening = original / "screening.json"
    old_decisions = screening_decisions(old_screening, {row["source_id"] for row in original_rows})
    seed_rows = read_jsonl(targeted / "manifest.jsonl")
    seeds = [row for row in seed_rows if row.get("status") == "ready"]
    if len(seeds) != len(seed_rows):
        raise ValueError("targeted_manifest_requires_only_retrieved_ready_sources")
    for row in seeds:
        if row.get("bibliography_verified") is not True or not canonical_doi(row.get("doi")):
            raise ValueError("seed_requires_verified_bibliography_and_doi")
        if canonical_doi(row.get("indexed_doi")) != canonical_doi(row["doi"]):
            raise ValueError("seed_doi_differs_from_verified_index_record")
    seed_screening = targeted / "screening.json"
    seed_decisions = screening_decisions(seed_screening, {row["source_id"] for row in seeds}) \
        if seeds or seed_screening.exists() else {}
    copies = [verified_copy(original / "corpus/manifest.jsonl",
                            corpus / "discovery_original/manifest.jsonl", paths["live"]),
              verified_copy(old_screening, corpus / "discovery_original/screening.json",
                            paths["live"])]
    for row in discovery:
        copies.append(verified_copy(source_text(original / "corpus", row["source_id"]),
                                    corpus / "discovery_original/texts" / f"{row['source_id']}.json",
                                    paths["live"]))
    combined, source_provenance = merge_ready_sources(seeds, discovery)
    chosen = {row["source_id"]: row for row in source_provenance if row["selected"]}
    decisions = []
    for row in combined:
        source_id = row["source_id"]
        is_seed = chosen[source_id]["cohort"] == "targeted_seed"
        source_corpus = targeted if is_seed else original / "corpus"
        source_screening = seed_screening if is_seed else old_screening
        document_path = source_text(source_corpus, source_id)
        document = read_json(document_path)
        if document.get("source_id") != source_id or not document.get("blocks"):
            raise ValueError("ready_source_requires_matching_nonempty_document")
        copies.append(verified_copy(document_path, source_text(corpus, source_id), paths["live"]))
        decision = seed_decisions[source_id] if is_seed else old_decisions[source_id]
        decisions.append({**decision, "screening_cohort": chosen[source_id]["cohort"],
                          "originating_screening_path": str(source_screening),
                          "originating_screening_sha256": file_hash(source_screening)})
    write_jsonl(corpus / "manifest.jsonl", combined)
    write_json(screening_path, {
        "system": "monarch_seeded", "completed_at": timestamp(),
        "basis": "Recorded seed decisions plus unchanged original discovery decisions.",
        "strict_directional_semantics_applied_at": "post_extraction_semantic_review",
        "decisions": decisions,
    })
    write_json(corpus / "provenance.json", {
        "source_selection": source_provenance, "verified_copies": copies,
        "targeted_manifest_sha256": file_hash(targeted / "manifest.jsonl"),
        "original_manifest_sha256": file_hash(original / "corpus/manifest.jsonl"),
        "original_screening_sha256": file_hash(old_screening),
        "deduplication_rule": "Ready seeds first, then original discovery; source ID or DOI identity.",
    })
    compatibility = adapter_compatibility(paths["root"], config)
    blocked = "no_retrieved_seed_fulltexts" if not seeds else None
    if not compatibility["compatible"]:
        blocked = "original_adapter_compatibility_failed"
    metrics = {
        "system": "monarch_seeded", "status": "complete", "offline": offline,
        "ready_sources": len(combined), "original_discovery_ready": len(discovery),
        "original_discovery_attempted": len(original_rows), "retrieved_seed_sources": len(seeds),
        "deduplicated_sources": len(source_provenance) - len(combined),
        "screened_sources": len(decisions),
        "screened_in": sum(row["decision"] == "include" for row in decisions),
        "screened_out": sum(row["decision"] == "exclude" for row in decisions),
        "source_texts_byte_verified": len(combined), "original_discovery_texts_archived": len(discovery),
    }
    write_json(corpus / "metrics.json", metrics)
    job_metrics = {"jobs": None, "job_limit": config.extraction_job_limit,
                   "grounding_version": config.extraction_grounding}
    jobs = []
    if not blocked:
        jobs, job_metrics = make_system_jobs(config, corpus, screening_path, MAXIMUM_CHARACTERS)
        export_system_jobs(jobs, payloads, job_metrics)
    elif (payloads / "index.json").exists():
        raise ValueError("blocked_preparation_cannot_leave_existing_payload_index_active")
    report = {
        "system": "monarch_seeded", "adapter_system": "monarch", "offline": offline,
        "status": "blocked" if blocked else "awaiting_payload_export_approval",
        "blocked_reason": blocked, "prepared_at": timestamp(),
        "approval_status": "pending", "external_payload_sent": False,
        "model_api_called": False, "payloads_prepared": not blocked,
        "model": compatibility["model"], "provider": compatibility["provider"],
        "corpus": metrics, "compatibility": compatibility, **job_metrics,
        "input_hashes": [job["input_hash"] for job in jobs],
        "seed_sources_selected_for_extraction": sorted({job["source_id"] for job in jobs
                                                       if chosen[job["source_id"]]["cohort"]
                                                       == "targeted_seed"}),
        "corpus_path": str(corpus), "screening_path": str(screening_path),
        "payload_path": str(payloads), "analysis_performed": False,
    }
    write_json(paths["results"] / "preparation.json", report)
    write_json(paths["results"] / "payload_approval_gate.json", report)
    return report
