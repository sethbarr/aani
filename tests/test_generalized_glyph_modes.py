"""Verify that v4 broadens comparison without changing any model request."""

import hashlib
from pathlib import Path
from unittest.mock import Mock

import httpx

from src.common.cache import CachedHTTP
from src.common.io import read_json
from src.extraction.gemini import request_gemini
from src.extraction.pipeline import make_jobs

CORPUS = Path("data/interim/corpus_targeted_saverschek")


def test_v4_preserves_model_context_and_binds_each_source_block() -> None:
    """Keep v3 prompts, schemas, source identity, and chunks byte-identical."""
    before = make_jobs(CORPUS, grounding_version="multispan_v3")
    after = make_jobs(CORPUS, grounding_version="multispan_v4")
    for old, new in zip(before, after, strict=True):
        for key in ("source_id", "title", "source_url", "chunk_index", "chunk_count",
                    "prompt", "schema", "blocks", "source_ant_identity"):
            assert old[key] == new[key]
        assert new["input_hash"] != old["input_hash"]
        assert new["glyph_source_hashes"]["source_id"] == new["source_id"]
        assert new["glyph_source_hashes"]["blocks"] == {
            block["block_id"]: hashlib.sha256(block["text"].encode("utf-8")).hexdigest()
            for block in new["blocks"]
        }


def test_legacy_job_hashes_remain_exactly_the_saved_hashes() -> None:
    """Keep baseline and v1 through v3 reproducible after the v4 mode addition."""
    for mode, suffix in (("single_quote_v1", ""), ("multispan_v1", "_multispan_v1"),
                         ("multispan_v2", "_multispan_v2"), ("multispan_v3", "_multispan_v3")):
        manifest = read_json(Path(f"data/interim/extraction_saverschek{suffix}/run_manifest.json"))
        jobs = make_jobs(CORPUS, grounding_version=mode)
        assert [job["input_hash"] for job in jobs] == manifest["input_hashes"]


def test_both_v4_samples_reuse_original_api_response_bytes_offline() -> None:
    """Forbid transport calls and prove exact proposal identity for both caches."""
    before = make_jobs(CORPUS, grounding_version="multispan_v3")
    after = make_jobs(CORPUS, grounding_version="multispan_v4")
    for path in (Path("data/raw"), Path("data/raw/grounding_v3_repeat")):
        handler = Mock(side_effect=AssertionError("Network request forbidden"))
        client = httpx.Client(transport=httpx.MockTransport(handler))
        cache = CachedHTTP(path, offline=True, client=client)
        try:
            for old, new in zip(before, after, strict=True):
                previous = request_gemini(old, cache, "gemini-3.8-flash")
                current = request_gemini(new, cache, "gemini-3.8-flash")
                assert previous["request_hash"] == current["request_hash"]
                assert previous["output"] == current["output"]
                assert previous["usage"] == current["usage"]
            handler.assert_not_called()
        finally:
            cache.close()
