"""Acquire a pinned LOTUS bulk export and preserve its row-level provenance."""

import csv
import gzip
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from src.chemistry.export_cache import download_export, file_hash
from src.chemistry.occurrences import COLUMNS, import_occurrences
from src.common.cache import CachedHTTP
from src.common.io import read_jsonl, write_json, write_jsonl

RECORD_ID = "6582121"
METADATA_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/legalcode.en"
FILENAME = "validated_referenced_structure_organism_pairs.tsv.gz"
REQUIRED_FIELDS = {
    "database", "organismValue", "organismCleaned", "organismCleaned_id",
    "organismCleaned_dbTaxo", "organismCleaned_dbTaxoTaxonRanks",
    "organismCleaned_dbTaxoTaxonomy", "structureCleanedInchikey",
    "structureCleanedSmiles", "referenceType", "referenceValue",
    "referenceCleanedDoi", "referenceCleanedPmcid", "referenceCleanedPmid",
}
EXTRA_COLUMNS = [
    "original_plant_name", "original_source_database", "original_reference_type",
    "original_reference_value", "export_record_number", "export_sha256",
    "source_taxonomy_database", "source_taxonomy_identifier", "source_taxonomy_ranks",
    "source_taxonomy_lineage", "reference_identifier_type", "database_record_id_kind",
]


def clean_value(value: str | None) -> str:
    """Treat the export's missing-value sentinels as missing, never as evidence."""
    text = (value or "").strip()
    return "" if text in {"NA", "N/A", "NULL", "null"} else text


def occurrence_reference(row: dict[str, str]) -> tuple[str, str]:
    """Use a curated reference identifier from the same structure-organism row."""
    doi = clean_value(row["referenceCleanedDoi"])
    if doi.startswith("10.") and "/" in doi and not any(char.isspace() for char in doi):
        return "https://doi.org/" + quote(doi.lower(), safe="/():;.,-_"), "doi"
    pmcid = clean_value(row["referenceCleanedPmcid"])
    if pmcid.startswith("PMC") and pmcid[3:].isdecimal():
        return f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/", "pmcid"
    pmid = clean_value(row["referenceCleanedPmid"])
    if pmid.isdecimal():
        return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "pmid"
    return "", "missing_curated_reference"


def taxonomy_lineage(row: dict[str, str]) -> dict[str, str]:
    """Parse the export's aligned rank and taxon arrays without taxon API calls."""
    ranks = row["organismCleaned_dbTaxoTaxonRanks"].split("|")
    taxa = row["organismCleaned_dbTaxoTaxonomy"].split("|")
    if len(ranks) != len(taxa) or len(set(ranks)) != len(ranks):
        return {}
    return dict(zip(ranks, taxa, strict=True))


def make_occurrence(
    row: dict[str, str], record_number: int, export_hash: str,
    database_version: str, genus: str, accepted_names: set[str],
) -> dict[str, str]:
    """Adapt one linked export row to the CSV contract while retaining provenance."""
    reference_url, reference_type = occurrence_reference(row)
    plant_name = clean_value(row["organismCleaned"])
    return {
        "database": "LOTUS",
        "database_version": database_version,
        "database_record_id": f"zenodo:{RECORD_ID}:record:{record_number}",
        "database_record_id_kind": "derived_one_based_export_record_locator",
        "plant_name": plant_name,
        "genus": genus,
        "inchikey": clean_value(row["structureCleanedInchikey"]),
        "canonical_smiles": clean_value(row["structureCleanedSmiles"]),
        "reference_url": reference_url,
        "aggregation_level": "species" if plant_name in accepted_names else "genus",
        "original_plant_name": row["organismValue"],
        "original_source_database": row["database"],
        "original_reference_type": row["referenceType"],
        "original_reference_value": row["referenceValue"],
        "export_record_number": str(record_number),
        "export_sha256": export_hash,
        "source_taxonomy_database": row["organismCleaned_dbTaxo"],
        "source_taxonomy_identifier": row["organismCleaned_id"],
        "source_taxonomy_ranks": row["organismCleaned_dbTaxoTaxonRanks"],
        "source_taxonomy_lineage": row["organismCleaned_dbTaxoTaxonomy"],
        "reference_identifier_type": reference_type,
    }


def filter_export(
    export: Path, genera: list[dict], interim: Path, export_hash: str,
    database_version: str,
) -> dict:
    """Scan the complete gzip TSV and select prespecified behavioural genera only.

    Args:
        export: Complete checksum-verified bulk response body.
        genera: Behavioural genera with accepted_names and status fields.
        interim: Directory for the CSV contract and full selected source rows.
        export_hash: Complete original export SHA-256.
        database_version: Version identifier established from Zenodo metadata.

    Returns:
        Full scan, selection, and pre-import review counts.
    """
    genus_names = {row["genus"] for row in genera}
    accepted_names = {
        row["genus"]: set(row.get("accepted_names", [])) for row in genera
    }
    interim.mkdir(parents=True, exist_ok=True)
    source_path = interim / "selected_export_records.jsonl"
    csv_path = interim / "occurrence_contract.csv"
    review = []
    counts: Counter[str] = Counter()
    with gzip.open(export, "rt", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        missing = REQUIRED_FIELDS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"LOTUS format cannot be verified; missing columns: {sorted(missing)}")
        with csv_path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=COLUMNS + EXTRA_COLUMNS)
            writer.writeheader()
            with source_path.open("w", encoding="utf-8") as provenance:
                for number, row in enumerate(reader, start=1):
                    counts["export_records_scanned"] += 1
                    lineage = taxonomy_lineage(row)
                    genus = lineage.get("genus", "")
                    name_parts = clean_value(row["organismCleaned"]).split()
                    candidate_genus = name_parts[0] if name_parts else ""
                    if genus not in genus_names and candidate_genus not in genus_names:
                        continue
                    counts["candidate_export_records"] += 1
                    source_record = {"export_record_number": number, "record": row}
                    provenance.write(json.dumps(source_record, ensure_ascii=False) + "\n")
                    reason = None
                    if lineage.get("kingdom") != "Plantae":
                        reason = "plant_kingdom_not_verified"
                    elif genus not in genus_names:
                        reason = "genus_lineage_not_verified"
                    elif None in row or any(value is None for value in row.values()):
                        reason = "malformed_export_row"
                    if reason:
                        review.append({**source_record, "reason": reason})
                        continue
                    occurrence = make_occurrence(
                        row, number, export_hash, database_version, genus, accepted_names[genus]
                    )
                    writer.writerow(occurrence)
                    counts["contract_rows"] += 1
    write_jsonl(interim / "transform_review.jsonl", review)
    return {
        **dict(counts), "transform_review": len(review),
        "contract_path": str(csv_path), "contract_sha256": file_hash(csv_path),
        "selected_source_rows_path": str(source_path),
        "selected_source_rows_sha256": file_hash(source_path),
        "requested_genera": sorted(genus_names),
    }


def acquire_lotus(
    genera_path: Path, raw: Path, interim: Path, output: Path, offline: bool = False,
) -> dict:
    """Verify, acquire, filter, and import the pinned LOTUS release with offline replay."""
    client = CachedHTTP(raw / "chemistry_export", offline=offline)
    try:
        metadata, metadata_hash = client.get_json(METADATA_URL)
        license_body, license_hash = client.request("GET", LICENSE_URL)
    finally:
        client.close()
    if metadata["metadata"].get("license", {}).get("id") != "cc-by-4.0":
        raise ValueError("LOTUS release licence cannot be verified as CC BY 4.0")
    if b"Attribution 4.0 International" not in license_body:
        raise ValueError("Official CC BY 4.0 licence response cannot be verified")
    files = [row for row in metadata["files"] if row["key"] == FILENAME]
    if len(files) != 1:
        raise ValueError("LOTUS version-specific bulk file cannot be identified uniquely")
    entry = files[0]
    export, download = download_export(
        entry["links"]["self"], raw / "chemistry_export", offline=offline
    )
    if download["bytes"] != entry["size"]:
        raise ValueError("Downloaded LOTUS file size differs from its versioned metadata")
    if f"md5:{download['md5']}" != entry["checksum"]:
        raise ValueError("Downloaded LOTUS checksum differs from its versioned metadata")
    version_number = metadata["metadata"]["relations"]["version"][0]["index"] + 1
    version = f"zenodo:{RECORD_ID}:v{version_number}"
    genera = read_jsonl(genera_path)
    transform = filter_export(export, genera, interim, download["sha256"], version)
    metrics = import_occurrences(
        Path(transform["contract_path"]), raw, output, imported_at=download["retrieved_at"]
    )
    occurrences = read_jsonl(output / "occurrences.jsonl")
    coverage = []
    for genus in genera:
        rows = [row for row in occurrences if row["genus"] == genus["genus"]]
        coverage.append({
            "genus": genus["genus"], "behaviour_status": genus["status"],
            "chemistry_status": "mapped" if rows else "missing_chemistry",
            "imported_records": len(rows),
            "distinct_occurrences": len({row["occurrence_id"] for row in rows}),
            "mapped_compounds": len({row["compound_id"] for row in rows}) if rows else None,
            "species_matched_occurrences": len({
                row["occurrence_id"] for row in rows if row["aggregation_level"] == "species"
            }),
        })
    write_jsonl(output / "genus_coverage.jsonl", coverage)
    manifest = {
        "status": "completed", "blocked_reason": None,
        "database": "LOTUS", "database_version": version,
        "export_doi": metadata["metadata"]["doi"],
        "export_publication_date": metadata["metadata"]["publication_date"],
        "download_url": entry["links"]["self"],
        "retrieved_at": download["retrieved_at"],
        "file_sha256": download["sha256"], "file_bytes": download["bytes"],
        "published_checksum": entry["checksum"], "checksum_verified": True,
        "download_request_hash": download["request_hash"],
        "metadata_url": METADATA_URL, "metadata_request_hash": metadata_hash,
        "licence": {
            "identifier": "CC-BY-4.0", "url": LICENSE_URL,
            "request_hash": license_hash,
            "terms": "Reuse and adaptation permitted with attribution, a licence link, and indication of changes; no additional restrictions.",
            "attribution": "Rutz, A.; Bisson, J.; Allard, P.-M. (2022). The LOTUS Initiative for Open Natural Products Research: frozen dataset, v4. Zenodo. https://doi.org/10.5281/zenodo.6582121",
            "scope": "This pinned Zenodo export is licensed CC BY 4.0; no CC0 claim is inferred from other LOTUS dissemination channels.",
        },
        "genus_input_path": str(genera_path), "genus_input_sha256": file_hash(genera_path),
        "transformer_sha256": file_hash(Path(__file__)),
        "importer_sha256": file_hash(Path(__file__).with_name("occurrences.py")),
        "transform": transform,
        "transformation_rules": [
            "Scan every record in the complete verified gzip TSV; filter solely by the supplied behavioural genera before inspecting bioactivity.",
            "Require aligned taxonomic ranks/lineage with kingdom Plantae and an exact genus field; no taxon API or fuzzy name substitution.",
            "Preserve the same row's cleaned full InChIKey, stereochemical SMILES, taxon, and curated DOI/PMCID/PMID; no cross-product of references and taxa.",
            "Preserve original source taxon, source database, reference, and complete selected rows; one-based export record locator is derived because the export has no native LOTUS record-ID column.",
            "Lowercase DOI identifiers and percent-encode the URL; retain original DOI in the archived selected row.",
            "Label species only for an exact cleaned-name match to the behavioural genus's accepted_names; other occurrences are labelled genus.",
            "Import only this explicitly labelled local genus subset, not the entire bulk export; keep all occurrence provenance and deduplicate structures only by full InChIKey downstream.",
        ],
        "metrics": metrics,
    }
    metrics.update({
        "status": "completed", "blocked_reason": None,
        "export_records_scanned": transform["export_records_scanned"],
        "candidate_export_records": transform["candidate_export_records"],
        "transform_review": transform["transform_review"],
        "requested_genera": len(genera),
        "conflict_genera_with_chemistry": sum(
            row["behaviour_status"] == "conflict" and row["chemistry_status"] == "mapped"
            for row in coverage
        ),
        "eligible_genera_with_chemistry": sum(
            row["behaviour_status"] in {"accepted", "rejected"}
            and row["chemistry_status"] == "mapped" for row in coverage
        ),
    })
    write_json(output / "run_manifest.json", manifest)
    write_json(output / "metrics.json", metrics)
    return manifest
