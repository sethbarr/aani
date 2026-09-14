"""Check seeded preparation, exact source copies, adapter parity, and approval gates."""

from pathlib import Path

import pytest

from src.chemistry.export_cache import file_hash
from src.common.io import read_json, read_jsonl, write_json, write_jsonl
from src.systems.config import load_system_config
from src.systems.extraction import export_system_jobs, make_system_jobs
from src.systems.monarch_seeded_prepare import (
    canonical_doi,
    merge_ready_sources,
    prepare_seeded_monarch,
    validate_preparation_contract,
)


def source_row(source_id: str, doi: str, **extra: object) -> dict:
    """Create source provenance with the fields consumed by the original adapter."""
    return {"source_id": source_id, "title": f"Paper {source_id}", "doi": doi,
            "source_url": f"https://example.org/{source_id}", "status": "ready",
            "retrieved_at": "2026-09-13T16:30:00+00:00", **extra}


def write_source(corpus: Path, row: dict, blocks: int = 1) -> None:
    """Create complete source blocks, each requiring one extraction chunk."""
    write_json(corpus / "texts" / f"{row['source_id']}.json", {
        "source_id": row["source_id"], "blocks": [
            {"source_id": row["source_id"], "block_id": f"b{index:05d}",
             "section": "Body", "text": "x" * 23900, "kind": "p"}
            for index in range(blocks)
        ],
    })


@pytest.fixture
def prepared_root(tmp_path: Path) -> Path:
    """Materialize an original twenty-source run with valid historical payload hashes."""
    config_path = tmp_path / "config/systems/monarch.json"
    write_json(config_path, read_json(Path("config/systems/monarch.json")))
    original = tmp_path / "data/interim/systems/monarch"
    rows = [source_row(f"PMC{index}", f"10.1000/discovery{index}") for index in range(20)]
    for row in rows:
        write_source(original / "corpus", row)
    rows.append(source_row("PMCfailed", "10.1000/failed", status="failed"))
    write_jsonl(original / "corpus/manifest.jsonl", rows)
    write_json(original / "screening.json", {"decisions": [
        {"source_id": row["source_id"], "decision": "include" if row["status"] == "ready"
         else "exclude", "reason": "Recorded original screening decision."} for row in rows
    ]})
    config = load_system_config(config_path)
    jobs, metrics = make_system_jobs(config, original / "corpus", original / "screening.json")
    export_system_jobs(jobs, original / "extraction_payloads", metrics)
    write_json(original / "extraction/run_manifest.json", {
        "model": "gemini-3.8-flash", "provider": "gemini", "grounding_version": "single_quote_v1",
    })
    write_json(tmp_path / "results/systems/monarch/run_manifest.json", {
        "config": {"sha256": file_hash(config_path)},
    })
    write_jsonl(tmp_path / "data/interim/systems/monarch_seeded/corpus_targeted_monarch/manifest.jsonl",
                [])
    return tmp_path


def add_seed(root: Path, source_id: str = "PMCseed", doi: str = "10.1000/seed",
             blocks: int = 1) -> dict:
    """Supply one independently verified ready seed and its recorded inclusion decision."""
    corpus = root / "data/interim/systems/monarch_seeded/corpus_targeted_monarch"
    row = source_row(source_id, doi, bibliography_verified=True, indexed_doi=doi)
    write_source(corpus, row, blocks)
    write_jsonl(corpus / "manifest.jsonl", [row])
    write_json(corpus / "screening.json", {"decisions": [
        {"source_id": source_id, "decision": "include", "reason": "Direct focal choice test."},
    ]})
    return row


def test_zero_seeds_copies_twenty_sources_and_blocks_payloads(prepared_root: Path) -> None:
    """Preserve exact discovery text and manifest bytes while refusing a discovery-only rerun."""
    original = prepared_root / "data/interim/systems/monarch"
    report = prepare_seeded_monarch(prepared_root)
    corpus = Path(report["corpus_path"])
    assert report["status"] == "blocked"
    assert report["blocked_reason"] == "no_retrieved_seed_fulltexts"
    assert report["jobs"] is None
    assert report["payloads_prepared"] is False
    assert report["compatibility"]["compatible"] is True
    assert report["corpus"]["ready_sources"] == report["corpus"]["screened_sources"] == 20
    assert not (Path(report["payload_path"]) / "index.json").exists()
    assert (corpus / "discovery_original/manifest.jsonl").read_bytes() == (
        original / "corpus/manifest.jsonl"
    ).read_bytes()
    for row in read_jsonl(corpus / "manifest.jsonl"):
        name = f"{row['source_id']}.json"
        assert (corpus / "texts" / name).read_bytes() == (
            original / "corpus/texts" / name
        ).read_bytes()
    decisions = read_json(Path(report["screening_path"]))["decisions"]
    assert all(row["originating_screening_sha256"] == file_hash(original / "screening.json")
               for row in decisions)


def test_seeds_prioritized_with_complete_papers_under_twelve_jobs(prepared_root: Path) -> None:
    """Give all chunks of a retrieved seed priority before remaining original sources."""
    add_seed(prepared_root, blocks=3)
    report = prepare_seeded_monarch(prepared_root)
    index = read_json(Path(report["payload_path"]) / "index.json")
    assert report["status"] == "awaiting_payload_export_approval"
    assert report["jobs"] == 12
    assert report["corpus"]["ready_sources"] == 21
    assert [row["source_id"] for row in index["jobs"][:3]] == ["PMCseed"] * 3
    assert [row["chunk_index"] for row in index["jobs"][:3]] == [0, 1, 2]
    assert all(row["chunk_count"] == 3 for row in index["jobs"][:3])
    assert report["seed_sources_selected_for_extraction"] == ["PMCseed"]
    assert report["compatibility"]["checks"]["regenerated_original_input_hashes_match"] is True
    assert index["approval_status"] == report["approval_status"] == "pending"
    assert report["model_api_called"] is report["external_payload_sent"] is False
    first_job = read_json(Path(report["payload_path"]) / f"{index['jobs'][0]['input_hash']}.json")
    assert first_job["system_slug"] == "monarch"
    assert first_job["grounding_version"] == "single_quote_v1"


def test_doi_identity_dedup_prefers_seed_and_archives_all_discovery(prepared_root: Path) -> None:
    """Deduplicate canonical DOI identity while preserving each original source copy."""
    add_seed(prepared_root, doi="https://doi.org/10.1000/DISCOVERY0")
    report = prepare_seeded_monarch(prepared_root)
    corpus = Path(report["corpus_path"])
    rows = read_jsonl(corpus / "manifest.jsonl")
    assert rows[0]["source_id"] == "PMCseed"
    assert "PMC0" not in {row["source_id"] for row in rows}
    assert report["corpus"]["ready_sources"] == 20
    assert report["corpus"]["deduplicated_sources"] == 1
    assert (corpus / "discovery_original/texts/PMC0.json").exists()
    provenance = read_json(corpus / "provenance.json")["source_selection"]
    duplicate = next(row for row in provenance if row["source_id"] == "PMC0")
    assert duplicate["deduplicated_to"] == "PMCseed"


def test_seed_screening_must_be_complete(prepared_root: Path) -> None:
    """Stop before payload export when a retrieved seed lacks a screening decision."""
    add_seed(prepared_root)
    targeted = prepared_root / "data/interim/systems/monarch_seeded/corpus_targeted_monarch"
    write_json(targeted / "screening.json", {"decisions": []})
    with pytest.raises(ValueError, match="screening_must_cover_exact_source_set"):
        prepare_seeded_monarch(prepared_root)


def test_seed_identity_must_match_verified_doi(prepared_root: Path) -> None:
    """Reject contradictory DOI provenance before preparing source text for extraction."""
    row = add_seed(prepared_root)
    row["indexed_doi"] = "10.1000/different"
    targeted = prepared_root / "data/interim/systems/monarch_seeded/corpus_targeted_monarch"
    write_jsonl(targeted / "manifest.jsonl", [row])
    with pytest.raises(ValueError, match="seed_doi_differs"):
        prepare_seeded_monarch(prepared_root)


def test_changed_original_adapter_contract_blocks_export(prepared_root: Path) -> None:
    """Detect changed prompt/config state through both exact file and payload comparisons."""
    add_seed(prepared_root)
    config_path = prepared_root / "config/systems/monarch.json"
    config = read_json(config_path)
    config["behaviour"] = "A changed behavioural target"
    write_json(config_path, config)
    report = prepare_seeded_monarch(prepared_root)
    assert report["status"] == "blocked"
    assert report["blocked_reason"] == "original_adapter_compatibility_failed"
    assert report["compatibility"]["checks"]["config_sha256_matches_original"] is False
    assert report["compatibility"]["checks"]["prompt_matches_all_original_payloads"] is False
    assert report["jobs"] is None


def test_offline_preparation_preserves_live_and_original_outputs(prepared_root: Path) -> None:
    """Replay preparation deterministically into seeded-only replay directories."""
    add_seed(prepared_root)
    live = prepare_seeded_monarch(prepared_root)
    live_index = Path(live["payload_path"]) / "index.json"
    live_bytes = live_index.read_bytes()
    original = prepared_root / "data/interim/systems/monarch/extraction_payloads/index.json"
    original_bytes = original.read_bytes()
    replay = prepare_seeded_monarch(prepared_root, offline=True)
    assert replay["input_hashes"] == live["input_hashes"]
    assert Path(replay["payload_path"]).parent.name == "offline_replay"
    assert live_index.read_bytes() == live_bytes
    assert original.read_bytes() == original_bytes


def test_preparation_preserves_approved_payload_boundary(prepared_root: Path) -> None:
    """Prevent a later preparation call from replacing approved source payloads."""
    write_json(prepared_root / "results/systems/monarch_seeded/payload_approval.json",
               {"approved": True})
    with pytest.raises(ValueError, match="approved_seeded_payloads_cannot_be_reprepared"):
        prepare_seeded_monarch(prepared_root)


def test_doi_normalization_and_source_id_dedup() -> None:
    """Retain original DOI text while matching standard DOI URL and case variants."""
    assert canonical_doi(" doi:10.1000/EXAMPLE ") == "10.1000/example"
    assert canonical_doi(None) is None
    selected, provenance = merge_ready_sources(
        [source_row("PMC1", "10.1000/seed")], [source_row("PMC1", "10.1000/different")],
    )
    assert len(selected) == 1
    assert provenance[1]["selected"] is False


def test_independent_preparation_cap_and_grounding_guards() -> None:
    """Keep the twelve-job single-quote boundary if a caller bypasses config validation."""
    config = load_system_config(Path("config/systems/monarch.json"))
    with pytest.raises(ValueError, match="job_cap_exceeds_twelve"):
        validate_preparation_contract(config.model_copy(update={"extraction_job_limit": 13}))
    with pytest.raises(ValueError, match="original_monarch_single_quote_adapter"):
        validate_preparation_contract(config.model_copy(update={"extraction_grounding": "v4"}))
