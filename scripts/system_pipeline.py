"""Run isolated exploratory-system stages through explicit approval boundaries."""

import argparse
import json
from pathlib import Path

from src.common.io import digest, read_json, timestamp, write_json
from src.systems.config import load_system_config, system_paths
from src.systems.extraction import export_system_jobs, make_system_jobs

AMENDMENT_COMMIT = "495b25d"
CONFIG_COMMIT = "bf3923f"


def assert_isolated(path: Path, allowed_root: Path) -> None:
    """Reject output paths outside the selected system root."""
    resolved = path.resolve()
    root = allowed_root.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path is outside the system isolation root: {resolved}")


def prepare(config_path: Path, root: Path) -> dict:
    """Prepare capped local model payloads and stop at the approval gate."""
    config = load_system_config(config_path)
    paths = system_paths(config, root)
    corpus = paths["interim"] / "corpus"
    screening = paths["interim"] / "screening.json"
    destination = paths["interim"] / "extraction_payloads"
    assert_isolated(corpus, paths["interim"])
    assert_isolated(screening, paths["interim"])
    assert_isolated(destination, paths["interim"])
    jobs, metrics = make_system_jobs(config, corpus, screening)
    export_system_jobs(jobs, destination, metrics)
    gate = {
        "system": config.slug,
        "status": "awaiting_payload_export_approval",
        "external_payload_sent": False,
        "prepared_at": timestamp(),
        "amendment_commit": AMENDMENT_COMMIT,
        "config_commit": CONFIG_COMMIT,
        "config_path": str(config_path),
        "config_hash": digest(read_json(config_path)),
        "corpus_path": str(corpus),
        "screening_path": str(screening),
        "payload_path": str(destination),
        **metrics,
    }
    write_json(paths["results"] / "payload_approval_gate.json", gate)
    return gate


def parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--config", type=Path, required=True)
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument("stage", choices=("prepare",))
    return value


def main() -> None:
    """Run one explicitly selected system stage."""
    args = parser().parse_args()
    if args.stage == "prepare":
        print(json.dumps(prepare(args.config, args.root), indent=2))


if __name__ == "__main__":
    main()
