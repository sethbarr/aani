"""Run isolated exploratory joins through the existing taxonomy and assay modules."""

import shutil
import signal
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import FrameType

from src.behaviour.aggregation import summarize_genus
from src.bioactivity.chembl import (
    RETRIEVAL_ERRORS,
    eligible_assays,
    pages,
    retrieve_labels,
    verified_service,
)
from src.chemistry.export_cache import file_hash
from src.chemistry.lotus import acquire_lotus
from src.common.cache import CachedHTTP
from src.common.io import (
    digest,
    normalise_space,
    read_json,
    read_jsonl,
    timestamp,
    write_json,
    write_jsonl,
)
from src.systems.config import SystemConfig, load_system_config, system_paths
from src.taxonomy.gbif import normalise

DIRECTION_OUTCOMES = {"accept": "accepted", "reject": "rejected", "unknown": "unknown"}
DIRECT_EVIDENCE = {
    "field_choice_assay", "lab_choice_assay", "observational", "pathogen_challenge",
}
COMPLETE_STATUSES = {"complete", "completed"}


def run_system_taxonomy(
    config: SystemConfig,
    observations_path: Path,
    output: Path,
    cache_path: Path,
    offline: bool = False,
    confidence: int = 95,
) -> dict:
    """Resolve reviewed target organisms in the system's configured kingdom.

    The caller supplies only semantic-review inclusions and controls the stage
    deadline and isolated paths. Taxonomy preserves unknown directions and
    compound-activity observations for coverage accounting.
    """
    observations = read_jsonl(observations_path)
    if any(row.get("semantic_decision") != "include" for row in observations):
        raise ValueError("Taxonomy input must contain applied semantic-review inclusions")
    cache = CachedHTTP(cache_path, offline=offline)
    try:
        metrics = normalise(
            observations, cache, output, confidence=confidence,
            kingdom=config.taxonomy_kingdom, name_field="target_name_as_written",
            rank_field="taxonomic_rank",
        )
    finally:
        cache.close()
    matched = read_jsonl(output / "observations.jsonl")
    reviewed = read_jsonl(output / "review.jsonl")
    failed = sum(row.get("taxonomy_request_hash") is None for row in reviewed)
    all_failed = bool(observations) and failed == len(observations)
    metrics.update({
        "status": "blocked" if all_failed else "partial" if failed else "complete",
        "blocked_reason": "taxonomy_request_failures" if all_failed else None,
        "incomplete_reason": "taxonomy_request_failures" if failed else None,
        "failed_observations": failed,
        "system": config.slug, "kingdom": config.taxonomy_kingdom,
        "resolved_taxa": None if all_failed else len({row["accepted_usage_key"] for row in matched}),
        "input_path": str(observations_path), "input_sha256": file_hash(observations_path),
        "cache_path": str(cache_path), "offline": offline,
    })
    write_json(output / "metrics.json", metrics)
    return metrics


def direct_behaviour_reason(row: dict) -> str | None:
    """Require semantic inclusion, direct behaviour and a directional observation."""
    if row.get("semantic_decision") != "include":
        return "semantic_inclusion_required"
    if row.get("behavioural_choice") is not True:
        return "direct_behaviour_unavailable"
    if row.get("evidence_type") not in DIRECT_EVIDENCE:
        return "direct_behavioural_evidence_required"
    if row.get("direction") not in {"accept", "reject"}:
        return "unknown_direction"
    if not all(row.get(key) for key in ("genus", "family", "accepted_name")):
        return "unresolved_taxonomy"
    return None


def deduplicate_system_contexts(observations: list[dict]) -> tuple[list[dict], list[dict]]:
    """Merge identical reviewed contexts while retaining distinct target taxa."""
    fields = (
        "source_id", "accepted_usage_key", "target_name_as_written", "direction",
        "evidence_quote", "behaving_organism_as_written", "study_context", "evidence_type",
        "behavioural_choice", "semantic_decision", "compound_name_as_written",
        "activity_target_as_written", "activity_outcome", "quantitative_measure",
    )
    unique: dict[str, dict] = {}
    duplicates = []
    for row in observations:
        key = digest({field: normalise_space(str(row.get(field, ""))) for field in fields})
        if key in unique:
            retained = unique[key]
            retained["merged_record_ids"].append(row["record_id"])
            duplicates.append({
                "discarded_record_id": row["record_id"],
                "retained_record_id": retained["record_id"], "grounded_identity": key,
            })
        else:
            unique[key] = {**row, "grounded_identity": key, "merged_record_ids": [row["record_id"]]}
    return list(unique.values()), duplicates


def genus_scope_metadata(rows: list[dict], config: SystemConfig | None) -> dict:
    """Carry reviewed biological scope into a technical directional genus summary."""
    focal = any(row.get("focal_eligible") is True for row in rows)
    infection = any(row.get("infection_comparison_eligible") is True for row in rows)
    scope = "focal_mechanism_coverage" if focal else "directional_behaviour_coverage"
    if config is not None and config.slug == "monarch" and not focal:
        scope = "ancillary_oviposition_coverage"
    return {
        "evaluation_scope": scope,
        "focal_eligible": focal,
        "infection_comparison_eligible": infection,
        "treatment_contexts": sorted({row["treatment_context"] for row in rows
                                      if row.get("treatment_context")}),
        "direction_scopes": sorted({row["direction_scope"] for row in rows
                                    if row.get("direction_scope")}),
        "semantic_scopes": sorted({row["semantic_scope"] for row in rows
                                   if row.get("semantic_scope")}),
        "source_record_ids": sorted(row["record_id"] for row in rows),
        "eligibility_interpretation": (
            "primary_eligible is the legacy technical directional-filter flag for this "
            "exploratory join. focal_eligible identifies evidence eligible for the declared "
            "biological mechanism."
        ),
    }


def build_genus_coverage(
    observations_path: Path, output: Path, config: SystemConfig | None = None,
) -> dict:
    """Apply existing genus unanimity after explicit direct-behaviour eligibility.

    All resolved observations remain in the coverage outputs. Unknown direction,
    secondary reports, named sources and compound assays cannot supply a
    directional behavioural genus. Conflicted genera remain separately recorded.
    """
    observations, duplicates = deduplicate_system_contexts(read_jsonl(observations_path))
    groups: dict[str, list[dict]] = {}
    review = []
    for row in observations:
        reason = direct_behaviour_reason(row)
        row["behaviour_eligibility_reason"] = reason
        if reason:
            review.append({**row, "exclusion_reason": reason})
        if row.get("genus"):
            groups.setdefault(row["genus"], []).append(row)
    eligible, conflicts, coverage = [], [], []
    for genus, rows in sorted(groups.items()):
        direct = [row for row in rows if row["behaviour_eligibility_reason"] is None]
        if direct:
            adapted = [{
                **row, "outcome": DIRECTION_OUTCOMES[row["direction"]],
                "ant_species": row["behaving_organism_as_written"],
            } for row in direct]
            summary = summarize_genus(genus, adapted)
            summary["behaving_organisms"] = summary.pop("ant_species")
            summary["n_behaving_organisms"] = summary.pop("n_ant_species")
            summary["directional_behaviour_records"] = len(direct)
            summary.update(genus_scope_metadata(direct, config))
            if summary["primary_eligible"]:
                eligible.append(summary)
            else:
                conflicts.append(summary)
        else:
            summary = {
                "genus": genus, "status": "unknown", "outcome": "unknown",
                "primary_eligible": False, "directional_behaviour_records": 0,
                "accepted_names": [], "behaviour_record_ids": [],
                **genus_scope_metadata([], config),
            }
        coverage.append({
            **summary,
            "all_resolved_observations": len(rows),
            "all_directions": sorted({row["direction"] for row in rows}),
            "direction_counts": dict(Counter(row["direction"] for row in rows)),
            "unknown_direction_observations": sum(row["direction"] == "unknown" for row in rows),
            "ineligible_observations": len(rows) - len(direct),
            "all_record_ids": sorted(row["record_id"] for row in rows),
            "all_accepted_names": sorted({row["accepted_name"] for row in rows}),
            "all_treatment_contexts": sorted({row["treatment_context"] for row in rows
                                              if row.get("treatment_context")}),
            "all_direction_scopes": sorted({row["direction_scope"] for row in rows
                                            if row.get("direction_scope")}),
        })
    for name, rows in (
        ("observations", observations), ("genera", eligible), ("conflicts", conflicts),
        ("genus_coverage", coverage), ("review", review), ("duplicates", duplicates),
    ):
        write_jsonl(output / f"{name}.jsonl", rows)
    metrics = {
        "status": "complete", "blocked_reason": None,
        "input_path": str(observations_path), "input_sha256": file_hash(observations_path),
        "resolved_observations": len(observations), "duplicate_observations": len(duplicates),
        "resolved_genera": len(coverage), "eligible_genera": len(eligible),
        "accepted_genera": sum(row["status"] == "accepted" for row in eligible),
        "rejected_genera": sum(row["status"] == "rejected" for row in eligible),
        "conflict_genera": len(conflicts),
        "unknown_genera": sum(row["status"] == "unknown" for row in coverage),
        "focal_eligible_genera": sum(row["focal_eligible"] for row in eligible),
        "infection_comparison_eligible_genera": sum(
            row["infection_comparison_eligible"] for row in eligible
        ),
        "ancillary_oviposition_genera": sum(
            row["evaluation_scope"] == "ancillary_oviposition_coverage" for row in eligible
        ),
        "direct_directional_observations": sum(
            row["behaviour_eligibility_reason"] is None for row in observations
        ),
        "unknown_direction_observations": sum(
            row["direction"] == "unknown" for row in observations
        ),
        "ineligible_observations": len(review),
    }
    write_json(output / "metrics.json", metrics)
    return metrics


def eligible_genus_rows(path: Path) -> list[dict]:
    """Verify that a chemistry input contains only audited directional genera."""
    rows = read_jsonl(path)
    if len({row["genus"] for row in rows}) != len(rows):
        raise ValueError("Duplicate genera in the chemistry selection")
    if any(
        row.get("status") not in {"accepted", "rejected"}
        or row.get("primary_eligible") is not True
        or row.get("directional_behaviour_records", 0) < 1
        for row in rows
    ):
        raise ValueError("Chemistry requires eligible direct directional behavioural genera")
    return rows


def unavailable_stage(output: Path, status: str, reason: str, fields: list[str]) -> dict:
    """Write explicit unavailable counts for a blocked or unconfigured stage."""
    metrics = {"status": status, "blocked_reason": reason, **dict.fromkeys(fields)}
    write_json(output / "metrics.json", metrics)
    return metrics


def run_system_chemistry(
    config: SystemConfig,
    genera_path: Path,
    raw: Path,
    interim: Path,
    output: Path,
    offline: bool = False,
) -> dict:
    """Use the existing versioned LOTUS importer on eligible behavioural genera.

    The caller may materialize the shared verified export cache beneath ``raw``
    before an offline run. This function reads and writes only the supplied paths.
    """
    counts = ["accepted", "unique_occurrences", "unique_compounds", "genera_with_chemistry"]
    if not config.run_chemistry:
        return unavailable_stage(output, "not_applicable", "disabled_in_system_config", counts)
    if config.chemistry_backend != "LOTUS" or config.taxonomy_kingdom != "Plantae":
        raise ValueError("LOTUS stage requires the configured plant chemistry backend")
    genera = eligible_genus_rows(genera_path)
    if not genera:
        for name in ("occurrences", "review", "genus_coverage"):
            write_jsonl(output / f"{name}.jsonl", [])
        metrics = {
            "status": "complete", "blocked_reason": None, **dict.fromkeys(counts, 0),
            "requested_genera": 0, "reason": "no_eligible_behavioural_genera",
            "export_scanned": False,
        }
        write_json(output / "metrics.json", metrics)
        write_json(output / "run_manifest.json", {
            "system": config.slug, "metrics": metrics, "offline": offline,
            "genus_input_path": str(genera_path), "genus_input_sha256": file_hash(genera_path),
        })
        return metrics
    manifest = acquire_lotus(genera_path, raw, interim, output, offline=offline)
    return manifest["metrics"]


def run_system_bioactivity(
    config: SystemConfig,
    occurrences_path: Path,
    genera_path: Path,
    chemistry_metrics_path: Path,
    output: Path,
    cache_path: Path,
    assay_config_path: Path,
    offline: bool = False,
) -> dict:
    """Retrieve exact ChEMBL structures under the explicit frozen assay configuration."""
    counts = [
        "compounds", "matched_compounds", "active", "inactive", "unknown",
        "failed_compounds", "classified_compounds", "genera_with_classified_compounds",
    ]
    if not config.run_bioactivity:
        return unavailable_stage(output, "not_applicable", "disabled_in_system_config", counts)
    inputs = [occurrences_path, genera_path, chemistry_metrics_path, assay_config_path]
    missing = [str(path) for path in inputs if not path.is_file()]
    if missing:
        return unavailable_stage(output, "blocked", "missing_inputs:" + ",".join(missing), counts)
    chemistry = read_json(chemistry_metrics_path)
    if chemistry.get("status") not in COMPLETE_STATUSES or chemistry.get("blocked_reason"):
        return unavailable_stage(output, "blocked", "chemistry_stage_incomplete", counts)
    genera = {row["genus"] for row in eligible_genus_rows(genera_path)}
    assay_config = read_json(assay_config_path)
    if set(assay_config["organisms"]) != set(config.assay_organisms):
        raise ValueError("System assay organisms differ from the frozen assay configuration")
    occurrences = read_jsonl(occurrences_path)
    selected = [row for row in occurrences if row["genus"] in genera]
    compounds = sorted({row["compound_id"] for row in selected})
    selection = {
        "selected_compounds": len(compounds), "selected_occurrences": len(selected),
        "eligible_behaviour_genera": sorted(genera),
        "excluded_occurrences": len(occurrences) - len(selected),
        "selection_rule": "Semantically retained direct directional genera before bioactivity.",
        "assay_mismatch": config.assay_mismatch,
    }
    write_json(output / "selection.json", selection)
    cache = CachedHTTP(cache_path, offline=offline)
    try:
        metrics = retrieve_labels(compounds, cache, output, assay_config)
    finally:
        cache.close()
    labels = read_jsonl(output / "labels.jsonl")
    classified = {
        row["compound_id"] for row in labels
        if row["label"] in {"active", "inactive"} and row.get("retrieval_status") != "failed"
    }
    metrics.update({
        **selection,
        "query_count": metrics.get("cached_requests", 0),
        "classified_compounds": len(classified),
        "genera_with_classified_compounds": len({
            row["genus"] for row in selected if row["compound_id"] in classified
        }),
        "classification_denominator": "active_and_inactive_with_successful_retrieval",
        "coverage_complete": metrics["status"] in COMPLETE_STATUSES,
    })
    if metrics.get("blocked_reason"):
        metrics["classified_compounds"] = None
        metrics["genera_with_classified_compounds"] = None
    write_json(output / "metrics.json", metrics)
    write_json(output / "run_manifest.json", {
        "system": config.slug, "offline": offline,
        "input_hashes": {str(path): file_hash(path) for path in inputs},
        "assay_config": assay_config, "selection": selection,
        "cache_path": str(cache_path), "metrics": metrics,
    })
    return metrics


def run_assay_scope_check(
    config: SystemConfig,
    output: Path,
    cache_path: Path,
    assay_config_path: Path,
    offline: bool = False,
) -> dict:
    """Measure monarch assay-organism coverage independently of compound joins.

    The primary panel retains exact functional fungal assays. The separate
    Ophryocystis inventory allows every assay type and contributes solely to
    the documented assay mismatch, never to primary compound classification.
    """
    if config.slug != "monarch":
        return unavailable_stage(output, "not_applicable", "monarch_scope_check_only", [])
    assay_config = read_json(assay_config_path)
    if set(assay_config["organisms"]) != set(config.assay_organisms):
        raise ValueError("System assay organisms differ from the frozen assay configuration")
    organism = config.biological_assay_target
    if not organism:
        raise ValueError("Monarch assay check requires its configured biological target")
    cache = CachedHTTP(cache_path, offline=offline)
    requests: list[dict] = []
    service, primary, parasite, errors = {}, None, None, {}
    try:
        try:
            service = verified_service(cache, requests)
            primary = list(eligible_assays(cache, assay_config, requests).values())
            write_jsonl(output / "primary_fungal_assays.jsonl", primary)
        except RETRIEVAL_ERRORS as error:
            errors["primary"] = f"{type(error).__name__}: {error}"
        try:
            parasite_rows = pages(cache, "assay", "assays", {"assay_organism": organism}, requests)
            if any(row.get("assay_organism") != organism for row in parasite_rows):
                raise ValueError("ChEMBL returned assays outside the exact parasite organism")
            ids = [row["assay_chembl_id"] for row in parasite_rows]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate parasite assays in the ChEMBL inventory")
            parasite = parasite_rows
            write_jsonl(output / "parasite_assays.jsonl", parasite)
        except RETRIEVAL_ERRORS as error:
            errors["parasite"] = f"{type(error).__name__}: {error}"
    finally:
        cache.close()
    metrics = {
        "system": config.slug,
        "status": "partial" if errors and (primary is not None or parasite is not None)
        else "blocked" if errors else "complete",
        "blocked_reason": "; ".join(errors.values()) if errors else None,
        "primary_fungal_assays": len(primary) if primary is not None else None,
        "primary_assays_by_organism": {
            name: sum(row["assay_organism"] == name for row in primary)
            for name in config.assay_organisms
        } if primary is not None else None,
        "parasite_organism": organism,
        "parasite_assays_all_types": len(parasite) if parasite is not None else None,
        "primary_assay_type": "F", "parasite_assay_type_filter": None,
        "assay_mismatch": config.assay_mismatch,
        "parasite_absent_from_complete_inventory": parasite == [] if parasite is not None else None,
        "zero_assays_interpretation": "Database assay coverage only; inactivity is unmeasured.",
        "query_count": len({row["request_hash"] for row in requests}),
        "offline": offline, "errors": errors,
    }
    write_json(output / "metrics.json", metrics)
    write_json(output / "assay_scope_check.json", {
        **metrics, "service": service, "requests": requests,
        "assay_config": assay_config, "assay_config_sha256": file_hash(assay_config_path),
        "cache_path": str(cache_path),
    })
    return metrics


def stage_metrics(path: Path) -> dict:
    """Read a completed stage or retain explicit absence semantics."""
    if not path.is_file():
        return {"status": "not_run", "blocked_reason": "stage_metrics_missing"}
    return read_json(path)


def build_system_funnel(
    config: SystemConfig,
    interim: Path,
    output: Path,
    source_interim: Path | None = None,
) -> dict:
    """Write stage coverage with missing stages null and partial counts identified.

    Conventional subdirectories are extraction, taxonomy, behaviour, chemistry
    and bioactivity. The semantic review metrics are optional under
    extraction/semantic_review.json. Counts describe the observed exploratory
    cohort and make no inference about enrichment or independent replication.
    """
    source = source_interim or interim
    extraction = stage_metrics(source / "extraction/metrics.json")
    semantic_path = source / "semantic_review/metrics.json"
    if not semantic_path.is_file():
        semantic_path = source / "extraction/semantic_review.json"
    semantic = stage_metrics(semantic_path)
    taxonomy = stage_metrics(interim / "taxonomy/metrics.json")
    behaviour = stage_metrics(interim / "behaviour/metrics.json")
    chemistry = stage_metrics(interim / "chemistry/metrics.json")
    activity = stage_metrics(interim / "bioactivity/metrics.json")
    specifications = [
        ("model_candidates", "candidate_records", "model records", extraction),
        ("grounded_records", "retained_records", "grounded model records", extraction),
        ("semantically_retained", "included", "reviewed model records", semantic),
        ("names_resolved", "resolved_taxa", "distinct accepted taxon identities", taxonomy),
        ("eligible_behaviour_genera", "eligible_genera", "directional genera", behaviour),
        ("genera_with_chemistry", "genera_with_chemistry", "eligible genera", chemistry),
        ("mapped_compounds", "unique_compounds", "distinct full InChIKeys", chemistry),
        ("classified_compounds", "classified_compounds", "active or inactive compounds", activity),
        ("genera_with_classified_compounds", "genera_with_classified_compounds",
         "eligible genera", activity),
    ]
    stages = []
    for name, field, unit, metrics in specifications:
        status = metrics.get("status") or (
            "partial" if metrics.get("blocked_reason") else "complete"
        )
        if not config.run_chemistry and metrics is chemistry:
            status = "not_applicable"
        if not config.run_bioactivity and metrics is activity:
            status = "not_applicable"
        available = status in COMPLETE_STATUSES | {"partial"}
        stages.append({
            "stage": name, "count": metrics.get(field) if available else None,
            "unit": unit, "status": status,
            "blocked_reason": metrics.get("blocked_reason"),
            "count_interpretation": "observed_lower_bound" if status == "partial" else "observed",
        })
    result = {
        "system": config.slug, "exploratory": True, "stages": stages,
        "behaviour_metrics": behaviour, "bioactivity_metrics": activity,
        "assay_scope_check": stage_metrics(interim / "assay_scope/metrics.json"),
        "assay_mismatch": config.assay_mismatch,
        "missingness_policy": (
            "Unavailable stages have null counts. Unknown directions do not supply directional "
            "genera. Conflicts are excluded from chemistry inputs. Unknown or failed assay "
            "labels are excluded from classified denominators."
        ),
        "analysis_performed": False,
    }
    write_json(output, result)
    return result


def isolated_path(path: Path, allowed_root: Path) -> Path:
    """Resolve a system artifact path and reject symlink or traversal escapes."""
    resolved = path.resolve()
    if not resolved.is_relative_to(allowed_root.resolve()):
        raise ValueError(f"Path is outside the system isolation root: {resolved}")
    return resolved


def corpus_deadline(config: SystemConfig, manifest_path: Path) -> datetime:
    """Derive the prospective wall-clock cap from the first corpus retrieval."""
    retrieved = [
        datetime.fromisoformat(row["retrieved_at"])
        for row in read_jsonl(manifest_path) if row.get("retrieved_at")
    ]
    if not retrieved or any(value.tzinfo is None for value in retrieved):
        raise ValueError("Corpus manifest requires timezone-aware retrieval timestamps")
    return min(retrieved) + timedelta(hours=config.time_limit_hours)


class SystemDeadlineExceeded(TimeoutError):
    """The configured exploratory-system wall-clock cap has elapsed."""


def raise_stage_deadline(signum: int, frame: FrameType | None) -> None:
    """Interrupt network retries as well as local export processing."""
    raise SystemDeadlineExceeded("configured_system_wall_clock_limit_reached")


@contextmanager
def bounded_stage(deadline: datetime | None) -> Iterator[None]:
    """Interrupt a live CLI stage at its remaining POSIX wall-clock deadline."""
    if deadline is None:
        yield
        return
    remaining = (deadline - datetime.now(UTC)).total_seconds()
    if remaining <= 0:
        raise SystemDeadlineExceeded("configured_system_wall_clock_limit_reached")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    signal.signal(signal.SIGALRM, raise_stage_deadline)
    signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


def materialize_lotus_cache(source: Path, destination: Path) -> dict:
    """Copy an existing shared export cache into the selected system cache."""
    if not source.is_dir():
        raise FileNotFoundError(f"Shared LOTUS cache is unavailable: {source}")
    copied, copied_bytes = 0, 0
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("Shared LOTUS cache must contain ordinary files and directories")
        if not path.is_file():
            continue
        target = isolated_path(destination / path.relative_to(source), destination)
        if target.exists():
            if file_hash(target) != file_hash(path):
                raise ValueError(f"Existing system LOTUS cache differs from shared source: {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = isolated_path(target.with_suffix(target.suffix + ".copying"), destination)
        shutil.copy2(path, temporary)
        temporary.replace(target)
        copied += 1
        copied_bytes += path.stat().st_size
    return {"source": str(source), "destination": str(destination),
            "files_copied": copied, "bytes_copied": copied_bytes}


def run_system_downstream(config_path: Path, root: Path, offline: bool = False) -> dict:
    """Run bounded isolated joins from live semantic inclusions and record coverage.

    Online runs reuse the shared LOTUS export through a system-local copy and
    permit the configured GBIF and ChEMBL requests. Offline verification reads
    the live system caches and writes under its offline_replay directories.
    The wall-clock cap limits live stages; deterministic replay remains available.
    """
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    config = load_system_config(config_path)
    paths = system_paths(config, root)
    live = isolated_path(paths["interim"], root)
    interim = isolated_path(live / "offline_replay" if offline else live, live)
    results_root = isolated_path(paths["results"], root)
    results = isolated_path(results_root / "offline_replay" if offline else results_root,
                            results_root)
    cache = isolated_path(live / "cache", live)
    reviewed = isolated_path(live / "semantic_review/observations.jsonl", live)
    outputs = {stage: isolated_path(interim / stage, live)
               for stage in ("taxonomy", "behaviour", "chemistry", "assay_scope", "bioactivity")}
    assay_config = root / "config/analysis.json"
    errors: dict[str, str] = {}
    try:
        deadline = corpus_deadline(config, live / "corpus/manifest.jsonl")
    except (OSError, KeyError, TypeError, ValueError) as error:
        deadline = None
        errors["deadline"] = f"{type(error).__name__}: {error}"
    live_deadline = None if offline else deadline
    stage_results: dict[str, dict] = {}
    cache_copy = None
    for stage, output in outputs.items():
        if (stage == "chemistry" and not config.run_chemistry) or (
            stage == "bioactivity" and not config.run_bioactivity
        ) or (
            stage == "assay_scope" and config.slug != "monarch"
        ):
            stage_results[stage] = unavailable_stage(
                output, "not_applicable", "disabled_in_system_config", [],
            )
            continue
        try:
            if "deadline" in errors and not offline:
                raise ValueError(errors["deadline"])
            with bounded_stage(live_deadline):
                if stage == "taxonomy":
                    metrics = run_system_taxonomy(
                        config, reviewed, output, isolated_path(cache / "taxonomy", live),
                        offline=offline,
                    )
                elif stage == "behaviour":
                    if stage_results["taxonomy"].get("status") not in COMPLETE_STATUSES:
                        raise ValueError("taxonomy_stage_incomplete")
                    metrics = build_genus_coverage(outputs["taxonomy"] / "observations.jsonl",
                                                   output, config)
                elif stage == "chemistry":
                    if stage_results["behaviour"].get("status") not in COMPLETE_STATUSES:
                        raise ValueError("behaviour_stage_incomplete")
                    genera_path = outputs["behaviour"] / "genera.jsonl"
                    if eligible_genus_rows(genera_path) and not offline:
                        cache_copy = materialize_lotus_cache(
                            root / "data/raw/chemistry_export",
                            isolated_path(cache / "chemistry_export", live),
                        )
                    metrics = run_system_chemistry(
                        config, genera_path, cache,
                        isolated_path(interim / "chemistry_transform", live), output,
                        offline=True,
                    )
                elif stage == "assay_scope":
                    metrics = run_assay_scope_check(
                        config, output, isolated_path(cache / "chembl", live), assay_config,
                        offline=offline,
                    )
                else:
                    metrics = run_system_bioactivity(
                        config, outputs["chemistry"] / "occurrences.jsonl",
                        outputs["behaviour"] / "genera.jsonl",
                        outputs["chemistry"] / "metrics.json", output,
                        isolated_path(cache / "chembl", live), assay_config, offline=offline,
                    )
                stage_results[stage] = metrics
        except (OSError, KeyError, TypeError, ValueError, RuntimeError) as error:
            reason = f"{type(error).__name__}: {error}"
            errors[stage] = reason
            stage_results[stage] = unavailable_stage(output, "blocked", reason, [])
    funnel = build_system_funnel(config, interim, results / "funnel.json", source_interim=live)
    report = {
        "system": config.slug, "offline": offline, "completed_at": timestamp(),
        "status": "blocked" if any(row.get("status") == "blocked"
                                    for row in stage_results.values()) else "complete",
        "config_path": str(config_path), "config_sha256": file_hash(config_path),
        "semantic_input_path": str(reviewed),
        "semantic_input_sha256": file_hash(reviewed) if reviewed.is_file() else None,
        "deadline": deadline.isoformat() if deadline is not None else None,
        "deadline_scope": "Live stages, including network retries and local processing.",
        "offline_replay_exempt_from_live_deadline": offline,
        "lotus_cache_copy": cache_copy, "lotus_export_network_downloads": 0,
        "stages": stage_results, "errors": errors,
        "funnel_path": str(results / "funnel.json"), "funnel": funnel,
    }
    write_json(results / "downstream_manifest.json", report)
    return report
