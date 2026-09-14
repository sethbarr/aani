"""Verify the predeclared single-response sampling contract without network access."""

from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from src.common.io import digest, read_json
from src.extraction.heldout_transport import HeldoutHTTP

URL = "https://example.invalid/model"
BODY = {"model": "fixture", "input": "fixed source"}
DESCRIPTOR = {"method": "POST", "url": URL, "params": {}, "json": BODY}


def transport_fixture(tmp_path: Path, replies: list) -> tuple[HeldoutHTTP, Mock]:
    """Build a fresh cache backed by a deterministic in-memory HTTP transport.

    Args:
        tmp_path: Test-local output directory.
        replies: HTTP responses or transport exceptions in attempt order.

    Returns:
        Restricted cache and mock transport handler.
    """
    handler = Mock(side_effect=replies)
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    return HeldoutHTTP(tmp_path, {digest(DESCRIPTOR): DESCRIPTOR}, client), handler


def test_success_makes_one_call_and_refuses_resampling(tmp_path: Path) -> None:
    """Retain one successful response and forbid another sample under its key."""
    cache, handler = transport_fixture(tmp_path, [httpx.Response(200, json={"ok": True})])
    try:
        content, key = cache.request("POST", URL, body=BODY, headers={"x-key": "secret"})
        assert b"true" in content
        assert handler.call_count == 1
        saved = read_json(tmp_path / "http" / f"{key}.json")
        assert len(saved["attempts"]) == 1
        assert "secret" not in str(saved)
        with pytest.raises(ValueError):
            cache.request("POST", URL, body=BODY)
        assert handler.call_count == 1
    finally:
        cache.close()


@pytest.mark.parametrize("status", [302, 400, 401, 403, 404, 429, 500, 502, 503, 504])
def test_http_status_errors_never_retry(tmp_path: Path, status: int) -> None:
    """Every actual HTTP response ends sampling for that job, including rate limits."""
    cache, handler = transport_fixture(tmp_path, [httpx.Response(status, json={"error": "fixture"})])
    try:
        with pytest.raises(httpx.HTTPStatusError):
            cache.request("POST", URL, body=BODY)
        assert handler.call_count == 1
        assert cache.attempt_log[0]["http_status"] == status
    finally:
        cache.close()


def test_transport_error_permits_one_recorded_retry(tmp_path: Path) -> None:
    """Retry only a transport exception and preserve its uncertainty in the ledger."""
    cache, handler = transport_fixture(tmp_path, [httpx.ReadTimeout("fixture"), httpx.Response(200)])
    try:
        cache.request("POST", URL, body=BODY)
        assert handler.call_count == 2
        assert [row["kind"] for row in cache.attempt_log] == ["transport_error", "http_response"]
        assert cache.attempt_log[1]["retry_reason"] == "previous_transport_error"
        assert cache.attempt_log[0]["remote_completion_unknown"] is True
    finally:
        cache.close()


def test_repeated_transport_failure_stops_after_two_attempts(tmp_path: Path) -> None:
    """Bound transport retries and record both failures without a fabricated response."""
    cache, handler = transport_fixture(tmp_path, [httpx.ConnectError("first"), httpx.ConnectError("second")])
    try:
        with pytest.raises(httpx.TransportError):
            cache.request("POST", URL, body=BODY)
        assert handler.call_count == 2
        saved = read_json(tmp_path / "http" / f"{digest(DESCRIPTOR)}.json")
        assert saved["attempts"] == []
        assert len(saved["transport_attempts"]) == 2
    finally:
        cache.close()


def test_changed_request_is_rejected_before_transport(tmp_path: Path) -> None:
    """Keep model, context, schema and every descriptor field fixed before sampling."""
    cache, handler = transport_fixture(tmp_path, [])
    try:
        with pytest.raises(ValueError):
            cache.request("POST", URL, body={"input": "changed"})
        handler.assert_not_called()
    finally:
        cache.close()
