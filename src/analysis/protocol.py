"""Require an unchanged committed protocol before a real analysis run."""

import subprocess
from pathlib import Path

FROZEN_COMMIT = "98b5e09199a5eef0c46be452793e953f5a2af31e"


def committed_protocol(root: Path) -> str:
    """Return the plan commit or refuse an uncommitted/modified protocol."""
    paths = ["docs/analysis_plan.md", "config/analysis.json"]
    for path in paths:
        result = subprocess.run(
            ["git", "show", f"{FROZEN_COMMIT}:{path}"], cwd=root, capture_output=True, check=False
        )
        if result.returncode or result.stdout != (root / path).read_bytes():
            raise RuntimeError(
                f"Frozen protocol differs from commit {FROZEN_COMMIT}: {path}"
            )
    return FROZEN_COMMIT
