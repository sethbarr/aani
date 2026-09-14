"""Replay sample three with byte-pinned runner copies and unchanged v4 dependencies."""

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from src.common.io import read_json

ROOT = Path.cwd()
COPIES = ROOT / "data/interim/grounding_v4_sample3_frozen_code"
RECOVERED = ("src/extraction/pipeline.py", "scripts/extract.py")


def verify_code() -> None:
    """Require every pre-draw protected hash, substituting only the two pinned copies."""
    snapshot = read_json(ROOT / "results/grounding_development_v4/heldout_preserved_inputs.json")
    for row in snapshot["files"]:
        path = (COPIES if row["path"] in RECOVERED else ROOT) / row["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(f"heldout_frozen_replay_input_changed:{path}")


def load_frozen_module(name: str, relative: str) -> ModuleType:
    """Load an exact pre-draw module while retaining its original config path.

    Args:
        name: Original Python module name required by its callers.
        relative: Repository-relative path of the hash-verified recovery copy.

    Returns:
        Loaded module whose source bytes come from the recovery copy. Its file
        attribute preserves the repository-relative configuration lookup.
    """
    spec = importlib.util.spec_from_file_location(name, COPIES / relative)
    if spec is None or spec.loader is None:
        raise ValueError(f"frozen_module_cannot_load:{name}")
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(ROOT / relative)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    """Run only the predeclared offline v4 replay, using the separate sample-three cache."""
    verify_code()
    destination = Path("data/interim/grounding_v4_sample3_replay")
    if destination.exists():
        raise ValueError("heldout_frozen_replay_destination_exists")
    load_frozen_module("src.extraction.pipeline", "src/extraction/pipeline.py")
    cli = load_frozen_module("scripts.extract", "scripts/extract.py")
    sys.argv = ["scripts.extract", "--provider", "gemini", "--model", "gemini-3.8-flash",
                "--grounding", "multispan_v4", "--corpus", "data/interim/corpus_targeted_saverschek",
                "--output", str(destination), "--cache", "data/raw/grounding_v4_sample3", "--offline"]
    cli.main()
    verify_code()


if __name__ == "__main__":
    main()
