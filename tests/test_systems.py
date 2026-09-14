"""Test config-driven exploratory systems and their isolation boundary."""

from pathlib import Path

import pytest

from scripts.system_pipeline import assert_isolated, prepare_controls
from src.common.io import read_json, write_json, write_jsonl
from src.systems.config import load_system_config, system_paths
from src.systems.extraction import make_system_jobs, validate_system_candidate


def test_all_prospective_configs_are_valid_and_capped() -> None:
    """Keep the three named systems inside the corpus, job, and time caps."""
    configs = [load_system_config(path) for path in sorted(Path("config/systems").glob("*.json"))]
    assert [config.slug for config in configs] == ["attine_actino", "monarch", "propolis"]
    assert all(config.corpus_limit <= 20 for config in configs)
    assert all(config.extraction_job_limit <= 12 for config in configs)
    assert all(config.time_limit_hours <= 4 for config in configs)
    assert configs[0].chemistry_backend == "none"
    assert not configs[0].run_chemistry and not configs[0].run_bioactivity


def test_system_paths_are_isolated(tmp_path: Path) -> None:
    """Resolve every artifact root under its system-specific directory."""
    config = load_system_config(Path("config/systems/propolis.json"))
    paths = system_paths(config, tmp_path)
    assert paths["interim"] == tmp_path / "data/interim/systems/propolis"
    assert paths["results"] == tmp_path / "results/systems/propolis"
    assert_isolated(paths["interim"] / "corpus", paths["interim"])
    with pytest.raises(ValueError):
        assert_isolated(tmp_path / "data/interim/corpus", paths["interim"])


def test_job_cap_keeps_whole_papers(tmp_path: Path) -> None:
    """Cap jobs without submitting a partial source document."""
    config = load_system_config(Path("config/systems/propolis.json"))
    papers = [
        {"source_id": "PMC1", "status": "ready", "title": "one", "source_url": "https://one"},
        {"source_id": "PMC2", "status": "ready", "title": "two", "source_url": "https://two"},
    ]
    write_jsonl(tmp_path / "manifest.jsonl", papers)
    blocks = [
        {"block_id": f"b{index:05d}", "section": "Body", "text": "x" * 20} for index in range(2)
    ]
    write_json(tmp_path / "texts/PMC1.json", {"source_id": "PMC1", "blocks": blocks})
    write_json(tmp_path / "texts/PMC2.json", {"source_id": "PMC2", "blocks": blocks})
    screening = tmp_path / "screening.json"
    write_json(
        screening,
        {
            "decisions": [
                {"source_id": "PMC1", "decision": "include", "reason": "relevant"},
                {"source_id": "PMC2", "decision": "include", "reason": "relevant"},
            ]
        },
    )
    config.extraction_job_limit = 3
    jobs, metrics = make_system_jobs(config, tmp_path, screening, maximum_characters=21)
    assert len(jobs) == 2
    assert {job["source_id"] for job in jobs} == {"PMC1"}
    assert metrics["sources_excluded_by_job_cap"] == ["PMC2"]


def test_system_grounding_and_direction_rules() -> None:
    """Require an exact target quote and enforce system-specific directions."""
    config = load_system_config(Path("config/systems/propolis.json"))
    quote = "Apis mellifera collected resin from Populus deltoides."
    job = {
        "source_id": "PMC1",
        "source_url": "https://example.org/PMC1",
        "input_hash": "input",
        "blocks": [{"block_id": "b00001", "section": "Body", "text": quote}],
    }
    candidate = {
        "behaving_organism_as_written": "Apis mellifera",
        "target_name_as_written": "Populus deltoides",
        "taxonomic_rank": "species",
        "direction": "accept",
        "evidence_type": "observational",
        "quantitative_measure": None,
        "compound_name_as_written": None,
        "activity_target_as_written": None,
        "activity_outcome": "unknown",
        "source_id": "PMC1",
        "section": "Body",
        "block_id": "b00001",
        "evidence_quote": quote,
        "extraction_confidence": 0.9,
        "behavioural_choice": True,
        "study_context": "resin collection",
        "original_source_id": None,
    }
    valid, reason = validate_system_candidate(candidate, job, config, 0.8)
    assert reason is None and valid is not None
    invalid, reason = validate_system_candidate(
        {**candidate, "direction": "reject"}, job, config, 0.8
    )
    assert invalid is None and reason == "reject_direction_unavailable"


def test_controls_replace_only_complete_discovery_sources(tmp_path: Path) -> None:
    """Prioritize the fixed controls while preserving original payload indexes."""
    config = Path("config/systems/attine_actino.json").resolve()
    interim = tmp_path / "data/interim/systems/attine_actino"
    reference = interim / "reference_sources"
    papers = [{
        "source_id": source, "status": "ready", "title": source,
        "source_url": "https://example.org/" + source,
    } for source in ("CURRIE1999", "PMC2748230")]
    write_jsonl(reference / "corpus/manifest.jsonl", papers)
    for paper in papers:
        write_json(reference / "corpus/texts" / f"{paper['source_id']}.json", {
            **paper, "blocks": [{"block_id": "b0", "section": "Body", "text": "reference"}],
        })
    write_json(reference / "screening.json", {"decisions": [
        {"source_id": paper["source_id"], "decision": "include"} for paper in papers
    ]})
    discovery = {"jobs": [{
        "source_id": source, "chunk_index": index, "chunk_count": chunks,
        "input_hash": f"{source}_{index}",
    } for source, chunks in (("PMC1", 9), ("PMC2", 2)) for index in range(chunks)]}
    path = interim / "extraction_payloads/index.json"
    write_json(path, discovery)
    selected = prepare_controls(config, tmp_path)
    assert len(selected["jobs"]) == 11
    assert selected["discovery_sources_displaced"] == ["PMC2"]
    assert {job["source_id"] for job in selected["jobs"]} == {
        "CURRIE1999", "PMC2748230", "PMC1",
    }
    assert read_json(path) == discovery
    assert not (tmp_path / "results/systems/attine_actino/payload_approval.json").exists()
