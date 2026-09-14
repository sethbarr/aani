"""Exhaustive C0 and adversarial checks for source-anchored glyph comparison."""

import copy
import hashlib

import pytest

from src.extraction.adaptive_glyph_grounding import (
    GLYPH_POLICY_V4,
    ground_quote_v4,
    is_substitutable_control,
)


def adaptive_job(text: str) -> dict:
    """Bind a generic source's block bytes to the fixed v4 policy."""
    return {
        "source_id": "GENERIC_SOURCE",
        "blocks": [{"block_id": "table_17", "section": "Results", "text": text}],
        "glyph_policy": copy.deepcopy(GLYPH_POLICY_V4),
        "glyph_source_hashes": {
            "source_id": "GENERIC_SOURCE",
            "blocks": {"table_17": hashlib.sha256(text.encode("utf-8")).hexdigest()},
        },
    }


@pytest.mark.parametrize("codepoint", range(32))
@pytest.mark.parametrize("cached_glyph", ["±", "¼"])
def test_all_c0_codes_follow_the_same_source_anchored_rule(
    codepoint: int, cached_glyph: str
) -> None:
    """Cover unseen C0 codes while retaining the existing whitespace behavior."""
    character = chr(codepoint)
    job = adaptive_job(f"prefix value {cached_glyph} 4 suffix")
    quote = f"value {character} 4"
    match, reason = ground_quote_v4(quote, job["blocks"][0], job)
    if character.isspace():
        assert match is None
        assert reason == "ungrounded_quote"
    else:
        assert reason is None
        assert match is not None
        assert match["route"] == "source_anchored_control_glyph"
        assert match["emitted_quote"] == quote
        assert match["replacements"][0]["model_codepoint"] == f"U+{codepoint:04X}"
        assert match["replacements"][0]["source_character"] == cached_glyph
        assert match["block_text_sha256"] == job["glyph_source_hashes"]["blocks"]["table_17"]


@pytest.mark.parametrize("character", ["", "xx", "\u007f", "\u0080", "\u0085", "\u009f", "�", "±", "¼"])
def test_the_control_class_is_strict(character: str) -> None:
    """Exclude DEL, C1, replacement characters, and printable glyphs."""
    assert is_substitutable_control(character) is False


@pytest.mark.parametrize(
    ("source", "quote"),
    [
        ("Hiraea 0.01 ± 0.00", "Hiraea 0.02 \u0002 0.00"),
        ("Hiraea -0.01 ± 0.00", "Hiraea +0.01 \u0002 0.00"),
        ("Hiraea rejected ± 0.00", "Hiraea accepted \u0002 0.00"),
        ("Hiraea 0.01 ± 0.00", "Hiraea 0.01 \u007f 0.00"),
        ("Hiraea 0.01 ± 0.00", "Hiraea 0.01 \u0080 0.00"),
        ("Hiraea 0.01 ± 0.00", "Hiraea 0.01 � 0.00"),
        ("Hiraea 0.01 ± 0.00", "Hiraea 0.01 + 0.00"),
        ("N ¼ 4", "N = 4"),
        ("Hiraea \u0002 0.00", "Hiraea ± 0.00"),
        ("Hiraea A 4", "Hiraea \u0002 4"),
        ("Hiraea 1 4", "Hiraea \u0002 4"),
        ("Hiraea - 4", "Hiraea \u0002 4"),
        ("Hiraea = 4", "Hiraea \u0002 4"),
        ("Hiraea 0.01 ± 0.00", "Hiraea 0.01 \u0002 0.00 invented"),
        ("Hiraea 0.01 ± 0.00", "Hiraea...0.01 \u0002 0.00"),
        ("Hiraea 0.01 ± 0.00", "Hiraea 0.01 0.00"),
    ],
)
def test_other_mismatches_and_insertions_remain_rejected(source: str, quote: str) -> None:
    """Keep letters, numbers, signs, lengths, and non-whitelisted glyphs exact."""
    job = adaptive_job(source)
    match, reason = ground_quote_v4(quote, job["blocks"][0], job)
    assert match is None
    assert reason == "ungrounded_quote"


@pytest.mark.parametrize("change", ["source", "hash", "text", "block", "missing_hashes", "missing_policy", "version", "glyphs", "model_class", "mapping_scope", "alignment"])
def test_fallback_requires_unchanged_source_binding_and_fixed_policy(change: str) -> None:
    """Deny broadened policy and stale or foreign source-block bindings."""
    job = adaptive_job("Hiraea 0.01 ± 0.00")
    if change == "source":
        job["glyph_source_hashes"]["source_id"] = "OTHER"
    elif change == "hash":
        job["glyph_source_hashes"]["blocks"]["table_17"] = "0" * 64
    elif change == "text":
        job["blocks"][0]["text"] += " changed"
    elif change == "block":
        job["blocks"][0]["block_id"] = "OTHER"
    elif change == "missing_hashes":
        del job["glyph_source_hashes"]
    elif change == "missing_policy":
        del job["glyph_policy"]
    else:
        field = {"glyphs": "source_glyphs", "model_class": "model_characters"}.get(change, change)
        job["glyph_policy"][field] = "broadened"
    match, reason = ground_quote_v4("Hiraea 0.01 \u0002 0.00", job["blocks"][0], job)
    assert match is None
    assert reason == "ungrounded_quote"


def test_unique_alignment_reports_original_whitespace_and_unicode_offsets() -> None:
    """Retain raw coordinates through the unchanged split/join whitespace rule."""
    source = "prefix\n \tHiraea\u2003 0.01 ± 0.00\nN ¼ 4. suffix"
    quote = "  Hiraea 0.01\t\u0015 0.00 N\n\u0016 4.  "
    job = adaptive_job(source)
    match, reason = ground_quote_v4(quote, job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert match["matched_source_quote"] == source[match["start"]:match["end"]]
    assert match["emitted_quote"] == quote
    assert match["offset_unit"] == "unicode_code_point"
    for replacement in match["replacements"]:
        assert quote[replacement["model_offset"]] == replacement["model_character"]
        assert source[replacement["source_offset"]] == replacement["source_character"]


@pytest.mark.parametrize("source", ["a ± b. a ± b.", "a ± b. a ¼ b."])
def test_multiple_source_alignments_are_ambiguous(source: str) -> None:
    """Reject duplicated spans and competing glyph interpretations."""
    job = adaptive_job(source)
    match, reason = ground_quote_v4("a \u0002 b", job["blocks"][0], job)
    assert match is None
    assert reason == "ambiguous_glyph_match"


def test_one_control_cannot_infer_two_glyphs_in_one_span() -> None:
    """Require a consistent one-way map across mismatching positions."""
    job = adaptive_job("value ± 0.1 N ¼ 4")
    match, reason = ground_quote_v4("value \u0002 0.1 N \u0002 4", job["blocks"][0], job)
    assert match is None
    assert reason == "conflicting_glyph_mapping"


def test_distinct_controls_can_independently_match_the_same_cached_glyph() -> None:
    """Avoid assuming a reverse bijection unsupported by model-output evidence."""
    job = adaptive_job("a ± b ± c")
    match, reason = ground_quote_v4("a \u0002 b \u0005 c", job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert len(match["inferred_mapping"]) == 2


@pytest.mark.parametrize(
    ("source", "quote"),
    [("±", "\u0002"), ("± 4", "\u0002 4"), ("N ¼", "N \u0002"), ("± ¼", "\u0002 \u0005")],
)
def test_control_runs_need_literal_context_on_both_sides(source: str, quote: str) -> None:
    """Reject glyph-only quotations and unanchored boundary substitutions."""
    job = adaptive_job(source)
    match, reason = ground_quote_v4(quote, job["blocks"][0], job)
    assert match is None
    assert reason == "unanchored_glyph_match"


def test_an_adjacent_control_run_uses_its_outer_literal_context() -> None:
    """Allow a bounded run of multiple distinct corrupted glyphs."""
    job = adaptive_job("N ± ¼ 4")
    match, reason = ground_quote_v4("N \u0002 \u0005 4", job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert len(match["replacements"]) == 2


def test_exact_controls_take_precedence_and_remain_outside_the_inferred_map() -> None:
    """Preserve real cached controls even when a glyph alternative also exists."""
    quote = "a \u0002 b"
    job = adaptive_job(f"{quote}. a ± b.")
    del job["glyph_policy"]
    match, reason = ground_quote_v4(quote, job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert match["route"] == "exact"
    assert match["inferred_mapping"] == []
    assert match["replacements"] == []


def test_literal_control_and_substituted_same_control_can_coexist() -> None:
    """Retain real numeric separators beside recovered cached glyphs."""
    job = adaptive_job("literal \u0003 and N ¼ 4")
    match, reason = ground_quote_v4("literal \u0003 and N \u0003 4", job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert len(match["replacements"]) == 1
    assert match["replacements"][0]["source_character"] == "¼"


def test_repeated_exact_quotes_preserve_existing_acceptance() -> None:
    """Keep first-occurrence provenance under the unchanged exact route."""
    job = adaptive_job("a ± b. a ± b.")
    match, reason = ground_quote_v4("a ± b", job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert match["route"] == "exact"
    assert match["start"] == 0
