"""Measure a separate grounding development run against the saved baseline."""

import argparse
import json
from pathlib import Path

from src.common.io import timestamp, write_json
from src.evaluation.comparison import build_comparison, render_comparison


def main() -> None:
    """Write a count-only comparison without changing baseline or extraction artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("results/grounding_development_v1"))
    parser.add_argument("--adjudication", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = build_comparison(args.extraction, root, args.adjudication)
    report["generated_at"] = timestamp()
    write_json(args.output / "compare.json", report)
    (args.output / "compare.md").write_text(render_comparison(report), encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "output": str(args.output),
        "blocked_reason": report["blocked_reason"],
        "groups": report["development"]["groups"],
    }, indent=2))


if __name__ == "__main__":
    main()
