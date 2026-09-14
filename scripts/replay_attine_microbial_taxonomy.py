"""Replay attine microbial taxonomy from the existing GBIF cache."""

import argparse
import hashlib
import json
from pathlib import Path

from src.common.cache import CachedHTTP
from src.common.io import read_jsonl, timestamp, write_json
from src.systems.microbial_taxonomy import (
    load_microbial_taxonomy_config,
    normalise_attine_microbes,
)


def file_sha256(path: Path) -> str:
    """Hash one complete replay input or output.

    Args:
        path: File to hash.

    Returns:
        Lowercase SHA-256 digest.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary_text(metrics: dict, input_hash: str) -> str:
    """Render the concise microbial taxonomy result.

    Args:
        metrics: Completed replay metrics.
        input_hash: SHA-256 of the retained records.

    Returns:
        Markdown summary.
    """
    genera = ", ".join(f"*{name}*" for name in metrics["resolved_genera"]) or "None"
    request_hashes = ", ".join(f"`{value}`" for value in metrics["taxonomy_request_hashes"])
    return "\n".join(
        [
            "# Attine microbial taxonomy replay",
            "",
            "The scoped microbial rule resolved all "
            f"{metrics['matched_observations']} retained attine records to {genera}. "
            f"There were {metrics['review_observations']} unresolved records.",
            "",
            "## Rule and evidence",
            "",
            "The replay required bacterial domain, exact genus rank, GBIF `EXACT` match type, "
            "and confidence at least 90. The cached response identifies domain `Bacteria`, "
            "kingdom `Bacillati`, family `Pseudonocardiaceae`, and confidence 93.",
            "",
            "The 90 threshold is scoped to this microbial control. Plant taxonomy and the "
            "primary pipeline retain their existing kingdom and confidence rules. The dated "
            "amendment records the rationale.",
            "",
            "## Offline boundary",
            "",
            f"- Input observations: {metrics['input_observations']}",
            f"- Resolved observations: {metrics['matched_observations']}",
            f"- Distinct accepted taxa: {metrics['resolved_taxa']}",
            f"- Resolved genera: {genera}",
            f"- External requests: {metrics['external_requests']}",
            f"- Cached request hash: {request_hashes}",
            f"- Retained-input SHA-256: `{input_hash}`",
            "",
            "Chemistry and bioactivity were not run. The original attine taxonomy and fixed "
            "positive-control recall artifacts were not changed.",
            "",
        ]
    )


def replay(root: Path, config_path: Path) -> dict:
    """Run and verify the isolated offline replay.

    Args:
        root: Repository root.
        config_path: Attine microbial taxonomy config.

    Returns:
        Verified replay manifest.
    """
    config = load_microbial_taxonomy_config(config_path)
    interim = root / "data/interim/systems/attine_actino"
    results = root / "results/systems/attine_actino/taxonomy_microbial"
    source = interim / "semantic_review/observations.jsonl"
    output = interim / "taxonomy_microbial"
    cache_path = interim / "cache/taxonomy"
    original_positive_control = root / "results/systems/attine_actino/positive_control.json"
    original_taxonomy_metrics = interim / "taxonomy/metrics.json"
    preserved_before = {
        "positive_control": file_sha256(original_positive_control),
        "original_taxonomy_metrics": file_sha256(original_taxonomy_metrics),
    }
    observations = read_jsonl(source)
    cache = CachedHTTP(cache_path, offline=True)
    try:
        metrics = normalise_attine_microbes(observations, cache, output, config)
    finally:
        cache.close()
    write_json(output / "metrics.json", metrics)
    if metrics["status"] != "complete":
        raise ValueError("Offline microbial taxonomy replay did not complete")
    if metrics["matched_observations"] != len(observations):
        raise ValueError("Offline microbial taxonomy replay did not resolve every input")
    preserved_after = {
        "positive_control": file_sha256(original_positive_control),
        "original_taxonomy_metrics": file_sha256(original_taxonomy_metrics),
    }
    if preserved_before != preserved_after:
        raise ValueError("Original attine artifacts changed during microbial taxonomy replay")
    summary = summary_text(metrics, file_sha256(source))
    results.mkdir(parents=True, exist_ok=True)
    (results / "summary.md").write_text(summary, encoding="utf-8")
    manifest = {
        "verified_at": timestamp(),
        "system": config.system_slug,
        "status": "complete",
        "analysis_freeze_commit": "98b5e09199a5eef0c46be452793e953f5a2af31e",
        "config_path": str(config_path.relative_to(root)),
        "config_sha256": file_sha256(config_path),
        "offline_replay_verified": True,
        "model_api_called": False,
        "gbif_api_called": False,
        "chemistry_run": False,
        "bioactivity_run": False,
        "input_path": str(source.relative_to(root)),
        "input_sha256": file_sha256(source),
        "output_path": str(output.relative_to(root)),
        "metrics": metrics,
        "preserved_artifact_sha256": preserved_after,
        "output_sha256": {
            "observations": file_sha256(output / "observations.jsonl"),
            "review": file_sha256(output / "review.jsonl"),
            "metrics": file_sha256(output / "metrics.json"),
        },
    }
    write_json(results / "verification.json", manifest)
    return manifest


def parser() -> argparse.ArgumentParser:
    """Build the replay command-line parser."""
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument(
        "--config",
        type=Path,
        default=Path("config/attine_actino_taxonomy_microbial.json"),
    )
    return value


def main() -> None:
    """Run the command-line replay."""
    args = parser().parse_args()
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    print(json.dumps(replay(root, config_path), indent=2))


if __name__ == "__main__":
    main()
