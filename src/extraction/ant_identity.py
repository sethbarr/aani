"""Resolve a documented ant identity once, before partitioning a source into jobs."""

from src.common.io import digest, normalise_space

ANT_GENERA = {"Atta", "Acromyrmex"}
NON_EPITHETS = {
    "aff", "and", "ant", "ants", "are", "as", "at", "by", "cf", "colonies",
    "colony", "for", "from", "genus", "in", "is", "laboratory", "leaf",
    "of", "on", "or", "population", "populations", "spp", "sp", "species",
    "the", "to", "was", "were", "with", "worker", "workers",
}
EDGE_PUNCTUATION = ".,;:!?()[]{}<>\"'“”‘’"


def _word_spans(text: str) -> list[tuple[int, int]]:
    """Return whitespace-delimited token offsets without changing source text."""
    spans = []
    offset = 0
    while offset < len(text):
        if text[offset].isspace():
            offset += 1
            continue
        start = offset
        while offset < len(text) and not text[offset].isspace():
            offset += 1
        spans.append((start, offset))
    return spans


def _full_binomial_spans(text: str) -> list[dict]:
    """Find spelled-out leafcutter binomials with exact contiguous source anchors."""
    spans = _word_spans(text)
    found = []
    for (start, end), (next_start, next_end) in zip(spans, spans[1:]):
        raw_genus = text[start:end]
        raw_epithet = text[next_start:next_end]
        genus = raw_genus.strip(EDGE_PUNCTUATION)
        epithet = raw_epithet.strip(EDGE_PUNCTUATION)
        if genus not in ANT_GENERA or epithet in NON_EPITHETS:
            continue
        if len(epithet) < 2 or not epithet.isascii() or not epithet.isalpha():
            continue
        if not epithet.islower():
            continue
        quote_start = start + len(raw_genus) - len(raw_genus.lstrip(EDGE_PUNCTUATION))
        quote_end = next_end - len(raw_epithet) + len(raw_epithet.rstrip(EDGE_PUNCTUATION))
        quote = text[quote_start:quote_end]
        if normalise_space(quote) != f"{genus} {epithet}":
            continue
        found.append({"scientific_name": f"{genus} {epithet}", "evidence_quote": quote})
    return found


def _canonical_binomial(value: object) -> str | None:
    """Accept only one full binomial in an explicit identity field."""
    if not isinstance(value, str):
        return None
    candidates = _full_binomial_spans(value)
    if len(candidates) != 1:
        return None
    name = candidates[0]["scientific_name"]
    return name if normalise_space(value) == name else None


def _provenance(method: str, block: dict | None = None, **extra: object) -> dict:
    """Create provenance with stable nullable block and source-quote fields."""
    origin = block or {}
    return {
        "method": method,
        "block_id": origin.get("block_id"),
        "section": origin.get("section"),
        "evidence_quote": None,
        **extra,
    }


def _result(
    paper: dict,
    document: dict,
    scientific_name: str | None,
    provenance: dict,
    blocked_reason: str | None = None,
) -> dict:
    """Bind a resolution or an explicit failure to the complete source inputs."""
    abbreviations = []
    if scientific_name is not None:
        genus, epithet = scientific_name.split()
        abbreviations = [f"{genus[0]}. {epithet}", f"{genus[0]}.{epithet}"]
    return {
        "source_id": paper.get("source_id"),
        "source_hash": digest(document),
        "source_metadata_hash": digest(paper),
        "status": "resolved" if scientific_name is not None else "blocked",
        "scientific_name": scientific_name,
        "abbreviated_forms": abbreviations,
        "provenance": provenance,
        "blocked_reason": blocked_reason,
    }


def _choose_identity(paper: dict, document: dict, candidates: list[dict], method: str) -> dict:
    """Resolve agreement within one priority tier or report its conflicting names."""
    names = sorted({candidate["scientific_name"] for candidate in candidates})
    if len(names) != 1:
        return _result(
            paper, document, None,
            _provenance(method, candidates=candidates),
            f"ambiguous_ant_identity:{method}:{','.join(names)}",
        )
    provenance = candidates[0]["provenance"]
    if len(candidates) > 1:
        provenance = {**provenance, "corroborating_anchors": candidates[1:]}
    return _result(paper, document, names[0], provenance)


def _resolve_override(paper: dict, document: dict, override: dict) -> dict:
    """Validate an explicit identity and its justification and optional text anchor."""
    name = _canonical_binomial(override.get("scientific_name", override.get("ant_species")))
    reason = override.get("reason")
    provenance = _provenance("override", reason=reason, override_hash=digest(override))
    if name is None or not isinstance(reason, str) or not reason.strip():
        return _result(paper, document, None, provenance, "invalid_ant_identity_override")
    if override.get("source_id", paper["source_id"]) != paper["source_id"]:
        return _result(paper, document, None, provenance, "override_source_id_mismatch")
    block_id = override.get("block_id")
    quote = override.get("evidence_quote")
    if block_id is None and quote is not None:
        return _result(paper, document, None, provenance, "override_quote_requires_block_id")
    if block_id is not None:
        blocks = [block for block in document["blocks"] if block.get("block_id") == block_id]
        if len(blocks) != 1:
            return _result(paper, document, None, provenance, "override_block_not_unique")
        block = blocks[0]
        if quote is None:
            anchors = _full_binomial_spans(block["text"])
            matching = [anchor for anchor in anchors if anchor["scientific_name"] == name]
            quote = matching[0]["evidence_quote"] if matching else None
        if not isinstance(quote, str) or not quote or quote not in block["text"]:
            return _result(paper, document, None, provenance, "override_quote_not_in_block")
        names = {anchor["scientific_name"] for anchor in _full_binomial_spans(quote)}
        if name not in names:
            return _result(paper, document, None, provenance, "override_name_not_in_quote")
        provenance = _provenance(
            "override", block, reason=reason, override_hash=digest(override), evidence_quote=quote,
        )
    return _result(paper, document, name, provenance)


def _metadata_candidates(paper: dict, document: dict) -> tuple[list[dict], str | None]:
    """Read explicit ant_species fields without inferring an identity from titles."""
    candidates = []
    for origin, container in (("paper", paper), ("document", document)):
        fields = [(f"{origin}.ant_species", container.get("ant_species"))]
        metadata = container.get("metadata")
        if isinstance(metadata, dict):
            fields.append((f"{origin}.metadata.ant_species", metadata.get("ant_species")))
        for field, value in fields:
            if value is None:
                continue
            name = _canonical_binomial(value)
            if name is None:
                return candidates, f"invalid_ant_identity_metadata:{field}"
            candidates.append({
                "scientific_name": name,
                "provenance": _provenance(
                    "metadata", metadata_field=field, evidence_quote=value,
                ),
            })
    return candidates, None


def _abstract_candidates(paper: dict, document: dict) -> list[dict]:
    """Collect names from explicit abstract fields and abstract-designated blocks."""
    candidates = []
    abstracts = []
    for origin, container in (("paper", paper), ("document", document)):
        value = container.get("abstract")
        if isinstance(value, str):
            abstracts.append((value, _provenance("abstract", metadata_field=f"{origin}.abstract")))
    for block in document["blocks"]:
        if block.get("section", "").casefold() == "abstract" or block.get("kind") == "abstract":
            abstracts.append((block["text"], _provenance("abstract", block)))
    for text, provenance in abstracts:
        for anchor in _full_binomial_spans(text):
            candidates.append({
                "scientific_name": anchor["scientific_name"],
                "provenance": {**provenance, "evidence_quote": anchor["evidence_quote"]},
            })
    return candidates


def resolve_source_ant_identity(
    paper: dict, document: dict, override: dict | None = None,
) -> dict:
    """Resolve a source-level leafcutter identity with exact recorded provenance.

    Explicit overrides take priority over ant_species metadata, explicit abstracts,
    and the first source block containing a full binomial, in that order. Conflicting
    identities within the selected tier or first qualifying block require review.
    Later blocks may cite other species and do not replace the selected identity.

    Args:
        paper: Corpus manifest row with source_id and optional ant_species metadata.
        document: Complete cached document with source_id and ordered text blocks.
        override: Optional scientific_name and reason; source_id, block_id and an
            exact evidence_quote can bind the override to a particular source span.

    Returns:
        Identity, allowed abbreviations, source hashes and provenance, or blocked
        status with a concrete blocked_reason. Hashes use canonical JSON inputs.
    """
    unresolved = _provenance("unresolved")
    if not isinstance(paper.get("source_id"), str) or not paper["source_id"].strip():
        return _result(paper, document, None, unresolved, "missing_source_id")
    if document.get("source_id") != paper["source_id"]:
        return _result(paper, document, None, unresolved, "document_source_id_mismatch")
    blocks = document.get("blocks")
    if not isinstance(blocks, list) or any(
        not isinstance(block, dict)
        or not isinstance(block.get("text"), str)
        or not isinstance(block.get("block_id"), str)
        or not isinstance(block.get("section"), str)
        for block in blocks
    ):
        return _result(paper, document, None, unresolved, "malformed_source_blocks")
    block_ids = [block["block_id"] for block in blocks]
    if len(block_ids) != len(set(block_ids)):
        return _result(paper, document, None, unresolved, "duplicate_source_block_ids")
    if override is not None:
        if not isinstance(override, dict):
            return _result(paper, document, None, _provenance("override"), "malformed_override")
        return _resolve_override(paper, document, override)
    candidates, blocked_reason = _metadata_candidates(paper, document)
    if blocked_reason is not None:
        return _result(paper, document, None, _provenance("metadata"), blocked_reason)
    if candidates:
        return _choose_identity(paper, document, candidates, "metadata")
    candidates = _abstract_candidates(paper, document)
    if candidates:
        return _choose_identity(paper, document, candidates, "abstract")
    for block in blocks:
        candidates = [
            {
                "scientific_name": anchor["scientific_name"],
                "provenance": _provenance(
                    "first_full_binomial", block, evidence_quote=anchor["evidence_quote"],
                ),
            }
            for anchor in _full_binomial_spans(block["text"])
        ]
        if candidates:
            return _choose_identity(paper, document, candidates, "first_full_binomial")
    return _result(paper, document, None, unresolved, "no_full_ant_binomial_in_source")
