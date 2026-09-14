"""Exact quote grounding with two source-scoped, one-way glyph equivalences."""

import hashlib
from dataclasses import dataclass

ALLOWED_SUBSTITUTIONS = {"\u0001": "±", "\u0003": "¼"}


@dataclass(frozen=True)
class NormalisedText:
    """Whitespace-normalized text with original character coordinates."""

    text: str
    raw_spans: list[tuple[int, int]]


def normalise_with_offsets(raw: str) -> NormalisedText:
    """Apply the existing split/join whitespace rule while retaining offsets.

    Args:
        raw: Unmodified source text or model-emitted quotation.

    Returns:
        Normalized text and a half-open raw span for each normalized character.
        Offsets count Unicode code points, matching Python string indexing.
    """
    characters: list[str] = []
    raw_spans: list[tuple[int, int]] = []
    whitespace_start: int | None = None
    for index, character in enumerate(raw):
        if character.isspace():
            if characters and whitespace_start is None:
                whitespace_start = index
            continue
        if whitespace_start is not None:
            characters.append(" ")
            raw_spans.append((whitespace_start, index))
            whitespace_start = None
        characters.append(character)
        raw_spans.append((index, index + 1))
    return NormalisedText("".join(characters), raw_spans)


def glyph_policy_allows(job: dict, block: dict) -> bool:
    """Check the explicit policy against this exact source-block text.

    Args:
        job: Extraction job carrying the comparison-only glyph policy.
        block: Declared source block from that job.

    Returns:
        Whether the fixed two-pair policy authorizes this Saverschek table block.
    """
    policy = job.get("glyph_policy")
    if not isinstance(policy, dict) or policy.get("version") != "glyph_v3":
        return False
    substitutions = policy.get("substitutions")
    if not isinstance(substitutions, list) or len(substitutions) != 2:
        return False
    if not all(isinstance(pair, dict) for pair in substitutions):
        return False
    configured = [(pair.get("model"), pair.get("source")) for pair in substitutions]
    if any(pair not in list(ALLOWED_SUBSTITUTIONS.items()) for pair in configured):
        return False
    if len(set(configured)) != 2:
        return False
    if job.get("source_id") != "SAVERSCHEK2010" or block.get("block_id") != "b00005":
        return False
    scopes = policy.get("scopes")
    if not isinstance(scopes, list):
        return False
    block_hash = hashlib.sha256(block["text"].encode("utf-8")).hexdigest()
    return any(
        isinstance(scope, dict)
        and scope.get("source_id") == job["source_id"]
        and scope.get("block_id") == block["block_id"]
        and scope.get("block_text_sha256") == block_hash
        for scope in scopes
    )


def aligned_replacements(model: str, source: str, start: int) -> list[int] | None:
    """Compare a fixed-length alignment using only the allowed glyph pairs.

    Args:
        model: Whitespace-normalized emitted quotation.
        source: Whitespace-normalized source block.
        start: Source offset at which this candidate alignment begins.

    Returns:
        Model offsets requiring substitution, or None for any other mismatch.
    """
    replacements: list[int] = []
    for index, model_character in enumerate(model):
        source_character = source[start + index]
        if model_character == source_character:
            continue
        if ALLOWED_SUBSTITUTIONS.get(model_character) != source_character:
            return None
        replacements.append(index)
    return replacements


def replacement_provenance(
    model: NormalisedText,
    source: NormalisedText,
    source_start: int,
    replacements: list[int],
) -> list[dict]:
    """Map every allowed mismatch to the unchanged model and source strings.

    Args:
        model: Normalized quotation with raw quotation coordinates.
        source: Normalized source block with raw block coordinates.
        source_start: Start of the unique normalized alignment.
        replacements: Normalized quotation offsets requiring equivalence.

    Returns:
        Characters, code points and raw offsets for each comparison substitution.
    """
    result: list[dict] = []
    for model_index in replacements:
        source_index = source_start + model_index
        model_character = model.text[model_index]
        source_character = source.text[source_index]
        result.append(
            {
                "model_character": model_character,
                "source_character": source_character,
                "model_codepoint": f"U+{ord(model_character):04X}",
                "source_codepoint": f"U+{ord(source_character):04X}",
                "model_offset": model.raw_spans[model_index][0],
                "source_offset": source.raw_spans[source_index][0],
            }
        )
    return result


def match_provenance(
    emitted_quote: str,
    block: dict,
    source_id: str,
    model: NormalisedText,
    source: NormalisedText,
    source_start: int,
    replacements: list[int],
) -> dict:
    """Describe one accepted span without changing either input string.

    Args:
        emitted_quote: Original model quotation.
        block: Original declared source block.
        source_id: Source identifier for the extraction job.
        model: Quotation normalized under the existing whitespace rule.
        source: Block normalized under the existing whitespace rule.
        source_start: Start of the accepted normalized alignment.
        replacements: Normalized quotation offsets using bounded equivalence.

    Returns:
        Raw-source coordinates, raw quotations and per-glyph comparison evidence.
    """
    start = source.raw_spans[source_start][0]
    end = source.raw_spans[source_start + len(model.text) - 1][1]
    return {
        "route": "bounded_glyph_equivalence" if replacements else "exact",
        "source_id": source_id,
        "source_block": block["block_id"],
        "section": block["section"],
        "start": start,
        "end": end,
        "offset_unit": "unicode_code_point",
        "matched_source_quote": block["text"][start:end],
        "emitted_quote": emitted_quote,
        "replacements": replacement_provenance(model, source, source_start, replacements),
    }


def ground_quote(quote: str, block: dict, job: dict) -> tuple[dict | None, str | None]:
    """Prefer exact grounding and permit only a unique policy-scoped fallback.

    Args:
        quote: Unmodified model-emitted quote.
        block: Declared source block whose section has already been checked.
        job: Job carrying the explicit source/block/hash-scoped policy.

    Returns:
        Match provenance or a rejection reason. Repeated exact text follows the
        existing validator's acceptance rule; fallback requires one alignment.
    """
    model = normalise_with_offsets(quote)
    source = normalise_with_offsets(block["text"])
    if not model.text:
        return None, "ungrounded_quote"
    exact_start = source.text.find(model.text)
    if exact_start >= 0:
        return match_provenance(quote, block, job["source_id"], model, source, exact_start, []), None
    if not glyph_policy_allows(job, block):
        return None, "ungrounded_quote"
    matches: list[tuple[int, list[int]]] = []
    for start in range(len(source.text) - len(model.text) + 1):
        replacements = aligned_replacements(model.text, source.text, start)
        if replacements:
            matches.append((start, replacements))
            if len(matches) > 1:
                return None, "ambiguous_glyph_match"
    if not matches:
        return None, "ungrounded_quote"
    start, replacements = matches[0]
    return match_provenance(quote, block, job["source_id"], model, source, start, replacements), None
