"""Retrieve taxonomy and classification anchors for exploratory coverage."""

import argparse
import json
from pathlib import Path

from src.any_fungus_coverage.retrieve import write_json
from src.any_fungus_coverage.taxonomy import resolve_assays, resolve_one


def main() -> None:
    """Resolve declared anchors or the complete retrieved assay inventory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchors", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    root = Path("data/interim/any_fungus_coverage")
    if not args.anchors:
        resolve_assays(root, args.offline)
        return
    names = json.loads((root / "anchor_names.json").read_text())
    overrides = json.loads((root / "anchor_overrides.json").read_text())
    results = {}
    for name in sorted({n for group in names.values() for n in group}):
        override = overrides.get(name)
        kind, value = ("id", override["tax_id"]) if override else ("name", name)
        key, result = resolve_one((kind, value, root, args.offline))
        if override:
            result["anchor_disambiguation"] = override
        results[name] = result
        print(name, result["status"], result.get("tax_id"), flush=True)
    if args.offline:
        assert results == json.loads((root / "anchors.json").read_text())
    else:
        write_json(root / "anchors.json", results)


if __name__ == "__main__":
    main()
