import json
from functools import partial
from pathlib import Path

import httpx
import pytest

from src.common.cache import CachedHTTP
from src.common.io import digest, read_json, read_jsonl
from src.extraction.errors import ExtractionServiceUnavailable
from src.extraction.gemini import request_gemini
from src.extraction.pipeline import run_extraction
from src.extraction.schema import PROMPT, Extraction

MODEL = "gemini-test-model"
QUOTE = "Atta colombica rejected leaves of Cecropia peltata after contact."


def gemini_job() -> dict:
    """Build a complete source job with the production extraction contract."""
    job = {
        "source_id": "PMC1",
        "source_url": "https://europepmc.org/articles/PMC1",
        "title": "Leafcutter substrate choice",
        "prompt": PROMPT,
        "schema": Extraction.model_json_schema(),
        "blocks": [{"block_id": "b00000", "section": "Results", "text": QUOTE}],
    }
    return {**job, "input_hash": digest(job)}


def grounded_record() -> dict:
    """Return one schema-valid observation grounded in the source job."""
    return {
        "ant_species": "Atta colombica",
        "plant_name_as_written": "Cecropia peltata",
        "taxonomic_rank": "species",
        "outcome": "rejected",
        "evidence_type": "field_choice_assay",
        "quantitative_measure": None,
        "source_id": "PMC1",
        "section": "Results",
        "block_id": "b00000",
        "evidence_quote": QUOTE,
        "extraction_confidence": 0.9,
        "substrate_treatment": "natural",
        "rejection_timing": "immediate",
        "behavioural_choice": True,
        "study_context": "contact choice",
        "original_source_id": None,
    }


def completed_response(records: list[dict]) -> dict:
    """Include non-answer content and split text to exercise output decoding."""
    encoded = json.dumps({"records": records})
    split = len(encoded) // 2
    return {
        "id": "interaction-test-id",
        "model": "gemini-resolved-test-model",
        "created": "2026-09-12T15:00:00Z",
        "status": "completed",
        "usage": {"total_input_tokens": 100, "total_output_tokens": 50},
        "steps": [
            {"type": "thought", "content": [{"type": "text", "text": "Ignore this."}]},
            {"type": "model_output", "content": [
                {"type": "text", "text": encoded[:split]},
                {"type": "text", "text": encoded[split:]},
            ]},
        ],
    }


def response_payload(
    request: httpx.Request, *, payload: object, status_code: int = 200,
) -> httpx.Response:
    """Return a controlled API response without making network requests."""
    return httpx.Response(
        status_code, request=request, json=payload, headers={"retry-after": "0"}
    )


def inspect_request(request: httpx.Request, *, expected_key: str) -> httpx.Response:
    """Verify the external request contract and return one grounded answer."""
    job = gemini_job()
    assert request.method == "POST"
    assert str(request.url) == "https://generativelanguage.googleapis.com/v1beta/interactions"
    assert request.headers["x-goog-api-key"] == expected_key
    body = json.loads(request.content)
    assert body["model"] == MODEL
    assert body["store"] is False
    assert body["system_instruction"] == job["prompt"]
    assert json.loads(body["input"]) == {
        "source_id": job["source_id"], "title": job["title"], "blocks": job["blocks"],
    }
    assert body["response_format"] == {
        "type": "text", "mime_type": "application/json", "schema": job["schema"],
    }
    assert body["generation_config"] == {
        "max_output_tokens": 32768,
        "thinking_level": "low",
        "thinking_summaries": "none",
    }
    return response_payload(request, payload=completed_response([grounded_record()]))


def unexpected_request(request: httpx.Request) -> httpx.Response:
    """Fail if an offline or unconfigured run reaches the transport."""
    raise AssertionError(f"Unexpected network request: {request.method} {request.url}")


def test_gemini_provenance_and_keyless_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the full schema and provenance while excluding keys from the cache."""
    monkeypatch.setenv("GEMINI_API_KEY", "preferred-gemini-secret")
    monkeypatch.setenv("GOOGLE_API_KEY", "fallback-google-secret")
    transport = httpx.MockTransport(partial(inspect_request, expected_key="preferred-gemini-secret"))
    cache = CachedHTTP(tmp_path, interval=0, client=httpx.Client(transport=transport))
    try:
        envelope = request_gemini(gemini_job(), cache, MODEL)
    finally:
        cache.close()
    assert envelope["input_hash"] == gemini_job()["input_hash"]
    assert envelope["engine"] == MODEL
    assert envelope["provider"] == "gemini"
    assert envelope["mode"] == "gemini_interactions_api"
    assert envelope["created_at"] == "2026-09-12T15:00:00Z"
    assert envelope["resolved_model"] == "gemini-resolved-test-model"
    assert envelope["response_id"] == "interaction-test-id"
    assert envelope["usage"] == {"total_input_tokens": 100, "total_output_tokens": 50}
    assert envelope["output"] == {"records": [grounded_record()]}
    entry = tmp_path / "http" / f"{envelope['request_hash']}.json"
    assert "preferred-gemini-secret" not in entry.read_text()
    assert "fallback-google-secret" not in entry.read_text()
    assert read_json(entry)["request"]["json"]["response_format"]["schema"] == gemini_job()["schema"]
    monkeypatch.delenv("GEMINI_API_KEY")
    monkeypatch.delenv("GOOGLE_API_KEY")
    offline = CachedHTTP(
        tmp_path, offline=True, client=httpx.Client(transport=httpx.MockTransport(unexpected_request))
    )
    try:
        assert request_gemini(gemini_job(), offline, MODEL) == envelope
    finally:
        offline.close()


def test_google_key_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow the standard Google key name when the Gemini-specific key is absent."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "fallback-google-secret")
    transport = httpx.MockTransport(partial(inspect_request, expected_key="fallback-google-secret"))
    cache = CachedHTTP(tmp_path, interval=0, client=httpx.Client(transport=transport))
    try:
        assert request_gemini(gemini_job(), cache, MODEL)["output"]["records"]
    finally:
        cache.close()


@pytest.mark.parametrize("payload", [
    {"status": "in_progress", "steps": []},
    {"status": "failed", "error": {"code": "SAFETY", "message": "Blocked"}},
    {"status": "completed", "steps": []},
    {"status": "completed", "steps": [{"type": "model_output", "content": [
        {"type": "safety", "message": "Blocked"},
    ]}]},
    {"status": "completed", "steps": [{"type": "model_output", "content": [
        {"type": "text", "text": "{invalid json"},
    ]}]},
])
def test_incomplete_or_invalid_gemini_output_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: dict,
) -> None:
    """Never turn failed, safety-blocked, empty or malformed answers into records."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    transport = httpx.MockTransport(partial(response_payload, payload=payload))
    cache = CachedHTTP(tmp_path, interval=0, client=httpx.Client(transport=transport))
    try:
        with pytest.raises(ValueError):
            request_gemini(gemini_job(), cache, MODEL)
    finally:
        cache.close()


def test_missing_gemini_key_stops_before_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing credentials stop the batch and leave later jobs unattempted."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    cache = CachedHTTP(
        tmp_path / "raw", client=httpx.Client(transport=httpx.MockTransport(unexpected_request))
    )
    jobs = [gemini_job(), {**gemini_job(), "source_id": "PMC2", "input_hash": "second"}]
    try:
        with pytest.raises(ExtractionServiceUnavailable):
            request_gemini(jobs[0], cache, MODEL)
        metrics = run_extraction(jobs, cache, tmp_path / "output", model=MODEL, provider="gemini")
    finally:
        cache.close()
    assert metrics["complete_papers"] == 0
    assert metrics["unattempted_chunks"] == 1
    assert [row["status"] for row in read_jsonl(tmp_path / "output/chunk_status.jsonl")] == [
        "failed", "blocked",
    ]
    assert not list((tmp_path / "raw").rglob("*.json"))


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 429])
def test_gemini_service_errors_stop_the_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status_code: int,
) -> None:
    """Bound retries and block later jobs for credential, model or quota failures."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    transport = httpx.MockTransport(partial(
        response_payload, status_code=status_code, payload={"error": {"code": status_code}},
    ))
    cache = CachedHTTP(tmp_path / "raw", interval=0, client=httpx.Client(transport=transport))
    jobs = [gemini_job(), {**gemini_job(), "source_id": "PMC2", "input_hash": "second"}]
    try:
        metrics = run_extraction(jobs, cache, tmp_path / "output", model=MODEL, provider="gemini")
    finally:
        cache.close()
    assert metrics["complete_papers"] == 0
    assert metrics["response_failures"] == 1
    assert metrics["unattempted_chunks"] == 1
    entries = list((tmp_path / "raw/http").glob("*.json"))
    assert len(entries) == 1
    attempts = read_json(entries[0])["attempts"]
    assert 1 <= len(attempts) <= 4
    assert all(attempt["status"] == status_code for attempt in attempts)
    assert "test-secret" not in entries[0].read_text()


def test_gemini_records_still_require_grounding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid API answer still rejects a claim with an invented evidence quote."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    invented = {**grounded_record(), "evidence_quote": "Atta never collected Cecropia peltata."}
    payload = completed_response([grounded_record(), invented])
    transport = httpx.MockTransport(partial(response_payload, payload=payload))
    cache = CachedHTTP(tmp_path / "raw", interval=0, client=httpx.Client(transport=transport))
    try:
        metrics = run_extraction(
            [gemini_job()], cache, tmp_path / "output", model=MODEL, provider="gemini"
        )
    finally:
        cache.close()
    assert metrics["validated_candidates"] == 1
    assert metrics["rejected_candidates"] == 1
    assert metrics["complete_papers"] == 1
    assert read_jsonl(tmp_path / "output/rejections.jsonl")[0]["reason"] == "ungrounded_quote"
    observation = read_jsonl(tmp_path / "output/observations.jsonl")[0]
    assert observation["engine"] == MODEL
    assert observation["evidence_quote"] == QUOTE
    envelope = read_json(tmp_path / "output/responses" / f"{gemini_job()['input_hash']}.json")
    assert envelope["provider"] == "gemini"
