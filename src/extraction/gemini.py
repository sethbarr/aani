"""Stateless Gemini Interactions requests with the shared extraction schema."""

import json
import os

import httpx

from src.common.cache import CachedHTTP, response_error_code
from src.extraction.errors import ExtractionServiceUnavailable

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_MODEL = "gemini-3.8-flash"


def gemini_output(response: dict) -> dict:
    """Read only completed model text, excluding thoughts and tool messages.

    Args:
        response: Decoded Interactions API response.

    Returns:
        Parsed extraction object, before per-record grounding validation.

    Raises:
        ValueError: The response is incomplete, failed, empty or malformed.
    """
    if response.get("status") != "completed" or response.get("errors"):
        raise ValueError(f"Incomplete Gemini response: {response.get('status')}")
    pieces = [
        part["text"]
        for step in response.get("steps", [])
        if step.get("type") == "model_output"
        for part in step.get("content", [])
        if part.get("type") == "text" and isinstance(part.get("text"), str)
    ]
    if not pieces or not "".join(pieces).strip():
        raise ValueError("Gemini returned no model text")
    parsed = json.loads("".join(pieces))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("records"), list):
        raise ValueError("Gemini output must be an object with a records array")
    return parsed


def request_gemini(job: dict, cache: CachedHTTP, model: str) -> dict:
    """Call Gemini using header authentication and cache the complete response.

    Args:
        job: Hashed prompt, schema and complete source blocks.
        cache: HTTP cache supporting replay without credentials.
        model: Explicit requested Gemini model identifier.

    Returns:
        Provider-labelled envelope compatible with the shared validator.

    Raises:
        ExtractionServiceUnavailable: Authentication, quota or configuration fails.
        ValueError: No completed structured response is available.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key and not cache.offline:
        raise ExtractionServiceUnavailable("Set GEMINI_API_KEY in the local .env file")
    body = {
        "model": model,
        "store": False,
        "system_instruction": job["prompt"],
        "input": json.dumps(
            {
                "source_id": job["source_id"],
                "title": job["title"],
                "blocks": job["blocks"],
            }
        ),
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": job["schema"],
        },
        "generation_config": {
            "max_output_tokens": 32768,
            "thinking_level": "low",
            "thinking_summaries": "none",
        },
    }
    try:
        content, request_hash = cache.request(
            "POST",
            ENDPOINT,
            body=body,
            headers={"x-goog-api-key": api_key},
        )
    except httpx.HTTPStatusError as error:
        if error.response.status_code in {400, 401, 403, 404, 429}:
            code = response_error_code(error.response)
            raise ExtractionServiceUnavailable(
                f"Gemini service unavailable: HTTP {error.response.status_code}; {code}"
            ) from error
        raise
    response = json.loads(content)
    if not isinstance(response, dict):
        raise ValueError("Gemini response must be an object")
    return {
        "input_hash": job["input_hash"],
        "engine": model,
        "resolved_model": response.get("model", model),
        "provider": "gemini",
        "mode": "gemini_interactions_api",
        "created_at": response.get("created"),
        "response_id": response.get("id"),
        "request_hash": request_hash,
        "usage": response.get("usage", {}),
        "output": gemini_output(response),
    }
