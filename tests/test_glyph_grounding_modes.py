"""Protect the single-variable glyph comparison against saved request drift."""

from pathlib import Path

import pytest

from src.common.cache import CachedHTTP
from src.common.io import read_json
from src.extraction.gemini import request_gemini
from src.extraction.pipeline import make_jobs

CORPUS = Path("data/interim/corpus_targeted_saverschek")


def test_v3_preserves_every_model_input() -> None:
    """Change only validator version and policy in the local job envelope."""
    before = make_jobs(CORPUS, grounding_version="multispan_v2")
    after = make_jobs(CORPUS, grounding_version="multispan_v3")
    assert len(before) == len(after) == 3
    for old, new in zip(before, after, strict=True):
        comparison = dict(new)
        comparison.pop("glyph_policy")
        comparison["grounding_version"] = old["grounding_version"]
        comparison["input_hash"] = old["input_hash"]
        assert comparison == old
        assert new["input_hash"] != old["input_hash"]


def test_all_legacy_job_hashes_are_preserved() -> None:
    """Keep default, v1, and v2 saved response lookup keys unchanged."""
    for mode, suffix in (("single_quote_v1", ""), ("multispan_v1", "_multispan_v1"),
                         ("multispan_v2", "_multispan_v2")):
        saved = read_json(Path(f"data/interim/extraction_saverschek{suffix}/run_manifest.json"))
        jobs = make_jobs(CORPUS, grounding_version=mode)
        assert [job["input_hash"] for job in jobs] == saved["input_hashes"]
        assert all("glyph_policy" not in job for job in jobs)


def test_v3_reuses_original_response_bytes_without_network() -> None:
    """Verify request keys and every model proposal for all three saved jobs."""
    before = make_jobs(CORPUS, grounding_version="multispan_v2")
    after = make_jobs(CORPUS, grounding_version="multispan_v3")
    cache = CachedHTTP(Path("data/raw"), offline=True)
    try:
        for old, new in zip(before, after, strict=True):
            original = request_gemini(old, cache, "gemini-3.8-flash")
            current = request_gemini(new, cache, "gemini-3.8-flash")
            assert original["request_hash"] == current["request_hash"]
            assert original["response_id"] == current["response_id"]
            assert original["output"] == current["output"]
    finally:
        cache.close()


@pytest.mark.parametrize("mode", ["single_quote_v1", "multispan_v1", "multispan_v2"])
def test_glyph_policy_requires_explicit_v3(mode: str) -> None:
    """Reject accidental normalization configuration on preserved modes."""
    with pytest.raises(ValueError) as error:
        make_jobs(CORPUS, grounding_version=mode, glyph_policy={})
    assert str(error.value) == "Glyph policy requires multispan_v3"
