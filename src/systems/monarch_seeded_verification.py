"""Verify completed seeded-monarch stages locally and preserve unrun-stage gaps."""

import base64
import hashlib
import json
from collections import Counter
from operator import itemgetter
from pathlib import Path

import httpx

from src.chemistry.export_cache import file_hash
from src.common.cache import CachedHTTP, OfflineCacheMiss
from src.common.io import digest, read_json, read_jsonl, timestamp, write_json
from src.extraction.gemini import ENDPOINT, gemini_output
from src.systems.config import SystemConfig
from src.systems.extraction import validate_system_candidate
from src.systems.monarch_infection import validate_source_design_annotations
from src.systems.monarch_seeded_downstream import seeded_paths
from src.systems.monarch_seeded_pdf import SOURCE_IDS, pdf_document
from src.systems.monarch_seeded_prepare import source_text
from src.systems.monarch_seeded_review import (
    apply_seeded_adjudications,
    summarize_seeded_focal_recovery,
)
from src.systems.monarch_seeded_run import approved_jobs, validate_envelope
from src.systems.monarch_seeded_sources import SEEDS
from src.systems.verification import STAGE_FILES, Audit, verify_primary

ORIGINAL_PATHS = (
    "data/interim/systems/monarch",
    "results/systems/monarch",
    "config/systems/monarch.json",
)
COMPATIBILITY_CHECKS = {
    "model_matches_original", "provider_matches_original", "config_sha256_matches_original",
    "grounding_matches_original", "regenerated_original_input_hashes_match",
    "prompt_matches_all_original_payloads", "schema_matches_all_original_payloads",
    "original_payload_hashes_valid",
}
EXTRACTION_OPERATIONAL_FIELDS = {
    "offline", "started_at", "completed_at", "approved_response_directory", "output_path",
    "raw_candidates_path",
}
ACQUISITION_OPERATIONAL_FIELDS = {
    "origin", "envelope_path", "envelope_sha256", "envelope_copy", "raw_response_copy",
    "original_request_hash", "new_model_request_function_called", "new_persisted_response_attempts",
}
EXTRACTION_DATA_FILES = (
    "candidates.jsonl", "observations.jsonl", "observations_progress.jsonl", "rejections.jsonl",
    "failures.jsonl", "job_status.jsonl", "partial_observations.jsonl",
)
DOWNSTREAM_OPERATIONAL_FIELDS = {"offline", "started_at", "completed_at", "generated_at", "imported_at", "retrieved_at"}
DOWNSTREAM_PATH_FIELDS = {
    "input_path", "output_path", "cache_path", "config_path", "genus_input_path", "contract_path",
    "selected_source_rows_path", "semantic_input_path", "funnel_path", "source_input_path",
}
DOWNSTREAM_MANIFEST_OPERATIONAL_FIELDS = {
    "deadline", "deadline_source", "offline_replay_exempt_from_live_deadline", "lotus_cache_copy",
}


def seeded_results(root: Path) -> Path:
    """Return the seeded output directory while rejecting redirected output roots."""
    path = root / "results/systems/monarch_seeded"
    if path.resolve() != path:
        raise ValueError("seeded_verification_output_cannot_be_redirected")
    return path


def original_inventory(root: Path) -> list[dict]:
    """Hash all files in the original run without modifying their contents."""
    inventory = []
    for relative in ORIGINAL_PATHS:
        scope = root / relative
        paths = sorted(scope.rglob("*")) if scope.is_dir() else [scope]
        for path in paths:
            if path.is_file():
                inventory.append({
                    "path": str(path.relative_to(root)),
                    "bytes": path.stat().st_size,
                    "sha256": file_hash(path),
                    "symlink_target": str(path.readlink()) if path.is_symlink() else None,
                })
    return sorted(inventory, key=itemgetter("path"))


def snapshot_original_run(root: Path) -> dict:
    """Create the original-run inventory once, with an explicit capture boundary.

    Args:
        root: Repository root containing the original and seeded monarch runs.

    Returns:
        The existing snapshot or the newly captured full SHA-256 file inventory.

    Raises:
        ValueError: A prior snapshot is invalid or the output root is redirected.
    """
    root = Path(root).resolve()
    output = seeded_results(root) / "original_snapshot.json"
    if output.exists():
        snapshot = read_json(output)
        if not isinstance(snapshot, dict) or snapshot.get("scope") != list(ORIGINAL_PATHS):
            raise ValueError("existing_original_snapshot_invalid")
        return snapshot
    started = timestamp()
    inventory = original_inventory(root)
    interim = root / "data/interim/systems/monarch_seeded"
    snapshot = {
        "schema_version": 1,
        "system": "monarch_seeded",
        "capture_started_at": started,
        "captured_at": timestamp(),
        "scope": list(ORIGINAL_PATHS),
        "missing_scope_paths": [name for name in ORIGINAL_PATHS if not (root / name).exists()],
        "timing": (
            "Captured after seeded source retrieval. The stage-presence fields record "
            "which seeded outputs existed at capture. This inventory proves preservation "
            "from capture time only; the historical audit is checked separately."
        ),
        "seeded_outputs_present_at_capture": {
            stage: (interim / stage).exists()
            for stage in ("corpus_targeted_monarch", "assay_scope", "extraction",
                          "semantic_review", "taxonomy", "behaviour", "chemistry", "bioactivity")
        },
        "files": len(inventory),
        "bytes": sum(row["bytes"] for row in inventory),
        "inventory_digest": digest(inventory),
        "inventory": inventory,
    }
    write_json(output, snapshot)
    return snapshot


def verify_original_snapshot(audit: Audit, results: Path) -> dict:
    """Compare the complete current original file set with the one-time snapshot."""
    snapshot = audit.load(results / "original_snapshot.json", "original_snapshot_read")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("inventory"), list):
        return {"status": "unavailable", "files_compared": None}
    expected = snapshot["inventory"]
    current = original_inventory(audit.root)
    before = {row["path"]: row for row in expected}
    after = {row["path"]: row for row in current}
    audit.add("original_snapshot_integrity", digest(expected) == snapshot.get("inventory_digest")
              and snapshot.get("scope") == list(ORIGINAL_PATHS)
              and len(before) == len(expected), snapshot_files=len(expected))
    audit.add("original_snapshot_scope_present", not snapshot.get("missing_scope_paths")
              and all((audit.root / name).exists() for name in ORIGINAL_PATHS))
    audit.add("original_file_set_unchanged", set(before) == set(after),
              added=sorted(set(after) - set(before)), removed=sorted(set(before) - set(after)))
    changed = [name for name in sorted(set(before) & set(after)) if before[name] != after[name]]
    audit.add("original_file_hashes_unchanged", not changed, changed_paths=changed,
              compared_files=len(set(before) & set(after)))
    return {
        "captured_at": snapshot.get("captured_at"),
        "coverage_boundary": snapshot.get("timing"),
        "snapshot_files": len(expected), "current_files": len(current),
        "files_compared": len(set(before) & set(after)),
        "snapshot_bytes": snapshot.get("bytes"),
        "inventory_digest": digest(current),
    }


def historical_hash_pairs(value: object) -> list[tuple[str, str]]:
    """Collect explicit path/hash pairs recursively without inferring missing hashes."""
    pairs = []
    if isinstance(value, dict):
        for path_key, hash_key in (("path", "sha256"), ("live_path", "live_sha256"),
                                   ("replay_path", "replay_sha256")):
            path, expected = value.get(path_key), value.get(hash_key)
            if isinstance(path, str) and isinstance(expected, str) and len(expected) == 64:
                pairs.append((path, expected))
        for item in value.values():
            pairs.extend(historical_hash_pairs(item))
    elif isinstance(value, list):
        for item in value:
            pairs.extend(historical_hash_pairs(item))
    return pairs


def verify_historical_original(audit: Audit) -> dict:
    """Check the original audit's recorded hashes independently of the new snapshot."""
    path = audit.root / "results/systems/monarch/verification.json"
    report = audit.load(path, "historical_original_audit_read")
    if not isinstance(report, dict):
        return {"status": "unavailable", "files_compared": None}
    pairs = historical_hash_pairs({key: report.get(key)
                                   for key in ("checks", "cache_inventory", "corpus_replay")})
    expected_by_path: dict[Path, set[str]] = {}
    excluded = []
    scopes = [audit.root / relative for relative in ORIGINAL_PATHS]
    for relative, expected in pairs:
        candidate = Path(relative)
        candidate = candidate if candidate.is_absolute() else audit.root / candidate
        if any(candidate == scope or candidate.is_relative_to(scope) for scope in scopes):
            expected_by_path.setdefault(candidate, set()).add(expected)
        else:
            excluded.append(relative)
    for candidate, expected in sorted(expected_by_path.items()):
        actual = file_hash(candidate) if candidate.is_file() else None
        audit.add("historical_original_file_checksum", actual in expected and len(expected) == 1,
                  path=audit.path(candidate), expected_sha256=sorted(expected), sha256=actual)
    audit.add("historical_original_hash_coverage", bool(expected_by_path),
              unique_files=len(expected_by_path), recorded_pairs=len(pairs))
    return {
        "historical_audit_path": audit.path(path), "historical_audit_sha256": file_hash(path),
        "historical_audit_recorded_at": report.get("verified_at"),
        "coverage_boundary": "Only explicit file hashes recorded in the original audit are covered.",
        "files_compared": len(expected_by_path), "recorded_pairs": len(pairs),
        "out_of_scope_paths": sorted(set(excluded)),
    }


def verify_seed_cache(audit: Audit, cache: Path) -> tuple[list[dict], list[str]]:
    """Inventory every cached response and validate descriptors and all encoded bodies."""
    inventory = []
    hashes = set()
    if not cache.is_dir():
        audit.add("seeded_cache_present", None, path=audit.path(cache))
        return inventory, []
    for path in sorted(cache.rglob("*")):
        if not path.is_file():
            continue
        item = {"path": audit.path(path), "bytes": path.stat().st_size, "sha256": file_hash(path)}
        inventory.append(item)
        if path.parent.name not in {"http", "downloads"} or path.suffix != ".json":
            continue
        record = audit.load(path, "cached_response_read")
        if not isinstance(record, dict):
            continue
        descriptor = record.get("request")
        key = digest(descriptor)
        valid = isinstance(descriptor, dict) and set(descriptor) == {"method", "url", "params", "json"}
        audit.add("cached_request_descriptor_hash", valid and key == path.stem == record.get("request_hash"),
                  path=audit.path(path), request_hash=key)
        hashes.add(key)
        item["request_hash"] = key
        if path.parent.name == "downloads":
            body_path = path.with_suffix(".body")
            actual_hash = file_hash(body_path) if body_path.is_file() else None
            audit.add("cached_download_body_valid", record.get("complete") is True and record.get("status") == 200
                      and body_path.is_file() and body_path.stat().st_size == record.get("bytes")
                      and actual_hash == record.get("sha256"), path=audit.path(path), request_hash=key,
                      body_sha256=actual_hash, expected_body_sha256=record.get("sha256"))
            item["body_sha256"] = actual_hash
            continue
        attempts = record.get("attempts")
        if not isinstance(attempts, list) or not attempts:
            audit.add("cached_response_attempts", False, path=audit.path(path))
            continue
        item["response_attempts"] = []
        for index, attempt in enumerate(attempts):
            try:
                body = base64.b64decode(attempt["body_base64"], validate=True)
                status = attempt["status"]
                body_hash = hashlib.sha256(body).hexdigest()
                audit.add("cached_response_body_valid", isinstance(status, int) and 100 <= status <= 599,
                          path=audit.path(path), attempt=index, status_code=status,
                          decoded_bytes=len(body), body_sha256=body_hash)
                item["response_attempts"].append({
                    "attempt": index, "status": status, "bytes": len(body), "sha256": body_hash,
                })
            except (KeyError, TypeError, ValueError) as error:
                audit.add("cached_response_body_valid", False, path=audit.path(path),
                          attempt=index, reason=str(error))
    audit.add("seeded_cache_inventory", bool(inventory) and bool(hashes), files=len(inventory),
              unique_request_hashes=len(hashes), bytes=sum(row["bytes"] for row in inventory))
    return inventory, sorted(hashes)


def verify_seed_access(audit: Audit, interim: Path) -> None:
    """Compare all five metadata records and access decisions with the offline replay."""
    live = interim / "corpus_targeted_monarch"
    replay = interim / "offline_replay/corpus_targeted_monarch"
    a = audit.load(live / "access_manifest.jsonl", "live_seed_access", jsonl=True)
    b = audit.load(replay / "access_manifest.jsonl", "replay_seed_access", jsonl=True)
    if isinstance(a, list) and isinstance(b, list):
        expected = [seed["seed_id"] for seed in SEEDS]
        audit.add("five_seed_access_records", [row.get("seed_id") for row in a] == expected
                  and [row.get("seed_id") for row in b] == expected)
        left = [{key: value for key, value in row.items() if key != "checked_at"} for row in a]
        right = [{key: value for key, value in row.items() if key != "checked_at"} for row in b]
        audit.add("seed_access_replay", left == right, comparison="json_rows_except_checked_at",
                  ignored_fields=["checked_at"], live_digest=digest(left), replay_digest=digest(right))
    for seed in SEEDS:
        name = f"{seed['seed_id']}.json"
        audit.compare(live / "metadata" / name, replay / "metadata" / name,
                      f"seed_metadata_replay:{seed['seed_id']}")
    audit.compare(live / "manifest.jsonl", replay / "manifest.jsonl", "seed_ready_manifest_replay")


def verify_seeded_assays(audit: Audit, interim: Path) -> None:
    """Require exact assay inventories and metrics equality except the offline flag."""
    live, replay = interim / "assay_scope", interim / "offline_replay/assay_scope"
    for name in ("primary_fungal_assays.jsonl", "parasite_assays.jsonl"):
        audit.compare(live / name, replay / name, f"assay_inventory_replay:{name}")
    a = audit.load(live / "metrics.json", "live_assay_metrics")
    b = audit.load(replay / "metrics.json", "replay_assay_metrics")
    if isinstance(a, dict) and isinstance(b, dict):
        left = {key: value for key, value in a.items() if key != "offline"}
        right = {key: value for key, value in b.items() if key != "offline"}
        audit.add("assay_metrics_replay", left == right, ignored_fields=["offline"],
                  live_digest=digest(left), replay_digest=digest(right),
                  primary_fungal_assays=a.get("primary_fungal_assays"),
                  parasite_assays_all_types=a.get("parasite_assays_all_types"))


def verify_seeded_preparation(audit: Audit, interim: Path, results: Path) -> dict:
    """Verify combined source copies, screening decisions, and adapter compatibility."""
    live, replay = interim / "corpus", interim / "offline_replay/corpus"
    audit.compare(live / "manifest.jsonl", replay / "manifest.jsonl", "combined_corpus_manifest_replay")
    manifest = audit.load(live / "manifest.jsonl", "prepared_corpus_manifest", jsonl=True)
    ready = [row for row in manifest if row.get("status") == "ready"] if isinstance(manifest, list) else []
    identifiers = [row["source_id"] for row in ready]
    audit.add("combined_corpus_ready_source_set", isinstance(manifest, list)
              and len(ready) == len(manifest) and len(set(identifiers)) == len(identifiers),
              ready_sources=len(ready))
    for identifier in identifiers:
        try:
            audit.compare(source_text(live, identifier), source_text(replay, identifier),
                          f"prepared_source_text_replay:{identifier}")
        except ValueError as error:
            audit.add("prepared_source_text_isolation", False, source_id=identifier, reason=str(error))
    a = audit.load(interim / "screening.json", "live_prepared_screening")
    b = audit.load(interim / "offline_replay/screening.json", "replay_prepared_screening")
    screened = None
    if isinstance(a, dict) and isinstance(b, dict):
        left = {key: value for key, value in a.items() if key != "completed_at"}
        right = {key: value for key, value in b.items() if key != "completed_at"}
        audit.add("prepared_screening_replay", left == right, ignored_fields=["completed_at"],
                  live_digest=digest(left), replay_digest=digest(right))
        decisions = a.get("decisions", [])
        screened = len(decisions)
        audit.add("prepared_screening_source_coverage", len(decisions) == len(identifiers)
                  and {row.get("source_id") for row in decisions} == set(identifiers)
                  and all(row.get("decision") in {"include", "exclude"} and row.get("reason")
                          for row in decisions), screened_sources=screened)
    first = audit.load(results / "preparation.json", "live_preparation_report")
    second = audit.load(results / "offline_replay/preparation.json", "replay_preparation_report")
    compatibility_checks = None
    if isinstance(first, dict) and isinstance(second, dict):
        a, b = first.get("compatibility"), second.get("compatibility")
        audit.add("adapter_compatibility_replay", isinstance(a, dict) and a == b,
                  live_digest=digest(a), replay_digest=digest(b))
        if isinstance(a, dict) and isinstance(b, dict):
            checks = a.get("checks", {})
            compatibility_checks = len(checks)
            audit.add("eight_original_adapter_compatibility_checks",
                      a.get("compatible") is True and b.get("compatible") is True
                      and set(checks) == COMPATIBILITY_CHECKS
                      and all(value is True for value in checks.values())
                      and checks == b.get("checks"), expected_checks=sorted(COMPATIBILITY_CHECKS),
                      recorded_checks=checks)
    return {"ready_sources": len(ready), "source_text_comparisons_requested": len(identifiers),
            "screened_sources": screened, "compatibility_checks": compatibility_checks}


def verify_local_pdf_source(
    audit: Audit, interim: Path, seed: dict, row: dict, imported: dict,
) -> dict | None:
    """Rebuild one imported document from cached XHTML and join its raw-source hashes."""
    identifier = SOURCE_IDS[seed["seed_id"]]
    folder = interim / "reference_sources" / seed["seed_id"]
    pdf_path, bbox_path = folder / "source.pdf", folder / "source.bbox.xhtml"
    metadata_path = folder / "source.extraction.json"
    metadata = audit.load(metadata_path, "local_pdf_extraction_metadata")
    if not isinstance(metadata, dict) or not pdf_path.is_file() or not bbox_path.is_file():
        audit.add("local_pdf_cached_source_available", None, seed_id=seed["seed_id"],
                  missing=[audit.path(path) for path in (pdf_path, bbox_path, metadata_path)
                           if not path.is_file()])
        return None
    hashes = {"pdf_sha256": file_hash(pdf_path), "bbox_sha256": file_hash(bbox_path)}
    audit.add("local_pdf_cached_source_checksums", all(metadata.get(key) == value
              for key, value in hashes.items()) and isinstance(metadata.get("extractor"), str)
              and bool(metadata.get("extractor")), seed_id=seed["seed_id"], **hashes,
              extraction_metadata_sha256=file_hash(metadata_path))
    live = source_text(interim / "corpus_targeted_monarch", identifier)
    replay = source_text(interim / "offline_replay/corpus_targeted_monarch", identifier)
    audit.compare(live, replay, f"local_pdf_text_replay:{identifier}")
    document = audit.load(live, "local_pdf_document_read")
    if not isinstance(document, dict):
        return None
    try:
        rebuilt = pdf_document(bbox_path.read_bytes(), seed, hashes["pdf_sha256"])
        rebuilt["provenance"]["extractor"] = metadata["extractor"]
        audit.add("local_pdf_document_rebuild", rebuilt == document, source_id=identifier,
                  cached_document_digest=digest(document), rebuilt_document_digest=digest(rebuilt))
        blocks = document.get("blocks", [])
        pages = document.get("provenance", {}).get("pages")
        page_ids = {block.get("provenance", {}).get("pdf_page") for block in blocks}
        block_ids = [block.get("block_id") for block in blocks]
        audit.add("local_pdf_page_and_block_coverage", isinstance(pages, int) and pages > 0
                  and page_ids == set(range(1, pages + 1)) and len(set(block_ids)) == len(blocks)
                  and all(block.get("source_id") == identifier for block in blocks),
                  source_id=identifier, pages=pages, blocks=len(blocks))
        exclusions = document.get("provenance", {}).get("excluded_blocks", [])
        audit.add("local_pdf_exclusion_provenance", all(
            item.get("reason") == "download_account_watermark" and "text" not in item
            and item.get("source_sha256") == hashes["pdf_sha256"]
            and item.get("pdf_page") in page_ids and len(item.get("bounds_points", [])) == 4
            and isinstance(item.get("text_sha256"), str) and len(item["text_sha256"]) == 64
            for item in exclusions), source_id=identifier, excluded_blocks=len(exclusions),
            exclusions=exclusions)
        audit.add("local_pdf_manifest_provenance", row.get("source_id") == identifier
                  and row.get("source_pdf_sha256") == hashes["pdf_sha256"]
                  and row.get("text_hash") == digest(document) and row.get("pages") == pages
                  and row.get("block_count") == len(blocks)
                  and imported.get("cached_pdf_path") == str(pdf_path)
                  and imported.get("cached_bbox_sha256") == hashes["bbox_sha256"]
                  and imported.get("source_characters") == sum(len(block["text"]) for block in blocks)
                  and {key: imported.get(key) for key in row} == row, source_id=identifier)
        return {
            "seed_id": seed["seed_id"], "source_id": identifier,
            "pages": rebuilt["provenance"]["pages"], "recorded_pages": pages,
            "blocks": len(blocks), "excluded_blocks": len(exclusions), **hashes,
            "document_sha256": file_hash(live), "document_digest": digest(document),
            "extractor": metadata["extractor"],
            "raw_inventory": [{"path": audit.path(path), "sha256": file_hash(path),
                               "bytes": path.stat().st_size}
                              for path in (pdf_path, bbox_path, metadata_path)],
        }
    except (KeyError, TypeError, ValueError) as error:
        audit.add("local_pdf_document_rebuild", False, source_id=identifier, reason=str(error))
        return None


def verify_local_pdf_import(audit: Audit, interim: Path, results: Path) -> dict:
    """Verify local PDFs independently of the historical Europe PMC access decisions."""
    live = interim / "corpus_targeted_monarch"
    replay = interim / "offline_replay/corpus_targeted_monarch"
    a = audit.load(results / "local_pdf_access.json", "live_local_pdf_access")
    b = audit.load(results / "offline_replay/local_pdf_access.json", "replay_local_pdf_access")
    manifest = audit.load(live / "manifest.jsonl", "local_pdf_manifest", jsonl=True)
    historical = audit.load(live / "access_manifest.jsonl", "historical_europepmc_access", jsonl=True)
    if not isinstance(a, dict) or not isinstance(b, dict) or not isinstance(manifest, list):
        return {"status": "unavailable", "sources_verified": None, "europe_pmc_retrieved": None}
    left = {key: value for key, value in a.items() if key not in {"offline", "imported_at"}}
    right = {key: value for key, value in b.items() if key not in {"offline", "imported_at"}}
    audit.add("local_pdf_access_replay", left == right, ignored_fields=["offline", "imported_at"],
              live_digest=digest(left), replay_digest=digest(right))
    audit.compare(live / "manifest.jsonl", replay / "manifest.jsonl", "local_pdf_manifest_replay")
    expected = [seed["seed_id"] for seed in SEEDS]
    audit.add("five_local_pdf_source_identities", [row.get("seed_id") for row in manifest] == expected
              and [row.get("seed_id") for row in a.get("seeds", [])] == expected
              and a.get("user_supplied_seed_pdfs") == len(SEEDS), expected_seed_ids=expected)
    by_seed = {row["seed_id"]: row for row in manifest}
    imported = {row["seed_id"]: row for row in a.get("seeds", [])}
    historic = {row["seed_id"]: row for row in historical} if isinstance(historical, list) else {}
    epmc_count = sum(row.get("status") == "retrieved" for row in historic.values()) if historic else None
    audit.add("historical_europepmc_pdf_access_separation", set(historic) == set(expected)
              and all(row.get("status") == "ready" and row.get("source_kind") == "user_supplied_pdf"
                      and row.get("local_pdf_access_status") == "retrieved"
                      and row.get("open_access_status") == "not_established_by_user_supply"
                      and row.get("europe_pmc_fulltext_status") == historic.get(row["seed_id"], {}).get("status")
                      and row.get("bibliography_request_hash") == historic.get(row["seed_id"], {}).get("search_request_hash")
                      and row.get("indexed_doi") == historic.get(row["seed_id"], {}).get("indexed_doi")
                      for row in manifest), europe_pmc_retrieved=epmc_count,
              local_pdf_sources=len(manifest))
    documents = []
    for seed in SEEDS:
        if seed["seed_id"] not in by_seed or seed["seed_id"] not in imported:
            audit.add("local_pdf_source_present", None, seed_id=seed["seed_id"])
            continue
        document = verify_local_pdf_source(audit, interim, seed, by_seed[seed["seed_id"]],
                                           imported[seed["seed_id"]])
        if document is not None:
            documents.append(document)
    metrics = audit.load(live / "metrics.json", "live_local_pdf_metrics")
    replay_metrics = audit.load(replay / "metrics.json", "replay_local_pdf_metrics")
    if isinstance(metrics, dict) and isinstance(replay_metrics, dict):
        left = {key: value for key, value in metrics.items() if key not in {"offline", "local_import_at"}}
        right = {key: value for key, value in replay_metrics.items() if key not in {"offline", "local_import_at"}}
        audit.add("local_pdf_metrics_replay", left == right, ignored_fields=["offline", "local_import_at"],
                  live_digest=digest(left), replay_digest=digest(right))
        audit.add("local_pdf_access_route_counts", metrics.get("europe_pmc_retrieved") == epmc_count
                  and metrics.get("user_supplied_retrieved") == len(manifest)
                  and metrics.get("retrieved") == len(manifest), europe_pmc_retrieved=epmc_count,
                  user_supplied_retrieved=len(manifest))
    return {"sources_verified": len(documents), "expected_sources": len(SEEDS),
            "pages": sum(item["pages"] for item in documents), "europe_pmc_retrieved": epmc_count,
            "user_supplied_sources": len(manifest), "documents": documents,
            "downloads_accessed": False, "poppler_invoked": False}


def verify_source_design_review(audit: Audit, interim: Path, results: Path) -> dict:
    """Regenerate exact source-only annotations without assigning model-record infection status."""
    adjudication_path = results / "source_design_adjudications.json"
    adjudications = audit.load(adjudication_path, "source_design_adjudications")
    review = audit.load(results / "source_design_review.json", "source_design_review")
    index = audit.load(interim / "extraction_payloads/index.json", "source_design_payload_index")
    if not all(isinstance(value, dict) for value in (adjudications, review, index)):
        return {"status": "unavailable", "source_designs": None, "model_record_recovery": None}
    audit.add("source_design_adjudication_identity",
              review.get("adjudications_sha256") == file_hash(adjudication_path)
              and review.get("adjudications_hash") == digest(adjudications)
              and review.get("adjudications_path") == str(adjudication_path),
              adjudications_sha256=file_hash(adjudication_path), adjudications_hash=digest(adjudications))
    jobs = {}
    for entry in index.get("jobs", []):
        key = entry["input_hash"]
        if not isinstance(key, str) or len(key) != 64 or any(character not in "0123456789abcdef"
                                                           for character in key):
            audit.add("source_design_payload_identity", False, reason="invalid_payload_hash")
            continue
        path = interim / "extraction_payloads" / f"{key}.json"
        job = audit.load(path, "source_design_payload")
        if not isinstance(job, dict):
            continue
        audit.add("source_design_payload_identity", job.get("input_hash") == key
                  and digest({name: value for name, value in job.items() if name != "input_hash"}) == key,
                  input_hash=key, path=audit.path(path))
        document = audit.load(source_text(interim / "corpus", job["source_id"]), "source_design_payload_source")
        if isinstance(document, dict):
            blocks = {block["block_id"]: block for block in document.get("blocks", [])}
            audit.add("source_design_payload_blocks_match_corpus", all(
                blocks.get(block["block_id"]) == block for block in job.get("blocks", [])
            ), input_hash=key, source_id=job["source_id"])
        jobs[key] = job
    try:
        regenerated = validate_source_design_annotations(adjudications, jobs)
        audit.add("source_design_annotations_regenerated", review.get("designs") == regenerated,
                  recorded_digest=digest(review.get("designs")), regenerated_digest=digest(regenerated))
        sources = sorted({row["source_id"] for row in regenerated if row["source_design_eligible"]})
        audit.add("source_design_counts_and_record_scope", review.get("source_design_count") == len(regenerated)
                  and review.get("primary_focal_design_source_count") == len(sources)
                  and all(row["record_origin"] == "source_design_review"
                          and row["infection_status"] == "unreported" and row["focal_eligible"] is False
                          and row["infection_comparison_eligible"] is False for row in regenerated),
                  source_designs=len(regenerated), primary_focal_design_sources=sources)
        return {"source_designs": len(regenerated), "primary_focal_design_sources": sources,
                "model_record_recovery": None,
                "scope": "Manual source-design evidence; source-level unreported status assigns no infection group to model records.",
                "compared_infection_groups": {row["design_id"]: row["compared_infection_groups"]
                                               for row in regenerated}}
    except (KeyError, TypeError, ValueError) as error:
        audit.add("source_design_annotations_regenerated", False, reason=str(error))
        return {"status": "failed", "source_designs": None, "model_record_recovery": None}


def acquisition_identity(row: dict) -> dict:
    """Exclude only acquisition-route operational fields from response identity comparisons."""
    return {key: value for key, value in row.items() if key not in ACQUISITION_OPERATIONAL_FIELDS}


def extraction_scientific_manifest(report: dict) -> dict:
    """Preserve extraction results while separating live acquisition work from cache replay."""
    result = {key: value for key, value in report.items() if key not in EXTRACTION_OPERATIONAL_FIELDS}
    result["metrics"] = {key: value for key, value in report.get("metrics", {}).items()
                         if key != "persisted_new_response_attempts"}
    result["response_acquisition"] = [acquisition_identity(row)
                                      for row in report.get("response_acquisition", [])]
    return result


def verify_seeded_envelope(
    audit: Audit, interim: Path, job: dict, model: str, provider: str, cohort: str,
) -> dict | None:
    """Join an actual response to its exact cached request, provider body, and original payload."""
    key = job["input_hash"]
    live = interim / "extraction/responses" / f"{key}.json"
    replay = interim / "offline_replay/extraction/responses" / f"{key}.json"
    cached = interim / "cache/extraction/envelopes" / f"{key}.json"
    audit.compare(live, replay, f"seeded_response_replay:{key}")
    audit.compare(live, cached, f"seeded_response_cached_envelope:{key}")
    envelope = audit.load(live, "seeded_response_envelope")
    if not isinstance(envelope, dict):
        return None
    try:
        validate_envelope(envelope, job, model, provider)
        audit.add("seeded_envelope_identity", True, input_hash=key, model=model, provider=provider)
        request_hash = envelope["request_hash"]
        raw_path = interim / "cache/extraction/http" / f"{request_hash}.json"
        raw = read_json(raw_path)
        if not isinstance(raw, dict) or not isinstance(raw.get("attempts"), list) or not raw["attempts"]:
            raise ValueError("cached_provider_response_attempts_required")
        expected_body = {
            "model": model, "store": False, "system_instruction": job["prompt"],
            "input": json.dumps({"source_id": job["source_id"], "title": job["title"], "blocks": job["blocks"]}),
            "response_format": {"type": "text", "mime_type": "application/json", "schema": job["schema"]},
            "generation_config": {"max_output_tokens": 32768, "thinking_level": "low", "thinking_summaries": "none"},
        }
        expected_request = {"method": "POST", "url": ENDPOINT, "params": {}, "json": expected_body}
        audit.add("seeded_request_matches_approved_payload", raw.get("request") == expected_request
                  and raw.get("request_hash") == request_hash == digest(expected_request), input_hash=key,
                  request_hash=request_hash, cached_raw_sha256=file_hash(raw_path))
        response = json.loads(base64.b64decode(raw["attempts"][-1]["body_base64"], validate=True))
        if not isinstance(response, dict):
            raise ValueError("cached_provider_response_object_required")
        reconstructed = {
            "input_hash": key, "engine": model, "resolved_model": response.get("model", model),
            "provider": provider, "mode": "gemini_interactions_api", "created_at": response.get("created"),
            "response_id": response.get("id"), "request_hash": request_hash,
            "usage": response.get("usage", {}), "output": gemini_output(response),
        }
        audit.add("seeded_envelope_matches_raw_response", raw["attempts"][-1]["status"] == 200
                  and envelope == reconstructed, input_hash=key, request_hash=request_hash,
                  reconstructed_envelope_digest=digest(reconstructed), envelope_digest=digest(envelope))
        if cohort == "original_discovery":
            original = audit.root / "data/interim/systems/monarch"
            audit.compare(original / "extraction_payloads" / f"{key}.json",
                          interim / "extraction_payloads" / f"{key}.json", f"discovery_payload_reused_exactly:{key}")
            audit.compare(original / "extraction/responses" / f"{key}.json", live,
                          f"discovery_envelope_reused_exactly:{key}")
            audit.compare(original / "cache/http" / f"{request_hash}.json", raw_path,
                          f"discovery_raw_response_reused_exactly:{key}")
        return envelope
    except (OSError, KeyError, IndexError, TypeError, ValueError) as error:
        audit.add("seeded_envelope_provenance", False, input_hash=key, reason=str(error))
        return None


def regenerated_grounding(jobs: list[dict], envelopes: dict[str, dict], config: SystemConfig, confidence: float) -> dict:
    """Apply the unchanged single-quote validator to every saved candidate without a model call."""
    candidates, accepted, rejected = [], [], []
    for job in jobs:
        envelope = envelopes[job["input_hash"]]
        for index, candidate in enumerate(envelope["output"]["records"]):
            candidates.append({"source_id": job["source_id"], "input_hash": job["input_hash"],
                               "candidate_index": index, "candidate": candidate})
            valid, reason = validate_system_candidate(candidate, job, config, confidence)
            if reason:
                rejected.append({"source_id": job["source_id"], "input_hash": job["input_hash"],
                                 "candidate": candidate, "reason": reason})
            elif valid is not None:
                valid.update(engine=envelope["engine"], provider=envelope["provider"],
                             response_hash=digest(envelope), extraction_request_hash=envelope["request_hash"],
                             resolved_model=envelope["resolved_model"])
                accepted.append(valid)
    return {"candidates.jsonl": candidates, "observations_progress.jsonl": accepted,
            "observations.jsonl": list({row["record_id"]: row for row in accepted}.values()),
            "rejections.jsonl": rejected, "failures.jsonl": [], "partial_observations.jsonl": [],
            "job_status.jsonl": [{"source_id": job["source_id"], "input_hash": job["input_hash"],
                                  "status": "complete"} for job in jobs]}


def verify_seeded_extraction(audit: Audit, interim: Path, results: Path) -> dict:
    """Verify approved extraction, byte-exact replay, raw response provenance, and fresh grounding."""
    live_path, replay_path = interim / "extraction", interim / "offline_replay/extraction"
    live = audit.load(live_path / "run_manifest.json", "live_seeded_extraction_manifest")
    replay = audit.load(replay_path / "run_manifest.json", "replay_seeded_extraction_manifest")
    if not isinstance(live, dict) or not isinstance(replay, dict):
        return {"status": "unavailable", "execution_complete": False}
    try:
        config, jobs, approval, cohorts, compatibility = approved_jobs(seeded_paths(audit.root))
        audit.add("seeded_approved_job_selection", True, jobs=len(jobs), input_hashes=approval["input_hashes"],
                  grounding=config.extraction_grounding, compatibility=compatibility["checks"])
    except (OSError, KeyError, TypeError, ValueError) as error:
        audit.add("seeded_approved_job_selection", False, reason=str(error))
        return {"status": "failed", "execution_complete": False}
    left, right = extraction_scientific_manifest(live), extraction_scientific_manifest(replay)
    audit.add("seeded_extraction_scientific_replay", left == right, live_digest=digest(left), replay_digest=digest(right),
              ignored_manifest_fields=sorted(EXTRACTION_OPERATIONAL_FIELDS),
              ignored_acquisition_fields=sorted(ACQUISITION_OPERATIONAL_FIELDS),
              ignored_metric_fields=["persisted_new_response_attempts"])
    for name in EXTRACTION_DATA_FILES:
        audit.compare(live_path / name, replay_path / name, f"seeded_extraction_data_replay:{name}")
    audit.compare(live_path / "run_manifest.json", results / "extraction_manifest.json", "live_extraction_report_copy")
    audit.compare(replay_path / "run_manifest.json", results / "offline_replay/extraction_manifest.json",
                  "replay_extraction_report_copy")
    envelopes = {}
    for job in jobs:
        envelope = verify_seeded_envelope(audit, interim, job, compatibility["model"], compatibility["provider"],
                                          cohorts[job["source_id"]])
        if envelope is not None:
            envelopes[job["input_hash"]] = envelope
    for execution, folder, offline in ((live, live_path, False), (replay, replay_path, True)):
        metrics = audit.load(folder / "metrics.json", "seeded_extraction_metrics")
        audit.add("seeded_extraction_metrics_match_manifest", metrics == execution.get("metrics"), offline=offline)
        response_names = {path.name for path in (folder / "responses").glob("*.json")}
        audit.add("seeded_response_files_exact_approval", response_names == {
            f"{key}.json" for key in approval["input_hashes"]}, offline=offline)
        acquisition = audit.load(folder / "response_acquisition.jsonl", "seeded_response_acquisition", jsonl=True)
        if not isinstance(acquisition, list):
            continue
        audit.add("seeded_response_acquisition_manifest", acquisition == execution.get("response_acquisition")
                  and [row.get("input_hash") for row in acquisition] == approval["input_hashes"], offline=offline)
        audit.add("seeded_acquisition_export_scope", all(
            row.get("cohort") == cohorts.get(row.get("source_id"))
            and (not row.get("new_model_request_function_called") or (not offline and row["cohort"] == "targeted_seed"))
            and (not offline or row.get("new_persisted_response_attempts") == 0)
            for row in acquisition), offline=offline)
        attempts = sum(row.get("new_persisted_response_attempts", 0) for row in acquisition)
        audit.add("seeded_acquisition_attempt_counts", attempts == execution.get("metrics", {}).get("persisted_new_response_attempts"),
                  offline=offline, persisted_new_response_attempts=attempts)
        for entry in acquisition:
            key = entry["input_hash"]
            envelope = envelopes.get(key)
            if envelope is not None:
                audit.add("seeded_acquisition_response_identity", entry.get("source_id") == next(
                    job["source_id"] for job in jobs if job["input_hash"] == key)
                    and entry.get("request_hash") == envelope["request_hash"] and entry.get("status") == "complete",
                    input_hash=key, offline=offline)
            provenance_path = Path(entry.get("initial_acquisition_provenance_path", "")).resolve()
            allowed = interim / "cache/extraction/envelope_provenance"
            if provenance_path.is_relative_to(allowed.resolve()):
                provenance = audit.load(provenance_path, "seeded_initial_acquisition_provenance")
                initial = next(row for row in live["response_acquisition"] if row["input_hash"] == key)
                expected = {name: value for name, value in initial.items()
                            if name != "initial_acquisition_provenance_path"}
                audit.add("seeded_initial_acquisition_provenance_matches_live", provenance == expected,
                          input_hash=key, offline=offline)
            else:
                audit.add("seeded_initial_acquisition_provenance_isolated", False, input_hash=key, offline=offline)
        directory = Path(execution.get("approved_response_directory", "")).resolve()
        audit.add("approved_response_directory_isolated", directory.is_relative_to(interim.resolve()), offline=offline)
        if directory.is_relative_to(interim.resolve()):
            for job in jobs:
                audit.compare(directory / f"{job['input_hash']}.json", folder / "responses" / f"{job['input_hash']}.json",
                              f"approved_envelope_copy:{offline}:{job['input_hash']}")
    complete = all(report.get("status") == "complete" for report in (live, replay)) and len(envelopes) == len(jobs)
    if complete:
        confidence = read_json(audit.root / "config/analysis.json")["extraction_confidence"]
        regenerated = regenerated_grounding(jobs, envelopes, config, confidence)
        for name, expected in regenerated.items():
            actual = audit.load(live_path / name, "seeded_regenerated_grounding_file", jsonl=True)
            audit.add("seeded_grounding_regenerated", actual == expected, artifact=name,
                      expected_rows=len(expected), expected_digest=digest(expected), actual_digest=digest(actual))
        counts = {"candidate_records": len(regenerated["candidates.jsonl"]),
                  "grounded_records": len(regenerated["observations_progress.jsonl"]),
                  "retained_records": len(regenerated["observations.jsonl"]),
                  "rejected_candidates": len(regenerated["rejections.jsonl"]), "complete_jobs": len(jobs)}
        for report in (live, replay):
            audit.add("seeded_extraction_counts_regenerated", all(report["metrics"].get(key) == value
                      for key, value in counts.items()), **counts)
    else:
        counts = {}
        audit.add("seeded_complete_extraction_available", None, live_status=live.get("status"), replay_status=replay.get("status"))
    return {"execution_complete": complete, "jobs_verified": len(envelopes), **counts,
            "live_new_response_attempts": live.get("metrics", {}).get("persisted_new_response_attempts"),
            "offline_new_response_attempts": replay.get("metrics", {}).get("persisted_new_response_attempts"),
            "reused_discovery_jobs": live.get("metrics", {}).get("reused_discovery_jobs")}


def verify_seeded_semantic_review(audit: Audit, interim: Path, results: Path) -> dict:
    """Regenerate exact infection and taxonomy annotations from saved source evidence."""
    folders = (interim / "semantic_review", interim / "offline_replay/semantic_review")
    live = audit.load(folders[0] / "metrics.json", "live_seeded_semantic_metrics")
    replay = audit.load(folders[1] / "metrics.json", "replay_seeded_semantic_metrics")
    if not isinstance(live, dict) or not isinstance(replay, dict):
        return {"execution_complete": False}
    for name in ("observations.jsonl", "decisions.jsonl"):
        audit.compare(folders[0] / name, folders[1] / name, f"seeded_semantic_data_replay:{name}")
    left = {key: value for key, value in live.items() if key != "offline"}
    right = {key: value for key, value in replay.items() if key != "offline"}
    audit.add("seeded_semantic_metrics_replay", left == right, ignored_fields=["offline"],
              live_digest=digest(left), replay_digest=digest(right))
    reports = []
    for metrics, report_root, offline in ((live, results, False), (replay, results / "offline_replay", True)):
        report = audit.load(report_root / "semantic_review.json", "seeded_semantic_result_report")
        if isinstance(report, dict):
            reports.append({key: value for key, value in report.items() if key not in {"offline", "completed_at"}})
            audit.add("seeded_semantic_result_metrics", all(report.get(key) == value for key, value in metrics.items()),
                      offline=offline)
    audit.add("seeded_semantic_report_replay", len(reports) == 2 and reports[0] == reports[1],
              ignored_fields=["offline", "completed_at"])
    try:
        index = read_json(interim / "extraction_payloads/index.json")
        jobs = {entry["input_hash"]: read_json(interim / "extraction_payloads" / f"{entry['input_hash']}.json")
                for entry in index["jobs"]}
        raw_path = interim / "extraction/observations.jsonl"
        records = read_jsonl(raw_path)
        adjudications = read_json(results / "semantic_adjudications.json")
        source_adjudications = read_json(results / "source_design_adjudications.json")
        retained, decisions = apply_seeded_adjudications(records, jobs, adjudications)
        designs = validate_source_design_annotations(source_adjudications, jobs)
        focal = summarize_seeded_focal_recovery(retained, decisions, designs)
        for name, expected in (("observations.jsonl", retained), ("decisions.jsonl", decisions)):
            actual = audit.load(folders[0] / name, "seeded_semantic_regenerated_file", jsonl=True)
            audit.add("seeded_semantic_regenerated", actual == expected, artifact=name,
                      expected_digest=digest(expected), actual_digest=digest(actual), expected_rows=len(expected))
        expected_metrics = {
            "input_records": len(records), "included": len(retained), "excluded": len(records) - len(retained),
            "infection_status_counts": dict(Counter(row["infection_status"] for row in retained)),
            "reviewed_infection_status_counts": dict(Counter(row["infection_status"] for row in decisions)),
            "origin_counts": dict(Counter(row["record_origin"] for row in retained)),
            "focal_recovery": focal, "raw_input_sha256": file_hash(raw_path),
            "adjudications_hash": digest(adjudications), "source_design_adjudications_hash": digest(source_adjudications),
            "taxonomy_query_expansions": sum("taxonomy_query_name" in row for row in retained),
            "independent_experiment_count": len({(row["source_id"], row["experiment_id"]) for row in retained}),
            "analysis_performed": False,
        }
        audit.add("seeded_semantic_counts_and_provenance_regenerated", all(
            live.get(key) == value for key, value in expected_metrics.items()), **expected_metrics)
        audit.add("seeded_semantic_report_decisions_regenerated", all(
            report.get("decisions") == decisions for report in reports) and len(reports) == 2)
        audit.add("seeded_semantic_model_record_ids_preserved", all(
            row["record_origin"] == "model_record" and row["record_id"] in {item["record_id"] for item in records}
            for row in retained), curator_added_records=sum(row["record_origin"] != "model_record" for row in retained))
    except (OSError, KeyError, TypeError, ValueError) as error:
        audit.add("seeded_semantic_regeneration", False, reason=str(error))
        return {"execution_complete": False}
    return {"execution_complete": live.get("status") == replay.get("status") == "complete",
            "input_records": len(records), "included": len(retained), "excluded": len(decisions) - len(retained),
            "focal_recovery": focal, "record_origin_counts": expected_metrics["origin_counts"],
            "taxonomy_query_expansions": expected_metrics["taxonomy_query_expansions"]}


def downstream_replay_value(value: object) -> object:
    """Canonicalize named execution fields while preserving every scientific metric.

    Only metric and report dictionaries use this function. Source and result rows
    are compared as exact bytes. Named paths preserve the whole path apart from
    the explicitly isolated seeded offline directory segment.
    """
    if isinstance(value, list):
        return [downstream_replay_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in DOWNSTREAM_OPERATIONAL_FIELDS:
            continue
        if key in DOWNSTREAM_PATH_FIELDS and isinstance(item, str):
            result[key] = item.replace("/monarch_seeded/offline_replay/", "/monarch_seeded/")
        elif key == "input_hashes" and isinstance(item, dict):
            result[key] = {path.replace("/monarch_seeded/offline_replay/", "/monarch_seeded/"): expected
                           for path, expected in item.items()}
        else:
            result[key] = downstream_replay_value(item)
    return result


def verify_downstream_input_hashes(audit: Audit, value: object) -> None:
    """Resolve explicit stage input path/hash pairs against current local files."""
    if isinstance(value, list):
        for item in value:
            verify_downstream_input_hashes(audit, item)
        return
    if not isinstance(value, dict):
        return
    pairs = list(value.get("input_hashes", {}).items())
    for path_key, hash_key in (
        ("input_path", "input_sha256"), ("source_input_path", "source_input_sha256"),
        ("genus_input_path", "genus_input_sha256"), ("contract_path", "contract_sha256"),
        ("selected_source_rows_path", "selected_source_rows_sha256"), ("config_path", "config_sha256"),
    ):
        if path_key in value and hash_key in value:
            pairs.append((value[path_key], value[hash_key]))
    for name, expected in pairs:
        path = Path(name).resolve()
        isolated = path.is_relative_to(audit.root)
        actual = file_hash(path) if isolated and path.is_file() else None
        audit.add("seeded_downstream_input_checksum", isolated and actual == expected,
                  path=audit.path(path), expected_sha256=expected, actual_sha256=actual)
    for item in value.values():
        verify_downstream_input_hashes(audit, item)


def verify_pinned_lotus_export(audit: Audit, interim: Path, report: dict) -> None:
    """Verify the pinned export's cache request, complete body, and published checksum."""
    key = report.get("download_request_hash")
    cache = interim / "cache/chemistry_export/downloads"
    metadata = audit.load(cache / f"{key}.json", "seeded_lotus_download_metadata")
    body = cache / f"{key}.body"
    if not isinstance(metadata, dict) or not body.is_file():
        audit.add("seeded_lotus_pinned_export", None, reason="cached_export_missing")
        return
    descriptor = {"method": "GET", "url": report.get("download_url"), "params": {}, "json": None}
    audit.add("seeded_lotus_download_request_identity", metadata.get("request") == descriptor
              and metadata.get("request_hash") == key == digest(descriptor))
    sha256, md5 = file_hash(body), file_hash(body, "md5")
    audit.add("seeded_lotus_pinned_export", report.get("database_version") == "zenodo:6582121:v4"
              and report.get("export_doi") == "10.5281/zenodo.6582121"
              and report.get("checksum_verified") is True
              and metadata.get("complete") is True and metadata.get("status") == 200
              and sha256 == metadata.get("sha256") == report.get("file_sha256")
              and md5 == metadata.get("md5") and f"md5:{md5}" == report.get("published_checksum")
              and body.stat().st_size == metadata.get("bytes") == report.get("file_bytes"),
              path=audit.path(body), sha256=sha256, md5=md5, bytes=body.stat().st_size)


def verify_record_context_preservation(audit: Audit, interim: Path, stage: str) -> None:
    """Check infection and model identity through completed taxonomy and behaviour rows."""
    originals = {row["record_id"]: row for row in read_jsonl(interim / "semantic_review/observations.jsonl")}
    retained_fields = (
        "target_name_as_written", "source_id", "input_hash", "evidence_quote", "direction",
        "record_origin", "infection_status", "experiment_id", "focal_eligible",
        "infection_comparison_eligible", "raw_model_record", "raw_model_record_hash",
        "taxonomy_query_name", "taxonomy_query_evidence",
    )
    for row in read_jsonl(interim / stage / "observations.jsonl"):
        original = originals.get(row["record_id"])
        audit.add("seeded_downstream_record_context_preserved", original is not None and all(
            row.get(key) == original.get(key) for key in retained_fields), stage=stage, record_id=row["record_id"])


def verify_seeded_downstream(audit: Audit, interim: Path, results: Path) -> dict:
    """Compare each executed downstream stage and preserve unavailable scientific values."""
    live = audit.load(results / "downstream_manifest.json", "live_seeded_downstream_manifest")
    replay = audit.load(results / "offline_replay/downstream_manifest.json", "replay_seeded_downstream_manifest")
    if not isinstance(live, dict) or not isinstance(replay, dict):
        return {"execution_complete": False, "stage_statuses": {}, "completed_stages": []}
    statuses, completed = {}, []
    for stage, required in STAGE_FILES.items():
        index = len(audit.checks)
        left_dir, right_dir = interim / stage, interim / "offline_replay" / stage
        left = audit.load(left_dir / "metrics.json", f"seeded_{stage}_live_metrics")
        right = audit.load(right_dir / "metrics.json", f"seeded_{stage}_replay_metrics")
        if not isinstance(left, dict) or not isinstance(right, dict):
            statuses[stage] = checks_status(audit.checks[index:])
            continue
        scientific_left, scientific_right = downstream_replay_value(left), downstream_replay_value(right)
        audit.add("seeded_downstream_metrics_replay", scientific_left == scientific_right, stage=stage,
                  live_digest=digest(scientific_left), replay_digest=digest(scientific_right),
                  ignored_fields=sorted(DOWNSTREAM_OPERATIONAL_FIELDS), canonical_path_fields=sorted(DOWNSTREAM_PATH_FIELDS))
        audit.add("seeded_downstream_metrics_match_manifest", live.get("stages", {}).get(stage) == left
                  and replay.get("stages", {}).get(stage) == right, stage=stage)
        verify_downstream_input_hashes(audit, left)
        verify_downstream_input_hashes(audit, right)
        complete = left.get("status") in {"complete", "completed"} and right.get("status") in {"complete", "completed"}
        if complete:
            completed.append(stage)
        names = {path.name for folder in (left_dir, right_dir) for path in folder.glob("*.jsonl")}
        if complete:
            names.update(required)
            if stage == "behaviour":
                names.add("aggregation_input.jsonl")
        for name in sorted(names):
            audit.compare(left_dir / name, right_dir / name, f"seeded_downstream_data_replay:{stage}/{name}")
        if complete and stage in {"taxonomy", "behaviour"}:
            try:
                verify_record_context_preservation(audit, interim, stage)
            except (OSError, KeyError, ValueError, TypeError) as error:
                audit.add("seeded_downstream_record_context_preserved", False, stage=stage, reason=str(error))
        manifests = {path.name for folder in (left_dir, right_dir) for path in folder.glob("*.json")
                     if path.name != "metrics.json"}
        for name in sorted(manifests):
            left_report = audit.load(left_dir / name, "seeded_downstream_stage_report")
            right_report = audit.load(right_dir / name, "seeded_downstream_stage_report")
            if isinstance(left_report, dict) and isinstance(right_report, dict):
                audit.add("seeded_downstream_stage_report_replay", downstream_replay_value(left_report)
                          == downstream_replay_value(right_report), stage=stage, artifact=name)
                verify_downstream_input_hashes(audit, left_report)
                verify_downstream_input_hashes(audit, right_report)
                if stage == "chemistry" and name == "run_manifest.json" and complete:
                    verify_pinned_lotus_export(audit, interim, left_report)
        if stage == "chemistry" and complete:
            for name in ("occurrence_contract.csv", "selected_export_records.jsonl", "transform_review.jsonl"):
                audit.compare(interim / "chemistry_transform" / name,
                              interim / "offline_replay/chemistry_transform" / name,
                              f"seeded_chemistry_transform_replay:{name}")
        statuses[stage] = checks_status(audit.checks[index:])
    manifests = [downstream_replay_value({key: value for key, value in report.items()
                                         if key not in DOWNSTREAM_MANIFEST_OPERATIONAL_FIELDS})
                 for report in (live, replay)]
    audit.add("seeded_downstream_manifest_replay", manifests[0] == manifests[1],
              live_digest=digest(manifests[0]), replay_digest=digest(manifests[1]),
              ignored_top_level_fields=sorted(DOWNSTREAM_MANIFEST_OPERATIONAL_FIELDS),
              ignored_fields=sorted(DOWNSTREAM_OPERATIONAL_FIELDS))
    left_funnel = audit.load(results / "funnel.json", "live_seeded_funnel")
    right_funnel = audit.load(results / "offline_replay/funnel.json", "replay_seeded_funnel")
    if isinstance(left_funnel, dict) and isinstance(right_funnel, dict):
        audit.add("seeded_funnel_replay", downstream_replay_value(left_funnel) == downstream_replay_value(right_funnel),
                  live_digest=digest(downstream_replay_value(left_funnel)), replay_digest=digest(downstream_replay_value(right_funnel)))
        audit.add("seeded_funnel_matches_manifest", live.get("funnel") == left_funnel and replay.get("funnel") == right_funnel)
    semantic_path = interim / "semantic_review/observations.jsonl"
    audit.add("seeded_downstream_uses_reviewed_input", all(
        report.get("semantic_input_path") == str(semantic_path)
        and report.get("semantic_input_audit", {}).get("input_sha256") == file_hash(semantic_path)
        for report in (live, replay)))
    audit.add("seeded_no_analysis_or_export_download", all(report.get("analysis_performed") is False
              and report.get("lotus_export_network_downloads") == 0 for report in (live, replay)))
    return {"execution_complete": live.get("status") == replay.get("status") == "complete"
            and len(completed) == len(STAGE_FILES), "stage_statuses": statuses, "completed_stages": completed,
            "live_status": live.get("status"), "offline_status": replay.get("status")}


def forbid_live_request(request: httpx.Request) -> httpx.Response:
    """Reject transport use during verification before any network request is sent."""
    raise RuntimeError(f"verification_transport_forbidden:{request.method}")


def verify_repository_replay(audit: Audit, cache_root: Path) -> dict:
    """Replay cached repository responses, including their original HTTP failures."""
    paths = sorted((cache_root / "http").glob("*.json"))
    audit.add("repository_response_cache_available", bool(paths), cached_requests=len(paths))
    cache = CachedHTTP(cache_root, offline=True, interval=0,
                       client=httpx.Client(transport=httpx.MockTransport(forbid_live_request)))
    replayed = []
    try:
        for path in paths:
            before = file_hash(path)
            record = audit.load(path, "repository_cached_response_read")
            if not isinstance(record, dict):
                continue
            try:
                descriptor = record["request"]
                expected = record["attempts"][-1]
                expected_body = base64.b64decode(expected["body_base64"], validate=True)
                expected_status = expected["status"]
                actual_status, actual_body = None, None
                try:
                    actual_body, key = cache.request(
                        descriptor["method"], descriptor["url"],
                        params=descriptor["params"], body=descriptor["json"],
                    )
                    actual_status = expected_status
                    audit.add("repository_replay_request_identity", key == path.stem,
                              path=audit.path(path), request_hash=key)
                except httpx.HTTPStatusError as error:
                    actual_status, actual_body = error.response.status_code, error.response.content
                body_hash = hashlib.sha256(expected_body).hexdigest()
                audit.add("repository_response_offline_replay",
                          actual_status == expected_status and actual_body == expected_body,
                          path=audit.path(path), request_hash=path.stem,
                          expected_status=expected_status, replay_status=actual_status,
                          expected_response_sha256=body_hash,
                          replay_response_sha256=hashlib.sha256(actual_body).hexdigest()
                          if actual_body is not None else None)
                replayed.append({"request_hash": path.stem, "status": actual_status,
                                 "response_sha256": body_hash})
            except (KeyError, IndexError, TypeError, ValueError, httpx.HTTPError,
                    OfflineCacheMiss, RuntimeError) as error:
                audit.add("repository_response_offline_replay", False,
                          path=audit.path(path), reason=str(error))
            audit.add("repository_response_cache_unchanged", file_hash(path) == before,
                      path=audit.path(path), original_cache_sha256=before,
                      current_cache_sha256=file_hash(path))
    finally:
        cache.close()
    return {"requests_replayed": len(replayed), "responses": replayed,
            "offline": True, "live_transport_forbidden": True}


def checks_status(checks: list[dict]) -> str:
    """Summarize only checks actually attempted within one verification scope."""
    if any(row["status"] == "failed" for row in checks):
        return "failed"
    if not checks or any(row["status"] == "unavailable" for row in checks):
        return "unavailable"
    return "passed"


def verify_seeded_partial(root: Path) -> dict:
    """Verify all available seeded stages without any live API requests.

    Args:
        root: Repository root containing seeded live artifacts and offline replays.

    Returns:
        A scoped verification report with null values for stages that have not run.
    """
    root = Path(root).resolve()
    results = seeded_results(root)
    interim = root / "data/interim/systems/monarch_seeded"
    audit = Audit(root)
    snapshot = verify_original_snapshot(audit, results)
    historical = verify_historical_original(audit)
    verify_primary(audit)
    preservation_status = checks_status(audit.checks)
    index = len(audit.checks)
    verify_seed_access(audit, interim)
    access_status = checks_status(audit.checks[index:])
    index = len(audit.checks)
    local_pdfs = verify_local_pdf_import(audit, interim, results)
    local_pdf_status = checks_status(audit.checks[index:])
    index = len(audit.checks)
    preparation = verify_seeded_preparation(audit, interim, results)
    preparation_status = checks_status(audit.checks[index:])
    index = len(audit.checks)
    source_design = verify_source_design_review(audit, interim, results)
    source_design_status = checks_status(audit.checks[index:])
    extraction, semantic, downstream = {}, {}, {}
    extraction_status, semantic_status, downstream_status = None, None, None
    if (interim / "extraction/run_manifest.json").is_file():
        index = len(audit.checks)
        extraction = verify_seeded_extraction(audit, interim, results)
        extraction_status = checks_status(audit.checks[index:])
    if (interim / "semantic_review/observations.jsonl").is_file():
        index = len(audit.checks)
        semantic = verify_seeded_semantic_review(audit, interim, results)
        semantic_status = checks_status(audit.checks[index:])
    if (results / "downstream_manifest.json").is_file():
        index = len(audit.checks)
        downstream = verify_seeded_downstream(audit, interim, results)
        downstream_status = checks_status(audit.checks[index:])
    index = len(audit.checks)
    verify_seeded_assays(audit, interim)
    assay_status = checks_status(audit.checks[index:])
    index = len(audit.checks)
    repository = verify_repository_replay(audit, interim / "cache/repository")
    repository_status = checks_status(audit.checks[index:])
    inventory, hashes = verify_seed_cache(audit, interim / "cache")
    status = checks_status(audit.checks)
    result = {
        "schema_version": 1, "system": "monarch_seeded", "verified_at": timestamp(),
        "status": status,
        "verification_scope": "available_retrieval_pdf_preparation_extraction_semantic_review_and_downstream_stages",
        "pipeline_complete": all(row.get("execution_complete") is True for row in (extraction, semantic, downstream)),
        "network_calls": 0, "model_calls": 0,
        "live_api_calls_during_verification": 0,
        "stage_verification": {
            "original_and_primary_preservation": preservation_status,
            "seed_access_and_metadata": access_status, "assay_scope": assay_status,
            "repository_access": repository_status,
            "local_pdf_import": local_pdf_status,
            "source_design_review": source_design_status,
            "corpus_preparation": preparation_status,
            "extraction": extraction_status, "semantic_review": semantic_status,
            "downstream_summary": downstream_status,
            **{stage: downstream.get("stage_statuses", {}).get(stage)
               for stage in ("taxonomy", "behaviour", "chemistry", "bioactivity")},
        },
        "unverified_stage_note": "Null stages have no executed artifact set. Pipeline completion describes execution; preservation failures remain explicit.",
        "original_snapshot_verification": snapshot,
        "historical_original_verification": historical,
        "repository_access_replay": repository,
        "corpus_preparation_replay": preparation,
        "local_pdf_import_replay": local_pdfs,
        "source_design_review_verification": source_design,
        "extraction_verification": extraction or None,
        "semantic_review_verification": semantic or None,
        "downstream_verification": downstream or None,
        "passed_checks": sum(row["status"] == "passed" for row in audit.checks),
        "failed_checks": sum(row["status"] == "failed" for row in audit.checks),
        "unavailable_checks": sum(row["status"] == "unavailable" for row in audit.checks),
        "cache_inventory": inventory, "unique_request_hashes": hashes,
        "unique_request_count": len(hashes), "checks": audit.checks,
    }
    write_json(results / "verification.json", result)
    return result
