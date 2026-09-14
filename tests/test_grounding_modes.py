"""Check opt-in extraction mode isolation and the preserved original job hashes."""

from pathlib import Path

import pytest

from src.common.io import read_json
from src.extraction.pipeline import make_jobs
from src.extraction.prompts import MULTISPAN_PROMPT

CORPUS = Path("data/interim/corpus_targeted_saverschek")


def test_default_mode_reconstructs_original_extraction_jobs() -> None:
    """Keep the baseline prompt, schema, source chunks and their hashes reproducible."""
    manifest = read_json(Path("data/interim/extraction_saverschek/run_manifest.json"))
    jobs = make_jobs(CORPUS)
    assert [job["input_hash"] for job in jobs] == manifest["input_hashes"]
    assert all("grounding_version" not in job for job in jobs)


def test_multispan_changes_contract_without_changing_source_chunks() -> None:
    """Compare identical paper content under the explicit experimental contract."""
    original = make_jobs(CORPUS)
    changed = make_jobs(CORPUS, grounding_version="multispan_v1")
    assert len(original) == len(changed) == 3
    for old, new in zip(original, changed, strict=True):
        assert old["blocks"] == new["blocks"]
        assert old["source_id"] == new["source_id"]
        assert old["input_hash"] != new["input_hash"]
        assert new["grounding_version"] == "multispan_v1"
        assert new["prompt"] == MULTISPAN_PROMPT
        assert new["schema"] != old["schema"]


def test_unknown_grounding_mode_fails_before_reading_sources() -> None:
    """Do not silently apply a legacy validator to a misspelled new contract."""
    with pytest.raises(ValueError) as error:
        make_jobs(Path("missing"), grounding_version="invalid")
    assert "Unsupported grounding version" in str(error.value)
