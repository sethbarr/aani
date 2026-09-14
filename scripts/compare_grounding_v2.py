"""Score the source-identity rerun with the frozen baseline's structured convention."""

import argparse
import json
from pathlib import Path

from src.common.io import timestamp, write_json
from src.evaluation.identity_comparison import (
    V2_EXTRACTION,
    build_identity_comparison,
    render_identity_summary,
)


def main() -> None:
    """Write separate comparison artifacts while preserving every original run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, default=V2_EXTRACTION)
    parser.add_argument("--output", type=Path, default=Path("results/grounding_development_v2"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = build_identity_comparison(args.extraction, root)
    report["generated_at"] = timestamp()
    write_json(args.output / "compare.json", report)
    (args.output / "compare.md").write_text(render_identity_summary(report), encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "output": str(args.output),
        "blocked_reason": report["blocked_reason"], "primary_change": report["primary_change"],
        "groups": report["v2"]["groups"], "failure_reasons": report["v2"]["failure_reasons"],
    }, indent=2))


if __name__ == "__main__":
    main()
