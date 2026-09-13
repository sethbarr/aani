"""Retrieve the open-access behavioural literature pilot."""

import argparse
import json
from pathlib import Path

from src.common.cache import CachedHTTP
from src.corpus.europepmc import QUERY, retrieve


def main() -> None:
    """Parse corpus options and run retrieval."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--query", default=QUERY)
    parser.add_argument("--output", type=Path, default=Path("data/interim/corpus"))
    parser.add_argument("--cache", type=Path, default=Path("data/raw"))
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    cache = CachedHTTP(args.cache, args.offline)
    try:
        print(json.dumps(retrieve(cache, args.output, args.limit, args.query), indent=2))
    finally:
        cache.close()


if __name__ == "__main__":
    main()
