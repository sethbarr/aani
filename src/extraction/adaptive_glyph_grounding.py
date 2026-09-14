"""Source-anchored C0 glyph matching with a fixed cached-glyph whitelist."""

import hashlib

from src.extraction.glyph_grounding import match_provenance, normalise_with_offsets

GLYPH_POLICY_V4 = {
    "version": "glyph_v4",
    "model_characters": "non_whitespace_c0",
    "source_glyphs": ["±", "¼"],
    "mapping_scope": "candidate",
    "alignment": "unique_equal_length",
}
SOURCE_GLYPHS = frozenset({"±", "¼"})


def is_substitutable_control(character: str) -> bool:
    """Identify C0 code points excluded from the existing whitespace rule."""
    return len(character) == 1 and ord(character) < 32 and not character.isspace()


def glyph_policy_allows_v4(job: dict, block: dict) -> bool:
    """Check the fixed policy and the job's immutable source-block binding.

    Args:
        job: Extraction job with comparison-only policy and source hashes.
        block: Declared block containing the unchanged cached text.

    Returns:
        Whether fallback is authorized for these exact source text bytes.
    """
    if job.get("glyph_policy") != GLYPH_POLICY_V4:
        return False
    binding = job.get("glyph_source_hashes")
    if not isinstance(binding, dict) or binding.get("source_id") != job.get("source_id"):
        return False
    hashes = binding.get("blocks")
    if not isinstance(hashes, dict):
        return False
    block_hash = hashlib.sha256(block["text"].encode("utf-8")).hexdigest()
    return hashes.get(block["block_id"]) == block_hash


def control_run_has_anchors(model: str, source: str, start: int, index: int) -> bool:
    """Require exact printable context on both sides of a control run.

    Args:
        model: Whitespace-normalized emitted quotation.
        source: Whitespace-normalized source block.
        start: Beginning of the proposed source alignment.
        index: Index of a substituted control in the quotation.

    Returns:
        Whether both ends of the whitespace/control run have a literal printable
        non-whitespace character. Existing literal controls can occur in a run.
    """
    for step in (-1, 1):
        anchor = index + step
        while 0 <= anchor < len(model) and (
            model[anchor].isspace() or is_substitutable_control(model[anchor])
        ):
            anchor += step
        if not 0 <= anchor < len(model):
            return False
        character = model[anchor]
        if not character.isprintable() or character.isspace():
            return False
        if character != source[start + anchor]:
            return False
    return True


def aligned_replacements_v4(
    model: str, source: str, start: int
) -> tuple[list[int] | None, str | None]:
    """Check one equal-length alignment and infer consistent control mappings.

    Args:
        model: Whitespace-normalized emitted quotation.
        source: Whitespace-normalized source block.
        start: Beginning of a possible source alignment.

    Returns:
        Substituted model offsets and no reason on success; otherwise no offsets
        and a reason. Equal literal control characters never infer a mapping.
    """
    replacements: list[int] = []
    mapping: dict[str, str] = {}
    for index, character in enumerate(model):
        cached = source[start + index]
        if character == cached:
            continue
        if not is_substitutable_control(character) or cached not in SOURCE_GLYPHS:
            return None, "ungrounded_quote"
        replacements.append(index)
    if not replacements:
        return [], None
    if any(not control_run_has_anchors(model, source, start, index) for index in replacements):
        return None, "unanchored_glyph_match"
    for index in replacements:
        character = model[index]
        cached = source[start + index]
        if character in mapping and mapping[character] != cached:
            return None, "conflicting_glyph_mapping"
        mapping[character] = cached
    return replacements, None


def inferred_mapping(replacements: list[dict]) -> list[dict]:
    """Summarize inferred one-way substitutions without rewriting either text."""
    pairs = sorted({
        (entry["model_character"], entry["source_character"])
        for entry in replacements
    })
    return [
        {
            "model_character": model,
            "source_character": source,
            "model_codepoint": f"U+{ord(model):04X}",
            "source_codepoint": f"U+{ord(source):04X}",
        }
        for model, source in pairs
    ]


def finish_match(match: dict, block: dict) -> dict:
    """Attach the v4 route, exact source hash, and inferred substitution map."""
    match["route"] = "source_anchored_control_glyph" if match["replacements"] else "exact"
    match["block_text_sha256"] = hashlib.sha256(block["text"].encode("utf-8")).hexdigest()
    match["inferred_mapping"] = inferred_mapping(match["replacements"])
    return match


def ground_quote_v4(quote: str, block: dict, job: dict) -> tuple[dict | None, str | None]:
    """Ground a quote exactly or through one source-anchored C0 alignment.

    Args:
        quote: Original model-emitted quotation.
        block: Unchanged declared source block.
        job: Extraction job with a fixed policy and source hash bindings.

    Returns:
        Source coordinates and per-position evidence, or a rejection reason.
        Exact matches preserve the existing first-occurrence acceptance rule.
        Fallback permits only one equal-length, fully anchored alignment.
    """
    model = normalise_with_offsets(quote)
    source = normalise_with_offsets(block["text"])
    if not model.text:
        return None, "ungrounded_quote"
    exact_start = source.text.find(model.text)
    if exact_start >= 0:
        match = match_provenance(
            quote, block, job["source_id"], model, source, exact_start, []
        )
        return finish_match(match, block), None
    if not glyph_policy_allows_v4(job, block):
        return None, "ungrounded_quote"
    matches: list[tuple[int, list[int]]] = []
    rejected_alignments: set[str] = set()
    for start in range(len(source.text) - len(model.text) + 1):
        replacements, reason = aligned_replacements_v4(model.text, source.text, start)
        if reason in {"unanchored_glyph_match", "conflicting_glyph_mapping"}:
            rejected_alignments.add(reason)
        if replacements:
            matches.append((start, replacements))
            if len(matches) > 1:
                return None, "ambiguous_glyph_match"
    if not matches:
        for reason in ("conflicting_glyph_mapping", "unanchored_glyph_match"):
            if reason in rejected_alignments:
                return None, reason
        return None, "ungrounded_quote"
    start, replacements = matches[0]
    match = match_provenance(
        quote, block, job["source_id"], model, source, start, replacements
    )
    return finish_match(match, block), None
