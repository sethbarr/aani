"""Adversarial checks for the two-pair, block-scoped glyph comparison."""

import hashlib

import pytest

from src.common.io import normalise_space
from src.extraction.glyph_grounding import ground_quote, normalise_with_offsets


def glyph_job(text: str) -> dict:
    """Create a test block with an explicit policy for its exact bytes."""
    return {
        "source_id": "SAVERSCHEK2010",
        "blocks": [{"block_id": "b00005", "section": "Results", "text": text}],
        "glyph_policy": {
            "version": "glyph_v3",
            "scopes": [
                {
                    "source_id": "SAVERSCHEK2010",
                    "block_id": "b00005",
                    "block_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                }
            ],
            "substitutions": [
                {"model": "\u0001", "source": "±"},
                {"model": "\u0003", "source": "¼"},
            ],
        },
    }


@pytest.mark.parametrize(
    "raw",
    ["", "  ", "\talpha\n beta  ", "a\u2003b\u00a0c", "α\u0001β\u0003γ", "a\u001cb"],
)
def test_normalisation_matches_the_existing_whitespace_rule(raw: str) -> None:
    """Keep exactly the current Unicode whitespace behavior."""
    normalized = normalise_with_offsets(raw)
    assert normalized.text == normalise_space(raw)
    assert len(normalized.text) == len(normalized.raw_spans)
    for character, (start, end) in zip(normalized.text, normalized.raw_spans, strict=True):
        assert normalise_space(raw[start:end]) == character.strip()


def test_unique_glyph_alignment_records_raw_unicode_and_whitespace_offsets() -> None:
    """Trace every mismatch through normalization to both unchanged strings."""
    source = "prefix\n \tHiraea\u2003 0.01 ± 0.00\nN ¼ 4. suffix"
    quote = "  Hiraea 0.01\t\u0001 0.00 N\n\u0003 4.  "
    job = glyph_job(source)
    match, reason = ground_quote(quote, job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert match["route"] == "bounded_glyph_equivalence"
    assert match["emitted_quote"] == quote
    assert source[match["start"] : match["end"]] == match["matched_source_quote"]
    assert match["matched_source_quote"] == "Hiraea\u2003 0.01 ± 0.00\nN ¼ 4."
    assert match["offset_unit"] == "unicode_code_point"
    assert [(item["model_codepoint"], item["source_codepoint"]) for item in match["replacements"]] == [
        ("U+0001", "U+00B1"), ("U+0003", "U+00BC")
    ]
    for item in match["replacements"]:
        assert quote[item["model_offset"]] == item["model_character"]
        assert source[item["source_offset"]] == item["source_character"]


@pytest.mark.parametrize(
    ("source", "quote"),
    [
        ("Hiraea 0.01 ± 0.00", "Hiraea 0.02 \u0001 0.00"),
        ("Hiraea -0.01 ± 0.00", "Hiraea +0.01 \u0001 0.00"),
        ("Hiraea rejected ± 0.00", "Hiraea accepted \u0001 0.00"),
        ("Hiraea 0.01 ± 0.00", "Hiraea 0.01 \u0002 0.00"),
        ("Hiraea 0.01 ± 0.00", "Hiraea 0.01 \u0003 0.00"),
        ("N ¼ 4", "N = 4"),
        ("Hiraea 0.01 \u0001 0.00", "Hiraea 0.01 ± 0.00"),
        ("N \u0003 4", "N ¼ 4"),
        ("Hiraea 0.01 ± 0.00", "Hiraea 0.01 \u0001 0.00 invented"),
        ("Hiraea 0.01 ± 0.00", "Hiraea...0.01 \u0001 0.00"),
    ],
)
def test_any_other_character_mismatch_is_rejected(source: str, quote: str) -> None:
    """Reject changed words, signs, numbers, reverse mappings and other glyphs."""
    job = glyph_job(source)
    match, reason = ground_quote(quote, job["blocks"][0], job)
    assert match is None
    assert reason == "ungrounded_quote"


@pytest.mark.parametrize("change", ["source", "block", "hash", "text", "missing", "version"])
def test_glyph_fallback_requires_the_exact_policy_scope(change: str) -> None:
    """Deny fallback for a different source, block, source hash or policy."""
    job = glyph_job("Hiraea 0.01 ± 0.00")
    if change == "source":
        job["source_id"] = "OTHER"
        job["glyph_policy"]["scopes"][0]["source_id"] = "OTHER"
    elif change == "block":
        job["blocks"][0]["block_id"] = "b00006"
        job["glyph_policy"]["scopes"][0]["block_id"] = "b00006"
    elif change == "hash":
        job["glyph_policy"]["scopes"][0]["block_text_sha256"] = "0" * 64
    elif change == "text":
        job["blocks"][0]["text"] += " changed"
    elif change == "missing":
        del job["glyph_policy"]
    else:
        job["glyph_policy"]["version"] = "unknown"
    match, reason = ground_quote("Hiraea 0.01 \u0001 0.00", job["blocks"][0], job)
    assert match is None
    assert reason == "ungrounded_quote"


@pytest.mark.parametrize(
    "substitutions",
    [
        [],
        [{"model": "\u0001", "source": "±"}],
        [{"model": "\u0001", "source": "±"}, {"model": "\u0002", "source": "¼"}],
        [{"model": "\u0001", "source": "±"}, {"model": "\u0001", "source": "±"}],
        [{"model": "\u0001", "source": "±"}, {"model": "\u0003", "source": "="}],
        [{"model": "\u0001", "source": "±"}, {"model": [], "source": "¼"}],
        ["invalid", "invalid"],
    ],
)
def test_policy_cannot_extend_or_replace_the_two_fixed_pairs(substitutions: list) -> None:
    """Treat malformed or broadened equivalence policies as unavailable."""
    job = glyph_job("Hiraea 0.01 ± 0.00")
    job["glyph_policy"]["substitutions"] = substitutions
    match, reason = ground_quote("Hiraea 0.01 \u0001 0.00", job["blocks"][0], job)
    assert match is None
    assert reason == "ungrounded_quote"


def test_repeated_fallback_alignment_is_rejected() -> None:
    """Require unique source coordinates for a glyph-equivalent quote."""
    job = glyph_job("Hiraea 0.01 ± 0.00. Hiraea 0.01 ± 0.00.")
    match, reason = ground_quote("Hiraea 0.01 \u0001 0.00", job["blocks"][0], job)
    assert match is None
    assert reason == "ambiguous_glyph_match"


def test_exact_literal_controls_take_precedence_over_glyph_fallback() -> None:
    """Keep a literal matching control character even beside an equivalent row."""
    quote = "Hiraea 0.01 \u0001 0.00"
    job = glyph_job(f"{quote}. Hiraea 0.01 ± 0.00.")
    del job["glyph_policy"]
    match, reason = ground_quote(quote, job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert match["route"] == "exact"
    assert match["matched_source_quote"] == quote
    assert match["replacements"] == []


def test_aligned_comparison_keeps_matching_literal_controls() -> None:
    """Apply equivalence only at mismatching aligned character positions."""
    job = glyph_job("literal \u0001 and N ¼ 4")
    match, reason = ground_quote("literal \u0001 and N \u0003 4", job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert len(match["replacements"]) == 1
    assert match["replacements"][0]["model_codepoint"] == "U+0003"


def test_numeric_control_separator_remains_literal_next_to_a_recovered_plus_minus() -> None:
    """Keep the observed U+0003 numeric separator outside the substitution log."""
    source = "Hiraea -0.1\u0003 -0.2 ± 0.01"
    quote = "Hiraea -0.1\u0003 -0.2 \u0001 0.01"
    job = glyph_job(source)
    match, reason = ground_quote(quote, job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert match["matched_source_quote"] == source
    assert len(match["replacements"]) == 1
    assert match["replacements"][0]["model_codepoint"] == "U+0001"
    assert match["replacements"][0]["source_codepoint"] == "U+00B1"


def test_repeated_exact_matches_keep_existing_acceptance() -> None:
    """Keep the old exact substring rule and report its first source location."""
    job = glyph_job("Hiraea ± 0. Hiraea ± 0.")
    match, reason = ground_quote("Hiraea ± 0.", job["blocks"][0], job)
    assert reason is None
    assert match is not None
    assert match["route"] == "exact"
    assert match["start"] == 0
