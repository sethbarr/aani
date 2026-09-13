"""Stream versioned bulk exports into a request-hash cache."""

import hashlib
from pathlib import Path

import httpx

from src.common.cache import OfflineCacheMiss
from src.common.io import digest, read_json, timestamp, write_json


def file_hash(path: Path, algorithm: str = "sha256") -> str:
    """Return a streaming file checksum without loading an export into memory."""
    checksum = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            checksum.update(chunk)
    return checksum.hexdigest()


def download_export(url: str, raw: Path, offline: bool = False) -> tuple[Path, dict]:
    """Archive a complete HTTP response and its request descriptor.

    Args:
        url: Verified version-specific bulk file URL.
        raw: Chemistry-specific raw cache directory.
        offline: Whether to forbid all network access.

    Returns:
        Cached response body path and metadata including SHA-256 and retrieval time.
    """
    descriptor = {"method": "GET", "url": url, "params": {}, "json": None}
    key = digest(descriptor)
    directory = raw / "downloads"
    metadata_path = directory / f"{key}.json"
    body_path = directory / f"{key}.body"
    if metadata_path.exists():
        metadata = read_json(metadata_path)
        if metadata.get("complete") and metadata.get("status") == 200:
            if file_hash(body_path) != metadata["sha256"]:
                raise ValueError(f"Cached export checksum mismatch: {body_path}")
            return body_path, metadata
        if offline:
            raise RuntimeError(f"Cached export unavailable: {metadata}")
    if offline:
        raise OfflineCacheMiss(f"Missing cached bulk request {key}: {url}")
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f"{key}.partial"
    metadata = {"request": descriptor, "request_hash": key, "complete": False}
    try:
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                metadata.update({
                    "status": response.status_code,
                    "retrieved_at": timestamp(),
                    "final_url": str(response.url),
                    "content_type": response.headers.get("content-type"),
                    "content_length": response.headers.get("content-length"),
                })
                with temporary.open("wb") as handle:
                    for chunk in response.iter_bytes(1024 * 1024):
                        handle.write(chunk)
                temporary.replace(body_path)
                metadata.update({
                    "complete": True,
                    "bytes": body_path.stat().st_size,
                    "sha256": file_hash(body_path),
                    "md5": file_hash(body_path, "md5"),
                    "body_path": str(body_path),
                })
                write_json(metadata_path, metadata)
                response.raise_for_status()
    except httpx.TransportError as exc:
        metadata["transport_error"] = str(exc)
        metadata["partial_bytes"] = temporary.stat().st_size if temporary.exists() else 0
        write_json(metadata_path, metadata)
        raise
    return body_path, metadata
