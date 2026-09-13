"""Merge audited taxonomy outputs and emit unanimous genus behaviour tables."""

import argparse
import json
from pathlib import Path

from src.behaviour.pipeline import run_merge
from src.common.io import write_json


def main() -> None:
    """Run the deterministic local merge, supporting identical offline replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("data/processed/behaviour"))
    parser.add_argument("--taxonomy-supplement", type=Path, action="append", default=[])
    parser.add_argument("--offline", action="store_true",
                        help="Explicitly require local cached inputs; this stage never networks.")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        metrics = run_merge(root, output, args.taxonomy_supplement)
    except (OSError, KeyError, TypeError, ValueError) as error:
        metrics = {"status": "blocked", "blocked_reason": str(error), "network_requests": 0}
        write_json(output / "metrics.json", metrics)
        print(json.dumps(metrics, indent=2))
        raise SystemExit(1) from error
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
