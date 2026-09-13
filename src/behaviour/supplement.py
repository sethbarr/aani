"""Validate explicit taxonomy supplements against original curator records."""

import hashlib
from pathlib import Path

from src.common.io import read_json, read_jsonl

TAXONOMY_FIELDS = {
    "usage_key", "accepted_usage_key", "accepted_name", "genus", "family",
    "checklist_key", "taxonomy_confidence", "taxonomy_request_hash",
    "taxonomy_query_name", "taxonomy_query_rank", "taxonomy_status", "name_resolution",
}


def checked_artifact(root: Path, descriptor: dict) -> Path:
    """Verify a supplement input against its recorded hash.

    Args:
        root: Repository root.
        descriptor: Repository-relative path and SHA-256.

    Returns:
        Verified absolute path.

    Raises:
        ValueError: An input escaped the repository or changed.
    """
    path = (root / descriptor["path"]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Taxonomy supplement input is outside the repository")
    if hashlib.sha256(path.read_bytes()).hexdigest() != descriptor["sha256"]:
        raise ValueError(f"Taxonomy supplement input changed: {path}")
    return path


def load_supplement(root: Path, manifest_path: Path, existing: list[dict]) -> tuple[list[dict], list[dict]]:
    """Load taxonomy-only additions while preserving every original context.

    Args:
        root: Repository root.
        manifest_path: Explicit supplement manifest.
        existing: Already included observation records.

    Returns:
        Additional observations and verified input descriptors.

    Raises:
        ValueError: A supplement changes evidence, omits contexts or duplicates input.
    """
    manifest = read_json(manifest_path)
    if manifest.get("schema_version") != 1 or manifest.get("status") != "complete":
        raise ValueError("Taxonomy supplement manifest is incomplete")
    descriptors = [manifest["original_observations"], manifest["observations"],
                   manifest["amendment"], *manifest["provenance"]]
    paths = [checked_artifact(root, item) for item in descriptors]
    originals = {row["record_id"]: row for row in read_jsonl(paths[0])
                 if row["source_id"] == manifest["source_id"]
                 and row["plant_name_as_written"] == manifest["plant_name_as_written"]}
    additions = read_jsonl(paths[1])
    ids = [row["record_id"] for row in additions]
    if not originals or set(ids) != set(originals) or len(ids) != len(set(ids)):
        raise ValueError("Taxonomy supplement must preserve every original directional context once")
    existing_ids = {row["record_id"] for row in existing}
    if existing_ids.intersection(ids):
        raise ValueError("Taxonomy supplement duplicates existing observations")
    for row in additions:
        original = originals[row["record_id"]]
        original_evidence = {key: value for key, value in original.items() if key not in TAXONOMY_FIELDS}
        supplied_evidence = {key: value for key, value in row.items() if key not in TAXONOMY_FIELDS}
        if supplied_evidence != original_evidence:
            raise ValueError(f"Taxonomy supplement changed original evidence: {row['record_id']}")
        if row["accepted_name"] != manifest["accepted_name"]:
            raise ValueError("Taxonomy supplement accepted name differs from decision")
        if row["name_resolution"] != manifest["name_resolution"]:
            raise ValueError("Taxonomy supplement name-resolution provenance differs")
    relative = str(manifest_path.resolve().relative_to(root.resolve()))
    return [{**row, "merge_input_path": manifest["observations"]["path"],
             "taxonomy_supplement_manifest": relative} for row in additions], descriptors
