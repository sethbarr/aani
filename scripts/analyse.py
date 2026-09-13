"""Run the frozen analysis with explicit feasibility and missing-input gates."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.dataset import aggregate_behaviour, build_dataset, csv_ready
from src.analysis.models import model_environment, run_mixed_effects
from src.analysis.protocol import committed_protocol
from src.analysis.shortlist import rank_candidates
from src.analysis.statistics import permutation_test
from src.common.io import read_json, read_jsonl, timestamp, write_json, write_jsonl

GENUS_COLUMNS = [
    "genus", "family", "rejected", "n_sources", "n_ant_species", "n_observations",
    "source_ids", "source_urls", "behaviour_record_ids", "accepted_names",
    "phytochemistry_records", "species_match_fraction", "n_compounds", "n_classified",
    "n_active", "n_unknown", "hit_fraction", "assay_coverage", "documented_active_fraction",
    "compound_ids", "occurrence_references",
]
COMPOUND_COLUMNS = [
    "genus", "family", "compound_id", "rejected", "active", "phytochemistry_records",
    "species_match_fraction",
]


def read_input(path: Path) -> tuple[list[dict] | None, dict]:
    """Read an input table or return an explicit unavailable-input descriptor."""
    if not path.is_file():
        return None, {"path": str(path), "sha256": None, "blocked_reason": "input_file_missing"}
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        rows = read_jsonl(path)
    except (ValueError, OSError) as error:
        return None, {"path": str(path), "sha256": checksum, "blocked_reason": str(error)}
    return rows, {"path": str(path), "sha256": checksum, "rows": len(rows), "blocked_reason": None}


def read_stage_metrics(path: Path | None) -> dict:
    """Read optional upstream metrics without assuming absent stages succeeded."""
    if path is None:
        return {}
    if not path.is_file():
        return {"status": "blocked", "blocked_reason": f"metrics_file_missing:{path}"}
    return read_json(path)


def blocked_summary(reasons: list[str], environment: dict) -> dict:
    """Describe an unavailable join without inventing measured zero counts."""
    return {
        "status": "feasibility_failure",
        "estimable": False,
        "execution_status": "blocked",
        "blocked_reason": ";".join(reasons),
        "n_genera": None,
        "n_rejected": None,
        "n_accepted": None,
        "observed_difference": None,
        "rejected_mean": None,
        "accepted_mean": None,
        "p_one_sided": None,
        "descriptive_bootstrap_95_interval": None,
        "permutations": 0,
        "zero_classified_genera": None,
        "n_classified_structures": None,
        "mixed_effects": {
            "status": "not_estimable", "estimable": False,
            "reason": "upstream_input_unavailable", "environment": environment,
        },
    }


def ensure_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Preserve an empty table's schema and all populated provenance columns."""
    return frame if not frame.empty else pd.DataFrame(columns=columns)


def coverage_counts(
    observations: list[dict], occurrences: list[dict], labels: list[dict],
    evidence: set[str] | None = None, delayed_only: bool = False,
    exclude_discordant: bool = False,
) -> dict:
    """Count observed join coverage with unknown labels excluded from classification."""
    genera, review = aggregate_behaviour(observations, evidence, delayed_only)
    eligible = {row["genus"] for row in genera}
    conflict = {
        row["genus"] for row in review
        if row["exclusion_reason"] == "conflicting_genus_direction_or_family"
    }
    with_chemistry = {row["genus"] for row in occurrences} & eligible
    classified = {
        row["compound_id"] for row in labels
        if row["label"] in {"active", "inactive"} and row.get("retrieval_status") != "failed"
        and not (exclude_discordant and row.get("discordant"))
    }
    with_classified = {
        row["genus"] for row in occurrences if row["compound_id"] in classified
    } & eligible
    mapped = {row["compound_id"] for row in occurrences if row["genus"] in eligible}
    retrieved = {
        row["compound_id"] for row in labels if row.get("retrieval_status") == "complete"
    }
    return {
        "genera_after_aggregation": len(eligible),
        "conflicting_genera": len(conflict),
        "genera_with_chemistry": len(with_chemistry),
        "genera_missing_chemistry": len(eligible - with_chemistry),
        "genera_with_classified_compound": len(with_classified),
        "genera_with_zero_classified_compounds": len(with_chemistry - with_classified),
        "genera_available_for_primary_test": len(with_classified),
        "activity_retrieval_complete": not (mapped - retrieved),
        "unretrieved_mapped_compounds": len(mapped - retrieved),
    }


def write_analysis_subset(
    name: str, observations: list[dict], occurrences: list[dict], labels: list[dict],
    config: dict, output: Path, processed: Path, environment: dict,
) -> dict:
    """Write one independently reaggregated sensitivity and its feasibility result."""
    evidence = set(config["experimental_evidence"]) if name == "experimental" else None
    genera, compounds, review = build_dataset(
        observations, occurrences, labels, evidence, name == "delayed", name == "nondiscordant"
    )
    genera = ensure_columns(genera, GENUS_COLUMNS)
    compounds = ensure_columns(compounds, COMPOUND_COLUMNS)
    destination = output / name
    destination.mkdir(parents=True, exist_ok=True)
    csv_ready(genera).to_csv(destination / "genera.csv", index=False)
    compounds.to_csv(destination / "compounds.csv", index=False)
    write_jsonl(destination / "review.jsonl", review)
    prepared = processed / name
    write_jsonl(prepared / "genera.jsonl", genera.to_dict("records"))
    write_jsonl(prepared / "compounds.jsonl", compounds.to_dict("records"))
    write_jsonl(prepared / "review.jsonl", review)
    summary, null = permutation_test(genera, config)
    summary.update(coverage_counts(
        observations, occurrences, labels, evidence, name == "delayed", name == "nondiscordant"
    ))
    summary["sensitivity_support_complete"] = summary["activity_retrieval_complete"]
    summary["execution_status"] = "complete"
    summary["blocked_reason"] = None
    summary["zero_classified_genera"] = sum(
        row.get("exclusion_reason") == "no_classified_compounds" for row in review
    )
    family_summary, family_null = permutation_test(genera, config, within_family=True)
    summary["within_family_sensitivity"] = family_summary
    np.save(destination / "null.npy", null)
    np.save(destination / "family_null.npy", family_null)
    if name in {"primary", "experimental"}:
        summary["mixed_effects"] = (
            run_mixed_effects(compounds, destination / "mixed_effects")
            if summary["estimable"] else {
                "status": "not_estimable", "estimable": False,
                "reason": "prespecified_feasibility_gate", "environment": environment,
            }
        )
    if name == "primary":
        count = int(compounds["compound_id"].nunique())
        summary["n_classified_structures"] = count
        if summary["estimable"] and len(null):
            from src.analysis.figure import plot_enrichment

            plot_enrichment(summary, null, output / "figures/enrichment.png", count)
        if summary["estimable"]:
            shortlist, shortlist_status = rank_candidates(genera, occurrences, labels)
        else:
            shortlist = pd.DataFrame(columns=["genus", "shortlist_score"])
            shortlist_status = {
                "status": "not_estimable", "reason": "prespecified_feasibility_gate",
                "ranked_genera": 0,
            }
        csv_ready(shortlist).to_csv(output / "candidate_genera.csv", index=False)
        summary["shortlist"] = shortlist_status
    write_json(destination / "summary.json", summary)
    return summary


def run_analysis(
    observations_path: Path, occurrences_path: Path, labels_path: Path, output: Path,
    processed: Path, occurrence_metrics_path: Path | None = None,
    label_metrics_path: Path | None = None, offline: bool = False,
) -> dict:
    """Run local analysis or emit blocked artifacts while preserving unknown coverage."""
    output.mkdir(parents=True, exist_ok=True)
    config = read_json(Path("config/analysis.json"))
    environment = model_environment()
    reasons = []
    try:
        commit = committed_protocol(Path.cwd())
    except (RuntimeError, OSError) as error:
        commit = None
        reasons.append(f"protocol_verification_failed:{error}")
    tables = []
    inputs = {}
    for role, path in (
        ("observations", observations_path), ("occurrences", occurrences_path), ("labels", labels_path)
    ):
        rows, descriptor = read_input(path)
        tables.append(rows)
        inputs[role] = descriptor
        if descriptor["blocked_reason"]:
            reasons.append(f"{role}:{descriptor['blocked_reason']}")
    upstream = {
        "chemistry": read_stage_metrics(occurrence_metrics_path),
        "bioactivity": read_stage_metrics(label_metrics_path),
    }
    for stage, metrics in upstream.items():
        if metrics.get("status") == "blocked" or metrics.get("blocked_reason"):
            reasons.append(f"{stage}:{metrics.get('blocked_reason') or 'upstream_stage_blocked'}")
    summaries = {}
    for name in ("primary", "experimental", "delayed", "nondiscordant"):
        if reasons:
            summary = blocked_summary(reasons, environment)
            destination = output / name
            destination.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(columns=GENUS_COLUMNS).to_csv(destination / "genera.csv", index=False)
            pd.DataFrame(columns=COMPOUND_COLUMNS).to_csv(destination / "compounds.csv", index=False)
            review = [{"exclusion_reason": "upstream_input_unavailable", "details": reasons}]
            write_jsonl(destination / "review.jsonl", review)
            write_jsonl(processed / name / "genera.jsonl", [])
            write_jsonl(processed / name / "compounds.jsonl", [])
            write_jsonl(processed / name / "review.jsonl", review)
            np.save(destination / "null.npy", np.array([]))
            np.save(destination / "family_null.npy", np.array([]))
            write_json(destination / "summary.json", summary)
        else:
            summary = write_analysis_subset(
                name, tables[0], tables[1], tables[2], config, output, processed, environment
            )
        summaries[name] = summary
    counts = (
        {key: None for key in (
            "genera_after_aggregation", "conflicting_genera", "genera_with_chemistry",
            "genera_missing_chemistry", "genera_with_classified_compound",
            "genera_with_zero_classified_compounds", "genera_available_for_primary_test",
        )}
        if reasons else coverage_counts(tables[0], tables[1], tables[2])
    )
    metrics = {
        "status": "blocked" if reasons else "complete",
        "blocked_reason": ";".join(reasons) if reasons else None,
        **counts,
        "primary_status": summaries["primary"]["status"],
        "primary_estimable": summaries["primary"]["estimable"],
        "model_environment": environment,
    }
    provenance = {
        "protocol_commit": commit,
        "completed_at": timestamp(),
        "offline": offline,
        "network_requests": 0,
        "config": config,
        "inputs": inputs,
        "input_hashes": {row["path"]: row["sha256"] for row in inputs.values()},
        "upstream_metrics": upstream,
        "reporting_rule": "No test or shortlist below 25 joined genera or two genera per direction.",
        "model_environment": environment,
    }
    write_json(output / "run_manifest.json", provenance)
    write_json(output / "metrics.json", metrics)
    write_json(output / "summary.json", summaries)
    return metrics


def main() -> None:
    """Generate audited coverage and feasibility artifacts from prepared inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, default=Path("data/interim/taxonomy/observations.jsonl"))
    parser.add_argument("--occurrences", type=Path, default=Path("data/interim/chemistry/occurrences.jsonl"))
    parser.add_argument("--labels", type=Path, default=Path("data/interim/bioactivity/labels.jsonl"))
    parser.add_argument("--occurrence-metrics", type=Path)
    parser.add_argument("--label-metrics", type=Path)
    parser.add_argument("--output", type=Path, default=Path("results"))
    parser.add_argument("--processed", type=Path, default=Path("data/processed/analysis"))
    parser.add_argument("--offline", action="store_true", help="Confirm local-only replay; analysis never makes network calls.")
    args = parser.parse_args()
    metrics = run_analysis(
        args.observations, args.occurrences, args.labels, args.output, args.processed,
        args.occurrence_metrics, args.label_metrics, args.offline,
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
