"""Import versioned natural-product occurrence exports."""

import argparse
import json
from pathlib import Path

from src.chemistry.lotus import acquire_lotus
from src.chemistry.occurrences import import_occurrences
from src.common.io import write_json


def main() -> None:
    """Validate and archive a LOTUS/COCONUT occurrence CSV."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("--lotus-export", action="store_true")
    parser.add_argument("--genera", type=Path)
    parser.add_argument("--interim", type=Path, default=Path("data/interim/chemistry"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/chemistry"))
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if args.lotus_export and args.source:
        parser.error("Choose a local occurrence CSV or --lotus-export, not both")
    if args.lotus_export and not args.genera:
        parser.error("--lotus-export requires --genera with the audited genus table")
    if not args.lotus_export and not args.source:
        parser.error("Provide a local occurrence CSV or --lotus-export")
    try:
        if args.lotus_export:
            result = acquire_lotus(
                args.genera, args.raw, args.interim, args.output, offline=args.offline
            )
            print(json.dumps(result["metrics"], indent=2))
        else:
            print(json.dumps(import_occurrences(args.source, args.raw, args.output), indent=2))
    except Exception as exc:
        blocked = {
            "status": "blocked", "blocked_reason": f"{type(exc).__name__}: {exc}",
            "accepted": None, "genera_with_chemistry": None,
        }
        write_json(args.output / "metrics.json", blocked)
        print(json.dumps(blocked, indent=2))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
