"""Check synthetic glyph exercises and their reported scope without model requests."""

from scripts.check_glyph_generalization import (
    OBSERVED_CONTROL_CODES,
    SYNTHETIC_BLOCK_ID,
    SYNTHETIC_SOURCE_ID,
    adversarial_probes,
    build_generalization_checks,
    exercise_probe,
    substitution_probes,
)


def test_every_c0_code_is_exercised_against_both_allowed_glyphs() -> None:
    """Cover all 32 C0 codes while preserving the whitespace exclusion."""
    definitions = substitution_probes()
    assert len(definitions) == 64
    assert {(probe["model_codepoint"], probe["cached_glyph"]) for probe in definitions} == {
        (f"U+{code:04X}", glyph) for code in range(32) for glyph in ("±", "¼")
    }
    assert sum(probe["expected_accepted"] for probe in definitions) == 46
    assert sum(not probe["expected_accepted"] for probe in definitions) == 18
    assert all(exercise_probe(probe)["passed"] for probe in definitions)


def test_unobserved_control_codes_are_reported_separately() -> None:
    """Separate codes not observed as glyph replacements from the four observed replacements."""
    report = build_generalization_checks()
    coverage = report["control_coverage"]
    assert coverage["non_whitespace_c0_code_count"] == 23
    assert coverage["c0_whitespace_code_count"] == 9
    assert coverage["observed_control_codepoints"] == [
        f"U+{code:04X}" for code in sorted(OBSERVED_CONTROL_CODES)
    ]
    assert coverage["previously_observed_codes"]["case_count"] == 8
    assert coverage["previously_observed_codes"]["passed"] == 8
    assert coverage["codes_not_observed_as_glyph_substitutions"]["case_count"] == 38
    assert coverage["codes_not_observed_as_glyph_substitutions"]["passed"] == 38


def test_adversarial_cases_reject_each_disallowed_change() -> None:
    """Exercise changed literals, targets, alignments, anchors, mappings, and bindings."""
    probes = [exercise_probe(probe) for probe in adversarial_probes()]
    assert all(probe["passed"] for probe in probes)
    categories = {probe["category"] for probe in probes if not probe["expected_accepted"]}
    assert categories == {
        "changed_number", "changed_sign", "changed_word", "changed_direction", "changed_length",
        "disallowed_target", "disallowed_model_character", "ambiguous_alignment",
        "missing_anchor", "conflicting_mapping", "source_binding",
    }
    by_id = {probe["id"]: probe for probe in probes}
    assert by_id["ambiguous_alignment"]["actual_reason"] == "ambiguous_glyph_match"
    assert by_id["same_control_conflicting_targets"]["actual_reason"] == "conflicting_glyph_mapping"
    assert by_id["missing_left_anchor"]["actual_reason"] == "unanchored_glyph_match"
    assert by_id["missing_right_anchor"]["actual_reason"] == "unanchored_glyph_match"


def test_exact_and_consistent_mapping_controls_keep_their_routes() -> None:
    """Preserve literal controls and the existing whitespace-normalized exact route."""
    probes = {probe["id"]: exercise_probe(probe) for probe in adversarial_probes()}
    for identifier in ("literal_control_exact_match", "whitespace_exact_match"):
        assert probes[identifier]["match"]["route"] == "exact"
        assert probes[identifier]["match"]["replacements"] == []
    for identifier in (
        "same_control_consistent_targets", "distinct_controls_distinct_targets",
        "distinct_controls_same_target",
    ):
        assert probes[identifier]["match"]["route"] == "source_anchored_control_glyph"


def test_report_is_counted_deterministic_and_explicitly_synthetic() -> None:
    """Avoid new-paper or model-sample generalization claims in the algorithm exercise."""
    report = build_generalization_checks()
    assert report == build_generalization_checks()
    assert report["status"] == "complete"
    assert report["counts"]["failed"] == 0
    assert report["counts"]["passed"] == len(report["probes"])
    assert report["model_requests"] == 0
    assert report["exercise_type"] == "synthetic algorithm check"
    assert "held-out paper or model sample" in report["scope"]
    assert all(probe["source_id"] == SYNTHETIC_SOURCE_ID for probe in report["probes"])
    assert all(probe["block_id"] == SYNTHETIC_BLOCK_ID for probe in report["probes"])
    assert all(probe["source_id"] != "SAVERSCHEK2010" for probe in report["probes"])
    assert len(report["implementation"]["sha256"]) == 64
