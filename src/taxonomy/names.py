"""Audited source-specific name expansion without changing extracted records."""

from pathlib import Path

from src.common.io import digest, normalise_space, read_json


def validate_mapping(mapping: dict, document: dict) -> None:
    """Verify that a reviewed name expansion still matches its source anchors.

    Args:
        mapping: Explicit source-specific scientific name and evidence anchors.
        document: Complete cached source document.

    Raises:
        ValueError: Source identity, rank, names or quoted evidence are invalid.
    """
    if mapping.get("source_document_hash") != digest(document):
        raise ValueError("Name mapping source document has changed")
    if mapping.get("taxonomic_rank") not in {"species", "genus"}:
        raise ValueError("Name mapping requires species or genus rank")
    evidence = mapping.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("Name mapping requires source evidence")
    blocks = {block["block_id"]: block for block in document["blocks"]}
    quotes = []
    for anchor in evidence:
        block = blocks.get(anchor.get("block_id"))
        quote = normalise_space(anchor.get("quote", ""))
        if block is None or not quote or quote not in normalise_space(block["text"]):
            raise ValueError("Name mapping quote is not grounded in its block")
        quotes.append(quote)
    text = " ".join(quotes).casefold()
    for field in ("plant_name_as_written", "scientific_name"):
        name = normalise_space(mapping.get(field, ""))
        if not name or name.casefold() not in text:
            raise ValueError(f"Name mapping {field} is absent from its evidence")


def apply_name_mappings(observations: list[dict], mappings: dict, corpus: Path) -> list[dict]:
    """Attach validated taxonomy queries while preserving model fields and IDs.

    Args:
        observations: Source-reviewed behavioural records.
        mappings: Version-one mapping manifest reviewed before activity joining.
        corpus: Directory containing the cached source documents under texts.

    Returns:
        Copies with source-specific query names, ranks and mapping provenance.

    Raises:
        ValueError: A mapping is duplicate, stale, ungrounded or outside the input.
    """
    if mappings.get("version") != 1:
        raise ValueError("Unsupported name mapping version")
    identities = {(row["source_id"], row["plant_name_as_written"]) for row in observations}
    by_identity = {}
    documents = {}
    for mapping in mappings["mappings"]:
        identity = (mapping["source_id"], mapping["plant_name_as_written"])
        if identity in by_identity:
            raise ValueError("Duplicate source-specific name mapping")
        if identity not in identities:
            raise ValueError("Name mapping does not match any input observation")
        if identity[0] not in documents:
            documents[identity[0]] = read_json(corpus / "texts" / f"{identity[0]}.json")
        validate_mapping(mapping, documents[identity[0]])
        by_identity[identity] = mapping
    manifest_hash = digest(mappings)
    prepared = []
    for observation in observations:
        mapping = by_identity.get((observation["source_id"], observation["plant_name_as_written"]))
        if mapping is None:
            prepared.append(dict(observation))
            continue
        prepared.append(
            {
                **observation,
                "taxonomy_query_name": mapping["scientific_name"],
                "taxonomy_query_rank": mapping["taxonomic_rank"],
                "name_resolution": {
                    "method": "source_specific_reviewed_mapping",
                    "mapping_manifest_hash": manifest_hash,
                    "mapping_hash": digest(mapping),
                    "mapping": mapping,
                },
            }
        )
    return prepared
