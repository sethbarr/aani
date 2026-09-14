"""Source-anchored v4 control matching plus closed printable classes."""

from copy import deepcopy
from hashlib import sha256

from src.extraction.adaptive_glyph_grounding import (
    GLYPH_POLICY_V4,
    ground_quote_v4,
    inferred_mapping,
    is_substitutable_control,
)
from src.extraction.glyph_grounding import (
    NormalisedText,
    match_provenance,
    normalise_with_offsets,
    replacement_provenance,
)

PRINTABLE_EQUIVALENCE_CLASSES = [
    ["-", "‐", "‑", "‒", "–", "—", "−"],
    ["'", "‘", "’"],
    ['"', "“", "”"],
    [" ", " "],
]
GLYPH_POLICY_V5 = {
    "version": "printable_confusables_v5",
    "control_glyph_policy": GLYPH_POLICY_V4,
    "printable_equivalence_classes": PRINTABLE_EQUIVALENCE_CLASSES,
    "mapping_scope": "candidate",
    "alignment": "unique_equal_length",
    "comparison_order": ["exact", "control_glyph_v4", "printable_confusable"],
}
PRINTABLE_CLASS_BY_CHARACTER = {
    character: frozenset(equivalence_class)
    for equivalence_class in PRINTABLE_EQUIVALENCE_CLASSES
    for character in equivalence_class
}


def glyph_policy_allows_v5(job: dict, block: dict) -> bool:
    """Check the fixed v5 policy and exact source-block hash binding."""
    if job.get("glyph_policy") != GLYPH_POLICY_V5:
        return False
    binding = job.get("glyph_source_hashes")
    if not isinstance(binding, dict) or binding.get("source_id") != job.get("source_id"):
        return False
    hashes = binding.get("blocks")
    if not isinstance(hashes, dict):
        return False
    block_hash = sha256(block["text"].encode("utf-8")).hexdigest()
    return hashes.get(block["block_id"]) == block_hash


def printable_characters_are_equivalent(model: str, source: str) -> bool:
    """Return whether two distinct characters belong to one permitted class."""
    return (
        len(model) == 1
        and len(source) == 1
        and model != source
        and source in PRINTABLE_CLASS_BY_CHARACTER.get(model, ())
    )


def mappings_are_consistent(model: str, source: str, replacements: list[int]) -> bool:
    """Require one source character for each emitted character in an alignment."""
    mapping: dict[str, str] = {}
    for index in replacements:
        emitted = model[index]
        cached = source[index]
        if emitted in mapping and mapping[emitted] != cached:
            return False
        mapping[emitted] = cached
    return True


def printable_run_has_anchors(model: str, source: str, start: int, index: int) -> bool:
    """Apply the v4 literal-context guard to a printable substitution."""
    for step in (-1, 1):
        anchor = index + step
        while 0 <= anchor < len(model):
            emitted = model[anchor]
            cached = source[start + anchor]
            in_substituted_run = printable_characters_are_equivalent(emitted, cached)
            if not (
                emitted.isspace()
                or is_substitutable_control(emitted)
                or in_substituted_run
            ):
                break
            anchor += step
        if not 0 <= anchor < len(model):
            return False
        character = model[anchor]
        if not character.isprintable() or character.isspace():
            return False
        if character != source[start + anchor]:
            return False
    return True


def aligned_printable_replacements(
    model: str, source: str, start: int,
) -> tuple[list[int] | None, str | None]:
    """Check one equal-length alignment against only the printable classes."""
    replacements: list[int] = []
    for index, character in enumerate(model):
        cached = source[start + index]
        if character == cached:
            continue
        if not printable_characters_are_equivalent(character, cached):
            return None, "ungrounded_quote"
        replacements.append(index)
    if not replacements:
        return [], None
    if any(
        not printable_run_has_anchors(model, source, start, index)
        for index in replacements
    ):
        return None, "unanchored_printable_match"
    aligned_source = source[start:start + len(model)]
    if not mappings_are_consistent(model, aligned_source, replacements):
        return None, "conflicting_glyph_mapping"
    return replacements, None


def normalized_occurrences(text: str, quote: str) -> list[int]:
    """List every occurrence without regular expressions."""
    starts: list[int] = []
    start = text.find(quote)
    while start >= 0:
        starts.append(start)
        start = text.find(quote, start + 1)
    return starts


def exact_space_replacements(
    quote: str,
    block_text: str,
    model: NormalisedText,
    source: NormalisedText,
    source_start: int,
) -> list[int]:
    """Find single-code-point SPACE/NBSP changes hidden by normalization."""
    replacements: list[int] = []
    for model_index, character in enumerate(model.text):
        if character != " ":
            continue
        source_index = source_start + model_index
        model_span = model.raw_spans[model_index]
        source_span = source.raw_spans[source_index]
        if model_span[1] - model_span[0] != 1 or source_span[1] - source_span[0] != 1:
            continue
        emitted = quote[model_span[0]]
        cached = block_text[source_span[0]]
        if printable_characters_are_equivalent(emitted, cached):
            replacements.append(model_index)
    return replacements


def exact_space_replacement_provenance(
    quote: str,
    block_text: str,
    model: NormalisedText,
    source: NormalisedText,
    source_start: int,
    replacements: list[int],
) -> list[dict]:
    """Log the raw SPACE/NBSP characters hidden by whitespace normalization."""
    result: list[dict] = []
    for model_index in replacements:
        source_index = source_start + model_index
        model_offset = model.raw_spans[model_index][0]
        source_offset = source.raw_spans[source_index][0]
        emitted = quote[model_offset]
        cached = block_text[source_offset]
        result.append({
            "model_character": emitted,
            "source_character": cached,
            "model_codepoint": f"U+{ord(emitted):04X}",
            "source_codepoint": f"U+{ord(cached):04X}",
            "model_offset": model_offset,
            "source_offset": source_offset,
        })
    return result


def replacement_entries_are_consistent(replacements: list[dict]) -> bool:
    """Check mapping consistency from logged raw replacement evidence."""
    mapping: dict[str, str] = {}
    for entry in replacements:
        emitted = entry["model_character"]
        cached = entry["source_character"]
        if emitted in mapping and mapping[emitted] != cached:
            return False
        mapping[emitted] = cached
    return True


def finish_v5_match(match: dict, block: dict, route: str) -> dict:
    """Attach the v5 route, block hash, and mapping summary."""
    match["route"] = route
    match["block_text_sha256"] = sha256(block["text"].encode("utf-8")).hexdigest()
    match["inferred_mapping"] = inferred_mapping(match["replacements"])
    return match


def exact_or_space_match(
    quote: str, block: dict, job: dict, model: NormalisedText, source: NormalisedText,
) -> tuple[dict | None, str | None, bool]:
    """Handle normalized exact matches and log permitted raw space changes."""
    starts = normalized_occurrences(source.text, model.text)
    if not starts:
        return None, None, False
    candidates: list[tuple[int, list[int]]] = []
    rejected_reasons: set[str] = set()
    for start in starts:
        replacements = exact_space_replacements(
            quote, block["text"], model, source, start,
        )
        if not replacements:
            match = match_provenance(
                quote, block, job["source_id"], model, source, start, [],
            )
            return finish_v5_match(match, block, "exact"), None, True
        if any(
            not printable_run_has_anchors(model.text, source.text, start, index)
            for index in replacements
        ):
            rejected_reasons.add("unanchored_printable_match")
            continue
        evidence = exact_space_replacement_provenance(
            quote, block["text"], model, source, start, replacements,
        )
        if not replacement_entries_are_consistent(evidence):
            rejected_reasons.add("conflicting_glyph_mapping")
            continue
        candidates.append((start, replacements))
    if not glyph_policy_allows_v5(job, block):
        return None, "ungrounded_quote", True
    if len(candidates) > 1:
        return None, "ambiguous_printable_match", True
    if not candidates:
        for reason in ("conflicting_glyph_mapping", "unanchored_printable_match"):
            if reason in rejected_reasons:
                return None, reason, True
        return None, "ungrounded_quote", True
    start, replacements = candidates[0]
    match = match_provenance(
        quote, block, job["source_id"], model, source, start, replacements,
    )
    match["replacements"] = exact_space_replacement_provenance(
        quote, block["text"], model, source, start, replacements,
    )
    return finish_v5_match(match, block, "source_anchored_printable_confusable"), None, True


def v4_job_view(job: dict) -> dict:
    """Create the fixed-policy view used by the unchanged v4 matcher."""
    view = deepcopy(job)
    view["glyph_policy"] = deepcopy(GLYPH_POLICY_V4)
    return view


def ground_quote_v5(quote: str, block: dict, job: dict) -> tuple[dict | None, str | None]:
    """Apply exact, v4-control, then printable-confusable grounding."""
    model = normalise_with_offsets(quote)
    source = normalise_with_offsets(block["text"])
    if not model.text:
        return None, "ungrounded_quote"
    exact, reason, handled = exact_or_space_match(quote, block, job, model, source)
    if handled:
        return exact, reason
    if not glyph_policy_allows_v5(job, block):
        return None, "ungrounded_quote"
    control_match, control_reason = ground_quote_v4(quote, block, v4_job_view(job))
    if control_match is not None:
        return control_match, None
    matches: list[tuple[int, list[int]]] = []
    rejected_reasons: set[str] = set()
    for start in range(len(source.text) - len(model.text) + 1):
        replacements, printable_reason = aligned_printable_replacements(
            model.text, source.text, start,
        )
        if printable_reason in {"unanchored_printable_match", "conflicting_glyph_mapping"}:
            rejected_reasons.add(printable_reason)
        if replacements:
            matches.append((start, replacements))
            if len(matches) > 1:
                return None, "ambiguous_printable_match"
    if not matches:
        for printable_reason in ("conflicting_glyph_mapping", "unanchored_printable_match"):
            if printable_reason in rejected_reasons:
                return None, printable_reason
        return None, control_reason or "ungrounded_quote"
    start, replacements = matches[0]
    match = match_provenance(
        quote, block, job["source_id"], model, source, start, replacements,
    )
    return finish_v5_match(match, block, "source_anchored_printable_confusable"), None


def ground_section_v5(section: str, block: dict, job: dict) -> tuple[dict | None, str | None]:
    """Ground a declared section against its bound block using v5 classes."""
    cached = block["section"]
    if section == cached:
        return {
            "route": "exact",
            "emitted_section": section,
            "matched_source_section": cached,
            "replacements": [],
            "inferred_mapping": [],
        }, None
    if not glyph_policy_allows_v5(job, block) or len(section) != len(cached):
        return None, "section_mismatch"
    replacements, reason = aligned_printable_replacements(section, cached, 0)
    if replacements is None or not replacements:
        return None, "section_mismatch" if reason == "ungrounded_quote" else reason
    model = NormalisedText(section, [(index, index + 1) for index in range(len(section))])
    source = NormalisedText(cached, [(index, index + 1) for index in range(len(cached))])
    evidence = replacement_provenance(model, source, 0, replacements)
    return {
        "route": "source_anchored_printable_confusable",
        "emitted_section": section,
        "matched_source_section": cached,
        "replacements": evidence,
        "inferred_mapping": inferred_mapping(evidence),
    }, None
