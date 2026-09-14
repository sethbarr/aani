"""Apply explicit attine semantic adjudications and score the fixed source controls."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from src.common.io import digest, normalise_space, read_json, read_jsonl, write_json, write_jsonl

REFERENCE_SOURCE_IDS = {"10.1038/19519": "CURRIE1999", "10.1038/nchembio.159": "PMC2748230"}
REVIEW_VERSION = "attine_semantic_review_v1"

# These are explicit reviews of the immutable 2026-09-13 model records. Reuse
# the functions with a new complete adjudication mapping for another run.
ADJUDICATIONS = {
    "49142d6591b7ccfb3bdb373a032206e7af8426e580537c266e58e641def1a55e": {
        "decision": "include",
        "reason_codes": [],
        "evidence_role": "direct_primary",
        "host_identity_grounding": "quote",
        "producer_relation_supported": True,
        "compound_relation_supported": True,
        "activity_relation_supported": True,
        "direction_supported": True,
        "note": "The quote links the cuticular Pseudonocardia isolate from Apterostigma dentigerum, assay-guided identification of dentigerumycin, and Escovopsis inhibition in one contiguous source passage.",
    },
    "329abdd3e6632d8d109922fc803f0d69b4d7ee7b947f565b96e5276b798bebf2": {
        "decision": "include",
        "reason_codes": [],
        "evidence_role": "secondary",
        "host_identity_grounding": "same_source_block",
        "producer_relation_supported": True,
        "compound_relation_supported": True,
        "activity_relation_supported": True,
        "direction_supported": True,
        "note": "The quote directly reports colonization of worker cuticle and production of compounds inhibiting Escovopsis. The host wording Fungus-growing ants (subtribe Attini) occurs in the opening sentence of this same block. No compound identity was extracted, so the row supports association and activity coverage only.",
    },
    "71f57e3566ef0fa46aa3db44d3f838613e53303a9928d7d2fa7d50fd0c718a15": {
        "decision": "exclude",
        "reason_codes": ["activity_outcome_not_stated"],
        "evidence_role": "study_aim",
        "host_identity_grounding": "quote",
        "producer_relation_supported": True,
        "compound_relation_supported": True,
        "activity_relation_supported": False,
        "direction_supported": True,
        "note": "The sentence describes investigating antimicrobial variation and microbial interactions. It does not report suppression of Escovopsis. The full raw record is excluded without changing its activity field.",
    },
    "6d6b5479a3f72359c788bbf01215728695d395b9cd1a2a3dfa53ca5672cf28c1": {
        "decision": "exclude",
        "reason_codes": ["compound_identity_overstated"],
        "evidence_role": "secondary",
        "host_identity_grounding": "quote",
        "producer_relation_supported": True,
        "compound_relation_supported": False,
        "activity_relation_supported": True,
        "direction_supported": True,
        "note": "The sentence reports dentigerumycin analogs, including dentigerumycin F, and describes the cyclic depsipeptide family. The extracted parent identity dentigerumycin collapses this compound distinction. This is a related secondary mention and cannot establish recovery of the named Oh compound.",
    },
    "b909994a2d7f929467c79b5e6d595c69b57dc1a5214aea5d565845526dfca15b": {
        "decision": "exclude",
        "reason_codes": ["activity_target_not_in_quote", "activity_outcome_not_stated"],
        "evidence_role": "secondary",
        "host_identity_grounding": "source_context",
        "producer_relation_supported": True,
        "compound_relation_supported": True,
        "activity_relation_supported": False,
        "direction_supported": True,
        "note": "The quote states that Pseudonocardia are ant symbionts. It contains neither Escovopsis weberi nor a report of suppression.",
    },
    "e6dbd8242865c85c5ac38cabcd186e68d13787d22407c5fa6c2161f069f2a019": {
        "decision": "exclude",
        "reason_codes": ["protection_does_not_specify_growth_suppression"],
        "evidence_role": "secondary",
        "host_identity_grounding": "quote",
        "producer_relation_supported": True,
        "compound_relation_supported": True,
        "activity_relation_supported": False,
        "direction_supported": True,
        "note": "The quote describes an antibiotic-producing ectosymbiont that helps protect gardens from Escovopsis. This ecological protection wording does not itself specify the extracted growth-suppression outcome.",
    },
    "97376a7596dee491b5d00cab9be98be51d9e44e3084f31062f8116d9cb7ccb52": {
        "decision": "include",
        "reason_codes": [],
        "evidence_role": "secondary",
        "host_identity_grounding": "quote",
        "producer_relation_supported": True,
        "compound_relation_supported": True,
        "activity_relation_supported": True,
        "direction_supported": True,
        "note": "The quote cites inhibitory activity by Pseudonocardia isolated from Trachymyrmex ants against Escovopsis. Its qualifier may have is retained in the quote and this remains a qualified secondary report. No compound identity was extracted.",
    },
    "b1527d731386132cd7bbf13a800f1dbdcdd288981ab10637ba104a8db9e39d9e": {
        "decision": "include",
        "reason_codes": [],
        "evidence_role": "secondary",
        "host_identity_grounding": "quote",
        "producer_relation_supported": True,
        "compound_relation_supported": True,
        "activity_relation_supported": True,
        "direction_supported": True,
        "note": "The quote describes increased Pseudonocardia coverage on workers associated with Escovopsis presence. The extracted activity outcome is unknown and the compound field is null, preserving the limited claim.",
    },
    "8d3be3a7f056c9ad459bda876e98cdd2f5b1df268ce6c1a2c0544885a8528309": {
        "decision": "include",
        "reason_codes": [],
        "evidence_role": "direct_primary",
        "host_identity_grounding": "same_source_block",
        "producer_relation_supported": True,
        "compound_relation_supported": True,
        "activity_relation_supported": True,
        "direction_supported": True,
        "note": "The quote reports visible Pseudonocardia on the Acromyrmex study species. The opening sentence of this same block identifies these as leaf-cutter ants. It supports a direct association observation; the row has no compound or activity claim and behavioural_choice remains false.",
    },
    "2de86549feb977111a081ab1060385ef5f9af7bdc1065c6ea810826f08cdecbe": {
        "decision": "exclude",
        "reason_codes": [
            "reject_comparison_absent_from_quote",
            "secondary_statement_labeled_observational",
        ],
        "evidence_role": "secondary",
        "host_identity_grounding": "quote",
        "producer_relation_supported": True,
        "compound_relation_supported": True,
        "activity_relation_supported": True,
        "direction_supported": False,
        "note": "The quoted sentence cites general absence of Pseudonocardia in Atta and its resulting inability to transmit the bacterium. The full block describes a cross-fostering experiment, but this quote does not report the controlled comparison required for the configured reject direction. Citation 43 also marks this sentence as secondary support.",
    },
}


def file_sha256(path: Path) -> str:
    """Hash the complete artifact bytes used in the review."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_checks(record: dict, job: dict, adjudication: dict) -> list[str]:
    """Verify quote, field grounding, and the explicit reviewed relation decisions."""
    issues = []
    blocks = {block["block_id"]: block for block in job["blocks"]}
    block = blocks.get(record["block_id"])
    if record["source_id"] != job["source_id"] or block is None:
        return ["unknown_source_or_block"]
    quote = normalise_space(record["evidence_quote"])
    if not quote or quote not in normalise_space(block["text"]):
        issues.append("ungrounded_quote")
    if record["section"] != block["section"]:
        issues.append("section_mismatch")
    for field, reason in (
        ("target_name_as_written", "producer_not_in_quote"),
        ("compound_name_as_written", "compound_not_in_quote"),
        ("activity_target_as_written", "activity_target_not_in_quote"),
    ):
        if record.get(field) and normalise_space(record[field]) not in quote:
            issues.append(reason)
    host_scope = adjudication.get("host_identity_grounding")
    host = normalise_space(record["behaving_organism_as_written"])
    if host_scope == "quote" and host not in quote:
        issues.append("host_not_in_quote")
    if host_scope == "same_source_block" and host not in normalise_space(block["text"]):
        issues.append("host_not_in_source_block")
    for check in (
        "producer_relation_supported",
        "compound_relation_supported",
        "activity_relation_supported",
        "direction_supported",
    ):
        if adjudication.get(check) is not True:
            issues.append(check.removesuffix("_supported") + "_unsupported")
    return sorted(set(issues + adjudication.get("reason_codes", [])))


def apply_adjudications(
    records: list[dict], jobs: dict[str, dict], adjudications: dict[str, dict]
) -> tuple[list[dict], list[dict]]:
    """Require one explicit review per record and retain raw fields in inclusions."""
    ids = {row["record_id"] for row in records}
    if len(ids) != len(records) or ids != set(adjudications):
        raise ValueError("Adjudications must cover exactly the unique grounded records")
    retained, decisions = [], []
    for record in records:
        review = adjudications[record["record_id"]]
        if review["decision"] not in {"include", "exclude"}:
            raise ValueError("Explicit semantic include/exclude decision required")
        job = jobs[record["input_hash"]]
        issues = semantic_checks(record, job, review)
        if review["decision"] == "include" and issues:
            raise ValueError(
                f"Included record fails semantic checks: {record['record_id']}: {issues}"
            )
        decision = {
            "record_id": record["record_id"],
            "raw_record_hash": digest(record),
            "source_id": record["source_id"],
            "input_hash": record["input_hash"],
            "block_id": record["block_id"],
            "quote": record["evidence_quote"],
            **review,
            "checks": {"issues": issues},
        }
        decisions.append(decision)
        if review["decision"] == "include":
            retained.append(
                {
                    **record,
                    "semantic_decision": "include",
                    "semantic_review_version": REVIEW_VERSION,
                    "semantic_note": review["note"],
                    "evidence_role": review["evidence_role"],
                    "host_identity_grounding": review["host_identity_grounding"],
                    "taxonomy_query_name": record["target_name_as_written"],
                    "taxonomy_query_rank": record["taxonomic_rank"],
                    "taxonomy_query_provenance": "The unchanged producer name occurs in the exact grounded quote.",
                }
            )
    return retained, decisions


def genus_token_matches(value: str, genus: str) -> bool:
    """Match an explicit first genus token at whitespace or common punctuation."""
    token = []
    for character in normalise_space(value).casefold():
        if character.isspace() or character in ".,;:()[]{}":
            break
        token.append(character)
    return "".join(token) == genus.casefold()


def reference_components(record: dict, reference: dict) -> dict[str, bool]:
    """Compare extracted fields to one fixed producer-compound-activity target."""
    producer = reference["producer_as_written"].split()[0].casefold()
    target = reference["activity_target_as_written"].split()[0].casefold()
    record_producer = normalise_space(record.get("target_name_as_written") or "").casefold()
    record_target = normalise_space(record.get("activity_target_as_written") or "").casefold()
    return {
        "producer": genus_token_matches(record_producer, producer),
        "compound": normalise_space(record.get("compound_name_as_written") or "").casefold()
        == reference["compound_as_written"].casefold(),
        "activity_target": genus_token_matches(record_target, target),
        "inhibition": record.get("activity_outcome") == "suppresses",
    }


def score_reference_set(
    reference_set: dict,
    retained: list[dict],
    raw: list[dict],
    rejections: list[dict],
    jobs: dict[str, dict],
    job_status: list[dict],
    response_counts: dict[str, int],
) -> dict:
    """Score the fixed two items using direct, grounded primary-source recovery."""
    references = reference_set["reference_items"]
    if reference_set["scoring"]["recall_denominator"] != 2 or len(references) != 2:
        raise ValueError("The fixed positive-control denominator must remain two")
    if {item["doi"] for item in references} != set(REFERENCE_SOURCE_IDS):
        raise ValueError("The prospective Currie and Oh reference identities changed")
    statuses = {row["input_hash"]: row["status"] for row in job_status}
    items = []
    for reference in references:
        source_id = REFERENCE_SOURCE_IDS[reference["doi"]]
        source_jobs = [job for job in jobs.values() if job["source_id"] == source_id]
        chunks = {job["chunk_index"] for job in source_jobs}
        full_source = bool(source_jobs) and all(
            chunks == set(range(job["chunk_count"])) for job in source_jobs
        )
        complete = full_source and all(
            statuses.get(job["input_hash"]) == "complete" for job in source_jobs
        )
        complete_matches = [
            row for row in retained if all(reference_components(row, reference).values())
        ]
        primary = [
            row
            for row in complete_matches
            if row["source_id"] == source_id and row.get("evidence_role") == "direct_primary"
        ]
        secondary = [
            row
            for row in complete_matches
            if row["source_id"] != source_id or row.get("evidence_role") == "secondary"
        ]
        source_raw = [row for row in raw if row["source_id"] == source_id]
        source_rejected = [row for row in rejections if row["source_id"] == source_id]
        partials = [
            {
                "record_id": row.get("record_id"),
                "source_id": row["source_id"],
                "semantically_retained": row.get("record_id")
                in {record["record_id"] for record in retained},
                "components": reference_components(row, reference),
                "all_fields_match": all(reference_components(row, reference).values()),
                "stage": "grounded_before_semantic_review",
            }
            for row in raw
            if any(reference_components(row, reference).values())
            and (row["source_id"] == source_id or row.get("compound_name_as_written"))
        ]
        failed_grounding = [
            {
                "source_id": row["source_id"],
                "input_hash": row["input_hash"],
                "reason": row["reason"],
                "components": reference_components(row["candidate"], reference),
            }
            for row in rejections
            if row["source_id"] == source_id
            or reference_components(row["candidate"], reference)["compound"]
        ]
        recovered = complete and bool(primary)
        if recovered:
            outcome = "recovered"
        elif not complete:
            outcome = "source_exposure_incomplete"
        elif not source_raw and not source_rejected:
            outcome = "empty_model_output"
        else:
            outcome = "no_complete_grounded_semantic_match"
        items.append(
            {
                "reference_id": reference["reference_id"],
                "doi": reference["doi"],
                "source_id": source_id,
                "full_source_selected": full_source,
                "all_source_jobs_complete": complete,
                "source_input_hashes": [job["input_hash"] for job in source_jobs],
                "model_candidates": sum(
                    response_counts.get(job["input_hash"], 0) for job in source_jobs
                ),
                "grounded_records_before_semantic_review": len(source_raw),
                "grounding_rejections": len(source_rejected),
                "recovered": recovered,
                "outcome": outcome,
                "primary_match_record_ids": [row["record_id"] for row in primary]
                if complete
                else [],
                "secondary_content_match_record_ids": [row["record_id"] for row in secondary],
                "secondary_attribution_policy": "Content similarity in another paper does not establish original-source attribution and never enters primary reference recall.",
                "candidate_component_comparison": partials,
                "failed_grounding_candidate_comparison": failed_grounding,
            }
        )
    numerator = sum(item["recovered"] for item in items)
    return {
        "system": "attine_actino",
        "review_version": REVIEW_VERSION,
        "status": "complete"
        if all(item["all_source_jobs_complete"] for item in items)
        else "partial",
        "reference_set_hash": digest(reference_set),
        "fixed_reference_denominator": 2,
        "recovered_reference_items": numerator,
        "reference_recall": numerator / 2,
        "recall_unit": "fixed_reference_item",
        "partial_matches_count_as_recovered": False,
        "items": items,
        "historical_taxonomy_annotation": {
            "source_id": "CURRIE1999",
            "original_producer_wording": "Streptomyces",
            "corrigendum_classification": "Pseudonocardiaceae",
            "corrigendum_block_id": "pdf:p461:corrigendum",
            "interpretation": "The family-level correction is recorded separately. It does not supply a Pseudonocardia genus assignment or replace the producer wording in a model record.",
            "taxonomy_query_changed": False,
        },
        "limitations": [
            "This is a two-item exploratory recall check, with no enrichment, specificity, or independent-replication claim.",
            "The Currie source contains historical taxonomy, embedded PDF glyph artifacts and printed hyphenation. An empty model output does not identify which factor caused the omission.",
            "Semantic review uses explicit assistant adjudications after extraction. Its counts describe this reviewed run and do not estimate annotation accuracy.",
        ],
    }


def run_control_review(root: Path, adjudications: dict[str, dict] | None = None) -> dict:
    """Review completed immutable extraction outputs and write isolated artifacts."""
    root = root.resolve()
    interim = root / "data/interim/systems/attine_actino"
    results = root / "results/systems/attine_actino"
    extraction = interim / "extraction"
    inputs = {
        "run_manifest": extraction / "run_manifest.json",
        "metrics": extraction / "metrics.json",
        "observations": extraction / "observations.jsonl",
        "rejections": extraction / "rejections.jsonl",
        "job_status": extraction / "job_status.jsonl",
        "selection": interim / "execution_selection.json",
        "reference_set": results / "reference_set.json",
    }
    hashes = {key: file_sha256(path) for key, path in inputs.items()}
    manifest = read_json(inputs["run_manifest"])
    metrics = read_json(inputs["metrics"])
    if not manifest.get("completed_at") or manifest.get("metrics") != metrics:
        raise ValueError(
            "Extraction requires a completed immutable run manifest and matching metrics"
        )
    selection = read_json(inputs["selection"])
    jobs = {}
    response_counts = {}
    for item in selection["jobs"]:
        job_path = interim / item.get("path", f"extraction_payloads/{item['input_hash']}.json")
        job = read_json(job_path)
        if (
            job["input_hash"] != item["input_hash"]
            or digest({key: value for key, value in job.items() if key != "input_hash"})
            != job["input_hash"]
        ):
            raise ValueError("Immutable selected payload hash mismatch")
        jobs[job["input_hash"]] = job
        response_path = extraction / "responses" / f"{job['input_hash']}.json"
        if response_path.is_file():
            envelope = read_json(response_path)
            if envelope["input_hash"] != job["input_hash"]:
                raise ValueError("Response input hash mismatch")
            response_counts[job["input_hash"]] = len(envelope["output"]["records"])
    if manifest["input_hashes"] != list(jobs) or len(jobs) != metrics["jobs"]:
        raise ValueError("Run manifest does not match the execution selection")
    records = read_jsonl(inputs["observations"])
    rejections = read_jsonl(inputs["rejections"])
    statuses = read_jsonl(inputs["job_status"])
    reference_set = read_json(inputs["reference_set"])
    applied = adjudications if adjudications is not None else ADJUDICATIONS
    retained, decisions = apply_adjudications(records, jobs, applied)
    status = (
        "partial"
        if metrics.get("blocked_reason") or metrics.get("incomplete_papers")
        else "complete"
    )
    review = {
        "system": "attine_actino",
        "status": status,
        "review_version": REVIEW_VERSION,
        "reviewer": "Codex",
        "blinded": False,
        "method": "Explicit record-by-record scientific adjudication, followed by deterministic source, field and relation checks.",
        "reviewed": len(records),
        "included": len(retained),
        "excluded": len(records) - len(retained),
        "exclusion_reasons": dict(
            Counter(
                reason
                for row in decisions
                if row["decision"] == "exclude"
                for reason in row["reason_codes"]
            )
        ),
        "retained_evidence_roles": dict(Counter(row["evidence_role"] for row in retained)),
        "retained_direction_counts": dict(Counter(row["direction"] for row in retained)),
        "retained_behavioural_choice_records": sum(row["behavioural_choice"] for row in retained),
        "retained_explicit_named_compound_activity_records": sum(
            bool(
                row["compound_name_as_written"]
                and row["activity_target_as_written"]
                and row["activity_outcome"] == "suppresses"
            )
            for row in retained
        ),
        "raw_observations_changed": False,
        "adjudications_hash": digest(applied),
        "input_sha256": hashes,
        "input_paths": {key: str(path.relative_to(root)) for key, path in inputs.items()},
        "source_exposure": {
            "discovery_sources_retrieved": 20,
            "additional_reference_sources": 2,
            "selected_sources": len({job["source_id"] for job in jobs.values()}),
            "selected_jobs": len(jobs),
        },
        "decisions": decisions,
        "policy": "Each inclusion retains all original extracted fields. Explicit compound and activity fields must occur in the same grounded quote and the reviewed relation must be supported. Broader host wording may be supported by the same source block with its scope recorded. Secondary reports remain secondary. Excluded records are not repaired or promoted.",
    }
    control = score_reference_set(
        reference_set, retained, records, rejections, jobs, statuses, response_counts
    )
    control["input_sha256"] = hashes
    if hashes != {key: file_sha256(path) for key, path in inputs.items()}:
        raise ValueError("Extraction inputs changed during semantic review")
    write_json(results / "semantic_review.json", review)
    write_json(extraction / "semantic_review.json", review)
    write_jsonl(interim / "semantic_review/observations.jsonl", retained)
    write_json(results / "positive_control.json", control)
    return {
        "semantic_review": {
            key: review[key] for key in ("status", "reviewed", "included", "excluded")
        },
        "positive_control": {
            key: control[key]
            for key in (
                "status",
                "fixed_reference_denominator",
                "recovered_reference_items",
                "reference_recall",
            )
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(run_control_review(args.root), indent=2))
