"""Diagnose repeated Currie extraction with the unchanged attine contract."""

import hashlib
from pathlib import Path

from src.common.io import digest, normalise_space
from src.systems.config import SystemConfig
from src.systems.control_review import reference_components
from src.systems.extraction import system_prompt, validate_system_candidate
from src.systems.schema import SystemExtraction

CURRIE_INPUT_HASH = "74c1ee6a105a05d5c5745d7be624efca8a7050135afd10b2991b371254c2eb2f"
EXPECTED_MODEL = "gemini-3.8-flash"
GLYPH_ARTIFACTS = {
    "®": "embedded-font substitution seen in words containing fi",
    "¯": "embedded-font substitution seen in words containing fl",
    "": "embedded-font substitution seen in mathematical notation",
}


def file_sha256(path: Path) -> str:
    """Hash the complete bytes of one diagnosis input.

    Args:
        path: Input file.

    Returns:
        Lowercase SHA-256 digest.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_currie_job(job: dict, document: dict, config: SystemConfig) -> dict:
    """Verify that the saved Currie job retains the original adapter contract.

    Args:
        job: Saved Currie extraction payload.
        document: Cached Currie source document.
        config: Existing attine system configuration.

    Returns:
        Adapter and source-integrity checks.

    Raises:
        ValueError: Any prompt, schema, source, or digest check differs.
    """
    calculated_hash = digest({key: value for key, value in job.items() if key != "input_hash"})
    source_blocks = {block["block_id"]: block for block in document["blocks"]}
    job_blocks = {block["block_id"]: block for block in job["blocks"]}
    checks = {
        "input_hash_matches_payload": calculated_hash == job["input_hash"] == CURRIE_INPUT_HASH,
        "source_is_currie_only": job["source_id"] == "CURRIE1999",
        "single_complete_source_chunk": job["chunk_index"] == 0 and job["chunk_count"] == 1,
        "grounding_version_unchanged": job["grounding_version"] == "single_quote_v1",
        "prompt_unchanged": job["prompt"] == system_prompt(config),
        "schema_unchanged": job["schema"] == SystemExtraction.model_json_schema(),
        "source_block_ids_unchanged": set(job_blocks) == set(source_blocks),
        "source_blocks_unchanged": job_blocks == source_blocks,
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise ValueError(f"Currie job differs from the saved attine contract: {failed}")
    return checks


def hyphenated_line_breaks(blocks: list[dict]) -> list[dict]:
    """List printed word hyphens that cross retained source lines.

    Args:
        blocks: Currie source blocks.

    Returns:
        Block-local left and right line fragments.
    """
    breaks = []
    for block in blocks:
        lines = block["text"].splitlines()
        for index, line in enumerate(lines[:-1]):
            if not line.rstrip().endswith("-"):
                continue
            left = line.rsplit(maxsplit=1)[-1]
            right = lines[index + 1].split(maxsplit=1)[0] if lines[index + 1].split() else ""
            breaks.append(
                {
                    "block_id": block["block_id"],
                    "line": index + 1,
                    "left_fragment": left,
                    "right_fragment": right,
                    "joined_display": left.removesuffix("-") + right,
                }
            )
    return breaks


def inspect_currie_blocks(job: dict, document: dict) -> dict:
    """Inspect naming, glyphs, line breaks, and relation-block integrity.

    Args:
        job: Exact model payload.
        document: Cached source document used to construct it.

    Returns:
        Deterministic source diagnostics.
    """
    blocks = job["blocks"]
    source_blocks = {block["block_id"]: block for block in document["blocks"]}
    historical_blocks = [
        block["block_id"] for block in blocks if "Streptomyces" in block["text"]
    ]
    glyphs = []
    for character, interpretation in GLYPH_ARTIFACTS.items():
        locations = [block["block_id"] for block in blocks if character in block["text"]]
        if locations:
            glyphs.append(
                {
                    "character": character,
                    "code_point": f"U+{ord(character):04X}",
                    "interpretation": interpretation,
                    "occurrences": sum(block["text"].count(character) for block in blocks),
                    "block_ids": locations,
                }
            )
    abstract = next(block for block in blocks if block["block_id"] == "pdf:p701:abstract")
    cached_abstract = source_blocks[abstract["block_id"]]
    relation_components = {
        "historical_producer": "Streptomyces" in abstract["text"],
        "compound_class": "antibiotics" in abstract["text"],
        "activity_target": "Escovopsis" in abstract["text"],
        "inhibition": "suppress the growth" in normalise_space(abstract["text"]),
    }
    corrigendum = next(block for block in blocks if block["block_id"] == "pdf:p461:corrigendum")
    return {
        "historical_streptomyces_naming": {
            "present": bool(historical_blocks),
            "block_ids": historical_blocks,
            "corrigendum_says_not_streptomyces": (
                "not a species of\nStreptomyces" in corrigendum["text"]
            ),
            "corrigendum_family_is_line_broken_pseudonocardiaceae": (
                "Pseudono-\ncardiaceae" in corrigendum["text"]
            ),
        },
        "glyph_artifacts": {"present": bool(glyphs), "artifacts": glyphs},
        "line_break_hyphenation": {
            "present": bool(hyphenated_line_breaks(blocks)),
            "instances": hyphenated_line_breaks(blocks),
        },
        "relation_block": {
            "block_id": abstract["block_id"],
            "section": abstract["section"],
            "components_present": relation_components,
            "complete_relation_present": all(relation_components.values()),
            "reached_model_intact": abstract == cached_abstract,
            "text_sha256": abstract["text_sha256"],
            "text": abstract["text"],
        },
    }


def score_currie_sample(
    envelope: dict,
    job: dict,
    config: SystemConfig,
    reference: dict,
    minimum_confidence: float,
) -> dict:
    """Score one response against the fixed Currie item.

    Args:
        envelope: Saved provider response envelope.
        job: Exact Currie request payload.
        config: Existing attine system configuration.
        reference: Fixed Currie reference item.
        minimum_confidence: Existing extraction confidence threshold.

    Returns:
        Candidate-level component checks and sample recovery.
    """
    candidates = []
    for index, candidate in enumerate(envelope["output"]["records"]):
        grounded, reason = validate_system_candidate(candidate, job, config, minimum_confidence)
        components = reference_components(grounded or candidate, reference)
        candidates.append(
            {
                "candidate_index": index,
                "grounded": grounded is not None,
                "validation_reason": reason,
                "record_id": grounded.get("record_id") if grounded else None,
                "components": components,
                "all_reference_components": all(components.values()),
                "fixed_reference_recovered": grounded is not None and all(components.values()),
                "candidate": candidate,
            }
        )
    return {
        "response_sha256": digest(envelope),
        "response_id": envelope.get("response_id"),
        "request_hash": envelope.get("request_hash"),
        "engine": envelope.get("engine"),
        "resolved_model": envelope.get("resolved_model"),
        "candidate_records": len(candidates),
        "any_candidate_surfaced": bool(candidates),
        "grounded_records": sum(row["grounded"] for row in candidates),
        "fixed_reference_recovered": any(row["fixed_reference_recovered"] for row in candidates),
        "candidates": candidates,
    }
