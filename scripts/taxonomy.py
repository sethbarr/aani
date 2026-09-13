"""Resolve extracted plants to accepted taxa."""

import argparse
import json
from pathlib import Path

from src.common.cache import CachedHTTP
from src.common.io import digest, read_json, read_jsonl, write_json, write_jsonl
from src.taxonomy.gbif import normalise
from src.taxonomy.names import apply_name_mappings


def main() -> None:
    """Run the taxonomy stage and write unmatched-name review records."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--observations", type=Path, default=Path("data/interim/extraction/observations.jsonl")
    )
    parser.add_argument("--output", type=Path, default=Path("data/interim/taxonomy"))
    parser.add_argument("--cache", type=Path, default=Path("data/raw"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--name-map", type=Path)
    parser.add_argument("--corpus", type=Path, default=Path("data/interim/corpus"))
    args = parser.parse_args()
    observations = read_jsonl(args.observations)
    input_hash = digest(observations)
    if args.name_map:
        observations = apply_name_mappings(observations, read_json(args.name_map), args.corpus)
    write_jsonl(args.output / "input_observations.jsonl", observations)
    write_json(
        args.output / "run_manifest.json",
        {
            "input": str(args.observations),
            "input_hash": input_hash,
            "name_map": str(args.name_map) if args.name_map else None,
            "name_map_hash": digest(read_json(args.name_map)) if args.name_map else None,
            "prepared_input_hash": digest(observations),
            "offline": args.offline,
        },
    )
    cache = CachedHTTP(args.cache, args.offline)
    try:
        config = read_json(Path("config/analysis.json"))
        metrics = normalise(observations, cache, args.output, config["taxonomy_confidence"])
        write_json(args.output / "metrics.json", metrics)
        print(json.dumps(metrics, indent=2))
    finally:
        cache.close()


if __name__ == "__main__":
    main()
