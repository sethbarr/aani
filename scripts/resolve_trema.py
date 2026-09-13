"""Prepare the dated Trema taxonomy supplement from unchanged curator contexts."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from src.behaviour.aggregation import aggregate
from src.common.cache import CachedHTTP
from src.common.io import read_json, read_jsonl, timestamp, write_json, write_jsonl
from src.taxonomy.gbif import CHECKLIST, interpret_match

ORIGINAL_NAME = "Trema micrantha"
QUERY_NAME = "Trema micranthum"
ORIGINAL_REQUEST = "cb9d68d50b6dd0401456f4b49933e91b8dc5a50c740d8ae03116c8a9e1edae8b"
SOURCE = Path("results/saverschek_audit/curated_directional_observations.jsonl")
AMENDMENT = Path("docs/amendment_2026-09-13_trema_taxonomy.md")
OUTPUT = Path("data/interim/trema_resolution")


def artifact(path: Path) -> dict:
    """Describe a local input for reproducible verification.

    Args:
        path: Repository-relative path.

    Returns:
        Path and byte-level SHA-256.
    """
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def resolve(offline: bool) -> dict:
    """Resolve an independently documented variant under the exact-match rule.

    Args:
        offline: Whether every authority response must already be cached.

    Returns:
        Taxonomy supplement manifest with checked provenance.

    Raises:
        ValueError: Authority identity, original match or exact query disagrees.
    """
    client = CachedHTTP(Path("data/raw"), offline=offline)
    try:
        authority_url = "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi"
        authority, authority_key = client.request(
            "GET", authority_url, params={"id": "28954", "lvl": "0"}
        )
        text = authority.decode("utf-8")
        marker = text.find(f"<i>{ORIGINAL_NAME}</i>")
        if QUERY_NAME not in text or marker < 0 or "orth. var." not in text[marker:marker + 300]:
            raise ValueError("NCBI orthographic-equivalence evidence did not verify")
        original, original_key = client.get_json(
            "https://api.gbif.org/v2/species/match",
            {"scientificName": ORIGINAL_NAME, "taxonRank": "SPECIES",
             "kingdom": "Plantae", "checklistKey": CHECKLIST},
        )
        response, exact_key = client.get_json(
            "https://api.gbif.org/v2/species/match",
            {"scientificName": QUERY_NAME, "taxonRank": "SPECIES",
             "kingdom": "Plantae", "checklistKey": CHECKLIST},
        )
    finally:
        client.close()
    confidence = read_json(Path("config/analysis.json"))["taxonomy_confidence"]
    match, reason = interpret_match(response, "species", confidence)
    if match is None:
        raise ValueError(f"Canonical Trema query failed frozen rule: {reason}")
    if original_key != ORIGINAL_REQUEST or original["diagnostics"]["matchType"] != "VARIANT":
        raise ValueError("Original Trema review response changed")
    if original["usage"]["key"] != match["accepted_usage_key"]:
        raise ValueError("Original variant and exact query identify different taxa")
    rows = [row for row in read_jsonl(SOURCE) if row["plant_name_as_written"] == ORIGINAL_NAME]
    if not rows or any(row["outcome"] != "rejected" for row in rows):
        raise ValueError("Original Trema directional contexts changed")
    evidence = {
        "method": "reviewed_orthographic_variant_then_exact_query",
        "original_name": ORIGINAL_NAME, "scientific_name": QUERY_NAME,
        "original_taxonomy_request_hash": original_key,
        "authority_url": authority_url + "?id=28954&lvl=0",
        "authority_request_hash": authority_key,
        "authority_statement": "Trema micrantha, orth. var.",
        "amendment": str(AMENDMENT),
    }
    prepared = [{**row, **match, "taxonomy_request_hash": exact_key,
                 "taxonomy_query_name": QUERY_NAME, "taxonomy_query_rank": "species",
                 "taxonomy_status": "exact_after_reviewed_orthographic_resolution",
                 "name_resolution": evidence} for row in rows]
    observations = OUTPUT / "observations.jsonl"
    write_jsonl(observations, prepared)
    genera, conflicts, review = aggregate(prepared)
    if len(genera) != 1 or conflicts or review:
        raise ValueError("Trema supplement did not aggregate to one eligible genus")
    write_jsonl(OUTPUT / "genera.jsonl", genera)
    manifest = {
        "schema_version": 1, "status": "complete", "blocked_reason": None,
        "decision_date": "2026-09-13", "prepared_at": timestamp(),
        "source_id": "SAVERSCHEK2010", "plant_name_as_written": ORIGINAL_NAME,
        "accepted_name": match["accepted_name"], "accepted_usage_key": match["accepted_usage_key"],
        "taxonomy_confidence": match["taxonomy_confidence"], "match_type": "EXACT",
        "resolved_context_records": len(prepared), "direction": "rejected",
        "original_observations": artifact(SOURCE), "observations": artifact(observations),
        "amendment": artifact(AMENDMENT), "name_resolution": evidence,
        "provenance": [artifact(Path("data/raw/http") / f"{key}.json")
                       for key in [original_key, exact_key, authority_key]],
        "scope": "Taxonomy-only supplementation of existing curator contexts; original labels and extraction outputs unchanged.",
    }
    write_json(OUTPUT / "manifest.json", manifest)
    return manifest


def report_coverage() -> dict:
    """Report targeted chemistry and activity results with their exact inputs.

    Returns:
        Verified counts and provenance for the Trema review outcome.

    Raises:
        ValueError: Any targeted stage is incomplete or contains another genus.
    """
    manifest = read_json(OUTPUT / "manifest.json")
    chemistry = read_json(OUTPUT / "chemistry/metrics.json")
    activity = read_json(OUTPUT / "bioactivity/metrics.json")
    if manifest["status"] != "complete" or chemistry["status"] != "completed" or activity["status"] != "complete":
        raise ValueError("Trema status requires completed taxonomy, chemistry and activity retrieval")
    occurrences = read_jsonl(OUTPUT / "chemistry/occurrences.jsonl")
    if any(row["genus"] != "Trema" for row in occurrences):
        raise ValueError("Trema chemistry output contains another genus")
    labels = read_jsonl(OUTPUT / "bioactivity/labels.jsonl")
    measurements = read_jsonl(OUTPUT / "bioactivity/measurements.jsonl")
    species = [row for row in occurrences if row["aggregation_level"] == "species"]
    genus = [row for row in occurrences if row["aggregation_level"] == "genus"]
    species_ids = {row["occurrence_id"] for row in species}
    genus_ids = {row["occurrence_id"] for row in genus}
    taxonomy = read_jsonl(OUTPUT / "observations.jsonl")[0]
    names = sorted({row["plant_name"] for row in occurrences})
    paths = [OUTPUT / relative for relative in [
        "manifest.json", "observations.jsonl", "chemistry/metrics.json",
        "chemistry/occurrences.jsonl", "chemistry/genus_coverage.jsonl",
        "bioactivity/metrics.json", "bioactivity/labels.jsonl",
        "bioactivity/measurements.jsonl", "bioactivity/query_manifest.json",
    ]]
    report = {
        "reported_at": timestamp(), "status": "complete", "blocked_reason": None,
        "taxonomy": {"source_name": ORIGINAL_NAME, "accepted_name": manifest["accepted_name"],
                     "accepted_usage_key": manifest["accepted_usage_key"], "family": taxonomy["family"],
                     "match_type": manifest["match_type"], "confidence": manifest["taxonomy_confidence"],
                     "resolved_context_records": manifest["resolved_context_records"]},
        "chemistry": {
            "database": "LOTUS", "has_chemistry": bool(occurrences),
            "imported_records": len(occurrences),
            "distinct_compounds": len({row["compound_id"] for row in occurrences}),
            "distinct_occurrences": len({row["occurrence_id"] for row in occurrences}),
            "exact_accepted_species_distinct_compounds": len({row["compound_id"] for row in species}),
            "exact_accepted_species_distinct_occurrences": len(species_ids),
            "exact_accepted_species_source_records": len(species),
            "genus_level_distinct_occurrences": len(genus_ids),
            "genus_level_source_records": len(genus),
            "genus_only_distinct_occurrences": len(genus_ids - species_ids),
            "occurrence_ids_shared_between_levels": len(genus_ids & species_ids),
            "occurrence_names": names,
            "scope_note": "The frozen genus-level join includes other Trema species and the legacy micrantha spelling; species-level labels require exact accepted-name equality. Occurrence IDs hash genus, compound and reference, so the species and genus occurrence sets overlap.",
        },
        "bioactivity": {
            "retrieval_complete": activity["failed_compounds"] == 0,
            "matched_compounds": activity["matched_compounds"],
            "classified_compounds": sum(row["label"] != "unknown" for row in labels),
            "unknown_compounds": sum(row["label"] == "unknown" for row in labels),
            "retrieved_measurements": len(measurements),
            "measurement_label_reasons": dict(Counter(row["label_reason"] for row in measurements)),
            "classified_measurements": activity["classified_measurements"],
            "failed_compounds": activity["failed_compounds"],
            "database_version": activity["database_status"]["chembl_db_version"],
        },
        "join": {"eligible_for_classified_primary_join": any(row["label"] != "unknown" for row in labels),
                 "exclusion_reason": "no_classified_compounds" if all(row["label"] == "unknown" for row in labels) else None,
                 "added_classified_rejected_genera": int(any(row["label"] != "unknown" for row in labels)),
                 "interpretation": "Unknown activity remains unknown. Only classified compounds can add a genus to the primary join; the 25-genus feasibility gate still applies."},
        "inputs": [artifact(path) for path in paths],
    }
    write_json(Path("results/day2_blockers/trema_status.json"), report)
    return report


def main() -> None:
    """Run the targeted resolution and record explicit failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--report-coverage", action="store_true")
    args = parser.parse_args()
    try:
        manifest = report_coverage() if args.report_coverage else resolve(args.offline)
    except Exception as error:
        manifest = {"status": "blocked", "blocked_reason": f"{type(error).__name__}: {error}"}
        write_json(OUTPUT / "blocked.json", manifest)
        print(json.dumps(manifest, indent=2))
        raise SystemExit(1) from error
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
