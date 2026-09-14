"""Run isolated exploratory-system stages through explicit approval boundaries."""

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from src.common.cache import CachedHTTP
from src.common.environment import load_local_environment
from src.common.io import digest, read_json, read_jsonl, timestamp, write_json
from src.extraction.gemini import DEFAULT_MODEL
from src.systems.config import load_system_config, system_paths
from src.systems.extraction import export_system_jobs, make_system_jobs, run_system_extraction

AMENDMENT_COMMIT = "495b25d"
CONFIG_COMMIT = "bf3923f"


def extract(config_path: Path, root: Path, offline: bool = False) -> dict:
    """Execute an approved, immutable selection with the current Gemini settings."""
    config = load_system_config(config_path)
    paths = system_paths(config, root)
    approval = read_json(paths["results"] / "payload_approval.json")
    if approval.get("approved") is not True:
        raise ValueError("System payload export approval is required")
    index = read_json(paths["interim"] / "extraction_payloads/index.json")
    selection_path = paths["interim"] / "execution_selection.json"
    if selection_path.exists():
        index = read_json(selection_path)
    jobs = []
    for item in index["jobs"]:
        path = paths["interim"] / item.get("path", f"extraction_payloads/{item['input_hash']}.json")
        assert_isolated(path, paths["interim"])
        job = read_json(path)
        if (
            digest({key: value for key, value in job.items() if key != "input_hash"})
            != job["input_hash"]
        ):
            raise ValueError("Extraction payload hash mismatch")
        if job["system_slug"] != config.slug:
            raise ValueError("Cross-system extraction payload")
        jobs.append(job)
    if len(jobs) > config.extraction_job_limit:
        raise ValueError("Extraction job cap exceeded")
    if approval["input_hashes"] != [job["input_hash"] for job in jobs]:
        raise ValueError("Approval does not cover the execution selection")
    priority = read_json(root / "results/grounding_development_v2/run_status.json")
    if priority.get("status") != "complete" and not offline:
        raise ValueError("Saverschek v2 has priority over exploratory extraction")
    load_local_environment(root / ".env")
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    if model != "gemini-3.8-flash":
        raise ValueError("Model differs from the primary default extractor")
    corpus = read_jsonl(paths["interim"] / "corpus/manifest.jsonl")
    started = min(datetime.fromisoformat(row["retrieved_at"]) for row in corpus)
    deadline = started + timedelta(hours=config.time_limit_hours)
    output = paths["interim"] / ("offline_replay/extraction" if offline else "extraction")
    config_values = read_json(root / "config/analysis.json")
    execution = {
        "started_at": timestamp(),
        "deadline": deadline.isoformat(),
        "offline": offline,
        "jobs": len(jobs),
        "input_hashes": [job["input_hash"] for job in jobs],
        "provider": "gemini",
        "model": model,
        "grounding_version": config.extraction_grounding,
        "prompt_schema_comparability": "system_adapted; differs_from_leafcutter_default_contract",
        "saverschek_v2_priority_status": priority["status"],
    }
    write_json(output / "run_manifest.json", execution)
    cache = CachedHTTP(
        paths["interim"] / "cache", offline, client=httpx.Client(timeout=180, follow_redirects=True)
    )
    try:
        metrics = run_system_extraction(
            config,
            jobs,
            cache,
            output,
            model=model,
            minimum_confidence=config_values["extraction_confidence"],
            deadline=None if offline else deadline,
        )
    finally:
        cache.close()
    write_json(
        output / "run_manifest.json", {**execution, "completed_at": timestamp(), "metrics": metrics}
    )
    return metrics


def assert_isolated(path: Path, allowed_root: Path) -> None:
    """Reject output paths outside the selected system root."""
    resolved = path.resolve()
    root = allowed_root.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path is outside the system isolation root: {resolved}")


def prepare_controls(config_path: Path, root: Path) -> dict:
    """Prioritize both fixed attine references within the existing job budget."""
    config = load_system_config(config_path)
    if config.slug != "attine_actino":
        raise ValueError("Reference controls are configured only for attine_actino")
    paths = system_paths(config, root)
    references = paths["interim"] / "reference_sources"
    jobs, metrics = make_system_jobs(
        config, references / "corpus", references / "screening.json"
    )
    export_system_jobs(jobs, references / "extraction_payloads", metrics)
    selected = [{
        **{key: job[key] for key in ("input_hash", "source_id", "chunk_index", "chunk_count")},
        "path": f"reference_sources/extraction_payloads/{job['input_hash']}.json",
        "cohort": "reference_control",
    } for job in jobs]
    discovery = read_json(paths["interim"] / "extraction_payloads/index.json")
    groups: dict[str, list[dict]] = {}
    for job in discovery["jobs"]:
        groups.setdefault(job["source_id"], []).append(job)
    excluded = []
    for source, group in groups.items():
        if len(selected) + len(group) <= config.extraction_job_limit:
            selected.extend({**job, "cohort": "discovery"} for job in group)
        else:
            excluded.append(source)
    selection = {
        "prepared_at": timestamp(), "system": config.slug, "jobs": selected,
        "reason": "Expose both fixed reference items before other complete-source jobs.",
        "discovery_sources_retrieved": 20, "additional_reference_sources": 2,
        "deviation": "Two reference supplements exceed the 20-source discovery cap in total source availability.",
        "discovery_sources_displaced": excluded,
        "original_payloads_preserved": True,
    }
    write_json(paths["interim"] / "execution_selection.json", selection)
    return selection


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
    value.add_argument("--offline", action="store_true")
    value.add_argument(
        "stage", choices=("prepare", "prepare-controls", "extract", "downstream", "verify")
    )
    return value


def main() -> None:
    """Run one explicitly selected system stage."""
    args = parser().parse_args()
    if args.stage == "prepare":
        print(json.dumps(prepare(args.config, args.root), indent=2))
    elif args.stage == "prepare-controls":
        print(json.dumps(prepare_controls(args.config, args.root), indent=2))
    elif args.stage == "extract":
        print(json.dumps(extract(args.config, args.root, args.offline), indent=2))
    elif args.stage == "downstream":
        from src.systems.downstream import run_system_downstream

        print(json.dumps(run_system_downstream(args.config, args.root, args.offline), indent=2))
    elif args.stage == "verify":
        from src.systems.verification import verify_system

        config = load_system_config(args.config)
        print(json.dumps(verify_system(config.slug, args.root), indent=2))


if __name__ == "__main__":
    main()
