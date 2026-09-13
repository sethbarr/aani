"""Load simple local environment settings without shell evaluation."""

import os
from pathlib import Path


def load_local_environment(path: Path = Path(".env")) -> None:
    """Load key/value settings without interpolation or overwriting environment."""
    if not path.exists():
        return
    allowed = {
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_MODEL",
        "EXTRACTION_PROVIDER",
    }
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key, value = key.strip(), value.strip()
        if key not in allowed:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if value:
            os.environ.setdefault(key, value)
