"""Compare a reviewed grounding development run with the immutable saved baseline."""

import hashlib
from collections import Counter
from copy import deepcopy
from pathlib import Path

from src.common.io import read_json
from src.evaluation.recall import candidate_inventory, context_status

BASELINE_COMMIT = "aeb5130341a8c41e0373ad51aabd79b7bbbf3a12"
BASELINE_HASHES = {
    "results/recall_baseline.json": "ce04827287e5be3782dc0be5ac9fe66ad8b1bc46d4d76c3f167088e5c120a48d",
    "results/recall_baseline.md": "2d01e3f36f4a4173980d19db2c4b8f5673091af6abcef9ca1e3fe97b57629afb",
}
REFERENCE_FIELDS = (
    "species", "group", "reference_directions", "provenance_strength",
    "table_membership_dependency", "reference_support", "scorable", "blocked_reason",
)
STAGE_FIELDS = {
    "detection": "proposed_directions",
    "survival": "surviving_directions",
    "correctness": "correct_directions",
}


def file_record(path: Path, expected: str | None = None) -> dict:
    """Record file bytes and an optional immutable expected hash."""
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return {
        "path": str(path), "sha256": actual, "expected_sha256": expected,
        "matches_expected": actual == expected if expected else None,
        "blocked_reason": "file_missing" if actual is None else None,
    }


def baseline_integrity(baseline: dict, root: Path) -> dict:
    """Verify baseline artifacts and every input recorded when the baseline was made."""
    records = [file_record(root / name, expected) for name, expected in BASELINE_HASHES.items()]
    records.extend(file_record(root / row["path"], row["sha256"]) for row in baseline["inputs"])
    unchanged = all(row["matches_expected"] for row in records)
    return {
        "commit": BASELINE_COMMIT, "files": records, "all_original_bytes_unchanged": unchanged,
        "blocked_reason": None if unchanged else "baseline_or_original_input_changed",
    }


def reference_rows(baseline: dict) -> list[dict]:
    """Copy saved reference labels without rebuilding them or changing their provenance."""
    return [{key: deepcopy(row[key]) for key in REFERENCE_FIELDS} for row in baseline["species"]]


def validate_adjudication(candidate: dict, review: dict | None, source: dict) -> dict:
    """Check that a semantic review identifies the candidate and cites exact source spans.

    Args:
        candidate: One reconciled extraction candidate.
        review: Independently authored semantic decision for that candidate.
        source: Complete cached source containing the cited blocks.

    Returns:
        Review metadata and explicit reasons preventing correctness scoring.
    """
    if review is None:
        return {"scorable": False, "blocked_reason": "semantic_adjudication_missing"}
    record = candidate["record"]
    reasons = []
    if review.get("record_digest") != candidate["record_digest"]:
        reasons.append("adjudication_record_digest_mismatch")
    if review.get("species") != record.get("plant_name_as_written"):
        reasons.append("adjudication_species_mismatch")
    if review.get("direction") != record.get("outcome"):
        reasons.append("adjudication_direction_mismatch")
    decision = review.get("decision")
    if decision not in {"correct", "incorrect", "out_of_scope", "unscorable"}:
        reasons.append("adjudication_decision_invalid")
    if not isinstance(review.get("natural_panel"), bool):
        reasons.append("adjudication_panel_scope_missing")
    if decision == "correct" and review.get("natural_panel") is not True:
        reasons.append("correct_decision_outside_natural_panel")
    if decision == "out_of_scope" and review.get("natural_panel") is not False:
        reasons.append("outside_scope_decision_has_panel_scope")
    if not review.get("reason") or not review.get("context"):
        reasons.append("adjudication_reason_or_context_missing")
    anchors = review.get("source_anchors", [])
    roles = {anchor.get("role") for anchor in anchors}
    if not {"direction", "context"}.issubset(roles):
        reasons.append("adjudication_direction_or_context_anchor_missing")
    blocks = {block["block_id"]: block["text"] for block in source["blocks"]}
    for index, anchor in enumerate(anchors):
        quote = anchor.get("evidence_quote")
        if (anchor.get("source_id") != record.get("source_id")
                or anchor.get("source_id") != source.get("source_id")
                or not isinstance(quote, str) or not quote.strip()
                or quote not in blocks.get(anchor.get("block_id"), "")):
            reasons.append(f"adjudication_anchor_unverified:{index + 1}")
    if decision == "unscorable":
        reasons.append(f"semantic_review_unscorable:{review.get('reason', 'reason_missing')}")
    return {
        **deepcopy(review), "scorable": not reasons,
        "blocked_reason": ";".join(reasons) or None,
    }


def directions(candidates: list[dict]) -> list[str]:
    """Collect emitted structured outcomes without inferring outcomes from quote words."""
    return sorted({row["record"].get("outcome") for row in candidates
                   if row["record"].get("outcome") in {"accepted", "rejected"}})


def score_development_species(reference: dict, candidates: list[dict], reviews: dict,
                              source: dict, inventory_reason: str | None = None) -> dict:
    """Score raw presence and grounding separately from reviewed natural-panel correctness."""
    selected = [row for row in candidates
                if row["record"].get("plant_name_as_written") == reference["species"]]
    surviving = [row for row in selected if row["grounding_status"] == "passed"]
    assessed = [
        {"candidate_id": row["candidate_id"], **validate_adjudication(
            row, reviews.get(row["candidate_id"]), source)} for row in surviving
    ]
    review_by_id = {row["candidate_id"]: row for row in assessed}
    correct_candidates = [row for row in surviving if review_by_id[row["candidate_id"]]["scorable"]
                          and review_by_id[row["candidate_id"]].get("decision") == "correct"
                          and review_by_id[row["candidate_id"]].get("natural_panel") is True]
    stage_reasons = {stage: [] for stage in STAGE_FIELDS}
    if inventory_reason:
        for reasons in stage_reasons.values():
            reasons.append(inventory_reason)
    for row in selected:
        if row["blocked_reason"]:
            stage_reasons["survival"].append(row["blocked_reason"])
            stage_reasons["correctness"].append(row["blocked_reason"])
    if not reference["scorable"]:
        stage_reasons["correctness"].append(reference["blocked_reason"] or "reference_unscorable")
    for review in assessed:
        if review["blocked_reason"]:
            stage_reasons["correctness"].append(
                f"{review['candidate_id']}:{review['blocked_reason']}"
            )
    proposed = directions(selected)
    retained = directions(surviving)
    correct = sorted(set(directions(correct_candidates)) & set(reference["reference_directions"]))
    stage_scorable = {stage: not reasons for stage, reasons in stage_reasons.items()}
    row = {
        **deepcopy(reference), "scorable": all(stage_scorable.values()),
        "blocked_reason": ";".join(sorted({r for rs in stage_reasons.values() for r in rs})) or None,
        "stage_scorable": stage_scorable,
        "stage_blocked_reason": {stage: ";".join(reasons) or None
                                 for stage, reasons in stage_reasons.items()},
        "candidate_ids": [c["candidate_id"] for c in selected],
        "surviving_candidate_ids": [c["candidate_id"] for c in surviving],
        "adjudications": assessed,
        "detection": bool(selected) if stage_scorable["detection"] else None,
        "survival": bool(surviving) if stage_scorable["survival"] else None,
        "correctness": bool(correct) if stage_scorable["correctness"] else None,
        "proposed_directions": proposed, "surviving_directions": retained,
        "correct_directions": correct if stage_scorable["correctness"] else [],
        "provisional_direction_matches": sorted(set(retained) & set(reference["reference_directions"])),
        "context_stages": None,
    }
    if reference["group"] == "CONTEXT":
        row["context_stages"] = {
            stage: context_status(row[field]) if stage_scorable[stage] else "unscorable"
            for stage, field in STAGE_FIELDS.items()
        }
    return row


def summarise_development_group(rows: list[dict], group: str) -> dict:
    """Keep fixed group denominators and stage-specific unknown coverage visible."""
    selected = [row for row in rows if row["group"] == group]
    result = {
        "species_denominator": len(selected),
        "species_direction_pair_denominator": sum(len(r["reference_directions"]) for r in selected),
        "reference_provenance_species": {
            strength: sum(row["provenance_strength"] == strength for row in selected)
            for strength in ("author_prose", "author_table_grouping")
        },
        "stages": {},
    }
    for stage, field in STAGE_FIELDS.items():
        known = [row for row in selected if row["stage_scorable"][stage]]
        unknown = [row["species"] for row in selected if not row["stage_scorable"][stage]]
        stage_result = {
            "species_count": sum(bool(row[stage]) for row in known),
            "species_direction_pair_count": sum(
                len(set(row[field]) & set(row["reference_directions"])) for row in known
            ),
            "unscorable_species": unknown,
            "complete": not unknown,
            "count_interpretation": "complete_count" if not unknown else "scored_species_only",
        }
        if group == "CONTEXT":
            counts = Counter(row["context_stages"][stage] for row in selected)
            stage_result["direction_coverage"] = {
                status: counts[status] for status in (
                    "both_directions_surfaced", "collapsed_to_one", "absent", "unscorable"
                )
            }
        result["stages"][stage] = stage_result
    return result


def source_from_baseline(baseline: dict, root: Path) -> dict:
    """Read the cached paper identified by the frozen baseline's source input."""
    source_name = f"{baseline['source_id']}.json"
    source_paths = [root / row["path"] for row in baseline["inputs"]
                    if Path(row["path"]).name == source_name]
    if len(source_paths) != 1:
        raise ValueError("baseline_cached_source_not_unique")
    return read_json(source_paths[0])


def load_adjudications(path: Path | None) -> tuple[dict, dict]:
    """Load reviewer decisions with an explicit blocked status when none are supplied."""
    if path is None:
        return {}, {"blocked_reason": "semantic_adjudication_not_supplied", "reviewer": None}
    if not path.is_file():
        return {}, {"blocked_reason": "semantic_adjudication_file_missing", "file": file_record(path)}
    data = read_json(path)
    if data.get("schema_version") != 1 or not isinstance(data.get("candidates"), dict):
        return {}, {"blocked_reason": "semantic_adjudication_schema_invalid", "file": file_record(path)}
    if not data.get("reviewer") or not data.get("method"):
        return {}, {"blocked_reason": "semantic_adjudication_reviewer_or_method_missing",
                    "file": file_record(path)}
    return data["candidates"], {
        "file": file_record(path), "reviewer": data["reviewer"], "method": data["method"],
        "blocked_reason": None,
    }


def development_inventory(extraction: Path) -> tuple[list[dict], dict]:
    """Block incomplete saved runs even when their available candidates reconcile."""
    names = ("observations.jsonl", "rejections.jsonl", "metrics.json")
    missing = [str(extraction / name) for name in names if not (extraction / name).is_file()]
    if missing:
        return [], {
            "candidate_records": None, "grounding_passes": None, "grounding_failures": None,
            "reconciled_with_original_artifacts": False, "missing_artifacts": missing,
            "blocked_reason": "development_extraction_artifacts_missing",
        }
    candidates, inventory = candidate_inventory(extraction)
    metrics = read_json(extraction / "metrics.json")
    completion_fields = ("response_failures", "unattempted_chunks", "incomplete_papers")
    reasons = [f"development_run_{field}:{metrics[field]}" for field in completion_fields
               if metrics.get(field, 0) != 0]
    if metrics.get("blocked_reason") is not None:
        reasons.append(f"development_run_blocked:{metrics['blocked_reason']}")
    inventory["run_completeness"] = {
        field: metrics.get(field) for field in (*completion_fields, "blocked_reason")
    }
    inventory["run_complete"] = not reasons
    if inventory["blocked_reason"]:
        reasons.insert(0, inventory["blocked_reason"])
    inventory["blocked_reason"] = ";".join(reasons) or None
    return candidates, inventory


def build_comparison(extraction: Path, root: Path, adjudication: Path | None = None) -> dict:
    """Assemble unchanged baseline counts and independently reviewed development counts."""
    baseline = read_json(root / "results/recall_baseline.json")
    integrity = baseline_integrity(baseline, root)
    source = source_from_baseline(baseline, root)
    candidates, inventory = development_inventory(extraction)
    reviews, review_metadata = load_adjudications(adjudication)
    reason = integrity["blocked_reason"] or inventory["blocked_reason"]
    rows = [score_development_species(row, candidates, reviews, source, reason)
            for row in reference_rows(baseline)]
    groups = {group: summarise_development_group(rows, group) for group in ("PRIMARY", "CONTEXT")}
    panel_names = {row["species"] for row in rows}
    scoped = [row for row in candidates if row["record"].get("plant_name_as_written") in panel_names]
    required_ids = {row["candidate_id"] for row in scoped if row["grounding_status"] == "passed"}
    if not required_ids and inventory["blocked_reason"] is None:
        review_metadata = {
            "status": "not_required_no_surviving_panel_candidates", "blocked_reason": None,
            "reviewer": None, "method": None, "semantic_review_performed": False,
        }
    else:
        review_metadata["status"] = "blocked" if review_metadata["blocked_reason"] else "provided"
    unknown_ids = sorted(set(reviews) - {row["candidate_id"] for row in candidates})
    manifest_path = extraction / "run_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else None
    reasons = sorted({row["blocked_reason"] for row in rows if row["blocked_reason"]})
    if unknown_ids:
        reasons.append("adjudication_contains_unknown_candidate_ids")
    if manifest is None:
        reasons.append("development_run_manifest_missing")
    paths = [extraction / name for name in ("observations.jsonl", "rejections.jsonl", "metrics.json")]
    paths.extend(sorted((extraction / "responses").glob("*.json")))
    return {
        "schema_version": 1, "set_type": "DEVELOPMENT SET", "unit": "species-direction pair",
        "source_id": baseline["source_id"], "panel_species_denominator": 11,
        "panel_species_direction_pair_denominator": 16,
        "sampling_scope": baseline["sampling_scope"],
        "status": "complete" if not reasons else "partially_blocked",
        "blocked_reason": ";".join(reasons) or None,
        "baseline_integrity": integrity,
        "baseline": {"groups": deepcopy(baseline["groups"]),
                     "correctness_definition": "Saved baseline structured-direction matches; unchanged."},
        "development": {
            "extraction": str(extraction), "manifest": manifest,
            "manifest_file": file_record(manifest_path), "files": [file_record(path) for path in paths],
            "inventory": {**inventory, "panel_name_candidates": len(scoped),
                          "outside_panel_name_candidates": len(candidates) - len(scoped)},
            "groups": groups, "species": rows, "candidates": candidates,
        },
        "adjudication": {
            **review_metadata, "required_surviving_panel_candidates": len(required_ids),
            "missing_candidate_ids": sorted(required_ids - set(reviews)),
            "unknown_candidate_ids": unknown_ids,
            "all_surviving_panel_candidates_scorable": all(
                row["stage_scorable"]["correctness"] for row in rows
            ),
        },
        "direction_scoring": "Raw detection and survival use structured species and outcome fields. "
        "Correctness requires a complete semantic review of each surviving candidate for a species, "
        "natural-panel membership, a matching reference direction, and exact direction/context anchors. "
        "Quote words never create additional outcomes. Automatic direction matches are provisional.",
        "contamination_risk": "The curator matrix was produced by reading the same text blocks the "
        "extractor read, so shared blind spots would inflate apparent recall. The curator had the "
        "complete cached text including tables; the original extractor worked chunk-wise under a "
        "strict quote constraint. The reference was known during development, which adds direct "
        "development-set contamination. This run provides no independent generalization estimate.",
    }


def render_comparison(report: dict) -> str:
    """Render stage counts, provenance and review limitations for the development panel."""
    lines = [
        "# Grounding development comparison — DEVELOPMENT SET", "",
        "This is one panel from one paper and is not a sample from any population. PRIMARY has "
        "six species-direction pairs across six species. CONTEXT has ten pairs across five species. "
        "The groups retain their separate denominators.", "",
        "| Run / stage | PRIMARY species | PRIMARY pairs | CONTEXT both | CONTEXT collapsed | "
        "CONTEXT absent | CONTEXT unscorable | CONTEXT pairs |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, groups in (("Baseline", report["baseline"]["groups"]),
                         ("Development", report["development"]["groups"])):
        for stage in STAGE_FIELDS:
            primary = groups["PRIMARY"]["stages"][stage]
            context = groups["CONTEXT"]["stages"][stage]
            coverage = context["direction_coverage"]
            complete = primary.get("complete", True) and context.get("complete", True)
            suffix = " (partial)" if not complete else ""
            lines.append(
                f"| {name} {stage}{suffix} | {primary['species_count']} of 6 | "
                f"{primary['species_direction_pair_count']} of 6 | "
                f"{coverage['both_directions_surfaced']} of 5 | "
                f"{coverage['collapsed_to_one']} of 5 | {coverage['absent']} of 5 | "
                f"{coverage['unscorable']} of 5 | {context['species_direction_pair_count']} of 10 |"
            )
    if report["adjudication"]["status"] == "not_required_no_surviving_panel_candidates":
        lines += [
            "", "The completed development run has zero surviving panel candidates. Its correctness "
            "counts are zero because no candidate survived grounding. Surviving-record semantic "
            "adjudication was unnecessary and was not performed; diagnostic source review of "
            "rejected records is recorded separately.",
        ]
    lines += [
        "", "Detection counts any raw candidate bearing the species name. Survival counts candidates "
        "that passed grounding. Development correctness counts independently reviewed records with "
        "matching species, direction and natural-panel context; each review cites exact cached source "
        "anchors. The saved baseline correctness counts remain unchanged and used structured-direction "
        "matching. This difference in review depth limits direct correctness comparisons. Automatic "
        "direction matches appear separately in JSON as provisional. An additional direction in a "
        "quote receives credit only when emitted as its own structured outcome.", "",
        "| Species | Group | Reference | Detected | Survived | Reviewed correct directions | "
        "Correctness status |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["development"]["species"]:
        status = "scored" if row["stage_scorable"]["correctness"] else "unscorable"
        correct = (", ".join(row["correct_directions"]) or "absent") if status == "scored" else status
        lines.append(
            f"| {row['species']} | {row['group']} | {', '.join(row['reference_directions'])} | "
            f"{row['detection']} | {row['survival']} | "
            f"{correct} | {status} |"
        )
    primary = report["development"]["groups"]["PRIMARY"]["reference_provenance_species"]
    context = report["development"]["groups"]["CONTEXT"]["reference_provenance_species"]
    lines += [
        "", f"Reference provenance is unchanged: PRIMARY has {primary['author_prose']} author_prose "
        f"and {primary['author_table_grouping']} author_table_grouping species; CONTEXT has "
        f"{context['author_prose']} author_prose and {context['author_table_grouping']} "
        f"author_table_grouping species. "
        "The numerical table transcription was never visually verified against the PDF, so "
        "table-derived labels are weaker ground truth. All reference labels and provenance tags "
        "come directly from the saved baseline.", "", report["contamination_risk"], "",
    ]
    for group, data in report["development"]["groups"].items():
        for stage, result in data["stages"].items():
            if result["unscorable_species"]:
                lines.append(f"{group} {stage} unscorable: {', '.join(result['unscorable_species'])}. "
                             "Counts include only scored species; the fixed denominator is retained.")
                lines.append("")
    inventory = report["development"]["inventory"]
    lines += [
        f"The development inventory has {inventory['candidate_records']} candidates, "
        f"{inventory['grounding_passes']} grounding passes and {inventory['grounding_failures']} "
        "grounding failures. Candidate retention counts are stage yields. The broader nine-of-41 "
        "semantic-retention count is also a stage yield.", "",
        f"Original baseline artifacts and recorded inputs unchanged: "
        f"{report['baseline_integrity']['all_original_bytes_unchanged']}. "
        "JSON records the baseline commit, expected and observed hashes, development manifest, "
        "per-candidate semantic decisions and exact source anchors.", "",
        f"Comparison status: {report['status']}. "
        f"Blocked reason: {report['blocked_reason'] or 'none'}.", "",
    ]
    return "\n".join(lines)
