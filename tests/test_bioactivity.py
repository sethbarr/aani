"""Verify complete-page bioactivity retrieval and conservative offline replay."""

from pathlib import Path

import httpx

from scripts.bioactivity import run_bioactivity
from src.bioactivity.chembl import retrieve_labels
from src.common.cache import CachedHTTP
from src.common.io import read_json, read_jsonl, write_jsonl

COMPOUND = "AAAAAAAAAAAAAA-BBBBBBBBBB-C"
CONFIG = {"organisms": ["Candida albicans"], "endpoints": ["MIC", "IC50"], "potency_threshold_um": 10.0}


def page(collection: str, rows: list[dict]) -> dict:
    """Return a complete single-page fixture."""
    return {collection: rows, "page_meta": {"total_count": len(rows), "next": None}}


def service_response(request: httpx.Request) -> httpx.Response:
    """Serve documented schemas and controlled exact-structure assay fixtures."""
    path = request.url.path
    if path.endswith("status.json"):
        payload = {"chembl_db_version": "TEST_ONLY"}
    elif path.endswith("activity/schema.json"):
        payload = {"filtering": {"molecule_chembl_id": 1, "standard_type": ["in"]}}
    elif path.endswith("molecule/schema.json"):
        payload = {"fields": {"molecule_structures": {"schema": {"filtering": {"standard_inchi_key": ["in"]}}}}}
    elif path.endswith("assay/schema.json"):
        payload = {"filtering": {"assay_organism": ["in"]}}
    elif path.endswith("assay.json"):
        payload = page("assays", [{"assay_chembl_id": "GOOD", "assay_organism": "Candida albicans", "assay_type": "F"}])
    elif path.endswith("molecule.json"):
        payload = page("molecules", [{"molecule_chembl_id": "MOL", "molecule_structures": {"standard_inchi_key": COMPOUND}}])
    else:
        common = {
            "molecule_chembl_id": "MOL", "standard_type": "MIC", "assay_type": "F",
            "standard_value": "5", "standard_units": "uM", "standard_relation": "=",
        }
        payload = page("activities", [
            {**common, "activity_id": 1, "assay_chembl_id": "GOOD", "target_organism": "Homo sapiens"},
            {**common, "activity_id": 2, "assay_chembl_id": "BAD", "target_organism": "Candida albicans"},
        ])
    return httpx.Response(200, json=payload)


def test_exact_assay_identity_and_offline_replay(tmp_path: Path) -> None:
    """Classify the assay organism, never the target, and replay identical outputs."""
    cache = CachedHTTP(tmp_path / "raw", interval=0, client=httpx.Client(transport=httpx.MockTransport(service_response)))
    metrics = retrieve_labels([COMPOUND], cache, tmp_path / "online", CONFIG)
    cache.close()
    assert metrics["active"] == 1
    audit = read_jsonl(tmp_path / "online/measurements.jsonl")
    assert [row["label"] for row in audit] == ["active", "unknown"]
    offline = CachedHTTP(tmp_path / "raw", offline=True, interval=0)
    repeated = retrieve_labels([COMPOUND], offline, tmp_path / "offline", CONFIG)
    offline.close()
    assert repeated == metrics
    for name in ("labels.jsonl", "measurements.jsonl", "retrieval_status.jsonl", "query_manifest.json"):
        assert (tmp_path / "online" / name).read_bytes() == (tmp_path / "offline" / name).read_bytes()


def test_missing_occurrences_have_unknown_input_counts(tmp_path: Path) -> None:
    """Write blocked metrics rather than treating missing chemistry as zero compounds."""
    metrics = run_bioactivity(tmp_path / "missing.jsonl", tmp_path / "output", tmp_path / "raw", True)
    assert metrics["status"] == "blocked"
    assert metrics["compounds"] is None
    assert read_jsonl(tmp_path / "output/labels.jsonl") == []


def test_empty_occurrences_complete_without_network(tmp_path: Path) -> None:
    """A verified empty table has a known zero count and no fabricated labels."""
    source = tmp_path / "occurrences.jsonl"
    write_jsonl(source, [])
    metrics = run_bioactivity(source, tmp_path / "output", tmp_path / "raw", True)
    assert metrics["status"] == "complete"
    assert metrics["compounds"] == 0
    assert read_json(tmp_path / "output/metrics.json")["unknown"] == 0
