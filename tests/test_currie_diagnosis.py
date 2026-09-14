"""Check deterministic Currie source and repeat-scoring diagnostics."""

from pathlib import Path

from src.common.io import read_json
from src.systems.config import load_system_config
from src.systems.currie_diagnosis import (
    CURRIE_INPUT_HASH,
    inspect_currie_blocks,
    score_currie_sample,
    verify_currie_job,
)


def currie_paths() -> tuple[Path, Path]:
    """Return the saved Currie job and source paths."""
    base = Path("data/interim/systems/attine_actino/reference_sources")
    return (
        base / f"extraction_payloads/{CURRIE_INPUT_HASH}.json",
        base / "corpus/texts/CURRIE1999.json",
    )


def test_saved_currie_job_has_unchanged_contract_and_intact_relation() -> None:
    """Verify source artifacts without changing the adapter or source text."""
    job_path, document_path = currie_paths()
    job = read_json(job_path)
    document = read_json(document_path)
    config = load_system_config(Path("config/systems/attine_actino.json"))
    checks = verify_currie_job(job, document, config)
    diagnosis = inspect_currie_blocks(job, document)
    assert all(checks.values())
    assert diagnosis["historical_streptomyces_naming"]["present"] is True
    assert diagnosis["glyph_artifacts"]["present"] is True
    assert diagnosis["line_break_hyphenation"]["present"] is True
    assert diagnosis["relation_block"]["complete_relation_present"] is True
    assert diagnosis["relation_block"]["reached_model_intact"] is True


def test_grounded_complete_candidate_recovers_fixed_currie_item() -> None:
    """Apply the fixed four-component match to an exact abstract record."""
    job_path, _ = currie_paths()
    job = read_json(job_path)
    config = load_system_config(Path("config/systems/attine_actino.json"))
    reference_set = read_json(Path("results/systems/attine_actino/reference_set.json"))
    reference = reference_set["reference_items"][0]
    abstract = next(block for block in job["blocks"] if block["block_id"] == "pdf:p701:abstract")
    candidate = {
        "behaving_organism_as_written": "attine ants",
        "target_name_as_written": "Streptomyces",
        "taxonomic_rank": "genus",
        "direction": "accept",
        "evidence_type": "compound_activity_assay",
        "quantitative_measure": None,
        "compound_name_as_written": "antibiotics",
        "activity_target_as_written": "Escovopsis",
        "activity_outcome": "suppresses",
        "source_id": "CURRIE1999",
        "section": "Abstract",
        "block_id": "pdf:p701:abstract",
        "evidence_quote": abstract["text"],
        "extraction_confidence": 0.95,
        "behavioural_choice": False,
        "study_context": "Currie 1999 abstract",
        "original_source_id": None,
    }
    envelope = {
        "input_hash": CURRIE_INPUT_HASH,
        "engine": "gemini-3.8-flash",
        "request_hash": "request",
        "output": {"records": [candidate]},
    }
    score = score_currie_sample(envelope, job, config, reference, 0.8)
    assert score["fixed_reference_recovered"] is True
    assert all(score["candidates"][0]["components"].values())

