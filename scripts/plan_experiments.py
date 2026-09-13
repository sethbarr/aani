"""Create an evidence-linked fungal experiment plan and local partner handoffs."""

import argparse
import json
from pathlib import Path

from src.experiments.planner import build_plan, export_plan


def main() -> None:
    """Generate prospective planning artifacts without running or submitting experiments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path(
        "research/attine_selection_2026-09-12/compound_assays_from_fulltexts.json"))
    parser.add_argument("--config", type=Path, default=Path("config/experiment_panel.json"))
    parser.add_argument("--records", nargs="+", help="Representative assay record IDs")
    parser.add_argument("--fungi", nargs="+", help="Fungus IDs from the panel configuration")
    parser.add_argument("--output", type=Path, default=Path("results/experiment_planner"))
    args = parser.parse_args()
    plan = build_plan(json.loads(args.evidence.read_text()), json.loads(args.config.read_text()),
                      args.records, args.fungi)
    export_plan(plan, args.output)
    print(f"Draft {plan['plan_id']}: {len(plan['candidates'])} materials × "
          f"{len(plan['fungi'])} fungi; {len(plan['layout'])} illustrative occupied wells.")
    print(f"Open {args.output.resolve() / 'index.html'}")


if __name__ == "__main__":
    main()
