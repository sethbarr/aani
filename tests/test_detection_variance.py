"""Verify the experiment's controlled contrast, adapter, and interpretation rules."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from scripts.detection_variance import adapt_candidate, descriptor, single_span_job, verdict
from src.common.io import digest
from src.extraction.cache_control_grounding import GLYPH_POLICY_V6
from src.extraction.gemini import DEFAULT_MODEL, request_gemini
from src.extraction.identity_prompt import source_identity_prompt
from src.extraction.multispan import MultiSpanExtraction
from src.extraction.multispan_v6 import validate_multispan_v6_candidate
from src.extraction.single_attempt_transport import SingleAttemptHTTP
from tests.test_multispan_v2 import identity_candidate, identity_job


def experiment_job() -> dict:
    """Bind an invented source to the real prompt, schema, and v6 policy."""
    job = identity_job()
    job.update(title="Synthetic source", chunk_index=0, chunk_count=1,
               prompt=source_identity_prompt(job["source_ant_identity"]),
               schema=MultiSpanExtraction.model_json_schema(),
               glyph_policy=deepcopy(GLYPH_POLICY_V6))
    job["glyph_source_hashes"] = {
        "source_id": job["source_id"],
        "blocks": {block["block_id"]: hashlib.sha256(block["text"].encode()).hexdigest()
                   for block in job["blocks"]},
    }
    return job


def test_single_span_changes_only_evidence_contract() -> None:
    """Keep identity and non-evidence fields identical and preserve the original job."""
    original = experiment_job()
    saved = deepcopy(original)
    alternative = single_span_job(original)
    assert original == saved
    for key in original.keys() - {"prompt", "schema", "input_hash"}:
        assert alternative[key] == original[key]
    a = original["schema"]["$defs"]["MultiSpanObservation"]
    b = alternative["schema"]["$defs"]["MultiSpanObservation"]
    for key, value in b["properties"].items():
        assert value == a["properties"][key]
    assert set(a["properties"]) - set(b["properties"]) == {
        "name_evidence", "supporting_evidence"}
    assert alternative["prompt"].split("Source-level ant identity context follows.")[1] == (
        original["prompt"].split("Source-level ant identity context follows.")[1])


def test_adapter_preserves_v6_name_gate_and_source_identity() -> None:
    """Pass a self-contained quote and reject a pronoun-only quote under the same v6."""
    raw = identity_candidate()
    del raw["name_evidence"]
    del raw["supporting_evidence"]
    original = deepcopy(raw)
    adapted = adapt_candidate(raw, "B")
    record, reason = validate_multispan_v6_candidate(adapted, experiment_job(), 0.8)
    assert record is not None and reason is None
    assert record["resolved_ant_species"] == "Atta colombica"
    assert raw == original
    raw.update(plant_name_as_written="Hymenaea courbaril", name_surface_form="Hymenaea courbaril",
               evidence_quote="They rejected its leaves on day two.", outcome="rejected")
    record, reason = validate_multispan_v6_candidate(adapt_candidate(raw, "B"), experiment_job(), 0.8)
    assert record is None and reason == "plant_not_in_name_evidence"


class CompletedResponse:
    """Serve an invented provider response without network access."""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        """Return an empty valid extraction to exercise actual request serialization."""
        return httpx.Response(200, json={"status": "completed", "steps": [
            {"type": "model_output", "content": [
                {"type": "text", "text": json.dumps({"records": []})}]}]}, request=request)


@pytest.mark.parametrize("arm", ["A", "B"])
def test_declared_descriptor_matches_existing_request_function(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arm: str,
) -> None:
    """Exercise both exact descriptors with the production one-attempt request path."""
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic")
    job = experiment_job()
    if arm == "B":
        job = single_span_job(job)
    expected = descriptor(job)
    cache = SingleAttemptHTTP(tmp_path, {digest(expected): expected},
                              httpx.Client(transport=httpx.MockTransport(CompletedResponse())))
    try:
        envelope = request_gemini(job, cache, DEFAULT_MODEL)
        assert envelope["output"]["records"] == []
        assert len(cache.attempt_log) == 1
    finally:
        cache.close()


@pytest.mark.parametrize(("a", "b", "expected"), [
    ([2, 3, 3, 2], [5, 6, 5, 6], "support H2"),
    ([6, 4, 6, 4], [5, 5, 5, 5], "support H1"),
    ([6, 6, 6, 6], [6, 6, 6, 6], "cannot distinguish"),
    ([4, 5, 6, 6], [6, 6, 6, 6], "cannot distinguish"),
    ([2, 2, 2, 2], [6, 6, 6], "cannot distinguish"),
])
def test_verdict_follows_committed_criteria(a: list[int], b: list[int], expected: str) -> None:
    """Keep ceilings, overlap, and incomplete arms out of unsupported conclusions."""
    arms = {name: {"complete_draws": len(values), "detection": {"counts": values}}
            for name, values in (("A", a), ("B", b))}
    assert expected in verdict(arms)
