"""Verify seeded monarch identifiers and cache Europe PMC full-text access."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from src.common.cache import CachedHTTP, OfflineCacheMiss
from src.common.io import digest, read_json, timestamp, write_json, write_jsonl
from src.corpus.europepmc import BASE, local_name, parse_fulltext

SEEDS = [
    {"seed_id": "lefevre_2010", "pmid": "21040353", "doi": "10.1111/j.1461-0248.2010.01537.x",
     "title": "Evidence for trans-generational medication in nature", "year": "2010"},
    {"seed_id": "lefevre_2012", "pmid": "21939438", "doi": "10.1111/j.1365-2656.2011.01901.x",
     "title": "Behavioural resistance against a protozoan parasite in the monarch butterfly", "year": "2012"},
    {"seed_id": "deroode_2008", "pmid": "18177332", "doi": "10.1111/j.1365-2656.2007.01305.x",
     "title": "Host plant species affects virulence in monarch butterfly parasites", "year": "2008"},
    {"seed_id": "sternberg_2012", "pmid": "23106703", "doi": "10.1111/j.1558-5646.2012.01693.x",
     "title": "Food plant derived disease tolerance and resistance in a natural butterfly-plant-parasite interactions", "year": "2012"},
    {"seed_id": "gowler_2015", "pmid": "25953502", "doi": "10.1007/s10886-015-0586-6",
     "title": "Secondary Defense Chemicals in Milkweed Reduce Parasite Infection in Monarch Butterflies, Danaus plexippus", "year": "2015"},
]


def title_key(value: str) -> str:
    """Compare bibliographic titles without case, punctuation or spacing changes."""
    return "".join(character for character in value.casefold() if character.isalnum())


def verify_doi_record(seed: dict, payload: dict) -> dict | None:
    """Require a unique matching DOI, PubMed identity, title and publication year."""
    matches = [row for row in payload.get("resultList", {}).get("result", [])
               if row.get("source") == "MED" and row.get("id") == seed["pmid"]]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError("ambiguous_seed_identity")
    row = matches[0]
    if str(row.get("doi", "")).casefold() != seed["doi"].casefold():
        raise ValueError("seed_doi_mismatch")
    if title_key(row.get("title", "")) != title_key(seed["title"]):
        raise ValueError("seed_title_mismatch")
    if str(row.get("pubYear")) != seed["year"]:
        raise ValueError("seed_publication_year_mismatch")
    return row


def retrieve_seed(seed: dict, cache: CachedHTTP, output: Path) -> dict:
    """Verify a seeded citation before attempting its indexed full-text route."""
    started = timestamp()
    row = {**seed, "checked_at": started, "access_scope": "Europe PMC fullTextXML",
           "bibliography_verified": False, "status": "not_found",
           "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{seed['pmid']}/"}
    params = {"query": f'DOI:"{seed["doi"]}"', "format": "json", "resultType": "core", "pageSize": 100}
    try:
        response, search_hash = cache.get_json(f"{BASE}/search", params)
        row["search_request_hash"] = search_hash
        record = verify_doi_record(seed, response)
        if record is None:
            row["reason"] = "No matching MED/PMID record in the DOI search."
            return row
        row.update(bibliography_verified=True, verified_title=record["title"],
                   author_string=record.get("authorString"), authors=record.get("authorList"),
                   journal=record.get("journalInfo"), indexed_doi=record["doi"],
                   pmcid=record.get("pmcid"), is_open_access=record.get("isOpenAccess"),
                   in_pmc=record.get("inPMC"), full_text_urls=record.get("fullTextUrlList"))
        write_json(output / "metadata" / f"{seed['seed_id']}.json", record)
        pmcid = record.get("pmcid")
        if not pmcid:
            row.update(status="not_open_access", reason="Indexed citation has no PMCID and no Europe PMC fullTextXML route.",
                       fulltext_attempt="no_indexed_pmcid_route")
            return row
        url = f"{BASE}/{pmcid}/fullTextXML"
        row.update(source_id=pmcid, fulltext_url=url, fulltext_attempt="requested")
        content, text_hash = cache.request("GET", url)
        row["fulltext_request_hash"] = text_hash
        document = ET.fromstring(content)
        front = next((node for node in document if local_name(node.tag) == "front"), None)
        article_meta = next((node for node in front if local_name(node.tag) == "article-meta"), None) if front is not None else None
        dois = {"".join(node.itertext()).strip().casefold() for node in article_meta
                if local_name(node.tag) == "article-id" and node.get("pub-id-type") == "doi"} if article_meta is not None else set()
        if seed["doi"].casefold() not in dois:
            raise ValueError("retrieved_fulltext_doi_mismatch")
        blocks = parse_fulltext(content, pmcid)
        if not blocks or not any(block["section"].startswith("Body") for block in blocks):
            raise ValueError("retrieved_fulltext_body_missing")
        parsed = {"source_id": pmcid, "blocks": blocks}
        write_json(output / "texts" / f"{pmcid}.json", parsed)
        row.update(status="retrieved", reason=None, title=record["title"],
                   source_url=f"https://europepmc.org/articles/{pmcid}",
                   fulltext_request_hash=text_hash, block_count=len(blocks),
                   retrieved_at=started, text_hash=digest(parsed))
        return row
    except (httpx.HTTPError, OfflineCacheMiss, ValueError, ET.ParseError) as error:
        row.update(status="not_found", reason=f"{type(error).__name__}: {error}",
                   blocked_reason="retrieval_or_identity_verification_failed")
        return row


def retrieve_seed_sources(root: Path, offline: bool = False) -> dict:
    """Retrieve exactly the five verified seeds under the seeded-run namespace."""
    root = root.resolve()
    interim = root / "data/interim/systems/monarch_seeded"
    results = root / "results/systems/monarch_seeded"
    provenance = read_json(results / "amendment_provenance.json")
    if not provenance.get("recorded_before_retrieval"):
        raise ValueError("amendment_provenance_required_before_retrieval")
    output = interim / ("offline_replay/corpus_targeted_monarch" if offline else "corpus_targeted_monarch")
    cache = CachedHTTP(interim / "cache/europepmc", offline=offline)
    started = timestamp()
    try:
        rows = []
        for seed in SEEDS:
            row = retrieve_seed(seed, cache, output)
            rows.append(row)
            write_jsonl(output / "access_manifest.jsonl", rows)
            print({"seed": seed["seed_id"], "doi": seed["doi"], "status": row["status"],
                   "bibliography_verified": row["bibliography_verified"], "reason": row.get("reason")}, flush=True)
    finally:
        cache.close()
    write_jsonl(output / "manifest.jsonl", [
        {**row, "status": "ready"} for row in rows if row["status"] == "retrieved"
    ])
    metrics = {"system": "monarch_seeded", "started_at": started, "completed_at": timestamp(),
               "offline": offline, "seeds": len(SEEDS), "amendment": provenance,
               "retrieved": sum(row["status"] == "retrieved" for row in rows),
               "not_open_access": sum(row["status"] == "not_open_access" for row in rows),
               "not_found": sum(row["status"] == "not_found" for row in rows),
               "bibliography_verified": sum(row["bibliography_verified"] for row in rows)}
    write_json(output / "metrics.json", metrics)
    if not offline:
        write_json(results / "seed_access.json", {"metrics": metrics, "seeds": rows})
    return metrics


def main() -> None:
    """Run cached live retrieval or offline source-access replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    print(json.dumps(retrieve_seed_sources(args.root, args.offline), indent=2))


if __name__ == "__main__":
    main()
