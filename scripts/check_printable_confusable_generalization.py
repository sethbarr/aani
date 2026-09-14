"""Exercise the complete v5 matcher on deterministic invented text."""

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from scripts.check_glyph_generalization import (
    adversarial_probes,
    probe_counts,
    substitution_probes,
)
from src.common.io import write_json
from src.extraction.printable_confusable_grounding import (
    GLYPH_POLICY_V5,
    PRINTABLE_EQUIVALENCE_CLASSES,
    ground_quote_v5,
)

SYNTHETIC_SOURCE_ID = "SYNTHETIC_PRINTABLE_EXERCISE"
SYNTHETIC_BLOCK_ID = "invented_block_v5"
DEFAULT_OUTPUT = Path("results/grounding_development_v5/generalization_checks.json")


def printable_probe(
    identifier: str,
    category: str,
    source: str,
    quote: str,
    accepted: bool,
    reason: str | None = None,
) -> dict:
    """Declare one v5-specific synthetic expectation."""
    return {
        "id": identifier,
        "category": category,
        "source_text": source,
        "emitted_quote": quote,
        "expected_accepted": accepted,
        "expected_reason": reason,
        "source_binding": "bound",
    }


def printable_substitution_probes() -> list[dict]:
    """Exercise every ordered distinct pair in each permitted class."""
    probes: list[dict] = []
    names = ("hyphen_dash", "single_quote", "double_quote", "space")
    for name, equivalence_class in zip(names, PRINTABLE_EQUIVALENCE_CLASSES, strict=True):
        for source_character in equivalence_class:
            for model_character in equivalence_class:
                if source_character == model_character:
                    continue
                identifier = (
                    f"{name}_{ord(model_character):04x}_to_{ord(source_character):04x}"
                )
                source = f"Invented A{source_character}B result accepted."
                quote = f"Invented A{model_character}B result accepted."
                probe = printable_probe(identifier, f"{name}_substitution", source, quote, True)
                probe.update({
                    "model_character": model_character,
                    "model_codepoint": f"U+{ord(model_character):04X}",
                    "source_character": source_character,
                    "source_codepoint": f"U+{ord(source_character):04X}",
                })
                probes.append(probe)
    return probes


def printable_adversarial_probes() -> list[dict]:
    """Reject semantic changes that occur beside permitted substitutions."""
    return [
        printable_probe(
            "changed_digit_next_to_hyphen",
            "printable_adversarial_hyphen",
            "Dose 2‐3 units accepted.",
            "Dose 4‑3 units accepted.",
            False,
            "ungrounded_quote",
        ),
        printable_probe(
            "changed_word_with_smart_single_quote",
            "printable_adversarial_quotation",
            "The ‘resin’ choice is accept.",
            "The 'waxin’ choice is accept.",
            False,
            "ungrounded_quote",
        ),
        printable_probe(
            "changed_word_with_smart_double_quote",
            "printable_adversarial_quotation",
            "The “resin” choice is accept.",
            'The "waxin” choice is accept.',
            False,
            "ungrounded_quote",
        ),
        printable_probe(
            "changed_direction_word_with_nbsp",
            "printable_adversarial_space",
            "Direction: accept today.",
            "Direction: reject today.",
            False,
            "ungrounded_quote",
        ),
        printable_probe(
            "conflicting_printable_mapping",
            "printable_conflicting_mapping",
            "Left A‐B and C‑D right.",
            "Left A-B and C-D right.",
            False,
            "conflicting_glyph_mapping",
        ),
        printable_probe(
            "ambiguous_printable_alignment",
            "printable_ambiguous_alignment",
            "Left A‐B right. Left A‐B right.",
            "Left A‑B right.",
            False,
            "ambiguous_printable_match",
        ),
        printable_probe(
            "printable_missing_left_anchor",
            "printable_missing_anchor",
            "‐B right.",
            "‑B right.",
            False,
            "unanchored_printable_match",
        ),
        printable_probe(
            "printable_missing_right_anchor",
            "printable_missing_anchor",
            "Left A‐",
            "Left A‑",
            False,
            "unanchored_printable_match",
        ),
        printable_probe(
            "letter_substitution_outside_classes",
            "printable_closed_scope",
            "Left A‐B right.",
            "Left C‑B right.",
            False,
            "ungrounded_quote",
        ),
        printable_probe(
            "sign_substitution_outside_classes",
            "printable_closed_scope",
            "Left A+‐B right.",
            "Left A=‑B right.",
            False,
            "ungrounded_quote",
        ),
    ]


def synthetic_context(probe: dict) -> tuple[dict, dict]:
    """Bind one invented source block to the exact v5 policy."""
    block = {
        "block_id": SYNTHETIC_BLOCK_ID,
        "section": "synthetic",
        "text": probe["source_text"],
    }
    job = {
        "source_id": SYNTHETIC_SOURCE_ID,
        "glyph_policy": deepcopy(GLYPH_POLICY_V5),
        "glyph_source_hashes": {
            "source_id": SYNTHETIC_SOURCE_ID,
            "blocks": {
                SYNTHETIC_BLOCK_ID: hashlib.sha256(
                    block["text"].encode("utf-8")
                ).hexdigest()
            },
        },
    }
    binding = probe.get("source_binding", "bound")
    if binding == "missing":
        job.pop("glyph_source_hashes")
    elif binding == "changed":
        job["glyph_source_hashes"]["blocks"][SYNTHETIC_BLOCK_ID] = "changed-hash"
    elif binding == "wrong_source":
        job["glyph_source_hashes"]["source_id"] = "DIFFERENT_SOURCE"
    return block, job


def exercise_probe(probe: dict) -> dict:
    """Run one declared v5 expectation and retain complete match evidence."""
    block, job = synthetic_context(probe)
    match, reason = ground_quote_v5(probe["emitted_quote"], block, job)
    accepted = match is not None and reason is None
    passed = accepted == probe["expected_accepted"] and reason == probe["expected_reason"]
    return {
        **probe,
        "actual_accepted": accepted,
        "actual_reason": reason,
        "passed": passed,
        "match": match,
        "source_id": SYNTHETIC_SOURCE_ID,
        "block_id": SYNTHETIC_BLOCK_ID,
    }


def build_generalization_checks() -> dict:
    """Run the inherited v4 checks and all new printable-class checks."""
    definitions = (
        substitution_probes()
        + adversarial_probes()
        + printable_substitution_probes()
        + printable_adversarial_probes()
    )
    probes = [exercise_probe(probe) for probe in definitions]
    counts = probe_counts(probes)
    source_path = (
        Path(__file__).resolve().parents[1]
        / "src/extraction/printable_confusable_grounding.py"
    )
    categories = sorted({probe["category"] for probe in probes})
    required_adversarial_ids = [
        "changed_digit_next_to_hyphen",
        "changed_word_with_smart_single_quote",
        "changed_word_with_smart_double_quote",
        "changed_direction_word_with_nbsp",
    ]
    required = [probe for probe in probes if probe["id"] in required_adversarial_ids]
    return {
        "schema_version": 1,
        "status": "complete" if counts["failed"] == 0 else "failed",
        "blocked_reason": None if counts["failed"] == 0 else "synthetic_expectation_mismatch",
        "exercise_type": "synthetic algorithm check",
        "scope": (
            "Invented source-bound text exercises the inherited v4 control checks, every "
            "ordered printable-class substitution, and semantic changes beside permitted "
            "characters. It contains no model samples."
        ),
        "model_requests": 0,
        "network_requests": 0,
        "policy": deepcopy(GLYPH_POLICY_V5),
        "implementation": {
            "path": "src/extraction/printable_confusable_grounding.py",
            "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        },
        "counts": counts,
        "categories": {
            category: probe_counts([
                probe for probe in probes if probe["category"] == category
            ])
            for category in categories
        },
        "required_adversarial_checks": {
            "ids": required_adversarial_ids,
            "counts": probe_counts(required),
        },
        "probes": probes,
    }


def main() -> None:
    """Write the v5 synthetic-check artifact without overwriting prior evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"preserve_existing_artifact:{args.output}")
    report = build_generalization_checks()
    write_json(args.output, report)
    print(json.dumps({
        "status": report["status"],
        "output": str(args.output),
        "counts": report["counts"],
        "required_adversarial_checks": report["required_adversarial_checks"],
        "model_requests": 0,
        "network_requests": 0,
    }))
    if report["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
