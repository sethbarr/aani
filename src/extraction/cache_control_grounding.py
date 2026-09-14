"""Additive source-anchored cache-side C0 comparison for evidence quotes."""

from copy import deepcopy
from hashlib import sha256
from unicodedata import category

from src.extraction.adaptive_glyph_grounding import (
    GLYPH_POLICY_V4,
    control_run_has_anchors,
    ground_quote_v4,
    inferred_mapping,
    is_substitutable_control,
)
from src.extraction.glyph_grounding import match_provenance, normalise_with_offsets
from src.extraction.printable_confusable_grounding import (
    GLYPH_POLICY_V5,
    ground_quote_v5,
    ground_section_v5,
)

GLYPH_POLICY_V6 = {
    "version": "cache_side_controls_v6",
    "prior_policy": deepcopy(GLYPH_POLICY_V5),
    "cache_characters": "non_whitespace_c0",
    "model_characters": "single_printable_unicode_punctuation_or_symbol",
    "differing_positions": 1,
    "mapping_scope": "candidate_bidirectional_for_cache_controls",
    "alignment": "unique_equal_length",
    "anchors": "mirrored_v4_literal_printable_both_sides",
    "comparison_order": ["exact", "control_glyph_v4", "printable_confusable_v5", "cache_control"],
    "fallback_after": "ungrounded_quote_only",
    "section_policy": "unchanged_v5",
}
CACHE_CONTROL_ROUTE = "source_anchored_cache_control"


def glyph_policy_allows_v6(job: dict, block: dict) -> bool:
    """Check the fixed policy against the exact cached source-block binding."""
    if job.get("glyph_policy") != GLYPH_POLICY_V6:
        return False
    binding = job.get("glyph_source_hashes")
    if not isinstance(binding, dict) or binding.get("source_id") != job.get("source_id"):
        return False
    hashes = binding.get("blocks")
    if not isinstance(hashes, dict):
        return False
    block_hash = sha256(block["text"].encode("utf-8")).hexdigest()
    return hashes.get(block["block_id"]) == block_hash


def prior_policy_job(job: dict, policy: dict) -> dict:
    """Create a policy-only view for an unchanged earlier matcher."""
    return {**job, "glyph_policy": deepcopy(policy)}


def cache_control_replacement_allowed(emitted: str, cached: str) -> bool:
    """Allow a cached C0 control to align to one printable punctuation or symbol."""
    return (
        is_substitutable_control(cached)
        and len(emitted) == 1
        and emitted.isprintable()
        and not emitted.isspace()
        and category(emitted)[0] in {"P", "S"}
    )


def aligned_cache_control_replacements(
    model: str, source: str, start: int,
) -> tuple[list[int] | None, str | None]:
    """Check one equal-length alignment with one cache-side substitution.

    Args:
        model: Whitespace-normalized emitted quotation.
        source: Whitespace-normalized source text.
        start: Beginning of the possible source alignment.

    Returns:
        The single changed model offset and no reason, or a rejection reason.
    """
    replacements: list[int] = []
    for index, emitted in enumerate(model):
        cached = source[start + index]
        if emitted == cached:
            continue
        if replacements or not cache_control_replacement_allowed(emitted, cached):
            return None, "ungrounded_quote"
        replacements.append(index)
    if not replacements:
        return [], None
    cached_quote = source[start:start + len(model)]
    if not control_run_has_anchors(cached_quote, model, 0, replacements[0]):
        return None, "unanchored_cache_control_match"
    return replacements, None


def cache_control_match(quote: str, block: dict, job: dict) -> tuple[dict | None, str | None]:
    """Find a unique anchored source span for the new cache-side class."""
    model = normalise_with_offsets(quote)
    source = normalise_with_offsets(block["text"])
    matches: list[tuple[int, list[int]]] = []
    unanchored = False
    for start in range(len(source.text) - len(model.text) + 1):
        replacements, reason = aligned_cache_control_replacements(model.text, source.text, start)
        unanchored = unanchored or reason == "unanchored_cache_control_match"
        if replacements:
            matches.append((start, replacements))
            if len(matches) > 1:
                return None, "ambiguous_cache_control_match"
    if not matches:
        return None, "unanchored_cache_control_match" if unanchored else "ungrounded_quote"
    start, replacements = matches[0]
    match = match_provenance(quote, block, job["source_id"], model, source, start, replacements)
    match["route"] = CACHE_CONTROL_ROUTE
    match["block_text_sha256"] = sha256(block["text"].encode("utf-8")).hexdigest()
    match["inferred_mapping"] = inferred_mapping(match["replacements"])
    for entry in match["replacements"]:
        entry["route"] = CACHE_CONTROL_ROUTE
    return match, None


def ground_quote_v6(quote: str, block: dict, job: dict) -> tuple[dict | None, str | None]:
    """Apply exact, v4, v5, then cache-side grounding in that order.

    Args:
        quote: Original model quotation.
        block: Bound source block with unchanged cached text.
        job: Source identity and immutable v6 comparison policy.

    Returns:
        Exact source provenance or the first applicable ordered failure. Earlier
        safety failures prevent the new cache-side route. Existing v5 success
        remains eligible after v4 failure. Normalized exact matches need no policy.
    """
    model = normalise_with_offsets(quote)
    source = normalise_with_offsets(block["text"])
    if not model.text:
        return None, "ungrounded_quote"
    if source.text.find(model.text) >= 0:
        return ground_quote_v4(quote, block, job)
    if not glyph_policy_allows_v6(job, block):
        return None, "ungrounded_quote"
    match, control_reason = ground_quote_v4(quote, block, prior_policy_job(job, GLYPH_POLICY_V4))
    if match is not None:
        return match, None
    match, reason = ground_quote_v5(quote, block, prior_policy_job(job, GLYPH_POLICY_V5))
    if match is not None:
        return match, None
    if control_reason != "ungrounded_quote":
        return None, control_reason
    if reason != "ungrounded_quote":
        return match, reason
    return cache_control_match(quote, block, job)


def ground_section_v6(section: str, block: dict, job: dict) -> tuple[dict | None, str | None]:
    """Apply unchanged v5 section handling without cache-side section repair."""
    view = prior_policy_job(job, GLYPH_POLICY_V5) if glyph_policy_allows_v6(job, block) else job
    return ground_section_v5(section, block, view)
