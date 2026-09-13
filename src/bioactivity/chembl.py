"""Fetch exact ChEMBL structures and independently verified organism assays."""

from pathlib import Path

import httpx

from src.bioactivity.labels import label_compounds
from src.common.cache import CachedHTTP, OfflineCacheMiss
from src.common.io import write_json, write_jsonl

BASE = "https://www.ebi.ac.uk/chembl/api/data"
BATCH_SIZE = 50
RETRIEVAL_ERRORS = (httpx.HTTPError, OfflineCacheMiss, ValueError, KeyError, TypeError, RuntimeError)


def pages(
    cache: CachedHTTP, resource: str, collection: str, params: dict,
    requests: list[dict] | None = None,
) -> list[dict]:
    """Follow every cached page and reject inconsistent or incomplete pagination."""
    offset = 0
    rows = []
    expected = None
    while True:
        query = {**params, "limit": 1000, "offset": offset}
        payload, key = cache.get_json(f"{BASE}/{resource}.json", query)
        if requests is not None:
            requests.append({"resource": resource, "params": query, "request_hash": key})
        batch = payload[collection]
        metadata = payload["page_meta"]
        total = int(metadata["total_count"])
        if expected is not None and total != expected:
            raise ValueError("ChEMBL total count changed during pagination")
        expected = total
        rows.extend({**row, "request_hash": key} for row in batch)
        if not metadata.get("next"):
            if len(rows) != expected:
                raise ValueError("ChEMBL pagination ended before the complete result set")
            break
        if not batch:
            raise ValueError("ChEMBL returned an empty page with a next-page link")
        offset += len(batch)
    return rows


def verified_service(cache: CachedHTTP, requests: list[dict]) -> dict:
    """Archive the database version and verify supported batch-filter contracts."""
    payloads = {}
    hashes = {}
    for resource in ("status", "activity/schema", "molecule/schema", "assay/schema"):
        payload, key = cache.get_json(f"{BASE}/{resource}.json")
        payloads[resource] = payload
        hashes[resource] = key
        requests.append({"resource": resource, "params": {}, "request_hash": key})
    molecule_filters = payloads["molecule/schema"]["fields"]["molecule_structures"]["schema"]["filtering"]
    assay_filters = payloads["assay/schema"]["filtering"]
    activity_filters = payloads["activity/schema"]["filtering"]
    if "in" not in molecule_filters["standard_inchi_key"]:
        raise ValueError("Exact InChIKey batch filter is not supported by ChEMBL schema")
    if "in" not in assay_filters["assay_organism"]:
        raise ValueError("Assay organism batch filter is not supported by ChEMBL schema")
    if "molecule_chembl_id" not in activity_filters or "in" not in activity_filters["standard_type"]:
        raise ValueError("Required activity filters are not supported by ChEMBL schema")
    return {"status": payloads["status"], "request_hashes": hashes}


def eligible_assays(cache: CachedHTTP, config: dict, requests: list[dict]) -> dict[str, dict]:
    """Enumerate exact eligible assay organisms without using target organism."""
    rows = pages(
        cache, "assay", "assays",
        {"assay_organism__in": ",".join(config["organisms"]), "assay_type": "F"}, requests,
    )
    if any(row.get("assay_organism") not in config["organisms"] or row.get("assay_type") != "F" for row in rows):
        raise ValueError("ChEMBL returned assays outside the requested organism/type filters")
    assays = {row["assay_chembl_id"]: row for row in rows}
    if len(assays) != len(rows):
        raise ValueError("Duplicate assays in the supposedly complete ChEMBL inventory")
    return assays


def resolve_batch(
    compounds: list[str], cache: CachedHTTP, requests: list[dict],
) -> dict[str, list[dict]]:
    """Resolve a batch while checking every returned full InChIKey exactly."""
    rows = pages(
        cache, "molecule", "molecules",
        {"molecule_structures__standard_inchi_key__in": ",".join(compounds)}, requests,
    )
    resolved = {compound: [] for compound in compounds}
    for row in rows:
        key = (row.get("molecule_structures") or {}).get("standard_inchi_key")
        if key not in resolved:
            raise ValueError("ChEMBL returned a molecule outside the exact InChIKey batch")
        resolved[key].append(row)
    return resolved


def activity_batch(
    molecule_map: dict[str, dict], assays: dict[str, dict], cache: CachedHTTP,
    config: dict, requests: list[dict],
) -> list[dict]:
    """Fetch all functional endpoints and attach the complete verified assay join."""
    if not molecule_map:
        return []
    records = pages(
        cache, "activity", "activities",
        {
            "molecule_chembl_id__in": ",".join(sorted(molecule_map)),
            "standard_type__in": ",".join(config["endpoints"]), "assay_type": "F",
        }, requests,
    )
    measurements = []
    for row in records:
        molecule = molecule_map.get(row["molecule_chembl_id"])
        if molecule is None or row.get("standard_type") not in config["endpoints"] or row.get("assay_type") != "F":
            raise ValueError("ChEMBL returned an activity outside the requested filters")
        assay = assays.get(row["assay_chembl_id"], {})
        measurements.append({
            **row,
            "compound_id": molecule["compound_id"],
            "assay": assay,
            "assay_request_hash": assay.get("request_hash"),
            "assay_verification": (
                "exact_assay_organism_and_type" if assay
                else "absent_from_complete_eligible_assay_inventory"
            ),
            "molecule_request_hash": molecule["request_hash"],
        })
    return measurements


def write_results(
    compounds: list[str], measurements: list[dict], statuses: list[dict], config: dict,
    output: Path, service: dict, requests: list[dict], blocked_reason: str | None = None,
) -> dict:
    """Write complete or partial retrieval outputs without relabelling failures."""
    labels, audit = label_compounds(compounds, measurements, config)
    status_map = {row["compound_id"]: row for row in statuses}
    labels = [
        {**row, "retrieval_status": status_map[row["compound_id"]]["status"]}
        for row in labels
    ]
    write_jsonl(output / "retrieval_status.jsonl", statuses)
    write_jsonl(output / "measurements.jsonl", audit)
    write_jsonl(output / "labels.jsonl", labels)
    write_json(output / "query_manifest.json", {
        "service": service, "requests": requests,
        "retrieval_strategy": "exact_full_inchikey_batches_and_complete_eligible_assay_inventory",
        "assay_identity_rule": "assay_organism exact match; target_organism never substitutes",
        "config": config,
    })
    failed = sum(row["status"] == "failed" for row in statuses)
    metrics = {
        "status": "blocked" if blocked_reason else "partial" if failed else "complete",
        "blocked_reason": blocked_reason,
        "incomplete_reason": "compound_retrieval_failures" if failed and not blocked_reason else None,
        "compounds": len(labels),
        "matched_compounds": sum(row.get("molecules", 0) > 0 for row in statuses),
        "active": sum(row["label"] == "active" for row in labels),
        "inactive": sum(row["label"] == "inactive" for row in labels),
        "unknown": sum(row["label"] == "unknown" for row in labels),
        "failed_compounds": failed,
        "retrieved_measurements": len(audit),
        "classified_measurements": sum(row["label"] != "unknown" for row in audit),
        "discordant_compounds": sum(row["discordant"] for row in labels),
        "unique_assays_with_classified_measurements": len({row["assay_chembl_id"] for row in audit if row["label"] != "unknown"}),
        "database_status": service.get("status"),
        "cached_requests": len({row["request_hash"] for row in requests}),
    }
    write_json(output / "metrics.json", metrics)
    return metrics


def retrieve_labels(compound_ids: list[str], cache: CachedHTTP, output: Path, config: dict) -> dict:
    """Retrieve all structures in deterministic batches with conservative failure handling."""
    compounds = sorted(set(compound_ids))
    measurements, statuses, requests = [], [], []
    service = {}
    if not compounds:
        return write_results(compounds, [], [], config, output, service, requests)
    try:
        service = verified_service(cache, requests)
        assays = eligible_assays(cache, config, requests)
        service["eligible_assays"] = len(assays)
        write_jsonl(output / "eligible_assays.jsonl", list(assays.values()))
    except RETRIEVAL_ERRORS as error:
        statuses = [{"compound_id": compound, "status": "failed", "reason": str(error)} for compound in compounds]
        return write_results(
            compounds, [], statuses, config, output, service, requests,
            f"assay_inventory_or_service_verification_failed:{type(error).__name__}",
        )
    for start in range(0, len(compounds), BATCH_SIZE):
        batch = compounds[start:start + BATCH_SIZE]
        request_start = len(requests)
        try:
            resolved = resolve_batch(batch, cache, requests)
            molecule_map = {
                row["molecule_chembl_id"]: {**row, "compound_id": compound}
                for compound, rows in resolved.items() for row in rows
            }
            current = activity_batch(molecule_map, assays, cache, config, requests)
            measurements.extend(current)
            statuses.extend({
                "compound_id": compound, "status": "complete", "molecules": len(resolved[compound]),
                "molecule_chembl_ids": [row["molecule_chembl_id"] for row in resolved[compound]],
                "request_hashes": [row["request_hash"] for row in requests[request_start:]],
            } for compound in batch)
        except RETRIEVAL_ERRORS as error:
            statuses.extend({
                "compound_id": compound, "status": "failed", "reason": str(error),
                "request_hashes": [row["request_hash"] for row in requests[request_start:]],
            } for compound in batch)
        completed = [row["compound_id"] for row in statuses]
        write_results(completed, measurements, statuses, config, output, service, requests)
    return write_results(compounds, measurements, statuses, config, output, service, requests)
