"""Score the bounded glyph rerun and optional independent v2 repeat sample."""

import argparse
import json
from pathlib import Path

from src.common.io import timestamp, write_json
from src.evaluation.glyph_comparison import (
    V3_EXTRACTION,
    build_glyph_comparison,
    render_glyph_summary,
)


def main() -> None:
    """Write new comparison artifacts while preserving all earlier run outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, default=V3_EXTRACTION)
    parser.add_argument("--repeat", type=Path)
    parser.add_argument("--output", type=Path, default=Path("results/grounding_development_v3"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = build_glyph_comparison(args.extraction, root, args.repeat)
    report["generated_at"] = timestamp()
    write_json(args.output / "compare.json", report)
    (args.output / "compare.md").write_text(render_glyph_summary(report), encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "output": str(args.output),
        "blocked_reason": report["blocked_reason"], "groups": report["v3"]["groups"],
        "glyph_recovery_count": report["glyph_recoveries"]["count"],
        "repeat_status": report["repeat_sample"]["status"],
        "failure_reasons": report["v3"]["failure_reasons"],
    }, indent=2))


if __name__ == "__main__":
    main()
