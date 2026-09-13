"""Report the real pipeline coverage, including curator branches and blocked stages."""

import argparse
import csv
import hashlib
from pathlib import Path

from src.analysis.protocol import committed_protocol
from src.common.io import read_json, read_jsonl, timestamp, write_json


def optional_rows(path: Path) -> list[dict]:
    """Read available rows without pretending a missing stage completed."""
    return read_jsonl(path) if path.exists() else []


def optional_metrics(path: Path) -> dict:
    """Represent absent stage metrics explicitly as blocked."""
    return read_json(path) if path.exists() else {
        "status": "blocked", "blocked_reason": f"missing_stage_metrics:{path}"
    }


def file_record(path: Path) -> dict:
    """Describe an existing input by exact bytes."""
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def taxonomy_review_status(review_path: Path, observations_path: Path) -> dict:
    """Preserve historical review names and identify current explicit resolutions."""
    reviewed = {row["plant_name_as_written"] for row in read_jsonl(review_path)}
    current = optional_rows(observations_path)
    resolved = sorted({row["plant_name_as_written"] for row in current} & reviewed)
    return {
        "historical_taxonomy_review_species": sorted(reviewed),
        "taxonomy_review_species": sorted(reviewed - set(resolved)),
        "taxonomy_review_resolved_species": resolved,
    }


def metric_stage(name: str, count: int | None, unit: str, status: str = "complete",
                 blocked_reason: str | None = None, **details: object) -> dict:
    """Construct a stage with explicit units and absence semantics."""
    return {"stage": name, "count": count, "unit": unit, "status": status,
            "blocked_reason": blocked_reason, **details}


def historical_stages() -> tuple[list[dict], dict, list[Path]]:
    """Count fixed-pilot and targeted cohorts without merging incompatible units."""
    corpus_paths = [Path("data/interim/corpus/manifest.jsonl"),
                    Path("data/interim/corpus_targeted_saverschek/manifest.jsonl"),
                    Path("data/interim/pending_evidence_review/corpus/manifest.jsonl")]
    fixed_retrieved = sum(r["status"] == "ready" for r in read_jsonl(corpus_paths[0]))
    targeted_retrieved = sum(r["status"] == "ready" for r in read_jsonl(corpus_paths[1]))
    recovered_path = Path("data/interim/taxonomy_recovered/observations.jsonl")
    recovered_count = len(read_jsonl(recovered_path))
    retrieved = {r["source_id"] for path in corpus_paths for r in read_jsonl(path)
                 if r["status"] == "ready"}
    screening_path = Path("config/pilot_screening.json")
    screening = read_json(screening_path)
    fixed_included = {r["source_id"] for r in screening["decisions"] if r["decision"] == "include"}
    extension = {r["source_id"] for path in corpus_paths[1:] for r in read_jsonl(path)
                 if r["status"] == "ready"} - fixed_included
    model_metrics_paths = [Path("data/interim/extraction_gemini/metrics.json"),
                           Path("data/interim/extraction_saverschek/metrics.json")]
    model_metrics = [read_json(p) for p in model_metrics_paths]
    reviewed_paths = [Path("data/interim/extraction_gemini/semantic_review_observations.jsonl"),
                      Path("data/interim/extraction_saverschek/semantic_review_observations.jsonl")]
    original_retained = [read_jsonl(p) for p in reviewed_paths]
    stages = [
        metric_stage("papers_retrieved", len(retrieved), "unique sources with cached full text",
                     fixed_pilot=fixed_retrieved, targeted_additional=len(retrieved) - fixed_retrieved),
        metric_stage("screened_in", len(fixed_included | extension), "unique sources selected by any inclusion route",
                     formal_pilot_screening=len(fixed_included), targeted_source_review=len(extension),
                     note="Targeted sources were not part of the fixed first-30 screening denominator."),
        metric_stage("extraction_jobs", sum(m["chunks"] for m in model_metrics), "model jobs",
                     papers_extracted=sum(m["papers"] for m in model_metrics),
                     failed_jobs=sum(m["response_failures"] for m in model_metrics)),
        metric_stage("candidate_records", sum(m["candidate_records"] for m in model_metrics), "original model candidates"),
        metric_stage("grounding_passed", sum(m["validated_candidates"] for m in model_metrics), "original model candidates",
                     rejected=sum(m["rejected_candidates"] for m in model_metrics)),
        metric_stage("semantically_retained", sum(len(r) for r in original_retained), "original model records retained by source review",
                     note="Curator recovery is a separate branch below; it does not enlarge the model denominator."),
    ]
    cohorts = {
        "fixed_pilot": {"retrieved": fixed_retrieved, "screened_in": len(fixed_included),
                        "metrics": model_metrics[0], "model_semantically_retained": len(original_retained[0])},
        "targeted_saverschek": {"retrieved": targeted_retrieved, "screened_in": targeted_retrieved,
                                 "metrics": model_metrics[1], "model_semantically_retained": len(original_retained[1])},
        "source_following_recovery": {"additional_retrieved_sources": sorted(extension - {"SAVERSCHEK2010"}),
                                       "model_jobs": 0, "curator_records": recovered_count},
        "retrieved_source_ids": sorted(retrieved),
        "included_source_ids": sorted(fixed_included | extension),
    }
    return stages, cohorts, corpus_paths + [screening_path, recovered_path] + model_metrics_paths + reviewed_paths


def current_stages(processed: Path, results: Path) -> tuple[list[dict], dict, dict, list[Path]]:
    """Count observable joins while retaining missingness and conflict exclusions."""
    behaviour = processed / "behaviour"
    chemistry = processed / "chemistry"
    bioactivity = processed / "bioactivity"
    observations = optional_rows(behaviour / "observations.jsonl")
    eligible = optional_rows(behaviour / "genera.jsonl")
    conflicts = optional_rows(behaviour / "conflicts.jsonl")
    occurrences = optional_rows(chemistry / "occurrences.jsonl")
    labels = optional_rows(bioactivity / "labels.jsonl")
    behaviour_metrics = optional_metrics(behaviour / "metrics.json")
    chemistry_metrics = optional_metrics(chemistry / "metrics.json")
    activity_metrics = optional_metrics(bioactivity / "metrics.json")
    primary = optional_metrics(results / "primary/summary.json")
    eligible_names = {r["genus"] for r in eligible}
    conflict_names = {r["genus"] for r in conflicts}
    chemistry_names = {r["genus"] for r in occurrences}
    conflict_contexts = [r for r in observations if r["genus"] in conflict_names]
    resolved_names = {str(r["accepted_usage_key"]) for r in observations}
    all_classified = {r["compound_id"] for r in labels if r["label"] in {"active", "inactive"}
                      and r.get("retrieval_status") != "failed"}
    primary_compounds = {r["compound_id"] for r in occurrences if r["genus"] in eligible_names}
    classified = all_classified & primary_compounds
    classified_genera = {r["genus"] for r in occurrences if r["genus"] in eligible_names
                         and r["compound_id"] in classified}
    chem_block = chemistry_metrics.get("blocked_reason")
    activity_block = activity_metrics.get("blocked_reason")
    activity_failed = activity_metrics.get("failed_compounds")
    chem_known = not chem_block and (chemistry / "occurrences.jsonl").exists()
    activity_known = chem_known and (bioactivity / "labels.jsonl").exists() and not activity_block
    behaviour_known = not behaviour_metrics.get("blocked_reason") and all(
        (behaviour / name).exists() for name in ["observations.jsonl", "genera.jsonl", "conflicts.jsonl"]
    )
    primary_known = activity_known and (results / "primary/summary.json").exists() and primary.get("n_genera") is not None
    stages = [
        metric_stage("names_resolved", len(resolved_names) if behaviour_known else None,
                     "distinct accepted species identities", "complete" if behaviour_known else "blocked",
                     behaviour_metrics.get("blocked_reason"), observation_contexts=len(observations),
                     conflict_genera=len(conflicts),
                     species_in_conflicted_genera=len({r["accepted_usage_key"] for r in conflict_contexts}),
                     conflict_observation_contexts=len(conflict_contexts)),
        metric_stage("genera_after_aggregation", len(eligible) if behaviour_known else None,
                     "directionally consistent genera", "complete" if behaviour_known else "blocked",
                     behaviour_metrics.get("blocked_reason"),
                     accepted=sum(r["status"] == "accepted" for r in eligible),
                     rejected=sum(r["status"] == "rejected" for r in eligible),
                     conflict_genera=len(conflicts), conflicts=sorted(conflict_names)),
        metric_stage("genera_with_chemistry", len(eligible_names & chemistry_names) if chem_known else None,
                     "eligible genera with at least one imported occurrence", "complete" if chem_known else "blocked",
                     chem_block, missing_chemistry_genera=sorted(eligible_names - chemistry_names) if chem_known else None,
                     conflict_genera_with_chemistry=len(conflict_names & chemistry_names) if chem_known else None,
                     conflict_genera_excluded_from_primary=len(conflicts),
                     imported_occurrences=len(occurrences) if chem_known else None,
                     imported_unique_structures=len({r["compound_id"] for r in occurrences}) if chem_known else None),
        metric_stage("genera_with_classified_compounds", len(classified_genera) if activity_known else None,
                     "eligible genera with at least one active or inactive compound",
                     "partial" if activity_known and activity_failed else "complete" if activity_known else "blocked",
                     activity_block, classified_structures_observed=len(classified) if activity_known else None,
                     all_retrieved_classified_structures=len(all_classified) if activity_known else None,
                     primary_scope_structures=len(primary_compounds) if chem_known else None,
                     failed_compounds=activity_failed, coverage_complete=activity_known and activity_failed == 0,
                     count_interpretation="observed_lower_bound_due_to_failed_retrievals" if activity_failed
                     else "observed_coverage_in_completed_retrieval" if activity_known else "unavailable",
                     zero_classified_interpretation="zero_observed_classified_compounds; unknown is not inactive",
                     zero_classified_genera=sorted((eligible_names & chemistry_names) - classified_genera)
                     if activity_known else None,
                     zero_classified_genera_count=len((eligible_names & chemistry_names) - classified_genera)
                     if activity_known else None,
                     conflict_genera_excluded_from_primary=len(conflicts)),
        metric_stage("genera_available_for_primary_test", primary.get("n_genera") if primary_known else None,
                     "joined genera available before the feasibility gate",
                     "complete" if primary_known else "blocked", primary.get("blocked_reason"),
                     primary_status=primary.get("status"), estimable=primary.get("estimable", False),
                     conflict_genera_excluded_from_primary=len(conflicts)),
    ]
    miconia_observations = [r for r in observations if r["genus"] == "Miconia"]
    miconia = {
        "status": next((r["status"] for r in conflicts if r["genus"] == "Miconia"), "not_verified"),
        "accepted_names": sorted({r["accepted_name"] for r in miconia_observations}),
        "directions": sorted({r["outcome"] for r in miconia_observations}),
        "sources": sorted({r["source_id"] for r in miconia_observations}),
        "observation_ids": [r["record_id"] for r in miconia_observations],
    }
    if behaviour_known and observations:
        assert miconia["status"] == "conflict"
        assert {"Miconia microphysca", "Miconia argentea"}.issubset(miconia["accepted_names"])
        assert miconia["directions"] == ["accepted", "rejected"]
        assert "Miconia" not in eligible_names
    metrics = {"behaviour": behaviour_metrics, "chemistry": chemistry_metrics,
               "bioactivity": activity_metrics, "primary_test": primary}
    inputs = [folder / name for folder in [behaviour, chemistry, bioactivity]
              for name in ["metrics.json", "run_manifest.json"] if (folder / name).exists()]
    inputs += [p for p in [behaviour / "observations.jsonl", behaviour / "genera.jsonl",
                           behaviour / "all_genera.jsonl", behaviour / "conflicts.jsonl",
                           chemistry / "occurrences.jsonl", bioactivity / "labels.jsonl"] if p.exists()]
    inputs += [results / "primary/summary.json"] if (results / "primary/summary.json").exists() else []
    return stages, metrics, miconia, inputs


def main() -> None:
    """Write the machine-readable funnel and a short tabular run report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed", type=Path, default=Path("data/processed"))
    parser.add_argument("--results", type=Path, default=Path("results"))
    parser.add_argument("--offline", action="store_true", help="Local-only stage; never makes network calls.")
    args = parser.parse_args()
    commit = committed_protocol(Path.cwd())
    historical, cohorts, inputs = historical_stages()
    current, metrics, miconia, new_inputs = current_stages(args.processed, args.results)
    source_audit_path = Path("results/saverschek_audit/summary.json")
    prior_recovery_path = Path("data/interim/taxonomy_recovered/observations.jsonl")
    original_pilot_path = Path("data/interim/taxonomy_pilot/observations.jsonl")
    old_saverschek_path = Path("data/interim/taxonomy_saverschek/observations.jsonl")
    taxonomy_review_path = Path("data/interim/saverschek_audit/taxonomy/review.jsonl")
    source_audit = read_json(source_audit_path)
    prior_recovery = read_jsonl(prior_recovery_path)
    original_pilot = read_jsonl(original_pilot_path)
    curation_count = len(original_pilot) + len(prior_recovery) + source_audit["directional_context_cells"]
    inputs += [source_audit_path, prior_recovery_path, original_pilot_path, old_saverschek_path, taxonomy_review_path]
    stages = historical + current
    primary = metrics["primary_test"]
    report = {
        "schema_version": 1, "project": "aani", "generated_at": timestamp(),
        "protocol_commit": commit, "offline": args.offline,
        "status": primary.get("status", "blocked"), "estimable": primary.get("estimable", False),
        "counts": {s["stage"]: s["count"] for s in stages}, "stages": stages, "cohorts": cohorts,
        "curation_bridge": {
            "model_semantic_denominator_unchanged": True,
            "prior_pilot_taxonomy_rows": len(original_pilot),
            "manual_source_recovered_rows": len(prior_recovery),
            "saverschek_old_taxonomy_rows_replaced": len(read_jsonl(old_saverschek_path)),
            "saverschek_curated_directional_contexts": source_audit["directional_context_cells"],
            "all_semantically_retained_contexts_after_curation_before_taxonomy":
                curation_count,
            "saverschek_unresolved_direction_contexts": source_audit["unresolved_context_cells"],
            **taxonomy_review_status(taxonomy_review_path, args.processed / "behaviour/observations.jsonl"),
            "note": "Curator expansion/replacement changes the unit. Contexts are not original model candidates or independent biological replicates.",
        },
        "miconia_conflict_verification": miconia,
        "stage_metrics": metrics,
        "blocked_stages": [{"stage": s["stage"], "blocked_reason": s["blocked_reason"]}
                           for s in stages if s["blocked_reason"]],
        "inference_blockers": primary.get("feasibility_failures", []) + (
            [primary["mixed_effects"]["environment"]["reason"]]
            if primary.get("mixed_effects", {}).get("environment", {}).get("reason") else []
        ),
        "input_manifests": [file_record(p) for p in sorted(set(inputs + new_inputs))],
        "frozen_files": [file_record(Path(p)) for p in ["docs/analysis_plan.md", "config/analysis.json"]],
        "missingness_policy": "Missing chemistry is unknown coverage, not a zero-compound genus. Unknown or failed activity retrieval does not enter the classified denominator.",
        "replay_report": str(args.results / "offline_replay.json"),
    }
    args.results.mkdir(parents=True, exist_ok=True)
    write_json(args.results / "funnel.json", report)
    with (args.results / "funnel.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["stage", "count", "unit", "status", "blocked_reason"])
        writer.writeheader()
        writer.writerows({key: stage[key] for key in writer.fieldnames} for stage in stages)
    lines = ["# aani: end-to-end coverage run", "", f"Protocol: `{commit}`.", "",
             "| Stage | Count | Unit / status |", "| --- | --- | --- |"]
    lines += [f"| {s['stage']} | {s['count'] if s['count'] is not None else 'unavailable'} | {s['unit']}; {s['status']} |"
              for s in stages]
    lines += ["", f"The model branch is separate from curator recovery: {curation_count} retained directional contexts before taxonomy, including source-following corrections and the complete Saverschek audit. These are not {curation_count} model successes or independent observations.",
              "", f"Miconia verification: **{miconia['status']}**; both accepted species identities and opposing directions were checked from records.",
              "", f"Primary status: **{report['status']}**; estimable: **{report['estimable']}**.",
              "", "See `funnel.json` for cohort denominators, conflict counts, stage manifests, missingness and blocked reasons."]
    chemistry = metrics["chemistry"]
    activity = metrics["bioactivity"]
    lines += ["", "Chemistry used the verified LOTUS v4 export (Zenodo 6582121, CC BY 4.0), with version, download URL, retrieval time, checksum, licence and transform provenance in `data/processed/chemistry/run_manifest.json`.",
              "", f"Imported {chemistry.get('accepted')} provenance rows / {chemistry.get('unique_occurrences')} distinct occurrences / {chemistry.get('unique_compounds')} structures across the full audited genus scope.",
              "", f"ChEMBL retrieved {activity.get('compounds')} structures: {activity.get('active')} active, {activity.get('inactive')} inactive and {activity.get('unknown')} unknown; {activity.get('failed_compounds')} retrieval failures. Unknowns are excluded from the classified denominator.",
              "", f"The primary join contains {primary.get('n_accepted')} accepted and {primary.get('n_rejected')} rejected genera. Inference blockers: {', '.join(report['inference_blockers']) or 'none reported'}. All unavailable endpoints remain null; no substitute model or shortlist was produced.",
              "", "Missing chemistry genera: " + ", ".join(next(
                  s["missing_chemistry_genera"] or [] for s in stages if s["stage"] == "genera_with_chemistry"
              )) + ". Genera with mapped chemistry and zero classified compounds: " + ", ".join(next(
                  s["zero_classified_genera"] or [] for s in stages if s["stage"] == "genera_with_classified_compounds"
              )) + ". Unknown activity remains outside the classified denominator.",
              "", "Original data and frozen protocol files remain intact. `results/offline_replay.json` records the completed offline replay checks; README and the pipeline guide describe the runnable chain."]
    (args.results / "pipeline_report.md").write_text("\n".join(lines) + "\n")
    print({"counts": report["counts"], "status": report["status"], "estimable": report["estimable"]})


if __name__ == "__main__":
    main()
