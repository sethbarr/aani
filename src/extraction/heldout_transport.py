"""Single-response sampling with explicit transport-only retry records."""

import base64
from pathlib import Path

import httpx

from src.common.cache import CachedHTTP
from src.common.io import digest, timestamp


class HeldoutHTTP(CachedHTTP):
    """Restrict held-out sampling to predeclared requests and one HTTP response each.

    Args:
        root: Fresh cache directory for the held-out sample.
        expected_requests: Request hashes mapped to original sanitized descriptors.
        client: HTTP client with automatic redirects and retries disabled.
    """

    def __init__(self, root: Path, expected_requests: dict[str, dict], client: httpx.Client) -> None:
        """Initialize a separate cache and a finite transport-error retry allowance."""
        super().__init__(root, offline=False, interval=0, client=client)
        self.expected_requests = expected_requests
        self.attempt_log: list[dict] = []

    def request(
        self, method: str, url: str, params: dict | None = None,
        body: dict | None = None, headers: dict[str, str] | None = None,
    ) -> tuple[bytes, str]:
        """Obtain one HTTP response, allowing one retry only after a transport error.

        Args:
            method: Original request method.
            url: Original provider endpoint.
            params: Original query parameters without credentials.
            body: Original structured request body.
            headers: Transient authentication headers, never persisted.

        Returns:
            Saved raw response bytes and the unchanged request descriptor hash.

        Raises:
            ValueError: Descriptor differs from the predeclared request or was already attempted.
            httpx.TransportError: Both allowed transport attempts failed.
            httpx.HTTPStatusError: Any non-success HTTP status; HTTP statuses are never retried.
        """
        descriptor = {"method": method.upper(), "url": url, "params": params or {}, "json": body}
        key = digest(descriptor)
        if self.expected_requests.get(key) != descriptor:
            raise ValueError("heldout_request_descriptor_changed")
        path = self.root / "http" / f"{key}.json"
        if path.exists():
            raise ValueError(f"heldout_request_already_attempted:{key}")
        stored = {"request": descriptor, "request_hash": key, "attempts": [],
                  "transport_attempts": [], "retry_policy": "one_retry_only_after_transport_error"}
        for attempt_index in range(2):
            event = {"request_hash": key, "attempt_number": attempt_index + 1,
                     "started_at": timestamp(), "kind": "started",
                     "retry_reason": "previous_transport_error" if attempt_index else None}
            stored["transport_attempts"].append(event)
            self.attempt_log.append(event)
            self.persist(path, stored)
            try:
                response = self.client.request(method, url, params=params, json=body, headers=headers)
            except httpx.TransportError as error:
                event.update({"kind": "transport_error", "finished_at": timestamp(),
                              "error_type": type(error).__name__, "error": str(error),
                              "remote_completion_unknown": True})
                self.persist(path, stored)
                if attempt_index == 1:
                    raise
                continue
            event.update({"kind": "http_response", "finished_at": timestamp(),
                          "http_status": response.status_code})
            stored["attempts"].append({
                "status": response.status_code, "retrieved_at": timestamp(),
                "body_base64": base64.b64encode(response.content).decode("ascii"),
                "content_type": response.headers.get("content-type", ""),
            })
            self.persist(path, stored)
            response.raise_for_status()
            return response.content, key
        raise RuntimeError("heldout_transport_attempts_exhausted")
