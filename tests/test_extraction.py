from pathlib import Path

import httpx
import pytest

from src.common.cache import CachedHTTP
from src.common.io import read_json, read_jsonl, write_json, write_jsonl
from src.extraction.pipeline import make_jobs, run_extraction, validate_candidate
from src.extraction.schema import Extraction


def job() -> dict:
    """Return a minimal source job for grounding tests."""
    return {
        "source_id": "PMC1",
        "input_hash": "input",
        "source_url": "https://europepmc.org/articles/PMC1",
        "blocks": [
            {
                "block_id": "b00000",
                "section": "Body / Choice",
                "text": "Atta colombica rejected leaves of Cecropia peltata after contact.",
            }
        ],
    }


def record(**updates: object) -> dict:
    """Return a valid candidate record with optional field overrides."""
    value = {
        "ant_species": "Atta colombica",
        "plant_name_as_written": "Cecropia peltata",
        "taxonomic_rank": "species",
        "outcome": "rejected",
        "evidence_type": "field_choice_assay",
        "quantitative_measure": None,
        "source_id": "PMC1",
        "section": "Body / Choice",
        "block_id": "b00000",
        "evidence_quote": "Atta colombica rejected leaves of Cecropia peltata after contact.",
        "extraction_confidence": 0.9,
        "substrate_treatment": "natural",
        "rejection_timing": "immediate",
        "behavioural_choice": True,
        "study_context": "contact choice",
        "original_source_id": None,
    }
    value.update(updates)
    return value


def test_grounded_candidate_is_accepted() -> None:
    """Accept a candidate whose quote and source metadata are grounded."""
    validated, reason = validate_candidate(record(), job(), 0.8)
    assert reason is None
    assert validated is not None
    assert validated["source_url"].startswith("https://")


def test_unquoted_plant_is_rejected() -> None:
    """Reject a grounded quote that omits the claimed plant name."""
    validated, reason = validate_candidate(
        record(evidence_quote="Atta colombica rejected leaves of"), job(), 0.8
    )
    assert validated is None
    assert reason == "plant_not_in_quote"


def test_screening_excludes_only_reviewed_sources(tmp_path: Path) -> None:
    """Require explicit screening for every source and preserve input order."""
    papers = [
        {"source_id": source, "status": "ready", "title": source, "source_url": "https://example.org"}
        for source in ("PMC1", "PMC2")
    ]
    write_jsonl(tmp_path / "manifest.jsonl", papers)
    write_json(tmp_path / "texts/PMC1.json", {"blocks": job()["blocks"]})
    screen = tmp_path / "screening.json"
    write_json(screen, {"decisions": [
        {"source_id": "PMC1", "decision": "include"},
        {"source_id": "PMC2", "decision": "exclude"},
    ]})
    jobs = make_jobs(tmp_path, screening=screen)
    assert [item["source_id"] for item in jobs] == ["PMC1"]
    write_json(screen, {"decisions": [{"source_id": "PMC1", "decision": "include"}]})
    with pytest.raises(ValueError) as error:
        make_jobs(tmp_path, screening=screen)
    assert "Screening must cover exactly" in str(error.value)


def quota_response(request: httpx.Request) -> httpx.Response:
    """Return an exhausted-credit response to exercise the request stop."""
    return httpx.Response(429, request=request, json={"error": {
        "code": "credit_balance_exhausted", "type": "insufficient_quota",
    }})


def test_quota_error_stops_without_retries_or_false_completeness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cache one quota response and mark the untouched paper as blocked."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    first = {**job(), "title": "First", "schema": Extraction.model_json_schema()}
    second = {**first, "title": "Second", "source_id": "PMC2", "input_hash": "second"}
    cache = CachedHTTP(
        tmp_path / "raw", interval=0, client=httpx.Client(transport=httpx.MockTransport(quota_response))
    )
    try:
        metrics = run_extraction([first, second], cache, tmp_path / "output", model="gpt-5.4")
    finally:
        cache.close()
    entries = list((tmp_path / "raw/http").glob("*.json"))
    assert len(entries) == 1
    assert len(read_json(entries[0])["attempts"]) == 1
    assert "test-key" not in entries[0].read_text()
    assert metrics["complete_papers"] == 0
    assert metrics["incomplete_papers"] == 2
    assert metrics["unattempted_chunks"] == 1
    assert metrics["rejection_rate"] is None
    assert [row["status"] for row in read_jsonl(tmp_path / "output/chunk_status.jsonl")] == [
        "failed", "blocked",
    ]
