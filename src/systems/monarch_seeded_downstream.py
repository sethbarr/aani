"""Run isolated seeded-monarch coverage with explicit infection-group provenance."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from src.chemistry.export_cache import file_hash
from src.common.io import read_jsonl, timestamp, write_json, write_jsonl
from src.systems.config import SystemConfig, load_system_config
from src.systems.downstream import (
    COMPLETE_STATUSES,
    bounded_stage,
    build_genus_coverage,
    build_system_funnel,
    eligible_genus_rows,
    isolated_path,
    materialize_lotus_cache,
    run_assay_scope_check,
    run_system_bioactivity,
    run_system_chemistry,
    run_system_taxonomy,
    unavailable_stage,
)

INFECTION_STATUSES = {"infected", "uninfected", "unreported"}
STAGE_COUNTS = {
    "taxonomy": ["matched_observations", "review_observations", "resolved_taxa"],
    "behaviour": ["resolved_observations", "eligible_genera", "conflict_genera"],
    "chemistry": ["unique_occurrences", "unique_compounds", "genera_with_chemistry"],
    "assay_scope": ["primary_fungal_assays", "parasite_assays_all_types"],
    "bioactivity": [
        "compounds", "matched_compounds", "active", "inactive", "unknown",
        "classified_compounds", "genera_with_classified_compounds",
    ],
}


def seeded_paths(root: Path, offline: bool = False) -> dict[str, Path]:
    """Resolve artifact roots and reject redirects into an earlier system run.

    Args:
        root: Repository root.
        offline: Write replay outputs below the seeded replay directories.

    Returns:
        Isolated input, output, cache, and original read-only configuration paths.
    """
    root = root.resolve()
    live = root / "data/interim/systems/monarch_seeded"
    results = root / "results/systems/monarch_seeded"
    for path in (live, results):
        if path.resolve() != path:
            raise ValueError(f"Seeded artifact root cannot be redirected: {path}")
    interim = live / "offline_replay" if offline else live
    output = results / "offline_replay" if offline else results
    return {
        "root": root,
        "live": live,
        "interim": isolated_path(interim, live),
        "results": isolated_path(output, results),
        "cache": isolated_path(live / "cache", live),
        "reviewed": isolated_path(live / "semantic_review/observations.jsonl", live),
        "config": root / "config/systems/monarch.json",
        "assay_config": root / "config/analysis.json",
    }


def validate_semantic_input(path: Path) -> dict:
    """Require reviewed records and an explicit choosing-female infection status.

    Args:
        path: Seeded semantic-inclusion JSON Lines file.

    Returns:
        Counts of retained records and their recorded infection groups.

    Raises:
        ValueError: Input is empty, invalid, or claims focal status without infection evidence.
    """
    rows = read_jsonl(path)
    if not rows:
        raise ValueError("no_reviewed_model_records_available")
    identifiers = [row["record_id"] for row in rows]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate_semantic_record_ids")
    for row in rows:
        if row.get("semantic_decision") != "include":
            raise ValueError("semantic_inclusion_required")
        if row.get("infection_status") not in INFECTION_STATUSES:
            raise ValueError("choosing_female_infection_status_required")
        if row["infection_status"] == "unreported" and (
            row.get("focal_eligible") is True
            or row.get("infection_comparison_eligible") is True
        ):
            raise ValueError("unreported_infection_cannot_satisfy_focal_design")
    return {
        "status": "complete", "records": len(rows),
        "infection_status_counts": dict(sorted(Counter(
            row["infection_status"] for row in rows
        ).items())),
        "unreported_infection_records": sum(
            row["infection_status"] == "unreported" for row in rows
        ),
        "record_origin_counts": dict(sorted(Counter(
            row.get("record_origin", "unreported") for row in rows
        ).items())),
        "input_sha256": file_hash(path),
    }


def infection_group_metadata(rows: list[dict]) -> dict:
    """Keep infection groups, source records, and treatment contexts in genus outputs."""
    groups = []
    for status in sorted({row["infection_status"] for row in rows}):
        selected = [row for row in rows if row["infection_status"] == status]
        groups.append({
            "infection_status": status,
            "record_ids": sorted(row["record_id"] for row in selected),
            "directions": sorted({row["direction"] for row in selected}),
            "source_ids": sorted({row["source_id"] for row in selected}),
            "experiment_ids": sorted({row["experiment_id"] for row in selected
                                      if row.get("experiment_id")}),
            "record_origin_counts": dict(sorted(Counter(
                row.get("record_origin", "unreported") for row in selected
            ).items())),
            "model_record_ids": sorted(row["record_id"] for row in selected
                                       if row.get("record_origin") == "model_record"),
            "curator_context_record_ids": sorted(
                row["record_id"] for row in selected
                if row.get("record_origin") == "curator_context_expansion"
            ),
            "study_contexts": sorted({row.get("study_context", "") for row in selected}),
            "treatment_contexts": sorted({row["treatment_context"] for row in selected
                                          if row.get("treatment_context")}),
            "focal_eligible_records": sum(row.get("focal_eligible") is True
                                           for row in selected),
            "infection_comparison_eligible_records": sum(
                row.get("infection_comparison_eligible") is True for row in selected
            ),
        })
    return {
        "infection_status_groups": groups,
        "infection_statuses": [group["infection_status"] for group in groups],
        "unreported_infection_records": sum(
            row["infection_status"] == "unreported" for row in rows
        ),
        "infection_group_policy": (
            "Infection groups remain distinct. Existing genus-level direction unanimity "
            "is applied across groups; conflicted genera are excluded from chemistry."
        ),
    }


def build_seeded_genus_coverage(
    observations_path: Path, output: Path, config: SystemConfig,
) -> dict:
    """Use shared aggregation while preserving independently annotated infection groups.

    The shared duplicate key contains study context and omits infection status.
    An explicit, reversible context discriminator is used only for aggregation.
    Reviewed and taxonomy inputs remain unchanged; output observations recover
    their original study context and retain the grouping-key provenance.
    """
    rows = read_jsonl(observations_path)
    originals = {row["record_id"]: row for row in rows}
    adapted = []
    for row in rows:
        if row.get("infection_status") not in INFECTION_STATUSES:
            raise ValueError("choosing_female_infection_status_required")
        discriminator = json.dumps({
            "original_study_context": row.get("study_context", ""),
            "infection_status": row["infection_status"],
            "treatment_context": row.get("treatment_context"),
            "experiment_id": row.get("experiment_id"),
            "infection_comparison_id": row.get("infection_comparison_id"),
        }, sort_keys=True, ensure_ascii=False)
        adapted.append({
            **row, "study_context": discriminator,
            "aggregation_original_study_context": row.get("study_context", ""),
            "aggregation_context_discriminator": discriminator,
        })
    adapted_path = output / "aggregation_input.jsonl"
    write_jsonl(adapted_path, adapted)
    metrics = build_genus_coverage(adapted_path, output, config)
    for name in ("observations", "review"):
        observations = read_jsonl(output / f"{name}.jsonl")
        for row in observations:
            row["study_context"] = row.pop("aggregation_original_study_context")
        write_jsonl(output / f"{name}.jsonl", observations)
    for name in ("genera", "conflicts", "genus_coverage"):
        genera = read_jsonl(output / f"{name}.jsonl")
        for genus in genera:
            identifiers = genus.get("all_record_ids", genus.get("source_record_ids", []))
            selected = [originals[identifier] for identifier in identifiers]
            genus.update(infection_group_metadata(selected))
        write_jsonl(output / f"{name}.jsonl", genera)
    metrics.update({
        "infection_status_counts": dict(sorted(Counter(
            row["infection_status"] for row in read_jsonl(output / "observations.jsonl")
        ).items())),
        "source_input_path": str(observations_path),
        "source_input_sha256": file_hash(observations_path),
        "grouping_discriminator_fields": [
            "study_context", "infection_status", "treatment_context", "experiment_id",
            "infection_comparison_id",
        ],
        "original_study_context_restored": True,
    })
    write_json(output / "metrics.json", metrics)
    return metrics


def run_seeded_assay_scope(
    root: Path, offline: bool = False, deadline: datetime | None = None,
) -> dict:
    """Query exact parasite assay coverage independently of the extraction cohort.

    Args:
        root: Repository root.
        offline: Replay the seeded run's own cache without network access.
        deadline: Optional caller-supplied timezone-aware live-stage deadline.

    Returns:
        The primary-fungi and all-type parasite assay inventory metrics.
    """
    paths = seeded_paths(root, offline)
    config = load_system_config(paths["config"])
    output = isolated_path(paths["interim"] / "assay_scope", paths["live"])
    cache = isolated_path(paths["cache"] / "chembl", paths["live"])
    with bounded_stage(None if offline else deadline):
        metrics = run_assay_scope_check(
            config, output, cache, paths["assay_config"], offline=offline,
        )
    write_json(paths["results"] / "assay_scope_manifest.json", {
        "system": "monarch_seeded", "adapter_system": config.slug,
        "offline": offline, "completed_at": timestamp(),
        "cache_path": str(cache), "cache_imported_from_first_monarch_run": False,
        "assay_config_sha256": file_hash(paths["assay_config"]), "metrics": metrics,
    })
    return metrics


def run_seeded_downstream(
    root: Path, offline: bool = False, deadline: datetime | None = None,
) -> dict:
    """Run seeded-only coverage joins and preserve unavailable counts as null.

    Args:
        root: Repository root; original configuration and pinned LOTUS cache are read-only.
        offline: Replay existing seeded cache responses into seeded replay outputs.
        deadline: Optional deadline derived by the caller from new retrieval provenance.

    Returns:
        Stage statuses, missing-input reasons, infection provenance, and the coverage funnel.
    """
    paths = seeded_paths(root, offline)
    config = load_system_config(paths["config"])
    outputs = {stage: isolated_path(paths["interim"] / stage, paths["live"])
               for stage in STAGE_COUNTS}
    errors: dict[str, str] = {}
    stage_results: dict[str, dict] = {}
    cache_copy = None
    try:
        input_audit = validate_semantic_input(paths["reviewed"])
    except (OSError, KeyError, TypeError, ValueError) as error:
        errors["semantic_input"] = f"{type(error).__name__}: {error}"
        input_audit = {"status": "blocked", "records": None,
                       "blocked_reason": errors["semantic_input"]}
    for stage, output in outputs.items():
        try:
            with bounded_stage(None if offline else deadline):
                if stage == "assay_scope":
                    metrics = run_assay_scope_check(
                        config, output,
                        isolated_path(paths["cache"] / "chembl", paths["live"]),
                        paths["assay_config"], offline=offline,
                    )
                elif input_audit["status"] != "complete":
                    raise ValueError("semantic_input_unavailable_or_invalid")
                elif stage == "taxonomy":
                    metrics = run_system_taxonomy(
                        config, paths["reviewed"], output,
                        isolated_path(paths["cache"] / "taxonomy", paths["live"]),
                        offline=offline,
                    )
                elif stage == "behaviour":
                    if stage_results["taxonomy"].get("status") not in COMPLETE_STATUSES:
                        raise ValueError("taxonomy_stage_incomplete")
                    metrics = build_seeded_genus_coverage(
                        outputs["taxonomy"] / "observations.jsonl", output, config,
                    )
                elif stage == "chemistry":
                    if stage_results["behaviour"].get("status") not in COMPLETE_STATUSES:
                        raise ValueError("behaviour_stage_incomplete")
                    genera = outputs["behaviour"] / "genera.jsonl"
                    if eligible_genus_rows(genera) and not offline:
                        cache_copy = materialize_lotus_cache(
                            paths["root"] / "data/raw/chemistry_export",
                            isolated_path(paths["cache"] / "chemistry_export", paths["live"]),
                        )
                    metrics = run_system_chemistry(
                        config, genera, paths["cache"],
                        isolated_path(paths["interim"] / "chemistry_transform", paths["live"]),
                        output, offline=True,
                    )
                else:
                    if stage_results["chemistry"].get("status") not in COMPLETE_STATUSES:
                        raise ValueError("chemistry_stage_incomplete")
                    metrics = run_system_bioactivity(
                        config, outputs["chemistry"] / "occurrences.jsonl",
                        outputs["behaviour"] / "genera.jsonl",
                        outputs["chemistry"] / "metrics.json", output,
                        isolated_path(paths["cache"] / "chembl", paths["live"]),
                        paths["assay_config"], offline=offline,
                    )
                stage_results[stage] = metrics
        except (OSError, KeyError, TypeError, ValueError, RuntimeError) as error:
            reason = f"{type(error).__name__}: {error}"
            errors[stage] = reason
            stage_results[stage] = unavailable_stage(
                output, "blocked", reason, STAGE_COUNTS[stage],
            )
    funnel_path = paths["results"] / "funnel.json"
    funnel = build_system_funnel(
        config, paths["interim"], funnel_path, source_interim=paths["live"],
    )
    funnel.update({"system": "monarch_seeded", "adapter_system": config.slug})
    write_json(funnel_path, funnel)
    completed = sum(row.get("status") in COMPLETE_STATUSES for row in stage_results.values())
    available = any(row.get("status") in COMPLETE_STATUSES | {"partial"}
                    for row in stage_results.values())
    status = "complete" if completed == len(stage_results) else "partial" if available else "blocked"
    report = {
        "system": "monarch_seeded", "adapter_system": config.slug,
        "offline": offline, "completed_at": timestamp(), "status": status,
        "config_path": str(paths["config"]), "config_sha256": file_hash(paths["config"]),
        "semantic_input_path": str(paths["reviewed"]), "semantic_input_audit": input_audit,
        "assay_config_sha256": file_hash(paths["assay_config"]),
        "deadline": deadline.isoformat() if deadline is not None else None,
        "deadline_source": "caller_supplied_new_retrieval_provenance" if deadline else None,
        "offline_replay_exempt_from_live_deadline": offline,
        "cache_path": str(paths["cache"]),
        "cache_imported_from_first_monarch_run": False,
        "lotus_cache_copy": cache_copy, "lotus_export_network_downloads": 0,
        "stages": stage_results, "errors": errors,
        "analysis_performed": False, "funnel_path": str(funnel_path), "funnel": funnel,
    }
    write_json(paths["results"] / "downstream_manifest.json", report)
    return report
