"""Synthetic safety and provenance checks for cache-side C0 inference."""

import copy
import json
from pathlib import Path

import pytest

from src.extraction.cache_control_grounding import (
    CACHE_CONTROL_ROUTE,
    GLYPH_POLICY_V6,
    ground_quote_v6,
    ground_section_v6,
)
from tests.test_adaptive_glyph_grounding import adaptive_job


def cache_control_job(text: str) -> dict:
    """Bind synthetic source bytes to the immutable v6 policy."""
    job = adaptive_job(text)
    job["glyph_policy"] = copy.deepcopy(GLYPH_POLICY_V6)
    return job


@pytest.mark.parametrize("codepoint", range(32))
@pytest.mark.parametrize("printable", ["-", "—", "±", "="])
def test_each_c0_code_uses_the_same_cache_side_rule(codepoint: int, printable: str) -> None:
    """Allow only non-whitespace C0 with printable punctuation or symbol output."""
    job = cache_control_job(f"prefix habitat{chr(codepoint)}related suffix")
    quote = f"habitat{printable}related"
    match, reason = ground_quote_v6(quote, job["blocks"][0], job)
    if chr(codepoint).isspace():
        assert match is None
        assert reason == "ungrounded_quote"
    else:
        assert reason is None
        assert match is not None
        assert match["route"] == CACHE_CONTROL_ROUTE
        assert match["replacements"][0]["source_codepoint"] == f"U+{codepoint:04X}"
        assert match["replacements"][0]["model_character"] == printable


@pytest.mark.parametrize(
    ("cached", "quote"),
    [
        ("value \u0002 4", "value 7 4"),
        ("value \u0002 4", "value ⁷ 4"),
        ("value \u0002 4", "value ¼ 4"),
        ("plants re\u0002ected leaves", "plants rejected leaves"),
        ("plants rejected habitat\u0002related leaves", "plants accepted habitat-related leaves"),
        ("value 0.01 habitat\u0002related", "value 0.02 habitat-related"),
        ("habitat\u0002related and habitat\u0002related", "habitat-related and habitat-related"),
        ("habitat\u0002related value ± 4", "habitat-related value \u0003 4"),
        ("habitat\u0002related and leaf–related", "habitat-related and leaf-related"),
        ("habitat\u0002related", "habitat--related"),
        ("habitat\u0002related", "habitatrelated"),
        ("habitat\u0002related", "habitat\u0301related"),
        ("habitat\u0002related", "habitatZrelated"),
        ("habitat\u007frelated", "habitat-related"),
        ("habitat\u0080related", "habitat-related"),
        ("habitat\u0002related", "habitat\u0080related"),
    ],
)
def test_other_classes_or_additional_changes_fail(cached: str, quote: str) -> None:
    """Reject changed digits, direction letters, two positions and mixed classes."""
    job = cache_control_job(cached)
    assert ground_quote_v6(quote, job["blocks"][0], job) == (None, "ungrounded_quote")


@pytest.mark.parametrize(
    ("cached", "quote"),
    [("\u0002related", "-related"), ("habitat\u0002", "habitat-"), ("\u0002", "-")],
)
def test_mirrored_literal_anchors_are_required(cached: str, quote: str) -> None:
    """Reject substitutions without exact printable context on both sides."""
    job = cache_control_job(cached)
    assert ground_quote_v6(quote, job["blocks"][0], job) == (
        None, "unanchored_cache_control_match",
    )


def test_duplicate_permitted_alignment_fails() -> None:
    """Require one source location for a cache-side substitution."""
    job = cache_control_job("habitat\u0002related. habitat\u0002related.")
    assert ground_quote_v6("habitat-related", job["blocks"][0], job) == (
        None, "ambiguous_cache_control_match",
    )


@pytest.mark.parametrize("change", ["policy", "hash", "source", "text", "block"])
def test_source_and_policy_binding_are_required(change: str) -> None:
    """Refuse stale text, foreign block identities and modified policies."""
    job = cache_control_job("habitat\u0002related")
    if change == "policy":
        job["glyph_policy"]["differing_positions"] = 2
    elif change == "hash":
        job["glyph_source_hashes"]["blocks"]["table_17"] = "0" * 64
    elif change == "source":
        job["source_id"] = "OTHER"
    elif change == "text":
        job["blocks"][0]["text"] += " edited"
    else:
        job["blocks"][0]["block_id"] = "other"
    assert ground_quote_v6("habitat-related", job["blocks"][0], job) == (
        None, "ungrounded_quote",
    )


def test_original_offsets_and_characters_are_logged() -> None:
    """Preserve raw Unicode coordinates through ordinary whitespace normalization."""
    cached = "prefix\n\tHiraea  habitat\u0002related\t leaves."
    quote = "  Hiraea\n habitat-related leaves.  "
    job = cache_control_job(cached)
    original = copy.deepcopy(job)
    match, reason = ground_quote_v6(quote, job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert job == original
    assert match["emitted_quote"] == quote
    assert cached[match["start"]:match["end"]] == match["matched_source_quote"]
    assert match["offset_unit"] == "unicode_code_point"
    assert match["block_text_sha256"] == job["glyph_source_hashes"]["blocks"]["table_17"]
    replacement = match["replacements"][0]
    assert replacement["model_offset"] == quote.index("-")
    assert replacement["source_offset"] == cached.index("\u0002")
    assert replacement["model_codepoint"] == "U+002D"
    assert replacement["source_codepoint"] == "U+0002"
    assert replacement["route"] == CACHE_CONTROL_ROUTE


def test_exact_matches_keep_priority_and_need_no_policy() -> None:
    """Accept repeated normalized exact text without inferring a mapping."""
    job = cache_control_job("a \u0002 b. a - b. a - b.")
    del job["glyph_policy"]
    del job["glyph_source_hashes"]
    match, reason = ground_quote_v6("a\t- b", job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert match["route"] == "exact"
    assert match["replacements"] == []
    assert match["matched_source_quote"] == "a - b"


@pytest.mark.parametrize(
    ("cached", "quote", "expected_route"),
    [
        ("value ± 4", "value \u0002 4", "source_anchored_control_glyph"),
        ("habitat–related", "habitat-related", "source_anchored_printable_confusable"),
        ("value\u00a04", "value 4", "exact"),
    ],
)
def test_prior_quote_routes_remain(cached: str, quote: str, expected_route: str) -> None:
    """Keep v4 and v5 quote survivors with the declared exact-first order."""
    job = cache_control_job(cached)
    match, reason = ground_quote_v6(quote, job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert match["route"] == expected_route


def test_v5_success_remains_available_after_a_v4_safety_failure() -> None:
    """Keep an existing printable match despite a competing ambiguous C0 route."""
    job = cache_control_job("a ± b - c. a ± b - c. a \u0002 b – c.")
    match, reason = ground_quote_v6("a \u0002 b - c", job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert match["route"] == "source_anchored_printable_confusable"


@pytest.mark.parametrize(
    ("cached", "quote", "reason"),
    [
        ("a ± b - c. a ± b - c. a \u0002 b \u0003 c.", "a \u0002 b - c", "ambiguous_glyph_match"),
        ("a – b. a — b. a \u0002 b.", "a - b", "ambiguous_printable_match"),
    ],
)
def test_prior_safety_failures_prevent_cache_side_fallback(
    cached: str, quote: str, reason: str,
) -> None:
    """Preserve ambiguity failures even if a cache-side alignment also exists."""
    job = cache_control_job(cached)
    assert ground_quote_v6(quote, job["blocks"][0], job) == (None, reason)


def test_sections_use_existing_v5_without_cache_side_repair() -> None:
    """Keep printable-confusable section handling restricted to existing classes."""
    job = cache_control_job("quoted text")
    block = job["blocks"][0]
    block["section"] = "Long–term Results"
    match, reason = ground_section_v6("Long-term Results", block, job)
    assert reason is None
    assert match is not None
    assert match["route"] == "source_anchored_printable_confusable"
    block["section"] = "Long\u0002term Results"
    assert ground_section_v6("Long-term Results", block, job) == (None, "section_mismatch")


def test_policy_file_matches_the_fixed_policy() -> None:
    """Prevent runtime policy drift from the versioned configuration."""
    assert json.loads(Path("config/grounding_glyphs_v6.json").read_text()) == GLYPH_POLICY_V6
