"""Small deterministic serialization helpers."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC).isoformat()


def digest(value: object) -> str:
    """Hash a canonical JSON value for stable request and record identifiers.

    Args:
        value: JSON-serializable value.

    Returns:
        SHA-256 hex digest.
    """
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def read_json(path: Path) -> object:
    """Read a UTF-8 JSON document."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    """Write a JSON document, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )


def read_jsonl(path: Path) -> list[dict]:
    """Read nonempty JSON Lines records."""
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Write records as JSON Lines, preserving an empty output file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_table(path: Path, rows: list[dict], columns: list[str]) -> None:
    """Write a CSV with a stable header even when no records survive."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def normalise_space(text: str) -> str:
    """Collapse whitespace without regular expressions."""
    return " ".join(text.split())
