"""A predeclared request transport with exactly one network attempt per job."""

import base64
from pathlib import Path

import httpx

from src.common.cache import CachedHTTP
from src.common.io import digest, timestamp


class SingleAttemptHTTP(CachedHTTP):
    """Save request and response evidence while prohibiting every retry."""

    def __init__(self, root: Path, expected_requests: dict[str, dict], client: httpx.Client) -> None:
        """Initialize a fresh response cache with exact permitted request descriptors."""
        super().__init__(root, offline=False, interval=0, client=client)
        self.expected_requests = expected_requests
        self.attempt_log: list[dict] = []

    def request(
        self, method: str, url: str, params: dict | None = None,
        body: dict | None = None, headers: dict[str, str] | None = None,
    ) -> tuple[bytes, str]:
        """Attempt one permitted request and persist any response or transport error.

        Args:
            method: Original HTTP method.
            url: Original provider URL.
            params: Original query parameters.
            body: Original structured request body.
            headers: Transient authentication headers, excluded from the cache.

        Returns:
            Exact response bytes and the original request hash.

        Raises:
            ValueError: Request differs from its predeclaration or was already attempted.
            httpx.HTTPError: The sole attempt fails; this transport never retries it.
            TimeoutError: The external wall-clock deadline interrupts the sole attempt.
        """
        descriptor = {"method": method.upper(), "url": url, "params": params or {}, "json": body}
        key = digest(descriptor)
        if self.expected_requests.get(key) != descriptor:
            raise ValueError("heldout_request_descriptor_changed")
        path = self.root / "http" / f"{key}.json"
        if path.exists():
            raise ValueError(f"heldout_request_already_attempted:{key}")
        event = {"request_hash": key, "attempt_number": 1, "started_at": timestamp(),
                 "kind": "started", "retry_reason": None}
        self.attempt_log.append(event)
        stored = {"request": descriptor, "request_hash": key, "attempts": [],
                  "transport_attempts": [event], "retry_policy": "one_attempt_no_retries"}
        self.persist(path, stored)
        try:
            response = self.client.request(method, url, params=params, json=body, headers=headers)
        except (httpx.TransportError, TimeoutError) as error:
            event.update({"kind": "transport_error", "finished_at": timestamp(),
                          "error_type": type(error).__name__, "error": str(error),
                          "remote_completion_unknown": True})
            self.persist(path, stored)
            raise
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
