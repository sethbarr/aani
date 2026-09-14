"""Source-identity grounding with the unchanged multi-span extraction schema."""

from pydantic import ValidationError

from src.common.io import digest, normalise_space
from src.extraction.multispan import (
    EvidenceSpan,
    MultiSpanObservation,
    contains_name,
    validate_name_link,
    validate_span,
)


def span_provenance(span: EvidenceSpan, route: str, index: int | None = None) -> dict:
    """Record the unchanged source span that satisfied a grounding check.

    Args:
        span: Grounded source span.
        route: Field containing the span.
        index: Zero-based supporting-evidence index, when applicable.

    Returns:
        Source coordinates and the original quote.
    """
    return {
        "route": route,
        "index": index,
        "block_id": span.block_id,
        "section": span.section,
        "evidence_quote": span.quote,
    }


def resolve_plant_surface(
    observation: MultiSpanObservation, primary: EvidenceSpan
) -> tuple[dict | None, str | None]:
    """Check the existing name relation in the primary or same-block support.

    Args:
        observation: Candidate whose spans have already passed exact grounding.
        primary: Candidate's primary evidence span.

    Returns:
        The span satisfying the existing lexical relation, or a rejection reason.
    """
    reason = validate_name_link(observation)
    if reason is None:
        return span_provenance(primary, "primary_quote"), None
    if reason != "name_surface_not_in_quote":
        return None, reason
    surface = normalise_space(observation.name_surface_form)
    for index, span in enumerate(observation.supporting_evidence):
        if span.block_id != primary.block_id:
            continue
        if not contains_name(normalise_space(span.quote), surface):
            continue
        supported = observation.model_copy(update={"evidence_quote": span.quote})
        reason = validate_name_link(supported)
        if reason is not None:
            return None, reason
        return span_provenance(span, "supporting_evidence", index), None
    return None, "name_surface_not_in_quote"


def ant_binomial(name: str) -> str | None:
    """Recognize a full binomial from either eligible leafcutter genus.

    Args:
        name: Ant name supplied by the record or source identity.

    Returns:
        Whitespace-normalized full binomial, or None for an unsupported name.
    """
    words = normalise_space(name).split()
    if len(words) != 2 or words[0] not in {"Atta", "Acromyrmex"}:
        return None
    if not words[1].isalpha() or not words[1].islower():
        return None
    return " ".join(words)


def ant_surface_forms(scientific_name: str) -> set[str]:
    """List exact full and abbreviated surfaces for a resolved ant binomial.

    Args:
        scientific_name: A previously checked full ant binomial.

    Returns:
        Canonical full, spaced-abbreviation and compact-abbreviation forms.
    """
    genus, epithet = scientific_name.split()
    return {scientific_name, f"{genus[0]}. {epithet}", f"{genus[0]}.{epithet}"}


def possible_ant_binomials(surface: str) -> list[str]:
    """Expand an exact record surface into full names requiring source evidence.

    Args:
        surface: Whitespace-normalized ant-species field.

    Returns:
        Eligible names compatible with the field; these are still ungrounded.
    """
    full_name = ant_binomial(surface)
    if full_name is not None:
        return [full_name]
    if not surface.startswith("A."):
        return []
    epithet = surface[2:].strip()
    if not epithet.isalpha() or not epithet.islower():
        return []
    return [f"Atta {epithet}", f"Acromyrmex {epithet}"]


def quoted_ant_identity(
    observation: MultiSpanObservation, primary: EvidenceSpan, possible_names: list[str]
) -> dict | None:
    """Find a compatible full ant name in an already-grounded record span.

    Args:
        observation: Candidate with exactly grounded evidence spans.
        primary: Primary evidence span.
        possible_names: Full binomials compatible with the ant-species field.

    Returns:
        Resolved ant name and span provenance when one unambiguous name occurs.
    """
    spans = [(primary, "primary_quote", None), (observation.name_evidence, "name_evidence", None)]
    spans.extend(
        (span, "supporting_evidence", index)
        for index, span in enumerate(observation.supporting_evidence)
    )
    matches = {}
    for span, route, index in spans:
        for name in possible_names:
            if contains_name(normalise_space(span.quote), name) and name not in matches:
                matches[name] = span_provenance(span, route, index)
    if len(matches) != 1:
        return None
    scientific_name, provenance = next(iter(matches.items()))
    return {
        "resolved_ant_species": scientific_name,
        "ant_identity_route": "full_binomial_in_quote",
        "ant_identity_provenance": provenance,
    }


def resolve_record_ant(
    observation: MultiSpanObservation, primary: EvidenceSpan, job: dict
) -> tuple[dict | None, str | None]:
    """Ground the ant field through a full quoted name or a source identity.

    Args:
        observation: Candidate with grounded record spans.
        primary: Primary evidence span.
        job: Extraction job carrying one source's independently resolved identity.

    Returns:
        Resolved identity metadata or an explicit identity rejection reason.
    """
    surface = normalise_space(observation.ant_species)
    possible_names = possible_ant_binomials(surface)
    if not possible_names:
        return None, "ant_requires_review"
    quoted = quoted_ant_identity(observation, primary, possible_names)
    if quoted is not None:
        return quoted, None
    identity = job.get("source_ant_identity")
    if not isinstance(identity, dict):
        return None, "ant_identity_unresolved"
    if identity.get("source_id") != job["source_id"]:
        return None, "ant_identity_source_mismatch"
    if identity.get("status") != "resolved":
        return None, "ant_identity_unresolved"
    name = identity.get("scientific_name")
    if not isinstance(name, str):
        return None, "ant_identity_unresolved"
    scientific_name = ant_binomial(name)
    if scientific_name is None:
        return None, "ant_identity_unresolved"
    if surface not in ant_surface_forms(scientific_name):
        return None, "ant_identity_mismatch"
    if surface != scientific_name and surface not in identity.get("abbreviated_forms", []):
        return None, "ant_identity_mismatch"
    route = "source_identity_full_name" if surface == scientific_name else "source_identity_abbreviation"
    return {
        "resolved_ant_species": scientific_name,
        "ant_identity_route": route,
        "ant_identity_provenance": {
            "source_id": identity["source_id"],
            "source_hash": identity.get("source_hash"),
            "source_metadata_hash": identity.get("source_metadata_hash"),
            **identity.get("provenance", {}),
        },
    }, None


def validate_multispan_v2_candidate(
    candidate: dict, job: dict, minimum_confidence: float
) -> tuple[dict | None, str | None]:
    """Ground the unchanged schema with source ant and same-block plant links.

    Args:
        candidate: Proposed observation under the existing multi-span schema.
        job: Exact source blocks, metadata and resolved source ant identity.
        minimum_confidence: Frozen extraction-confidence threshold.

    Returns:
        Grounded record with identity routes or a rejection reason. The record ID
        hashes the original schema fields before identity metadata is added.
    """
    try:
        observation = MultiSpanObservation.model_validate(candidate)
        primary = EvidenceSpan(
            block_id=observation.block_id,
            section=observation.section,
            quote=observation.evidence_quote,
        )
    except ValidationError as error:
        return None, f"schema: {error}"
    blocks = {block["block_id"]: block for block in job["blocks"]}
    if observation.source_id != job["source_id"] or observation.block_id not in blocks:
        return None, "unknown_source_or_block"
    reason = validate_span(primary, blocks)
    if reason:
        return None, reason
    reason = validate_span(observation.name_evidence, blocks)
    if reason:
        return None, f"name_evidence:{reason}"
    for index, span in enumerate(observation.supporting_evidence):
        reason = validate_span(span, blocks)
        if reason:
            return None, f"supporting_evidence[{index}]:{reason}"
    plant_provenance, reason = resolve_plant_surface(observation, primary)
    if reason:
        return None, reason
    ant_metadata, reason = resolve_record_ant(observation, primary, job)
    if reason:
        return None, reason
    if observation.extraction_confidence < minimum_confidence:
        return None, "low_confidence"
    record = observation.model_dump()
    record["record_id"] = digest(record)
    record["source_url"] = job["source_url"]
    record["input_hash"] = job["input_hash"]
    record["grounding_review_required"] = True
    record["grounding_review_reasons"] = ["direction_semantics"]
    if observation.name_link == "genus_reference":
        record["grounding_review_reasons"].append("genus_reference_species_link")
    record["plant_name_surface_provenance"] = plant_provenance
    record.update(ant_metadata or {})
    return record, None
