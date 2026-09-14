"""Check offline-only replay and the two-sample report contract."""

from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from scripts.replay_grounding_repeat import run_offline
from scripts.report_grounding_repeat import HEADERS, generalization_verdict, render_summary
from src.common.cache import CachedHTTP
from src.common.io import read_json
from src.evaluation.repeat_comparison import build_repeat_comparison
from src.evaluation.repeat_failures import classify_repeat_failures
from src.extraction.gemini import request_gemini
from src.extraction.pipeline import make_jobs

CORPUS = Path("data/interim/corpus_targeted_saverschek")
EXTRACTION = Path("data/interim/extraction_saverschek_multispan_v3_repeat")
REPORT = Path("results/grounding_development_v3")


def test_saved_repeat_requests_require_zero_network_calls() -> None:
    """Read all three saved responses with a transport that fails if called."""
    handler = Mock(side_effect=AssertionError("Network request forbidden"))
    client = httpx.Client(transport=httpx.MockTransport(handler))
    cache = CachedHTTP(Path("data/raw/grounding_v3_repeat"), offline=True, client=client)
    try:
        counts = []
        for job in make_jobs(CORPUS, grounding_version="multispan_v3"):
            envelope = request_gemini(job, cache, "gemini-3.8-flash")
            counts.append(len(envelope["output"]["records"]))
        assert counts == [0, 16, 2]
        handler.assert_not_called()
    finally:
        cache.close()


def test_offline_runner_refuses_an_existing_output(tmp_path: Path) -> None:
    """Prevent rerun helpers from replacing any saved output directory."""
    with pytest.raises(ValueError) as error:
        run_offline(tmp_path)
    assert "refusing_to_overwrite_existing_artifacts" in str(error.value)


def test_summary_has_four_columns_counts_and_evidence_limits() -> None:
    """Keep both samples visible and describe observed failures with their codepoints."""
    comparison = build_repeat_comparison(Path.cwd())
    jobs = make_jobs(CORPUS, grounding_version="multispan_v3")
    failures = classify_repeat_failures(EXTRACTION, jobs)
    verification = read_json(REPORT / "repeat_verification.json")
    summary = render_summary(comparison, failures, verification)
    assert summary.count(HEADERS) == 3
    assert "six species-direction pairs" in summary
    assert "five species, ten species-direction pairs" in summary
    assert "U+0010" in summary and "U+0011" in summary
    assert "12 records" in summary
    assert "zero model requests" in summary
    assert "Later gates are not adjudicated" in summary
    assert "implementers know the reference" in summary
    assert "not a sample from any population" in summary
    assert "%" not in summary
    assert "precision" not in summary
    assert len(failures["records"]) == 12
    assert "gains zero survivors" in generalization_verdict(comparison, failures)


def test_blocked_evidence_has_no_generalization_claim() -> None:
    """Report a blocker when failure attribution cannot be completed."""
    text = generalization_verdict({"blocked_reason": "missing_sample"}, {"blocked_reason": None})
    assert "conclusion is blocked" in text
