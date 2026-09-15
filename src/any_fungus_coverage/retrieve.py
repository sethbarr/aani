"""Unfiltered ChEMBL activity retrieval for exact mapped structures."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from src.any_fungus_coverage.http import PublicCache
from src.bioactivity.chembl import pages, resolve_batch
from src.chemical_distance.datasets import read_jsonl

BASE = "https://www.ebi.ac.uk/chembl/api/data"
DEADLINE = datetime(2026, 9, 15, 1, 25, tzinfo=UTC)


def write_json(path: Path, value: object) -> None:
    """Atomically store a reproducible stage result."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False))
    temporary.replace(path)


def retrieve_batch(task: tuple[str, int, list[str], Path, bool]) -> dict:
    """Retrieve one identity, activity, or assay batch into an isolated file."""
    stage, index, identifiers, root, offline = task
    path = root / stage / f"{index:05}.json"
    cache = PublicCache(root / "http", offline)
    requests: list[dict] = []
    result = {"index": index, "identifiers": identifiers, "requests": requests}
    try:
        if not offline and datetime.now(UTC) >= DEADLINE:
            raise RuntimeError("Retrieval stopping time reached")
        if stage == "molecules":
            result["rows"] = resolve_batch(identifiers, cache, requests)
        elif stage == "activities":
            result["rows"] = pages(
                cache,
                "activity",
                "activities",
                {"molecule_chembl_id__in": ",".join(identifiers), "order_by": "activity_id"},
                requests,
            )
            assert all(row["molecule_chembl_id"] in identifiers for row in result["rows"])
            assert len({r["activity_id"] for r in result["rows"]}) == len(result["rows"])
        else:
            result["rows"] = pages(
                cache, "assay", "assays", {"assay_chembl_id__in": ",".join(identifiers)}, requests
            )
            assert {r["assay_chembl_id"] for r in result["rows"]} == set(identifiers)
        result["status"] = "complete"
    except (RuntimeError, ValueError, KeyError, AssertionError) as error:
        result.update(status="incomplete", error=str(error))
    finally:
        cache.client.close()
    if offline:
        stored = json.loads(path.read_text())
        assert result == stored, f"Offline result differs: {path}"
    else:
        write_json(path, result)
    return result


def run_stage(stage: str, identifiers: list[str], root: Path, offline: bool) -> list[dict]:
    """Run three bounded public retrieval workers and report progress."""
    size = 50
    tasks = [
        (stage, index // size, identifiers[index : index + size], root, offline)
        for index in range(0, len(identifiers), size)
    ]
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(retrieve_batch, task) for task in tasks]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"{stage} {len(results)}/{len(tasks)} batch={result['index']} {result['status']} rows={len(result.get('rows', []))}",
                flush=True,
            )
    return sorted(results, key=lambda row: row["index"])


def retrieve(root: Path, offline: bool = False) -> dict:
    """Retrieve all identities and unfiltered activities, then their assays."""
    cache = PublicCache(root / "http", offline)
    service, service_hash = cache.get_json(f"{BASE}/status.json")
    cache.client.close()
    compounds = sorted(
        {r["compound_id"] for r in read_jsonl(Path("data/processed/chemistry/occurrences.jsonl"))}
    )
    assert len(compounds) == 2198
    identities = run_stage("molecules", compounds, root, offline)
    mapping = {
        compound: [r["molecule_chembl_id"] for r in records]
        for batch in identities
        if batch["status"] == "complete"
        for compound, records in batch["rows"].items()
    }
    molecule_ids = sorted({m for ids in mapping.values() for m in ids})
    activities = run_stage("activities", molecule_ids, root, offline)
    assay_ids = sorted(
        {
            r["assay_chembl_id"]
            for batch in activities
            if batch["status"] == "complete"
            for r in batch["rows"]
        }
    )
    assays = run_stage("assays", assay_ids, root, offline)
    result = {
        "service": service,
        "service_hash": service_hash,
        "compound_to_molecules": mapping,
        "molecule_ids": molecule_ids,
        "assay_ids": assay_ids,
        "stages": {
            "molecules": [r["status"] for r in identities],
            "activities": [r["status"] for r in activities],
            "assays": [r["status"] for r in assays],
        },
    }
    if offline:
        assert result == json.loads((root / "retrieval.json").read_text())
    else:
        write_json(root / "retrieval.json", result)
    return result
