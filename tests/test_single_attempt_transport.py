"""Ensure held-out sampling has one attempt even after transport and HTTP errors."""

from pathlib import Path

import httpx
import pytest

from src.common.io import digest, read_json
from src.extraction.single_attempt_transport import SingleAttemptHTTP


class ResponseHandler:
    """Return one configured HTTP outcome and count actual network attempts."""

    def __init__(self, status: int | None) -> None:
        """Select an HTTP status or a transport-error outcome."""
        self.status = status
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        """Count the call and return or raise the configured result."""
        self.calls += 1
        if self.status == -1:
            raise TimeoutError("v6_wall_clock_deadline_reached")
        if self.status is None:
            raise httpx.ConnectError("synthetic transport failure", request=request)
        return httpx.Response(self.status, json={"records": []}, request=request)


@pytest.mark.parametrize("status", [200, 302, 429, 500, None, -1])
def test_each_outcome_has_exactly_one_attempt(tmp_path: Path, status: int | None) -> None:
    """Prohibit retries for success, redirects, quota errors and transport failures."""
    descriptor = {"method": "POST", "url": "https://example.invalid/model", "params": {},
                  "json": {"fixture": True}}
    key = digest(descriptor)
    handler = ResponseHandler(status)
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    cache = SingleAttemptHTTP(tmp_path, {key: descriptor}, client)
    try:
        if status == 200:
            _, returned = cache.request("POST", descriptor["url"], body=descriptor["json"])
            assert returned == key
        else:
            error_type = TimeoutError if status == -1 else httpx.HTTPError
            with pytest.raises(error_type):
                cache.request("POST", descriptor["url"], body=descriptor["json"])
        assert handler.calls == 1
        saved = read_json(tmp_path / "http" / f"{key}.json")
        assert len(saved["transport_attempts"]) == 1
        with pytest.raises(ValueError):
            cache.request("POST", descriptor["url"], body=descriptor["json"])
        assert handler.calls == 1
    finally:
        cache.close()


def test_descriptor_change_fails_before_network(tmp_path: Path) -> None:
    """Reject an unapproved descriptor before any network or cache mutation."""
    handler = ResponseHandler(200)
    cache = SingleAttemptHTTP(tmp_path, {}, httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        with pytest.raises(ValueError):
            cache.request("POST", "https://example.invalid/changed", body={})
        assert handler.calls == 0
        assert not list(tmp_path.rglob("*.json"))
    finally:
        cache.close()
