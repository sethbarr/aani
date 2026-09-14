"""Apply auditable choosing-female infection annotations after fixed extraction."""

from copy import deepcopy
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.common.io import digest, normalise_space

REVIEW_VERSION = "monarch_explicit_infection_review_v1"
type Record = dict[str, Any]
type InfectionStatus = Literal["infected", "uninfected", "unreported"]


class SourceEvidence(BaseModel):
    """An exact source span supporting an explicit human-reviewed claim."""

    model_config = ConfigDict(extra="forbid", strict=True)
    input_hash: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    block_id: str = Field(min_length=1)
    section: str
    evidence_quote: str = Field(min_length=1)


class InfectionAnnotation(BaseModel):
    """Manual biological claims with source anchors; defaults assert no recovery."""

    model_config = ConfigDict(extra="forbid", strict=True)
    infection_status: InfectionStatus
    infection_subject: Literal["choosing_adult_female", "unreported"] = "unreported"
    infection_evidence: list[SourceEvidence] = Field(default_factory=list)
    primary_oviposition_choice: bool = False
    between_milkweed_species: bool = False
    choosing_adult_female: bool = False
    design_evidence: list[SourceEvidence] = Field(default_factory=list)
    experiment_id: str | None = None
    same_experiment_comparison: bool = False
    compared_infection_groups: list[Literal["infected", "uninfected"]] = Field(
        default_factory=list
    )
    comparison_evidence: list[SourceEvidence] = Field(default_factory=list)
    direction_supported: bool = False


class RecordAdjudication(InfectionAnnotation):
    """One review of a raw model record, including explicit context additions."""

    decision: Literal["include", "exclude"]
    note: str = Field(min_length=1)
    reason_codes: list[str] = Field(default_factory=list)
    context_expansions: list[InfectionAnnotation] = Field(default_factory=list)


def anchored_evidence(evidence: SourceEvidence, source_id: str, jobs: dict[str, Record]) -> Record:
    """Validate an exact source quote and attach its immutable block provenance.

    Args:
        evidence: Explicit source, block and quote supplied by the reviewer.
        source_id: Source to which the reviewed claim belongs.
        jobs: Original extraction jobs indexed by their input hashes.

    Returns:
        Evidence with exact offsets, a block checksum and an evidence checksum.

    Raises:
        ValueError: The quote, block, job or source identity cannot be verified.
    """
    job = jobs.get(evidence.input_hash)
    if job is None or job.get("input_hash") != evidence.input_hash:
        raise ValueError("Unknown evidence input hash")
    if evidence.source_id != source_id or job.get("source_id") != source_id:
        raise ValueError("Evidence must belong to the reviewed source")
    matching = [block for block in job["blocks"] if block["block_id"] == evidence.block_id]
    if len(matching) != 1 or matching[0]["section"] != evidence.section:
        raise ValueError("Evidence block or section mismatch")
    text = matching[0]["text"]
    start = text.find(evidence.evidence_quote)
    if start < 0 or not evidence.evidence_quote.strip():
        raise ValueError("Annotation evidence must be an exact source quote")
    result = {
        **evidence.model_dump(),
        "start": start,
        "end": start + len(evidence.evidence_quote),
        "block_text_sha256": sha256(text.encode("utf-8")).hexdigest(),
    }
    result["evidence_hash"] = digest(result)
    return result


def validate_annotation(
    annotation: InfectionAnnotation, source_id: str, jobs: dict[str, Record]
) -> Record:
    """Check evidence bindings and derive eligibility from explicit reviewed claims.

    This function verifies source provenance and logical consistency. The reviewer
    is responsible for interpreting experimental subjects, species and contrasts.
    No keyword or biological inference assigns an infection status.

    Args:
        annotation: Explicit reviewed claims and their source quotations.
        source_id: Source containing the record or design under review.
        jobs: Unchanged extraction jobs indexed by input hash.

    Returns:
        Validated annotation with derived source-design and record eligibility.

    Raises:
        ValueError: A positive biological claim lacks required source evidence.
    """
    infection = [anchored_evidence(item, source_id, jobs)
                 for item in annotation.infection_evidence]
    design = [anchored_evidence(item, source_id, jobs) for item in annotation.design_evidence]
    comparison = [anchored_evidence(item, source_id, jobs)
                  for item in annotation.comparison_evidence]
    reported = annotation.infection_status != "unreported"
    if reported and (annotation.infection_subject != "choosing_adult_female" or not infection):
        raise ValueError("Reported infection status requires choosing-female source evidence")
    design_flags = (
        annotation.primary_oviposition_choice,
        annotation.between_milkweed_species,
        annotation.choosing_adult_female,
    )
    if any(design_flags) and not design:
        raise ValueError("Positive choice-design claims require source evidence")
    if reported and not annotation.choosing_adult_female:
        raise ValueError("Reported infection status requires an identified choosing adult female")
    compared = annotation.compared_infection_groups
    if annotation.same_experiment_comparison:
        if len(compared) != 2 or set(compared) != {"infected", "uninfected"}:
            raise ValueError("Comparison requires distinct infected and uninfected groups")
        if not annotation.experiment_id or not annotation.experiment_id.strip() or not comparison:
            raise ValueError("Comparison requires a named experiment and exact source evidence")
    elif compared or comparison:
        raise ValueError("Comparison evidence requires an explicit same-experiment adjudication")
    design_eligible = all(design_flags) and annotation.same_experiment_comparison
    flags = []
    if not reported:
        flags.append("choosing_female_infection_unreported")
    if not all(design_flags):
        flags.append("focal_species_choice_design_not_established")
    if not annotation.same_experiment_comparison:
        flags.append("infected_uninfected_comparison_not_established")
    return {
        **annotation.model_dump(include=set(InfectionAnnotation.model_fields)),
        "infection_evidence": infection,
        "design_evidence": design,
        "comparison_evidence": comparison,
        "infection_status_provenance": "explicit_manual_source_review",
        "source_design_eligible": design_eligible,
        "focal_eligible": design_eligible and reported,
        "infection_comparison_eligible": design_eligible and reported,
        "infection_flags": flags,
    }


def validate_raw_record(record: Record, jobs: dict[str, Record]) -> None:
    """Verify the original single-quote identity without modifying its raw fields.

    Args:
        record: Grounded model record being annotated.
        jobs: Original jobs indexed by input hash.

    Raises:
        ValueError: The original record no longer matches its quoted source block.
    """
    job = jobs.get(record["input_hash"])
    if job is None or job.get("input_hash") != record["input_hash"]:
        raise ValueError("Unknown raw-record input hash")
    if job.get("source_id") != record["source_id"]:
        raise ValueError("Raw-record source mismatch")
    blocks = [block for block in job["blocks"] if block["block_id"] == record["block_id"]]
    if len(blocks) != 1 or blocks[0]["section"] != record["section"]:
        raise ValueError("Raw-record block or section mismatch")
    quote = normalise_space(record["evidence_quote"])
    if not quote or quote not in normalise_space(blocks[0]["text"]):
        raise ValueError("Raw record fails original single-quote grounding")


def annotated_record(
    record: Record, annotation: Record, review: RecordAdjudication, expanded: bool
) -> Record:
    """Preserve raw model fields and distinguish curator-added infection contexts.

    Args:
        record: Original model record, including its immutable record identifier.
        annotation: Validated explicit infection annotation.
        review: Parent inclusion decision and note.
        expanded: Whether this row was added as a manual context expansion.

    Returns:
        A copy with review metadata and a preserved complete raw model record.

    Raises:
        ValueError: An annotation would overwrite an existing raw model field.
    """
    addition = {
        **annotation,
        "semantic_decision": "include",
        "semantic_review_version": REVIEW_VERSION,
        "semantic_note": review.note,
        "record_origin": "curator_context_expansion" if expanded else "model_record",
        "curator_added_context": expanded,
        "parent_record_id": record["record_id"],
        "raw_model_record": deepcopy(record),
        "raw_model_record_hash": digest(record),
        "direction_scope": "milkweed_species_choice",
        "semantic_scope": "direct_primary_oviposition_choice",
        "treatment_context": (
            f"choosing_female_infection={annotation['infection_status']}; "
            f"experiment={annotation['experiment_id'] or 'unreported'}"
        ),
    }
    if set(record) & set(addition):
        raise ValueError("Review metadata would overwrite raw model fields")
    result = {**deepcopy(record), **addition}
    if expanded:
        result["record_id"] = digest({"parent_record_id": record["record_id"],
                                      "review_version": REVIEW_VERSION,
                                      "explicit_context": annotation})
    return result


def apply_explicit_infection_annotations(
    records: list[Record], jobs: dict[str, Record], adjudications: dict[str, Record]
) -> tuple[list[Record], list[Record]]:
    """Apply an exact-cover manual review while retaining infection-group identity.

    Args:
        records: Original grounded model records with stable record IDs.
        jobs: Original extraction jobs indexed by input hash.
        adjudications: One RecordAdjudication-shaped mapping per raw record ID.
            Optional context_expansions require complete explicit annotations.

    Returns:
        Retained annotated rows and all review decisions. Added contexts have new
        stable IDs, parent IDs and curator_context_expansion origin. They never
        increase model-record recovery counts. Excluded records remain in the
        decisions with their required infection status and original model record.

    Raises:
        ValueError: Coverage, inclusion semantics, evidence or uniqueness fails.
    """
    identifiers = {row["record_id"] for row in records}
    if len(identifiers) != len(records) or identifiers != set(adjudications):
        raise ValueError("Adjudications must cover exactly the unique grounded records")
    retained: list[Record] = []
    decisions: list[Record] = []
    for record in records:
        validate_raw_record(record, jobs)
        review = RecordAdjudication.model_validate(adjudications[record["record_id"]])
        annotation = validate_annotation(review, record["source_id"], jobs)
        if review.context_expansions and review.decision != "include":
            raise ValueError("Context expansions require an included parent record")
        if review.decision == "include":
            if not all((review.primary_oviposition_choice, review.between_milkweed_species,
                        review.choosing_adult_female)):
                raise ValueError("Inclusion requires primary choosing-female species choice")
            if record["direction"] in {"accept", "reject"} and not review.direction_supported:
                raise ValueError("Directional inclusion requires explicit choice support")
            retained.append(annotated_record(record, annotation, review, expanded=False))
        expansion_ids: list[str] = []
        for expansion in review.context_expansions:
            checked = validate_annotation(expansion, record["source_id"], jobs)
            if not all((expansion.primary_oviposition_choice, expansion.between_milkweed_species,
                        expansion.choosing_adult_female)):
                raise ValueError("Expanded context requires primary choosing-female species choice")
            if record["direction"] in {"accept", "reject"} and not expansion.direction_supported:
                raise ValueError("Expanded direction requires explicit choice support")
            expanded = annotated_record(record, checked, review, expanded=True)
            expansion_ids.append(expanded["record_id"])
            retained.append(expanded)
        decisions.append({
            "record_id": record["record_id"], "input_hash": record["input_hash"],
            "source_id": record["source_id"], "raw_model_record": deepcopy(record),
            "raw_model_record_hash": digest(record), **review.model_dump(),
            "validated_annotation": annotation, "context_expansion_ids": expansion_ids,
            "semantic_review_version": REVIEW_VERSION,
        })
    if len({row["record_id"] for row in retained}) != len(retained):
        raise ValueError("Duplicate retained model or context-expansion IDs")
    return retained, decisions


def validate_source_design_annotations(
    adjudications: dict[str, Record], jobs: dict[str, Record]
) -> list[Record]:
    """Review source designs even when extraction yielded no matching model record.

    Args:
        adjudications: Mapping from unique manual design IDs to source_id plus
            InfectionAnnotation fields. Source-level reviews use unreported
            infection_status; their evidence describes both experimental groups.
        jobs: Original source jobs indexed by input hash.

    Returns:
        Validated source-design evidence, explicitly outside model-record counts.

    Raises:
        ValueError: A design lacks an available source or claims a record-level status.
    """
    designs: list[Record] = []
    for design_id, raw in adjudications.items():
        source_id = raw.get("source_id")
        if not design_id.strip() or not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("Source design requires explicit nonempty source and design IDs")
        if not any(job.get("source_id") == source_id for job in jobs.values()):
            raise ValueError("Source design must belong to supplied source jobs")
        annotation = InfectionAnnotation.model_validate(
            {key: value for key, value in raw.items() if key != "source_id"}
        )
        if annotation.infection_status != "unreported":
            raise ValueError("Source-level review keeps record infection status unreported")
        designs.append({"design_id": design_id, "source_id": source_id,
                        "record_origin": "source_design_review",
                        **validate_annotation(annotation, source_id, jobs)})
    return designs


def summarize_focal_recovery(
    records: list[Record], decisions: list[Record], source_designs: list[Record] | None = None
) -> Record:
    """Count source design, original model recovery and curator context separately.

    Args:
        records: Retained annotated rows produced by this module.
        decisions: Complete raw-record review decisions produced by this module.
        source_designs: Optional validated independent source-level design reviews.

    Returns:
        Descriptive coverage counts with an explicit model-group-pairing verdict.
    """
    source_ids = {row["source_id"] for row in decisions
                  if row["validated_annotation"]["source_design_eligible"]}
    if source_designs is not None:
        source_ids.update(row["source_id"] for row in source_designs
                          if row["source_design_eligible"])
    focal_model = [row for row in records if row["record_origin"] == "model_record"
                   and row["focal_eligible"]]
    groups: dict[tuple[str, str], set[str]] = {}
    for row in focal_model:
        key = (row["source_id"], row["experiment_id"])
        groups.setdefault(key, set()).add(row["infection_status"])
    paired = [{"source_id": source_id, "experiment_id": experiment_id}
              for (source_id, experiment_id), statuses in sorted(groups.items())
              if statuses == {"infected", "uninfected"}]
    return {
        "source_design_recovered": bool(source_ids),
        "source_design_sources": sorted(source_ids),
        "source_design_scope": (
            "reviewed source designs and sources represented among reviewed model records"
            if source_designs is not None else "sources represented among reviewed model records"
        ),
        "focal_model_record_count": len(focal_model),
        "model_infected_uninfected_pair_recovered": bool(paired),
        "paired_model_experiments": paired,
        "curator_context_expansion_count": sum(row["curator_added_context"] for row in records),
        "unreported_model_record_count": sum(row["record_origin"] == "model_record"
                                              and row["infection_status"] == "unreported"
                                              for row in records),
        "counts_interpretation": "Descriptive reviewed-record coverage; excluded from inference.",
    }
