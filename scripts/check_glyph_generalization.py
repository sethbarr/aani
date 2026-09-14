"""Exercise source-anchored glyph matching on invented text without model requests."""

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from src.common.io import write_json
from src.extraction.adaptive_glyph_grounding import GLYPH_POLICY_V4, ground_quote_v4

OBSERVED_CONTROL_CODES = frozenset({1, 3, 16, 17})
SYNTHETIC_SOURCE_ID = "SYNTHETIC_GLYPH_EXERCISE"
SYNTHETIC_BLOCK_ID = "invented_block_47"
DEFAULT_OUTPUT = Path("results/grounding_development_v4/generalization_checks.json")


def probe_definition(
    identifier: str, category: str, source: str, quote: str, accepted: bool,
    reason: str | None = None, code: int | None = None, glyph: str | None = None,
    binding: str = "bound",
) -> dict:
    """Describe one synthetic case and its predeclared expected outcome.

    Args:
        identifier: Stable case identifier.
        category: Aggregate category for the exercised behavior.
        source: Invented cached text.
        quote: Invented emitted quotation.
        accepted: Expected matcher acceptance.
        reason: Expected rejection reason, when acceptance is false.
        code: Model control code for single-substitution cases.
        glyph: Cached replacement glyph for single-substitution cases.
        binding: Whether to supply a valid, missing, or changed source hash.

    Returns:
        A JSON-compatible case definition containing raw synthetic text.
    """
    return {
        "id": identifier, "category": category,
        "source_text": source, "emitted_quote": quote,
        "expected_accepted": accepted, "expected_reason": reason,
        "model_codepoint": f"U+{code:04X}" if code is not None else None,
        "cached_glyph": glyph,
        "cached_codepoint": f"U+{ord(glyph):04X}" if glyph else None,
        "previously_observed_control_code": code in OBSERVED_CONTROL_CODES if code is not None else None,
        "source_binding": binding,
    }


def substitution_probes() -> list[dict]:
    """Exercise every C0 code against each allowed cached glyph.

    Returns:
        Accepted cases for non-whitespace controls and rejected cases for C0
        whitespace controls; whitespace handling retains its existing meaning.
    """
    probes = []
    for code in range(32):
        character = chr(code)
        accepted = not character.isspace()
        category = "non_whitespace_c0_substitution" if accepted else "whitespace_substitution"
        for glyph in ("±", "¼"):
            source = f"Invented result: 72 {glyph} 8 units; accepted material."
            quote = source.replace(glyph, character)
            probes.append(probe_definition(
                f"c0_{code:04x}_to_{ord(glyph):04x}", category, source, quote,
                accepted, None if accepted else "ungrounded_quote", code, glyph,
            ))
    return probes


def adversarial_probes() -> list[dict]:
    """Declare literal-text, alignment, anchoring, and mapping-conflict cases.

    Returns:
        Adversarial rejections and exact-match or consistent-map control cases.
    """
    definitions = [
        ("changed_number", "changed_number", "Result 72 ± 8 units accepted.",
         "Result 73 \x02 8 units accepted.", False, "ungrounded_quote"),
        ("changed_sign", "changed_sign", "Result -72 ± 8 units accepted.",
         "Result +72 \x02 8 units accepted.", False, "ungrounded_quote"),
        ("changed_word", "changed_word", "Result 72 ± 8 units accepted.",
         "Result 72 \x02 8 grams accepted.", False, "ungrounded_quote"),
        ("changed_direction", "changed_direction", "Result 72 ± 8 units accepted.",
         "Result 72 \x02 8 units rejected.", False, "ungrounded_quote"),
        ("inserted_printable", "changed_length", "Result 72 ± 8 units accepted.",
         "Result 720 \x02 8 units accepted.", False, "ungrounded_quote"),
        ("deleted_printable", "changed_length", "Result 72 ± 8 units accepted.",
         "Result 7 \x02 8 units accepted.", False, "ungrounded_quote"),
        ("digit_target", "disallowed_target", "Left 4 right.",
         "Left \x02 right.", False, "ungrounded_quote"),
        ("letter_target", "disallowed_target", "Left Q right.",
         "Left \x02 right.", False, "ungrounded_quote"),
        ("other_glyph_target", "disallowed_target", "Left ≈ right.",
         "Left \x02 right.", False, "ungrounded_quote"),
        ("minus_target", "disallowed_target", "Left − right.",
         "Left \x02 right.", False, "ungrounded_quote"),
        ("control_target", "disallowed_target", "Left \x03 right.",
         "Left \x02 right.", False, "ungrounded_quote"),
        ("printable_model_character", "disallowed_model_character", "Left ± right.",
         "Left ? right.", False, "ungrounded_quote"),
        ("c1_model_character", "disallowed_model_character", "Left ± right.",
         "Left \x81 right.", False, "ungrounded_quote"),
        ("delete_model_character", "disallowed_model_character", "Left ± right.",
         "Left \x7f right.", False, "ungrounded_quote"),
        ("ambiguous_alignment", "ambiguous_alignment", "Left ± right. Left ± right.",
         "Left \x02 right.", False, "ambiguous_glyph_match"),
        ("missing_left_anchor", "missing_anchor", "± right.",
         "\x02 right.", False, "unanchored_glyph_match"),
        ("missing_right_anchor", "missing_anchor", "Left ±",
         "Left \x02", False, "unanchored_glyph_match"),
        ("control_only_quote", "missing_anchor", "±",
         "\x02", False, "unanchored_glyph_match"),
        ("same_control_conflicting_targets", "conflicting_mapping", "Left ± middle ¼ right.",
         "Left \x02 middle \x02 right.", False, "conflicting_glyph_mapping"),
        ("same_control_consistent_targets", "consistent_mapping", "Left ± middle ± right.",
         "Left \x02 middle \x02 right.", True, None),
        ("distinct_controls_distinct_targets", "consistent_mapping", "Left ± middle ¼ right.",
         "Left \x02 middle \x04 right.", True, None),
        ("distinct_controls_same_target", "consistent_mapping", "Left ± middle ± right.",
         "Left \x02 middle \x04 right.", True, None),
        ("literal_control_exact_match", "exact_control", "Left \x02 middle ± right.",
         "Left \x02 middle ± right.", True, None),
        ("whitespace_exact_match", "exact_control", "Left ± middle ¼ right.",
         "Left\t±\nmiddle ¼ right.", True, None),
    ]
    probes = [probe_definition(*definition) for definition in definitions]
    for binding in ("missing", "changed", "wrong_source"):
        probes.append(probe_definition(
            f"source_binding_{binding}", "source_binding", "Left ± right.",
            "Left \x02 right.", False, "ungrounded_quote", binding=binding,
        ))
    return probes


def synthetic_context(probe: dict) -> tuple[dict, dict]:
    """Create an unrelated source and bind its exact invented text to the job.

    Args:
        probe: Synthetic case with raw text and source-binding expectations.

    Returns:
        The declared block and matcher job, containing no paper data.
    """
    block = {"block_id": SYNTHETIC_BLOCK_ID, "section": "synthetic",
             "text": probe["source_text"]}
    job = {
        "source_id": SYNTHETIC_SOURCE_ID,
        "glyph_policy": deepcopy(GLYPH_POLICY_V4),
        "glyph_source_hashes": {
            "source_id": SYNTHETIC_SOURCE_ID,
            "blocks": {SYNTHETIC_BLOCK_ID: hashlib.sha256(
                block["text"].encode("utf-8")
            ).hexdigest()},
        },
    }
    binding = probe["source_binding"]
    if binding == "missing":
        job.pop("glyph_source_hashes")
    elif binding == "changed":
        job["glyph_source_hashes"]["blocks"][SYNTHETIC_BLOCK_ID] = "changed-hash"
    elif binding == "wrong_source":
        job["glyph_source_hashes"]["source_id"] = "DIFFERENT_SYNTHETIC_SOURCE"
    return block, job


def exercise_probe(probe: dict) -> dict:
    """Run one declared matcher exercise and retain its actual provenance.

    Args:
        probe: A predeclared synthetic acceptance or rejection case.

    Returns:
        Expected and actual outcomes, the rejection reason, and any source match.
    """
    block, job = synthetic_context(probe)
    match, reason = ground_quote_v4(probe["emitted_quote"], block, job)
    accepted = match is not None and reason is None
    passed = accepted == probe["expected_accepted"] and reason == probe["expected_reason"]
    return {
        **probe, "actual_accepted": accepted, "actual_reason": reason,
        "passed": passed, "match": match,
        "source_id": SYNTHETIC_SOURCE_ID, "block_id": SYNTHETIC_BLOCK_ID,
    }


def probe_counts(probes: list[dict]) -> dict:
    """Count expected and actual matcher outcomes without percentages.

    Args:
        probes: Completed synthetic exercises within one reporting group.

    Returns:
        Case counts, acceptance counts, and expectation agreement counts.
    """
    return {
        "case_count": len(probes),
        "expected_accepted": sum(probe["expected_accepted"] for probe in probes),
        "expected_rejected": sum(not probe["expected_accepted"] for probe in probes),
        "actual_accepted": sum(probe["actual_accepted"] for probe in probes),
        "actual_rejected": sum(not probe["actual_accepted"] for probe in probes),
        "passed": sum(probe["passed"] for probe in probes),
        "failed": sum(not probe["passed"] for probe in probes),
    }


def build_generalization_checks() -> dict:
    """Run deterministic synthetic checks without loading proposals or contacting a model.

    Returns:
        Individual expected and actual outcomes, control-code coverage, aggregate
        counts, and explicit limits on what the exercise establishes.
    """
    probes = [exercise_probe(probe) for probe in substitution_probes() + adversarial_probes()]
    substitutions = [probe for probe in probes
                     if probe["category"] == "non_whitespace_c0_substitution"]
    source_path = Path(__file__).resolve().parents[1] / "src/extraction/adaptive_glyph_grounding.py"
    counts = probe_counts(probes)
    return {
        "schema_version": 1,
        "status": "complete" if counts["failed"] == 0 else "failed",
        "blocked_reason": None if counts["failed"] == 0 else "synthetic_expectation_mismatch",
        "exercise_type": "synthetic algorithm check",
        "scope": "Invented text under an unrelated source and block identifier; every source "
        "hash is bound before matching. This checks the algorithm across C0 codes and "
        "adversarial text changes. It provides no evidence from a held-out paper or model sample.",
        "model_requests": 0,
        "policy": deepcopy(GLYPH_POLICY_V4),
        "implementation": {"path": "src/extraction/adaptive_glyph_grounding.py",
                           "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest()},
        "counts": counts,
        "categories": {category: probe_counts([probe for probe in probes
                                                if probe["category"] == category])
                       for category in sorted({probe["category"] for probe in probes})},
        "control_coverage": {
            "definition": "Observed means emitted as a replacement for ± or ¼; literal controls already present in source text are excluded from that designation.",
            "non_whitespace_c0_code_count": sum(not chr(code).isspace() for code in range(32)),
            "c0_whitespace_code_count": sum(chr(code).isspace() for code in range(32)),
            "source_glyph_count": 2,
            "observed_control_codepoints": [f"U+{code:04X}" for code in sorted(OBSERVED_CONTROL_CODES)],
            "previously_observed_codes": probe_counts([
                probe for probe in substitutions if probe["previously_observed_control_code"]
            ]),
            "codes_not_observed_as_glyph_substitutions": probe_counts([
                probe for probe in substitutions if not probe["previously_observed_control_code"]
            ]),
        },
        "probes": probes,
    }


def main() -> None:
    """Write a new synthetic-check artifact and refuse to overwrite an existing file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"preserve_existing_artifact:{args.output}")
    report = build_generalization_checks()
    write_json(args.output, report)
    print(json.dumps({"status": report["status"], "output": str(args.output),
                      "counts": report["counts"], "model_requests": report["model_requests"]}))


if __name__ == "__main__":
    main()
