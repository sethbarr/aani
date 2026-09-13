"""Simulate the generated water demonstration in an isolated Opentrons environment."""

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    """Record a simulation result tied to the exact protocol bytes; never connect a robot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path("results/experiment_planner"))
    args = parser.parse_args()
    protocol_path = args.bundle / "opentrons_water_demo.py"
    plan = json.loads((args.bundle / "experiment_plan.json").read_text())
    report_path = args.bundle / "simulation_report.json"
    report = {
        "status": "running", "scope": "water_only_layout_demo", "plan_id": plan["plan_id"],
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "checked_at": datetime.now(UTC).isoformat(), "biological_assay_validated": False,
        "robot_connected": False,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    try:
        with TemporaryDirectory(prefix="fungal-opentrons-config-") as config_dir:
            os.environ["OT_API_CONFIG_DIR"] = config_dir
            from opentrons.simulate import format_runlog, simulate

            report["opentrons_version"] = version("opentrons")
            with protocol_path.open() as protocol_file:
                runlog, _ = simulate(protocol_file, file_name=protocol_path.name)
            (args.bundle / "simulation_runlog.txt").write_text(format_runlog(runlog) + "\n")
            messages = [entry["payload"]["text"] for entry in runlog]
            report["logged_commands"] = len(runlog)
            report["dispense_commands"] = sum(text.startswith("Dispensing") for text in messages)
            report["status"] = "passed"
            report["runlog"] = "simulation_runlog.txt"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        from src.experiments.render import render_viewer

        render_viewer(plan, args.bundle)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
