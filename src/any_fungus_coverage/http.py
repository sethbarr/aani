"""Hash-cached public requests with persistent transport failures."""

import base64
import hashlib
import json
import time
from pathlib import Path

import httpx

from src.common.io import timestamp


class PublicCache:
    """Store immutable successful responses and all unsuccessful attempts."""

    def __init__(self, root: Path, offline: bool = False) -> None:
        """Initialize a cache with optional strict offline operation."""
        self.root = root
        self.offline = offline
        self.client = httpx.Client(timeout=35, follow_redirects=True)

    def get_json(self, url: str, params: dict | None = None) -> tuple[object, str]:
        """Retrieve JSON, validating its stored body hash on every read."""
        body, key = self.get(url, params)
        return json.loads(body), key

    def get(self, url: str, params: dict | None = None) -> tuple[bytes, str]:
        """Retrieve public content with at most three recorded attempts."""
        descriptor = {"method": "GET", "url": url, "params": params or {}}
        key = hashlib.sha256(json.dumps(descriptor, sort_keys=True).encode()).hexdigest()
        path = self.root / f"{key}.json"
        record = (
            json.loads(path.read_text())
            if path.exists()
            else {"request": descriptor, "request_hash": key, "attempts": []}
        )
        if record["attempts"]:
            last = record["attempts"][-1]
            if last.get("status") == 200:
                body = base64.b64decode(last["body_base64"])
                assert hashlib.sha256(body).hexdigest() == last["body_sha256"]
                return body, key
        if self.offline:
            if record["attempts"]:
                raise RuntimeError(f"Public request failed: {key}: {last.get('error')}")
            raise RuntimeError(f"Offline missing request: {key}")
        for attempt in range(3):
            item: dict = {"retrieved_at": timestamp()}
            try:
                response = self.client.get(url, params=params)
                item.update(
                    status=response.status_code,
                    body_base64=base64.b64encode(response.content).decode(),
                    body_sha256=hashlib.sha256(response.content).hexdigest(),
                    final_url=str(response.url),
                )
                response.raise_for_status()
            except httpx.HTTPError as error:
                item["error"] = str(error)
            record["attempts"].append(item)
            self.root.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(record))
            temporary.replace(path)
            if item.get("status") == 200:
                return response.content, key
            if item.get("status") in {400, 404, 422}:
                break
            time.sleep(attempt + 1)
        raise RuntimeError(f"Public request failed: {key}: {item.get('error')}")
