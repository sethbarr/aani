"""Replay explicit seeded-monarch semantic and taxonomy-query adjudications."""

import argparse
import json
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.common.io import (
    digest,
    normalise_space,
    read_json,
    read_jsonl,
    timestamp,
    write_json,
    write_jsonl,
)
from src.systems.monarch_infection import (
    Record,
    RecordAdjudication,
    SourceEvidence,
    anchored_evidence,
    apply_explicit_infection_annotations,
    summarize_focal_recovery,
    validate_source_design_annotations,
)


class TaxonomyQuery(BaseModel):
    """An explicit source-grounded expansion of a model's abbreviated binomial."""

    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1)
    rank: Literal["species"]
    reason: str = Field(min_length=1)
    evidence: list[SourceEvidence] = Field(min_length=1)


class SeededAdjudication(RecordAdjudication):
    """An infection adjudication with optional independent taxonomy-query metadata."""

    taxonomy_query: TaxonomyQuery | None = None


def taxonomy_query_metadata(record: Record, query: TaxonomyQuery, jobs: dict[str, Record]) -> Record:
    """Validate a genus expansion and preserve its exact source evidence.

    Args:
        record: Unchanged retained model record.
        query: Explicit full binomial and source evidence.
        jobs: Original extraction jobs indexed by input hash.

    Returns:
        Separate taxonomy-query metadata without changing original names or IDs.

    Raises:
        ValueError: The proposed name changes the epithet or lacks source support.
    """
    original = normalise_space(record["target_name_as_written"]).split()
    expanded = normalise_space(query.name).split()
    if record["taxonomic_rank"] != "species" or len(original) != 2 or len(expanded) != 2:
        raise ValueError("Taxonomy override requires a binomial species name")
    if original[1] != expanded[1] or original[0] not in {expanded[0], expanded[0][0] + "."}:
        raise ValueError("Taxonomy override must preserve the original genus initial and epithet")
    evidence = [anchored_evidence(item, record["source_id"], jobs) for item in query.evidence]
    if not any(normalise_space(query.name) in normalise_space(item["evidence_quote"])
               for item in evidence):
        raise ValueError("Expanded taxonomy name requires an exact same-source quote")
    return {"taxonomy_query_name": query.name, "taxonomy_query_rank": query.rank,
            "taxonomy_query_provenance": query.reason, "taxonomy_query_evidence": evidence}


def apply_seeded_adjudications(
    records: list[Record], jobs: dict[str, Record], adjudications: dict[str, Record]
) -> tuple[list[Record], list[Record]]:
    """Apply infection review and independently validate optional taxonomy expansions.

    Args:
        records: Complete-source grounded model records.
        jobs: Original extraction jobs indexed by input hash.
        adjudications: Exact-cover explicit record reviews.

    Returns:
        Retained records and all decisions, including separate taxonomy metadata.

    Raises:
        ValueError: A review expands records, overrides raw fields or fails evidence checks.
    """
    reviews = {key: SeededAdjudication.model_validate(value)
               for key, value in adjudications.items()}
    if any(review.context_expansions for review in reviews.values()):
        raise ValueError("Seeded rerun does not authorize curator-added model records")
    plain = {key: review.model_dump(exclude={"taxonomy_query"}) for key, review in reviews.items()}
    retained, decisions = apply_explicit_infection_annotations(records, jobs, plain)
    retained_by_id = {row["record_id"]: row for row in retained}
    decisions_by_id = {row["record_id"]: row for row in decisions}
    for record_id, review in reviews.items():
        if review.taxonomy_query is None:
            continue
        if record_id not in retained_by_id:
            raise ValueError("Taxonomy query annotations require an included record")
        row = retained_by_id[record_id]
        metadata = taxonomy_query_metadata(row, review.taxonomy_query, jobs)
        if set(metadata) & set(row):
            raise ValueError("Taxonomy query metadata would overwrite original fields")
        row.update(metadata)
        decisions_by_id[record_id]["taxonomy_query"] = review.taxonomy_query.model_dump()
        decisions_by_id[record_id]["validated_taxonomy_query"] = deepcopy(metadata)
    return retained, decisions


def summarize_seeded_focal_recovery(
    records: list[Record], decisions: list[Record], source_designs: list[Record] | None = None,
) -> Record:
    """Qualify experiment-level coverage with separately counted same-target panels.

    Args:
        records: Retained rows with validated infection and taxonomy-query metadata.
        decisions: Complete original-record review decisions.
        source_designs: Optional independently validated source-design reviews.

    Returns:
        Existing recovery metrics plus explicit pairing units and same-target coverage.
        Unknown directions can supply infection-group coverage without implying preference.
    """
    focal = summarize_focal_recovery(records, decisions, source_designs)
    groups: dict[tuple[str, str, str], set[str]] = {}
    for row in records:
        if (row["record_origin"] != "model_record" or not row["focal_eligible"]
                or row["infection_status"] not in {"infected", "uninfected"}):
            continue
        target = row.get("taxonomy_query_name", row["target_name_as_written"])
        key = (row["source_id"], row["experiment_id"], target)
        groups.setdefault(key, set()).add(row["infection_status"])
    panels = [{"source_id": source_id, "experiment_id": experiment_id, "target_name": target}
              for (source_id, experiment_id, target), statuses in sorted(groups.items())
              if statuses == {"infected", "uninfected"}]
    return {
        **focal,
        "model_pairing_unit": "source_id + experiment_id",
        "model_pairing_interpretation": (
            "Both infection groups occur in original model records from the same reviewed "
            "experiment. Their retained target species may differ."
        ),
        "same_target_pairing_unit": (
            "source_id + experiment_id + validated taxonomy_query_name "
            "(target_name_as_written fallback)"
        ),
        "same_target_model_panel_count": len(panels),
        "same_target_model_panel_recovered": bool(panels),
        "same_target_model_panels": panels,
    }


def run_seeded_semantic_review(root: Path, offline: bool = False) -> Record:
    """Apply or offline-replay an explicit seeded semantic review without model calls.

    Args:
        root: Repository root containing the isolated seeded artifacts.
        offline: Write replay artifacts without changing live review outputs.

    Returns:
        Review metrics with source-design and model-recovery counts separated.

    Raises:
        ValueError: Extraction, payloads, source review or isolation checks fail.
    """
    root = root.resolve()
    live = root / "data/interim/systems/monarch_seeded"
    results = root / "results/systems/monarch_seeded"
    for path in (live, results):
        if path.resolve() != path:
            raise ValueError("Seeded semantic artifact roots cannot be redirected")
    extraction = read_json(live / "extraction/metrics.json")
    if extraction.get("status") != "complete" or extraction.get("incomplete_papers") != 0:
        raise ValueError("Complete-source extraction required before seeded semantic review")
    payloads = live / "extraction_payloads"
    jobs: dict[str, Record] = {}
    for entry in read_json(payloads / "index.json")["jobs"]:
        job = read_json(payloads / f"{entry['input_hash']}.json")
        if digest({key: value for key, value in job.items() if key != "input_hash"}) != entry["input_hash"]:
            raise ValueError("Original extraction payload hash mismatch")
        jobs[entry["input_hash"]] = job
    raw_path = live / "extraction/observations.jsonl"
    records = read_jsonl(raw_path)
    if len(records) != extraction.get("retained_records"):
        raise ValueError("Raw record count differs from complete-source extraction metrics")
    adjudication_path = results / "semantic_adjudications.json"
    adjudications = read_json(adjudication_path)
    retained, decisions = apply_seeded_adjudications(records, jobs, adjudications)
    source_adjudications = read_json(results / "source_design_adjudications.json")
    designs = validate_source_design_annotations(source_adjudications, jobs)
    if designs != read_json(results / "source_design_review.json")["designs"]:
        raise ValueError("Independent source-design review differs from regenerated evidence")
    focal = summarize_seeded_focal_recovery(retained, decisions, designs)
    metrics = {
        "system": "monarch_seeded", "status": "complete", "blocked_reason": None,
        "offline": offline, "input_records": len(records), "included": len(retained),
        "excluded": len(records) - len(retained),
        "infection_status_counts": dict(sorted(Counter(row["infection_status"]
                                                         for row in retained).items())),
        "reviewed_infection_status_counts": dict(sorted(Counter(row["infection_status"]
                                                                  for row in decisions).items())),
        "origin_counts": dict(sorted(Counter(row["record_origin"] for row in retained).items())),
        "focal_recovery": focal,
        "raw_input_path": str(raw_path), "raw_input_sha256": sha256(raw_path.read_bytes()).hexdigest(),
        "adjudications_path": str(adjudication_path), "adjudications_hash": digest(adjudications),
        "source_design_adjudications_hash": digest(source_adjudications),
        "taxonomy_query_expansions": sum("taxonomy_query_name" in row for row in retained),
        "independent_experiment_count": len({(row["source_id"], row["experiment_id"])
                                              for row in retained}),
        "record_count_caveat": (
            "Distinct published analyses of one experiment remain distinct raw model records. "
            "They do not increase the independent experiment count."
        ),
        "analysis_performed": False,
    }
    destination = live / "offline_replay/semantic_review" if offline else live / "semantic_review"
    report_root = results / "offline_replay" if offline else results
    for path, allowed in ((destination, live), (report_root, results)):
        if not path.resolve().is_relative_to(allowed):
            raise ValueError("Semantic review destination leaves the seeded namespace")
    write_jsonl(destination / "observations.jsonl", retained)
    write_jsonl(destination / "decisions.jsonl", decisions)
    write_json(destination / "metrics.json", metrics)
    write_json(report_root / "semantic_review.json", {
        **metrics, "completed_at": timestamp(),
        "method": "Explicit source-reviewed adjudications, deterministic exact evidence validation and preserved raw model records.",
        "decisions": decisions,
    })
    return metrics


def main() -> None:
    """Run the deterministic review or its isolated offline replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_seeded_semantic_review(args.root, args.offline), indent=2))


if __name__ == "__main__":
    main()
