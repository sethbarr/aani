"""Integration checks for additive multispan v5 job construction."""

import hashlib
from pathlib import Path

from src.common.io import read_json
from src.extraction.pipeline import make_jobs
from src.extraction.printable_confusable_grounding import GLYPH_POLICY_V5

CORPUS = Path("data/interim/corpus_targeted_saverschek")


def test_v5_preserves_v4_model_context_and_binds_source_blocks() -> None:
    """Keep model-visible fields unchanged while adding the v5 local policy."""
    before = make_jobs(CORPUS, grounding_version="multispan_v4")
    after = make_jobs(CORPUS, grounding_version="multispan_v5")
    assert len(before) == len(after) == 3
    for old, new in zip(before, after, strict=True):
        for key in (
            "source_id",
            "title",
            "source_url",
            "chunk_index",
            "chunk_count",
            "prompt",
            "schema",
            "blocks",
            "source_ant_identity",
        ):
            assert old[key] == new[key]
        assert old["grounding_version"] == "multispan_v4"
        assert new["grounding_version"] == "multispan_v5"
        assert new["glyph_policy"] == GLYPH_POLICY_V5
        assert new["glyph_source_hashes"]["blocks"] == {
            block["block_id"]: hashlib.sha256(block["text"].encode("utf-8")).hexdigest()
            for block in new["blocks"]
        }


def test_v4_saved_job_hashes_remain_reproducible() -> None:
    """Keep the prior command mode and saved v4 hashes available."""
    manifest = read_json(
        Path("data/interim/extraction_saverschek_multispan_v4/run_manifest.json")
    )
    jobs = make_jobs(CORPUS, grounding_version="multispan_v4")
    assert [job["input_hash"] for job in jobs] == manifest["input_hashes"]
