"""Run the isolated exploratory any-fungus coverage analysis."""

import argparse
from pathlib import Path

from src.any_fungus_coverage.retrieve import retrieve


def main() -> None:
    """Select live retrieval or strict offline replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    retrieve(Path("data/interim/any_fungus_coverage"), args.offline)


if __name__ == "__main__":
    main()
