"""Optional grounding contract for observations supported by several source spans."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.common.io import digest, normalise_space
from src.extraction.schema import Observation


class EvidenceSpan(BaseModel):
    """One contiguous quote from a declared block in the extraction job."""

    model_config = ConfigDict(extra="forbid")
    block_id: str = Field(min_length=1)
    section: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class MultiSpanObservation(Observation):
    """Observation with an explicit name anchor and independent supporting spans."""

    name_evidence: EvidenceSpan
    name_surface_form: str = Field(min_length=1)
    name_link: Literal["exact", "abbreviated_binomial", "genus_reference"]
    supporting_evidence: list[EvidenceSpan]


class MultiSpanExtraction(BaseModel):
    """Complete structured answer under the optional multi-span contract."""

    model_config = ConfigDict(extra="forbid")
    records: list[MultiSpanObservation]


def contains_name(text: str, name: str) -> bool:
    """Find an exact name with boundaries that exclude longer word matches.

    Args:
        text: Whitespace-normalized quote to inspect.
        name: Nonempty whitespace-normalized taxon surface form.

    Returns:
        Whether the complete surface form occurs outside a longer word.
    """
    if not name:
        return False
    start = text.find(name)
    while start >= 0:
        end = start + len(name)
        left_ok = start == 0 or not (text[start - 1].isalnum() or text[start - 1] == "_")
        right_ok = end == len(text) or not (text[end].isalnum() or text[end] == "_")
        if left_ok and right_ok:
            return True
        start = text.find(name, start + 1)
    return False


def validate_span(span: EvidenceSpan, blocks: dict[str, dict]) -> str | None:
    """Check one quote against its declared source block and section.

    Args:
        span: Candidate source span.
        blocks: Blocks from the exact job shown to the extractor.

    Returns:
        A rejection reason, or None when the quote is grounded.
    """
    block = blocks.get(span.block_id)
    if block is None:
        return "unknown_block"
    if span.section != block["section"]:
        return "section_mismatch"
    quote = normalise_space(span.quote)
    if not quote or quote not in normalise_space(block["text"]):
        return "ungrounded_quote"
    return None


def validate_name_link(observation: MultiSpanObservation) -> str | None:
    """Check a taxon surface form against an independently quoted full name.

    Args:
        observation: Structurally validated candidate observation.

    Returns:
        A rejection reason, or None when the lexical relation is valid.
        A genus relation still requires review of species identity in context.
    """
    full_name = normalise_space(observation.plant_name_as_written)
    surface = normalise_space(observation.name_surface_form)
    if not contains_name(normalise_space(observation.name_evidence.quote), full_name):
        return "plant_not_in_name_evidence"
    if not contains_name(normalise_space(observation.evidence_quote), surface):
        return "name_surface_not_in_quote"
    words = full_name.split()
    if observation.taxonomic_rank == "species" and (
        len(words) < 2 or len(words[0]) < 2 or not words[0].isalpha()
    ):
        return "unabbreviated_genus_required"
    if observation.name_link == "exact":
        return None if surface == full_name else "invalid_exact_name_link"
    if observation.name_link == "abbreviated_binomial":
        if observation.taxonomic_rank != "species" or len(words) != 2 or len(words[0]) < 2:
            return "invalid_abbreviated_binomial_link"
        abbreviated = {f"{words[0][0]}. {words[1]}", f"{words[0][0]}.{words[1]}"}
        return None if surface in abbreviated else "invalid_abbreviated_binomial_link"
    if not words or surface != words[0] or len(words[0]) < 2:
        return "invalid_genus_reference_link"
    if observation.taxonomic_rank not in {"species", "genus"}:
        return "invalid_genus_reference_link"
    return None


def validate_multispan_candidate(
    candidate: dict, job: dict, minimum_confidence: float
) -> tuple[dict | None, str | None]:
    """Validate source spans and lexical name links without inferring semantics.

    Args:
        candidate: Proposed observation under the optional multi-span schema.
        job: Exact source blocks and metadata shown to the extractor.
        minimum_confidence: Frozen extraction-confidence threshold.

    Returns:
        Grounded record with provenance and explicit review requirements, or a
        rejection reason. Record identity hashes schema fields before metadata.
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
    reason = validate_name_link(observation)
    if reason:
        return None, reason
    ant_words = observation.ant_species.split()
    if len(ant_words) < 2 or ant_words[0] not in {"Atta", "Acromyrmex"}:
        return None, "ant_requires_review"
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
    return record, None
