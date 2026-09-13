from pathlib import Path

import httpx
import pytest

from src.common.cache import CachedHTTP
from src.common.io import read_jsonl
from src.taxonomy.gbif import CHECKLIST, interpret_match, normalise


@pytest.fixture
def accepted_match() -> dict:
    """Return relevant fields from the cached live Poa annua v2 response.

    The verified request hash is
    ef8b7f9f28d74afaa9d29c421ac917b27fb84d06df27dde8276b453915cf2256.
    Keeping its relevant fields here makes tests independent of the raw cache.
    """
    return {
        "usage": {
            "key": "6W3C4",
            "name": "Poa annua L.",
            "canonicalName": "Poa annua",
            "rank": "SPECIES",
            "status": "ACCEPTED",
        },
        "classification": [
            {"key": "P", "name": "Plantae", "rank": "KINGDOM"},
            {"key": "627FW", "name": "Poaceae", "rank": "FAMILY"},
            {"key": "8W2K5", "name": "Poa", "rank": "GENUS"},
            {"key": "6W3C4", "name": "Poa annua", "rank": "SPECIES"},
        ],
        "diagnostics": {"matchType": "EXACT", "confidence": 99},
        "synonym": False,
    }


def test_interpret_accepted_v2_without_accepted_usage(accepted_match: dict) -> None:
    """Resolve the accepted taxon directly from the live v2 usage shape."""
    resolved, reason = interpret_match(accepted_match, "species")
    assert reason is None
    assert resolved == {
        "usage_key": "6W3C4",
        "accepted_usage_key": "6W3C4",
        "accepted_name": "Poa annua",
        "genus": "Poa",
        "family": "Poaceae",
        "checklist_key": CHECKLIST,
        "taxonomy_confidence": 99.0,
    }
    del accepted_match["usage"]["canonicalName"]
    resolved, reason = interpret_match(accepted_match, "species")
    assert reason is None
    assert resolved["accepted_name"] == "Poa annua L."


def test_synonym_never_falls_back_to_matched_name(accepted_match: dict) -> None:
    """Require a synonym's accepted key and name to come from that identity."""
    accepted_match["synonym"] = True
    accepted_match["usage"]["status"] = "SYNONYM"
    assert interpret_match(accepted_match, "species")[1] == "incomplete_classification"
    accepted_match["acceptedUsage"] = {"key": "accepted-id", "rank": "SPECIES"}
    assert interpret_match(accepted_match, "species")[1] == "incomplete_classification"
    accepted_match["acceptedUsage"]["canonicalName"] = "Accepted plant"
    resolved, reason = interpret_match(accepted_match, "species")
    assert reason is None
    assert resolved["accepted_usage_key"] == "accepted-id"
    assert resolved["accepted_name"] == "Accepted plant"


@pytest.mark.parametrize("confidence", [94, "invalid", float("nan"), float("inf")])
def test_confidence_gate_rejects_invalid_or_low_values(
    accepted_match: dict, confidence: object
) -> None:
    """Require a finite confidence that reaches the protocol threshold."""
    accepted_match["diagnostics"]["confidence"] = confidence
    assert interpret_match(accepted_match, "species")[1] == "inexact_or_low_confidence"


def test_rank_kingdom_and_exact_gates_stay_strict(accepted_match: dict) -> None:
    """Accept the confidence boundary while retaining taxonomic exclusions."""
    accepted_match["diagnostics"]["confidence"] = 95
    assert interpret_match(accepted_match, "species")[1] is None
    assert interpret_match(accepted_match, "genus")[1] == "rank_mismatch"
    assert interpret_match(accepted_match, "family")[1] == "rank_mismatch"
    accepted_match["diagnostics"]["matchType"] = "FUZZY"
    assert interpret_match(accepted_match, "species")[1] == "inexact_or_low_confidence"
    accepted_match["diagnostics"]["matchType"] = "EXACT"
    accepted_match["classification"][0]["name"] = "Animalia"
    assert interpret_match(accepted_match, "species")[1] == "not_plantae"


def test_normalise_preserves_provenance_and_uses_v2_rank(
    tmp_path: Path, accepted_match: dict
) -> None:
    """Resolve repeated names once with taxonRank and retain each source row."""
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        """Check the documented request contract and return the v2 fixture."""
        requests.append(request)
        assert dict(request.url.params) == {
            "scientificName": "Poa annua",
            "taxonRank": "SPECIES",
            "kingdom": "Plantae",
            "checklistKey": CHECKLIST,
        }
        return httpx.Response(200, json=accepted_match)

    cache = CachedHTTP(
        tmp_path / "raw", interval=0, client=httpx.Client(transport=httpx.MockTransport(respond))
    )
    observations = [
        {"plant_name_as_written": "Poa annua", "taxonomic_rank": "species", "source": source}
        for source in ("paper-one", "paper-two")
    ]
    try:
        summary = normalise(observations, cache, tmp_path / "taxonomy")
    finally:
        cache.close()
    assert summary == {"matched_observations": 2, "review_observations": 0, "unique_names": 1}
    assert len(requests) == 1
    rows = read_jsonl(tmp_path / "taxonomy" / "observations.jsonl")
    assert [row["source"] for row in rows] == ["paper-one", "paper-two"]
    assert rows[0]["taxonomy_request_hash"] == rows[1]["taxonomy_request_hash"]
    assert (tmp_path / "raw" / "http" / f"{rows[0]['taxonomy_request_hash']}.json").exists()


def test_interpret_nested_match() -> None:
    """Interpret a v2-style nested exact species match."""
    resolved, reason = interpret_match(
        {
            "diagnostics": {"matchType": "EXACT", "confidence": 99},
            "usage": {"key": 123, "rank": "SPECIES"},
            "acceptedUsage": {"key": 123, "rank": "SPECIES", "canonicalName": "Poa annua"},
            "classification": [
                {"rank": "KINGDOM", "name": "Plantae"},
                {"rank": "FAMILY", "name": "Poaceae"},
                {"rank": "GENUS", "name": "Poa"},
            ],
        },
        "species",
    )
    assert reason is None
    assert resolved == {
        "usage_key": "123",
        "accepted_usage_key": "123",
        "accepted_name": "Poa annua",
        "genus": "Poa",
        "family": "Poaceae",
        "checklist_key": "7ddf754f-d193-4cc9-b351-99906754a03b",
        "taxonomy_confidence": 99.0,
    }


def test_interpret_flat_match_and_reject_rank_collapse() -> None:
    """Support flat payloads while rejecting species-to-genus collapse."""
    flat = {
        "matchType": "EXACT",
        "confidence": 99,
        "usageKey": 123,
        "acceptedUsageKey": 123,
        "rank": "SPECIES",
        "canonicalName": "Poa annua",
        "kingdom": "Plantae",
        "family": "Poaceae",
        "genus": "Poa",
    }
    resolved, reason = interpret_match(flat, "species")
    assert reason is None
    assert resolved is not None
    collapsed = {**flat, "acceptedRank": "GENUS"}
    assert interpret_match(collapsed, "species")[1] == "rank_mismatch"
