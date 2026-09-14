"""Check additive v6 jobs and the strict task-deadline guard."""

from pathlib import Path

import pytest

from scripts.draw_grounding_v6_holdout import stop_at_deadline
from src.common.io import read_json
from src.extraction.cache_control_grounding import GLYPH_POLICY_V6
from src.extraction.pipeline import make_jobs

CORPUS = Path("data/interim/corpus_targeted_saverschek")


def test_v6_changes_only_local_grounding_metadata() -> None:
    """Preserve the original three model-visible jobs and identity contexts."""
    old = make_jobs(CORPUS, grounding_version="multispan_v2")
    new = make_jobs(CORPUS, grounding_version="multispan_v6")
    assert len(old) == len(new) == 3
    for before, after in zip(old, new, strict=True):
        for key in ("source_id", "title", "source_url", "chunk_index", "chunk_count",
                    "prompt", "schema", "blocks", "source_ant_identity"):
            assert before[key] == after[key]
        assert after["glyph_policy"] == GLYPH_POLICY_V6


@pytest.mark.parametrize("version", ["v4", "v5"])
def test_old_modes_keep_exact_saved_job_hashes(version: str) -> None:
    """Keep existing mode selection and original context hashes reproducible."""
    path = Path(f"data/interim/extraction_saverschek_multispan_{version}/run_manifest.json")
    jobs = make_jobs(CORPUS, grounding_version=f"multispan_{version}")
    assert [job["input_hash"] for job in jobs] == read_json(path)["input_hashes"]


def test_hard_deadline_raises_explicit_blocker() -> None:
    """Interrupt the active operation even if transport inactivity never times out."""
    with pytest.raises(TimeoutError) as error:
        stop_at_deadline(14, None)
    assert str(error.value) == "v6_wall_clock_deadline_reached"
