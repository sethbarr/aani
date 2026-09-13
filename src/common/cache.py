"""Disk-cached HTTP with deterministic keys, throttling and offline replay."""

import base64
import json
import time
import uuid
from pathlib import Path

import httpx

from src.common.io import digest, read_json, timestamp


class OfflineCacheMiss(RuntimeError):
    """A request is missing from an explicitly offline run."""


def response_error_code(response: httpx.Response) -> str:
    """Read a service error code without logging payloads or credentials."""
    try:
        payload = response.json()
    except ValueError:
        return ""
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return ""
    return str(error.get("status") or error.get("code") or error.get("type") or "")


class CachedHTTP:
    """Cache responses without recording authorization headers.

    Args:
        root: Raw response cache directory.
        offline: Whether network access is forbidden.
        interval: Minimum seconds between network requests.
        client: Optional HTTP client, useful for isolated tests.
    """

    def __init__(
        self,
        root: Path,
        offline: bool = False,
        interval: float = 1.0,
        client: httpx.Client | None = None,
    ) -> None:
        """Initialize request caching and a bounded synchronous client."""
        self.root = root
        self.offline = offline
        self.interval = interval
        self.client = client or httpx.Client(timeout=60, follow_redirects=True)
        self.last_request = 0.0

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()

    def request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        body: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, str]:
        """Return a cached response body and request hash.

        Every HTTP attempt is persisted, including unsuccessful statuses. Offline
        replay raises the recorded error rather than converting it into data.

        Args:
            method: HTTP method.
            url: Absolute endpoint URL.
            params: Query parameters, excluding secrets.
            body: JSON request body, excluding secrets.
            headers: Transient headers; never persisted.

        Returns:
            Response bytes and deterministic request hash.

        Raises:
            OfflineCacheMiss: No cached request exists in offline mode.
            httpx.HTTPError: Transport or unsuccessful response status.
        """
        descriptor = {"method": method.upper(), "url": url, "params": params or {}, "json": body}
        key = digest(descriptor)
        path = self.root / "http" / f"{key}.json"
        if path.exists():
            stored = read_json(path)
            last = stored["attempts"][-1]
            if last["status"] < 400 or self.offline:
                return self.decode(last, method, url), key
        if self.offline:
            raise OfflineCacheMiss(f"Missing cached request {key}: {url}")
        attempts = read_json(path)["attempts"] if path.exists() else []
        for attempt in range(4):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            response = self.client.request(method, url, params=params, json=body, headers=headers)
            item = {
                "status": response.status_code,
                "retrieved_at": timestamp(),
                "body_base64": base64.b64encode(response.content).decode(),
                "content_type": response.headers.get("content-type", ""),
            }
            attempts.append(item)
            self.persist(path, {"request": descriptor, "request_hash": key, "attempts": attempts})
            quota_exhausted = response.status_code == 429 and response_error_code(response) in {
                "credit_balance_exhausted",
                "insufficient_quota",
                "quota_exceeded",
            }
            if (
                quota_exhausted
                or response.status_code not in {429, 500, 502, 503, 504}
                or attempt == 3
            ):
                response.raise_for_status()
                return response.content, key
            retry = response.headers.get("retry-after", "")
            delay = float(retry) if retry.isdecimal() else 2 ** (attempt + 1)
            if delay > 60:
                raise RuntimeError(
                    f"Rate limited; retry after {delay} seconds. Response cached at {path}"
                )
            time.sleep(delay)
        raise RuntimeError("HTTP retry loop exhausted")

    def get_json(self, url: str, params: dict | None = None) -> tuple[object, str]:
        """Fetch and decode a cached JSON GET response."""
        content, key = self.request("GET", url, params=params)
        return json.loads(content), key

    @staticmethod
    def decode(item: dict, method: str, url: str) -> bytes:
        """Reconstruct cached status semantics and return its body."""
        content = base64.b64decode(item["body_base64"])
        response = httpx.Response(
            item["status"], content=content, request=httpx.Request(method, url)
        )
        response.raise_for_status()
        return content

    @staticmethod
    def persist(path: Path, value: dict) -> None:
        """Atomically replace a cache entry to avoid partial JSON on interruption."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
