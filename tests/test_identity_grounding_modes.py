"""Protect attribution to source identity and same-block links in the v2 experiment."""

from pathlib import Path

import pytest

from src.common.io import read_json, read_jsonl
from src.extraction.multispan_v2 import validate_multispan_v2_candidate
from src.extraction.pipeline import make_jobs
from src.extraction.prompts import MULTISPAN_PROMPT

CORPUS = Path("data/interim/corpus_targeted_saverschek")


def test_v2_keeps_chunks_and_multispan_schema_unchanged() -> None:
    """Add the same resolved identity to each job without changing extraction requirements."""
    first = make_jobs(CORPUS, grounding_version="multispan_v1")
    second = make_jobs(CORPUS, grounding_version="multispan_v2")
    assert len(first) == len(second) == 3
    identity = second[0]["source_ant_identity"]
    assert identity["status"] == "resolved"
    assert identity["scientific_name"] == "Atta colombica"
    assert identity["provenance"]["block_id"] == "b00000"
    assert identity["provenance"]["evidence_quote"] == "Atta colombica"
    for old, new in zip(first, second, strict=True):
        assert new["source_ant_identity"] is identity
        assert new["blocks"] == old["blocks"]
        assert new["schema"] == old["schema"]
        assert new["prompt"].startswith(MULTISPAN_PROMPT)
        assert new["input_hash"] != old["input_hash"]


def test_v1_and_default_job_hashes_remain_reproducible() -> None:
    """Keep the preserved baseline and first experiment accessible through their cache keys."""
    for mode, directory in (("single_quote_v1", "extraction_saverschek"),
                            ("multispan_v1", "extraction_saverschek_multispan_v1")):
        saved = read_json(Path("data/interim") / directory / "run_manifest.json")
        jobs = make_jobs(CORPUS, grounding_version=mode)
        assert [job["input_hash"] for job in jobs] == saved["input_hashes"]
        assert all("source_ant_identity" not in job for job in jobs)


def test_overrides_cannot_mutate_legacy_jobs() -> None:
    """Require explicit v2 selection before any source-wide identity override is applied."""
    with pytest.raises(ValueError) as error:
        make_jobs(CORPUS, ant_identity_overrides={})
    assert "require multispan_v2" in str(error.value)


def test_same_saved_v1_candidates_exercise_only_new_grounding_routes() -> None:
    """Recover the ant abbreviations and Hymenaea supporting name without sampling again."""
    original = make_jobs(CORPUS, grounding_version="multispan_v1")
    changed = make_jobs(CORPUS, grounding_version="multispan_v2")
    job_by_old_hash = {old["input_hash"]: new for old, new in zip(original, changed, strict=True)}
    rows = read_jsonl(Path("data/interim/extraction_saverschek_multispan_v1/rejections.jsonl"))
    recovered = []
    failures = []
    for row in rows:
        record, reason = validate_multispan_v2_candidate(
            row["candidate"], job_by_old_hash[row["input_hash"]], 0.8
        )
        if record is not None:
            recovered.append(record)
        else:
            failures.append((row["candidate"]["plant_name_as_written"], reason))
    assert len(recovered) == 6
    assert failures == [("S. lindenianum", "unabbreviated_genus_required")]
    assert sum(row["plant_name_as_written"] == "Hymenaea courbaril" for row in recovered) == 3
