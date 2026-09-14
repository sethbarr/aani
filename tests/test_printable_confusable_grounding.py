"""Tests for the ordered v5 printable-confusable matcher."""

from hashlib import sha256

import pytest

from src.extraction.adaptive_glyph_grounding import GLYPH_POLICY_V4
from src.extraction.printable_confusable_grounding import (
    GLYPH_POLICY_V5,
    ground_quote_v5,
    ground_section_v5,
)


def bound_job(source: str, section: str = "Results") -> tuple[dict, dict]:
    """Create one source-bound synthetic v5 job and block."""
    block = {"block_id": "b1", "section": section, "text": source}
    job = {
        "source_id": "SYNTHETIC",
        "glyph_policy": GLYPH_POLICY_V5,
        "glyph_source_hashes": {
            "source_id": "SYNTHETIC",
            "blocks": {"b1": sha256(source.encode("utf-8")).hexdigest()},
        },
    }
    return job, block


@pytest.mark.parametrize(
    ("source_character", "model_character"),
    [
        ("‐", "‑"),
        ("'", "’"),
        ("‘", "'"),
        ('"', "”"),
        ("“", '"'),
        (" ", " "),
        (" ", " "),
    ],
)
def test_each_printable_class_is_logged(
    source_character: str, model_character: str,
) -> None:
    """Accept a unique aligned substitution and retain raw code points."""
    source = f"Left A{source_character}B right."
    quote = f"Left A{model_character}B right."
    job, block = bound_job(source)
    match, reason = ground_quote_v5(quote, block, job)
    assert reason is None
    assert match is not None
    assert match["route"] == "source_anchored_printable_confusable"
    assert match["replacements"] == [{
        "model_character": model_character,
        "source_character": source_character,
        "model_codepoint": f"U+{ord(model_character):04X}",
        "source_codepoint": f"U+{ord(source_character):04X}",
        "model_offset": 6,
        "source_offset": 6,
    }]


@pytest.mark.parametrize(
    ("source", "quote"),
    [
        ("Dose 2‐3 accepted.", "Dose 4‑3 accepted."),
        ("The ‘resin’ word accepted.", "The 'waxin’ word accepted."),
        ("Direction: accept now.", "Direction: reject now."),
    ],
)
def test_nearby_semantic_changes_reject(source: str, quote: str) -> None:
    """Reject digits, words, and direction changes beside permitted classes."""
    job, block = bound_job(source)
    assert ground_quote_v5(quote, block, job) == (None, "ungrounded_quote")


def test_v4_control_route_runs_before_printable_fallback() -> None:
    """Preserve v4 control inference and its route in v5."""
    source = "Result 2 ± 1 accepted."
    job, block = bound_job(source)
    match, reason = ground_quote_v5("Result 2 \u0015 1 accepted.", block, job)
    assert reason is None
    assert match is not None
    assert match["route"] == "source_anchored_control_glyph"
    assert job["glyph_policy"]["control_glyph_policy"] == GLYPH_POLICY_V4


def test_conflicting_printable_mapping_rejects() -> None:
    """Reject one emitted character aligned to two cached characters."""
    source = "Left A‐B and C‑D right."
    quote = "Left A-B and C-D right."
    job, block = bound_job(source)
    assert ground_quote_v5(quote, block, job) == (None, "conflicting_glyph_mapping")


def test_ambiguous_printable_alignment_rejects() -> None:
    """Require one acceptable source alignment for printable inference."""
    source = "Left A‐B right. Left A‐B right."
    job, block = bound_job(source)
    assert ground_quote_v5("Left A‑B right.", block, job) == (
        None, "ambiguous_printable_match",
    )


def test_section_uses_same_printable_guards_and_logs_offsets() -> None:
    """Canonicalize a bound section only after aligned v5 comparison."""
    source = "Quote text."
    cached_section = "Origin‐ and Species‐Specific"
    emitted_section = "Origin‑ and Species‑Specific"
    job, block = bound_job(source, cached_section)
    match, reason = ground_section_v5(emitted_section, block, job)
    assert reason is None
    assert match is not None
    assert match["matched_source_section"] == cached_section
    assert match["replacements"][0]["model_codepoint"] == "U+2011"
    assert match["replacements"][0]["source_codepoint"] == "U+2010"


def test_policy_scope_is_closed() -> None:
    """Reject an added printable class or changed source binding."""
    source = "Left A‐B right."
    job, block = bound_job(source)
    job["glyph_policy"] = {**GLYPH_POLICY_V5, "extra": True}
    assert ground_quote_v5("Left A‑B right.", block, job) == (None, "ungrounded_quote")
