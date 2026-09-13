"""Verify linked occurrence adaptation and checksum-protected offline replay."""

import base64
import csv
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from src.chemistry.export_cache import download_export, file_hash
from src.chemistry.lotus import (
    FILENAME,
    LICENSE_URL,
    METADATA_URL,
    REQUIRED_FIELDS,
    acquire_lotus,
    occurrence_reference,
)
from src.common.cache import OfflineCacheMiss
from src.common.io import digest, write_json, write_jsonl


def cache_http(root: Path, url: str, body: bytes) -> None:
    """Store an isolated successful fixture response using the real cache schema."""
    request = {"method": "GET", "url": url, "params": {}, "json": None}
    key = digest(request)
    write_json(root / "http" / f"{key}.json", {
        "request": request, "request_hash": key,
        "attempts": [{
            "status": 200, "retrieved_at": "2026-09-12T00:00:00+00:00",
            "body_base64": base64.b64encode(body).decode(), "content_type": "text/plain",
        }],
    })


def source_row(genus: str, kingdom: str = "Plantae", doi: str = "10.1234/TEST") -> dict:
    """Build a linked fixture row whose structure and taxon share one reference."""
    row = dict.fromkeys(REQUIRED_FIELDS, "NA")
    row.update({
        "database": "fixture", "organismValue": f"original {genus} species",
        "organismCleaned": f"{genus} species", "organismCleaned_id": "123",
        "organismCleaned_dbTaxo": "Fixture taxonomy",
        "organismCleaned_dbTaxoTaxonRanks": "kingdom|genus|species",
        "organismCleaned_dbTaxoTaxonomy": f"{kingdom}|{genus}|{genus} species",
        "structureCleanedInchikey": "AAAAAAAAAAAAAA-BBBBBBBBBB-C",
        "structureCleanedSmiles": "C[C@H](O)N", "referenceType": "doi",
        "referenceValue": doi, "referenceCleanedDoi": doi,
    })
    return row


def prepare_export_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Create a complete tiny versioned export and all required cached responses."""
    raw = tmp_path / "raw"
    cache = raw / "chemistry_export"
    tsv = tmp_path / "export.tsv.gz"
    rows = [
        source_row("Example"), source_row("Example", doi="10.1234/test"),
        source_row("Example", kingdom="Fungi"), source_row("Other"),
    ]
    with gzip.open(tsv, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted(REQUIRED_FIELDS), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    url = f"https://zenodo.org/api/records/6582121/files/{FILENAME}/content"
    request = {"method": "GET", "url": url, "params": {}, "json": None}
    key = digest(request)
    body = cache / "downloads" / f"{key}.body"
    body.parent.mkdir(parents=True)
    body.write_bytes(tsv.read_bytes())
    metadata = {
        "request": request, "request_hash": key, "complete": True, "status": 200,
        "bytes": body.stat().st_size, "sha256": file_hash(body),
        "md5": file_hash(body, "md5"), "body_path": str(body),
        "retrieved_at": "2026-09-12T00:00:00+00:00",
    }
    write_json(cache / "downloads" / f"{key}.json", metadata)
    release = {
        "metadata": {
            "license": {"id": "cc-by-4.0"}, "doi": "10.5281/zenodo.6582121",
            "publication_date": "2022-05-25",
            "relations": {"version": [{"index": 3}]},
        },
        "files": [{
            "key": FILENAME, "size": body.stat().st_size,
            "checksum": "md5:" + file_hash(body, "md5"), "links": {"self": url},
        }],
    }
    cache_http(cache, METADATA_URL, json.dumps(release).encode())
    cache_http(cache, LICENSE_URL, b"Attribution 4.0 International")
    genera = tmp_path / "genera.jsonl"
    write_jsonl(genera, [{
        "genus": "Example", "status": "rejected", "accepted_names": ["Example species"],
    }])
    return raw, genera


def test_offline_import_preserves_provenance_and_deduplicates_effort(tmp_path: Path) -> None:
    """Keep duplicate source rows while counting one genus-key-reference occurrence."""
    raw, genera = prepare_export_fixture(tmp_path)
    interim, output = tmp_path / "interim", tmp_path / "processed"
    result = acquire_lotus(genera, raw, interim, output, offline=True)
    assert result["metrics"]["accepted"] == 2
    assert result["metrics"]["unique_occurrences"] == 1
    assert result["metrics"]["unique_compounds"] == 1
    assert result["transform"]["export_records_scanned"] == 4
    assert result["transform"]["transform_review"] == 1
    rows = [json.loads(line) for line in (output / "occurrences.jsonl").read_text().splitlines()]
    assert rows[0]["canonical_smiles"] == "C[C@H](O)N"
    assert rows[0]["original_plant_name"] == "original Example species"
    assert rows[0]["aggregation_level"] == "species"
    assert rows[0]["reference_url"] == "https://doi.org/10.1234/test"
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir()}
    acquire_lotus(genera, raw, interim, output, offline=True)
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir()}
    assert before == after


def test_offline_bulk_cache_miss_and_corruption_fail(tmp_path: Path) -> None:
    """Forbid uncached requests and refuse an altered complete export."""
    with pytest.raises(OfflineCacheMiss):
        download_export("https://example.org/export", tmp_path, offline=True)
    raw, _ = prepare_export_fixture(tmp_path)
    cache = raw / "chemistry_export"
    body = next((cache / "downloads").glob("*.body"))
    body.write_bytes(b"changed")
    url = f"https://zenodo.org/api/records/6582121/files/{FILENAME}/content"
    with pytest.raises(ValueError, match="checksum mismatch"):
        download_export(url, cache, offline=True)


def test_missing_reference_is_not_replaced_by_a_database_homepage() -> None:
    """Untraceable rows remain review items rather than acquiring invented citations."""
    row = source_row("Example")
    row["referenceCleanedDoi"] = "NA"
    assert occurrence_reference(row) == ("", "missing_curated_reference")


def test_unverified_licence_stops_before_import(tmp_path: Path) -> None:
    """An unknown release licence blocks acquisition despite a usable local file."""
    raw, genera = prepare_export_fixture(tmp_path)
    cache_http(raw / "chemistry_export", METADATA_URL, json.dumps({
        "metadata": {"license": {"id": "unknown"}},
    }).encode())
    with pytest.raises(ValueError, match="licence cannot be verified"):
        acquire_lotus(genera, raw, tmp_path / "interim", tmp_path / "output", offline=True)
