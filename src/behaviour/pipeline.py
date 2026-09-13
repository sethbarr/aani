"""Assemble existing taxonomy outputs with explicitly superseding source audits."""

import base64
import csv
import hashlib
import json
import shlex
from collections import Counter
from pathlib import Path

from src.behaviour.aggregation import aggregate, deduplicate, verify_miconia
from src.behaviour.supplement import load_supplement
from src.common.io import normalise_space, read_json, read_jsonl, write_json, write_jsonl
from src.taxonomy.gbif import interpret_match

PROTOCOL_COMMIT = "98b5e09199a5eef0c46be452793e953f5a2af31e"
TAXONOMY_INPUTS = [
    "data/interim/taxonomy_pilot/observations.jsonl",
    "data/interim/taxonomy_recovered/observations.jsonl",
    "data/interim/taxonomy_saverschek/observations.jsonl",
]
AUDIT_DIRECTORY = "results/saverschek_audit"
SOURCE_PATHS = {
    "PMC11543716": "data/interim/corpus/texts/PMC11543716.json",
    "PMC5710599": "data/interim/pending_evidence_review/corpus/texts/PMC5710599.json",
    "PMC3140513": "data/interim/pending_evidence_review/corpus/texts/PMC3140513.json",
    "PMC9965205": "data/interim/corpus/texts/PMC9965205.json",
    "SAVERSCHEK2010": "data/interim/corpus_targeted_saverschek/texts/SAVERSCHEK2010.json",
}


def file_manifest(path: Path, root: Path) -> dict:
    """Identify a file by repository-relative path and byte-level SHA-256."""
    return {"path": str(path.relative_to(root)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def validate_grounding(row: dict, source: dict, anchors: dict) -> None:
    """Recheck quoted names and all linked audit anchors against cached source text."""
    blocks = {block["block_id"]: block["text"] for block in source["blocks"]}
    quote = normalise_space(row["evidence_quote"])
    if not quote or quote not in normalise_space(blocks[row["block_id"]]):
        raise ValueError(f"Ungrounded quote: {row['record_id']}")
    if normalise_space(row["plant_name_as_written"]).casefold() not in quote.casefold():
        raise ValueError(f"Plant name absent from quote: {row['record_id']}")
    for anchor_id in row.get("evidence_anchor_ids", []):
        anchor = anchors[anchor_id]
        if normalise_space(anchor["evidence_quote"]) not in normalise_space(
            blocks[anchor["block_id"]]
        ):
            raise ValueError(f"Ungrounded supporting anchor: {anchor_id}")


def validate_taxonomy(row: dict, cache_root: Path, threshold: int) -> Path:
    """Reinterpret the cached GBIF response without making any network request."""
    path = cache_root / "http" / f"{row['taxonomy_request_hash']}.json"
    cached = read_json(path)
    response = cached["attempts"][-1]
    if response["status"] != 200:
        raise ValueError(f"Taxonomy cache is not successful: {path}")
    payload = json.loads(base64.b64decode(response["body_base64"]))
    rank = cached["request"]["params"]["taxonRank"].lower()
    matched, reason = interpret_match(payload, rank, threshold)
    if matched is None:
        raise ValueError(f"Ineligible taxonomy match: {row['record_id']}: {reason}")
    for key, value in matched.items():
        if row[key] != value:
            raise ValueError(f"Taxonomy field differs from cache: {row['record_id']}: {key}")
    return path


def write_csv(path: Path, rows: list[dict], fallback_columns: list[str]) -> None:
    """Write stable CSV headers and serialize structured cells as JSON."""
    columns = list(dict.fromkeys(key for row in rows for key in row)) or fallback_columns
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: json.dumps(value, ensure_ascii=False)
                          if isinstance(value, (dict, list)) else value
                          for key, value in row.items()} for row in rows)


def load_inputs(root: Path, taxonomy_supplements: list[Path] | None = None) -> tuple[list[dict], list[dict], list[dict], dict]:
    """Read all three requested inputs and replace coarse Saverschek evidence explicitly."""
    baseline = []
    inputs = []
    counts = {}
    for relative in TAXONOMY_INPUTS:
        path = root / relative
        records = read_jsonl(path)
        baseline.extend({**row, "merge_input_path": relative} for row in records)
        inputs.append(file_manifest(path, root))
        counts[relative] = len(records)
    audit_path = root / AUDIT_DIRECTORY / "taxonomy_matched_directional.jsonl"
    audit = read_jsonl(audit_path)
    manifest_path = root / AUDIT_DIRECTORY / "manifest.json"
    manifest = read_json(manifest_path)
    inputs.extend([file_manifest(audit_path, root), file_manifest(manifest_path, root)])
    advertised = next(row["sha256"] for row in manifest["artifacts"]
                      if row["path"] == str(audit_path.relative_to(root)))
    if advertised != file_manifest(audit_path, root)["sha256"]:
        raise ValueError("Saverschek curated artifact differs from its audit manifest")
    if not audit or any(row["source_id"] != "SAVERSCHEK2010" for row in audit):
        raise ValueError("Saverschek replacement audit is empty or contains another source")
    superseded = [row for row in baseline if row["source_id"] == "SAVERSCHEK2010"]
    preserved = [row for row in baseline if row["source_id"] != "SAVERSCHEK2010"]
    replacements = []
    for old in superseded:
        same_taxon = [row for row in audit if row["accepted_usage_key"]
                      == old["accepted_usage_key"]]
        if not same_taxon:
            raise ValueError(f"Superseded taxon has no audited replacement: {old['record_id']}")
        replacements.append({
            "superseded_record_id": old["record_id"], "source_id": old["source_id"],
            "genus": old["genus"], "old_direction": old["outcome"],
            "replacement_record_ids": [row["record_id"] for row in same_taxon],
            "replacement_directions": sorted({row["outcome"] for row in same_taxon}),
            "reason": "coarse_model_summary_replaced_by_complete_source_context_audit",
        })
    combined = preserved + [{**row, "merge_input_path": str(audit_path.relative_to(root))}
                            for row in audit]
    supplement_records = 0
    for supplied in taxonomy_supplements or []:
        path = supplied if supplied.is_absolute() else root / supplied
        additions, descriptors = load_supplement(root, path, combined)
        combined.extend(additions)
        inputs.extend([file_manifest(path, root), *descriptors])
        supplement_records += len(additions)
    lineage = {
        "baseline_input_counts": counts, "baseline_taxonomy_records": len(baseline),
        "superseded_model_records": len(superseded),
        "preserved_model_records": sum(row.get("provider") == "gemini" for row in preserved),
        "preserved_manually_recovered_records": sum(
            row.get("provider") != "gemini" for row in preserved
        ),
        "curated_context_records": len(audit) + supplement_records,
        "taxonomy_supplement_context_records": supplement_records,
        "taxonomy_supplement_manifests": [str(path) for path in taxonomy_supplements or []],
        "records_after_replacement_before_deduplication": len(combined),
        "replacement_policy": (
            "Read all three requested taxonomy outputs. Replace every SAVERSCHEK2010 "
            "coarse model record with the completed audit's taxonomy-matched directional "
            "contexts, retaining all opposite directions. Do not append both representations. "
            "Explicit taxonomy supplements add all supported contexts for reviewed taxa, "
            "preserving original source evidence and directions. Curated contexts have "
            "separate denominators from model candidates."
        ),
    }
    return combined, replacements, inputs, lineage


def run_merge(root: Path, output: Path, taxonomy_supplements: list[Path] | None = None) -> dict:
    """Verify immutable inputs, merge local evidence and write reproducible aggregation."""
    rows, replacements, inputs, lineage = load_inputs(root, taxonomy_supplements)
    anchors_path = root / AUDIT_DIRECTORY / "evidence_anchors.json"
    anchors = read_json(anchors_path)
    config_path = root / "config/analysis.json"
    threshold = read_json(config_path)["taxonomy_confidence"]
    sources = {source: read_json(root / path) for source, path in SOURCE_PATHS.items()}
    paths = {root / path for path in SOURCE_PATHS.values()}
    paths.update({anchors_path, config_path, root / "docs/analysis_plan.md"})
    for row in rows:
        validate_grounding(row, sources[row["source_id"]], anchors)
        paths.add(validate_taxonomy(row, root / "data/raw", threshold))
    inputs.extend(file_manifest(path, root) for path in sorted(paths))
    observations, duplicates = deduplicate(rows)
    genera, conflicts, review = aggregate(observations)
    miconia = verify_miconia(observations, conflicts)
    if not miconia["verified"]:
        raise ValueError("Required Miconia source/species/direction conflict did not verify")
    all_genera = sorted(genera + conflicts, key=genus_order)
    conflict_names = {row["genus"] for row in conflicts}
    conflict_observations = [row for row in observations if row["genus"] in conflict_names]
    primary_observations = [row for row in observations if row["genus"] not in conflict_names]
    status_counts = Counter(row["outcome"] for row in all_genera)
    metrics = {
        "status": "complete", "blocked_reason": None, **lineage,
        "grounding_and_cached_taxonomy_reverified_records": len(rows),
        "deduplicated_observations": len(observations),
        "identical_grounded_duplicates_removed": len(duplicates),
        "semantically_retained_model_records_in_current_merge": lineage["preserved_model_records"],
        "manually_recovered_records_in_current_merge": (
            lineage["preserved_manually_recovered_records"] + lineage["curated_context_records"]
        ),
        "resolved_accepted_species": len({row["accepted_name"] for row in observations}),
        "unique_names_as_written": len({row["plant_name_as_written"] for row in observations}),
        "source_count": len({row["source_id"] for row in observations}),
        "ant_species_count": len({row["ant_species"] for row in observations}),
        "genera_before_conflict_exclusion": len(all_genera),
        "genera_after_aggregation": len(genera),
        "accepted_genera": status_counts["accepted"],
        "rejected_genera": status_counts["rejected"],
        "conflict_genera": len(conflicts),
        "conflict_observations": len(conflict_observations),
        "primary_eligible_observations": len(primary_observations),
        "eligibility_review_observations": len(review),
        "miconia_conflict_verified": miconia["verified"],
        "observation_count_interpretation": "grounded_contexts_not_independent_replicates",
        "network_requests": 0,
    }
    for name, records in [
        ("observations", observations), ("primary_observations", primary_observations),
        ("genera", genera), ("all_genera", all_genera), ("conflicts", conflicts),
        ("conflict_genera", conflicts),
        ("conflict_observations", conflict_observations), ("review", review),
        ("duplicates", duplicates), ("superseded_records", replacements),
    ]:
        write_jsonl(output / f"{name}.jsonl", records)
        write_csv(output / f"{name}.csv", records, ["record_id", "genus", "reason"])
    write_json(output / "miconia_verification.json", miconia)
    write_json(output / "metrics.json", metrics)
    write_json(output / "run_manifest.json", {
        "schema_version": 1, "protocol_commit": PROTOCOL_COMMIT,
        "stage": "behaviour", "network_required": False,
        "replay": ".venv/bin/python -m scripts.behaviour --offline" + "".join(
            f" --taxonomy-supplement {shlex.quote(str(path))}"
            for path in taxonomy_supplements or []
        ),
        "inputs": inputs, "replacement_policy": lineage["replacement_policy"],
        "deduplication": (
            "Whitespace-normalized source, genus, direction, quote, ant and actual experimental "
            "context; different habitats, test days and designs remain distinct."
        ),
        "limitations": [
            "Curated context totals are not model records or independent biological replicates.",
            "Saverschek original PDF graphics and numerical transcriptions remain unverified.",
            "Only the completed audit's supported, exact-taxonomy directional contexts enter.",
        ],
    })
    return metrics


def genus_order(row: dict) -> str:
    """Sort genus summary rows deterministically."""
    return row["genus"]
