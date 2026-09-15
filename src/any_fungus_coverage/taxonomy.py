"""NCBI/ENA lineage resolution for assay taxonomy fields."""

import json
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

from src.any_fungus_coverage.http import PublicCache
from src.any_fungus_coverage.retrieve import write_json

ENA = "https://www.ebi.ac.uk/ena"


def parse_taxon(body: bytes, request_hash: str) -> dict:
    """Parse an ENA record into canonical IDs, lineage, and exact synonyms."""
    tree = ET.fromstring(body)
    node = tree.find("taxon")
    if node is None:
        raise ValueError("ENA returned no taxon")
    lineage = [dict(item.attrib) for item in node.findall("lineage/taxon")]
    return {
        "tax_id": node.attrib["taxId"],
        "scientific_name": node.attrib["scientificName"],
        "rank": node.get("rank"),
        "lineage": lineage,
        "lineage_ids": [node.attrib["taxId"], *[r["taxId"] for r in lineage]],
        "synonyms": [dict(item.attrib) for item in node.findall("synonym")],
        "merged_ids": [item.attrib["taxId"] for item in node.findall("merged/taxon")],
        "request_hash": request_hash,
    }


def taxon_by_id(cache: PublicCache, tax_id: str) -> dict:
    """Resolve an assay's taxon identifier and preserve merged-ID provenance."""
    resolution_hash = None
    try:
        body, key = cache.get(f"{ENA}/browser/api/xml/{tax_id}")
    except RuntimeError as error:
        if "404" not in str(error):
            raise
        metadata, resolution_hash = cache.get_json(f"{ENA}/taxonomy/rest/tax-id/{tax_id}")
        merged = json.loads(metadata.get("merged", "[]"))
        if metadata["taxId"] != tax_id and int(tax_id) not in merged:
            raise ValueError(f"Unverified retired taxon ID: {tax_id}") from error
        body, key = cache.get(f"{ENA}/browser/api/xml/{metadata['taxId']}")
    result = parse_taxon(body, key)
    if result["tax_id"] != tax_id and tax_id not in result["merged_ids"]:
        raise ValueError(f"Unexplained taxon ID change: {tax_id}")
    if resolution_hash:
        result["retired_id_request_hash"] = resolution_hash
    return result


def taxon_by_name(cache: PublicCache, name: str) -> dict:
    """Accept only one exact scientific-name or synonym resolution."""
    payload, key = cache.get_json(f"{ENA}/taxonomy/rest/any-name/{quote(name, safe='')}")
    if not isinstance(payload, list):
        raise ValueError("Unexpected name resolution payload")
    candidates = []
    for row in payload:
        taxon = taxon_by_id(cache, str(row["taxId"]))
        names = [taxon["scientific_name"], *[s["name"] for s in taxon["synonyms"]]]
        if name.casefold() in {n.casefold() for n in names}:
            candidates.append(taxon)
    unique = {r["tax_id"]: r for r in candidates}
    if len(unique) != 1:
        raise ValueError(f"Name has {len(unique)} exact taxonomic resolutions: {name}")
    return {**next(iter(unique.values())), "name_request_hash": key}


def resolve_one(task: tuple[str, str, Path, bool]) -> tuple[str, dict]:
    """Resolve one distinct assay taxon ID or explicitly missing-ID name."""
    kind, value, root, offline = task
    cache = PublicCache(root / "http", offline)
    try:
        taxon = taxon_by_id(cache, value) if kind == "id" else taxon_by_name(cache, value)
        result = {"status": "resolved", "method": kind, "input": value, **taxon}
    except (RuntimeError, ValueError, KeyError, ET.ParseError) as error:
        result = {"status": "unresolved", "method": kind, "input": value, "error": str(error)}
    finally:
        cache.client.close()
    return f"{kind}:{value}", result


def resolve_assays(root: Path, offline: bool = False) -> dict:
    """Resolve every unique assay identity without organism-name filtering."""
    assays = [
        row
        for path in sorted((root / "assays").glob("*.json"))
        for row in json.loads(path.read_text()).get("rows", [])
    ]
    keys = sorted(
        {
            ("id", str(a["assay_tax_id"]))
            if a.get("assay_tax_id")
            else ("name", a["assay_organism"])
            for a in assays
            if a.get("assay_tax_id") or a.get("assay_organism")
        }
    )
    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(resolve_one, (*key, root, offline)) for key in keys]
        for future in as_completed(futures):
            key, value = future.result()
            results[key] = value
            if len(results) % 25 == 0 or value["status"] != "resolved":
                print(f"taxonomy {len(results)}/{len(keys)} {key} {value['status']}", flush=True)
    if offline:
        assert results == json.loads((root / "taxonomy.json").read_text())
    else:
        write_json(root / "taxonomy.json", results)
    return results
