"""Run the pre-draw v6 dispatcher copies with fixed offline sample-four arguments."""

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from src.common.io import read_json

ROOT = Path.cwd()
CODE = ROOT / "data/interim/grounding_v6_sample4_frozen_code"


def load_module(name: str, relative: str) -> ModuleType:
    """Load pinned source bytes while preserving the original configuration lookup path."""
    spec = importlib.util.spec_from_file_location(name, CODE / relative)
    if spec is None or spec.loader is None:
        raise ValueError(f"frozen_module_unavailable:{name}")
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(ROOT / relative)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_inputs() -> None:
    """Verify every frozen rule input before and after the offline execution."""
    import hashlib

    protocol = read_json(ROOT / "results/grounding_development_v6/heldout_sample4_protocol.json")
    for row in protocol["frozen_inputs"]:
        base = CODE if row["path"] in {"src/extraction/pipeline.py", "scripts/extract.py"} else ROOT
        path = base / row["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError(f"sample4_frozen_input_changed:{row['path']}")


def main() -> None:
    """Use the same saved response cache for initial scoring or isolated offline replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sample4", action="store_true")
    mode.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    destination = ("data/interim/grounding_v6_replay/sample4" if args.replay
                   else "data/interim/extraction_saverschek_multispan_v6/sample4")
    if Path(destination).exists():
        raise ValueError(f"preserve_existing_output:{destination}")
    verify_inputs()
    load_module("src.extraction.pipeline", "src/extraction/pipeline.py")
    cli = load_module("scripts.extract", "scripts/extract.py")
    sys.argv = ["scripts.extract", "--provider", "gemini", "--model", "gemini-3.8-flash",
                "--grounding", "multispan_v6", "--corpus", "data/interim/corpus_targeted_saverschek",
                "--output", destination, "--cache", "data/raw/grounding_v6_sample4", "--offline"]
    cli.main()
    verify_inputs()


if __name__ == "__main__":
    main()
