"""Check the isolated attine microbial taxonomy policy."""

import base64
import json
from pathlib import Path

from src.common.cache import CachedHTTP
from src.common.io import digest, read_jsonl, write_json
from src.systems.microbial_taxonomy import (
    interpret_microbial_genus_match,
    load_microbial_taxonomy_config,
    normalise_attine_microbes,
)
from src.taxonomy.gbif import CHECKLIST, interpret_match


def pseudonocardia_response() -> dict:
    """Return the relevant fields from the cached GBIF response."""
    return {
        "usage": {
            "key": "CSXDG",
            "name": "Pseudonocardia Henssen, 1957 (Approved Lists 1980)",
            "canonicalName": "Pseudonocardia",
            "rank": "GENUS",
            "status": "ACCEPTED",
        },
        "classification": [
            {"key": "CRRY6", "name": "Bacteria", "rank": "DOMAIN"},
            {"key": "CTJFC", "name": "Bacillati", "rank": "KINGDOM"},
            {"key": "F9N", "name": "Pseudonocardiaceae", "rank": "FAMILY"},
            {"key": "CSXDG", "name": "Pseudonocardia", "rank": "GENUS"},
        ],
        "diagnostics": {"matchType": "EXACT", "confidence": 93},
        "synonym": False,
    }


def test_microbe_rule_accepts_exact_bacterial_domain_at_93() -> None:
    """Resolve the observed GBIF response under the attine-only threshold."""
    config = load_microbial_taxonomy_config(
        Path("config/attine_actino_taxonomy_microbial.json")
    )
    resolved, reason = interpret_microbial_genus_match(pseudonocardia_response(), config)
    assert reason is None
    assert resolved is not None
    assert resolved["genus"] == "Pseudonocardia"
    assert resolved["family"] == "Pseudonocardiaceae"
    assert resolved["domain"] == "Bacteria"
    assert resolved["kingdom"] == "Bacillati"
    assert resolved["taxonomy_confidence"] == 93


def test_plant_rule_remains_at_95_and_checks_kingdom() -> None:
    """Show that the shared plant matcher still rejects this microbial response."""
    resolved, reason = interpret_match(pseudonocardia_response(), "genus")
    assert resolved is None
    assert reason == "inexact_or_low_confidence"


def test_microbe_rule_rejects_nonbacterial_domain() -> None:
    """Require the configured domain even for an exact high-confidence genus."""
    config = load_microbial_taxonomy_config(
        Path("config/attine_actino_taxonomy_microbial.json")
    )
    response = pseudonocardia_response()
    response["diagnostics"]["confidence"] = 100
    response["classification"][0]["name"] = "Eukaryota"
    assert interpret_microbial_genus_match(response, config)[1] == "wrong_domain"


def test_offline_replay_resolves_repeated_retained_records(tmp_path: Path) -> None:
    """Resolve one cached name once while preserving two input records."""
    config = load_microbial_taxonomy_config(
        Path("config/attine_actino_taxonomy_microbial.json")
    )
    observations = [
        {
            "record_id": value,
            "semantic_decision": "include",
            "target_name_as_written": "Pseudonocardia",
            "taxonomic_rank": "genus",
            "taxonomy_query_name": "Pseudonocardia",
            "taxonomy_query_rank": "genus",
        }
        for value in ("one", "two")
    ]
    request = {
        "method": "GET",
        "url": "https://api.gbif.org/v2/species/match",
        "params": {
            "scientificName": "Pseudonocardia",
            "taxonRank": "GENUS",
            "kingdom": "Bacteria",
            "checklistKey": CHECKLIST,
        },
        "json": None,
    }
    key = digest(request)
    body = json.dumps(pseudonocardia_response()).encode()
    write_json(
        tmp_path / "cache/http" / f"{key}.json",
        {
            "request": request,
            "request_hash": key,
            "attempts": [
                {"status": 200, "body_base64": base64.b64encode(body).decode()}
            ],
        },
    )
    cache = CachedHTTP(tmp_path / "cache", offline=True)
    try:
        metrics = normalise_attine_microbes(observations, cache, tmp_path / "output", config)
    finally:
        cache.close()
    assert metrics["status"] == "complete"
    assert metrics["matched_observations"] == 2
    assert metrics["resolved_genera"] == ["Pseudonocardia"]
    assert metrics["external_requests"] == 0
    assert {row["taxonomy_request_hash"] for row in read_jsonl(
        tmp_path / "output/observations.jsonl"
    )} == {key}
