"""Small local fixtures for seeded-monarch preservation and offline replay checks."""

import base64
import json
import shutil
from copy import deepcopy
from html import escape
from pathlib import Path

import httpx
import pytest

from src.chemistry.export_cache import file_hash
from src.common.io import digest, read_json, read_jsonl, write_json, write_jsonl
from src.extraction.gemini import ENDPOINT
from src.systems.config import load_system_config
from src.systems.monarch_infection import validate_source_design_annotations
from src.systems.monarch_seeded_pdf import import_seed_pdfs
from src.systems.monarch_seeded_review import run_seeded_semantic_review
from src.systems.monarch_seeded_sources import SEEDS
from src.systems.monarch_seeded_verification import (
    COMPATIBILITY_CHECKS,
    downstream_replay_value,
    extraction_scientific_manifest,
    forbid_live_request,
    regenerated_grounding,
    snapshot_original_run,
    verify_downstream_input_hashes,
    verify_historical_original,
    verify_local_pdf_import,
    verify_original_snapshot,
    verify_pinned_lotus_export,
    verify_repository_replay,
    verify_seed_access,
    verify_seed_cache,
    verify_seeded_assays,
    verify_seeded_envelope,
    verify_seeded_preparation,
    verify_seeded_semantic_review,
    verify_source_design_review,
)
from src.systems.verification import Audit


def original_fixture(root: Path) -> Path:
    """Create three small original-scope files for immutable snapshot checks."""
    target = root / "data/interim/systems/monarch/record.json"
    write_json(target, {"record": "original"})
    write_json(root / "results/systems/monarch/summary.json", {"status": "complete"})
    write_json(root / "config/systems/monarch.json", {"slug": "monarch"})
    return target


def cache_fixture(root: Path, body: bytes = b"Access denied", status: int = 403) -> Path:
    """Persist one deterministic cache envelope without making a request."""
    descriptor = {"method": "GET", "url": "https://example.org/source.pdf", "params": {}, "json": None}
    key = digest(descriptor)
    path = root / "http" / f"{key}.json"
    write_json(path, {"request": descriptor, "request_hash": key, "attempts": [
        {"status": status, "body_base64": base64.b64encode(body).decode(),
         "retrieved_at": "2026-09-13T17:00:00Z", "content_type": "text/plain"},
    ]})
    return path


def test_snapshot_is_created_once_and_detects_file_changes(tmp_path: Path) -> None:
    """Preserve the initial capture when a later call sees changed original bytes."""
    target = original_fixture(tmp_path)
    snapshot = snapshot_original_run(tmp_path)
    snapshot_path = tmp_path / "results/systems/monarch_seeded/original_snapshot.json"
    before = snapshot_path.read_bytes()
    assert snapshot["files"] == 3
    write_json(target, {"record": "changed"})
    assert snapshot_original_run(tmp_path) == snapshot
    assert snapshot_path.read_bytes() == before
    audit = Audit(tmp_path)
    verify_original_snapshot(audit, snapshot_path.parent)
    assert any(row["check"] == "original_file_hashes_unchanged" and row["status"] == "failed"
               for row in audit.checks)
    assert read_json(target) == {"record": "changed"}


def test_snapshot_detects_added_and_removed_files(tmp_path: Path) -> None:
    """Compare original file membership in addition to checksums of surviving files."""
    target = original_fixture(tmp_path)
    snapshot_original_run(tmp_path)
    target.unlink()
    write_json(target.with_name("added.json"), {"record": "added"})
    audit = Audit(tmp_path)
    verify_original_snapshot(audit, tmp_path / "results/systems/monarch_seeded")
    check = next(row for row in audit.checks if row["check"] == "original_file_set_unchanged")
    assert check["status"] == "failed"
    assert check["added"] == ["data/interim/systems/monarch/added.json"]
    assert check["removed"] == ["data/interim/systems/monarch/record.json"]


def test_historical_hashes_detect_changes_before_current_snapshot(tmp_path: Path) -> None:
    """Keep historical recorded checks independent of the later inventory boundary."""
    target = original_fixture(tmp_path)
    write_json(tmp_path / "results/systems/monarch/verification.json", {
        "verified_at": "earlier", "cache_inventory": [
            {"path": str(target.relative_to(tmp_path)), "sha256": file_hash(target)},
        ], "checks": [], "corpus_replay": {},
    })
    write_json(target, {"record": "changed"})
    snapshot_original_run(tmp_path)
    audit = Audit(tmp_path)
    result = verify_historical_original(audit)
    assert result["files_compared"] == 1
    assert any(row["check"] == "historical_original_file_checksum" and row["status"] == "failed"
               for row in audit.checks)


@pytest.mark.parametrize("mutation", ["body", "descriptor"])
def test_cache_validation_rejects_body_or_descriptor_corruption(tmp_path: Path, mutation: str) -> None:
    """Validate the response encoding and the complete deterministic request identity."""
    path = cache_fixture(tmp_path)
    value = read_json(path)
    if mutation == "body":
        value["attempts"][0]["body_base64"] = "bad encoding!"
        expected_check = "cached_response_body_valid"
    else:
        value["request"]["url"] = "https://example.org/changed.pdf"
        expected_check = "cached_request_descriptor_hash"
    write_json(path, value)
    audit = Audit(tmp_path)
    verify_seed_cache(audit, tmp_path)
    assert any(row["check"] == expected_check and row["status"] == "failed"
               for row in audit.checks)


def test_repository_failure_replay_preserves_status_body_and_cache(tmp_path: Path) -> None:
    """Replay a real cached 403 through CachedHTTP with a transport that forbids network use."""
    path = cache_fixture(tmp_path)
    before = path.read_bytes()
    audit = Audit(tmp_path)
    result = verify_repository_replay(audit, tmp_path)
    assert result["requests_replayed"] == 1
    assert result["responses"][0]["status"] == 403
    assert result["live_transport_forbidden"] is True
    assert all(row["status"] == "passed" for row in audit.checks)
    assert path.read_bytes() == before


def test_verification_transport_cannot_send_live_requests() -> None:
    """Fail before sending a request if code accidentally invokes the replay transport."""
    with httpx.Client(transport=httpx.MockTransport(forbid_live_request)) as client:
        with pytest.raises(RuntimeError, match="verification_transport_forbidden"):
            client.get("https://example.org/forbidden")


def test_seed_replay_ignores_only_checked_at(tmp_path: Path) -> None:
    """Allow replay clock differences while detecting changed access decisions."""
    live = tmp_path / "corpus_targeted_monarch"
    replay = tmp_path / "offline_replay/corpus_targeted_monarch"
    for folder, checked in ((live, "first"), (replay, "second")):
        rows = [{"seed_id": seed["seed_id"], "checked_at": checked, "status": "not_open_access"}
                for seed in SEEDS]
        write_jsonl(folder / "access_manifest.jsonl", rows)
        write_jsonl(folder / "manifest.jsonl", [])
        for seed in SEEDS:
            write_json(folder / "metadata" / f"{seed['seed_id']}.json", seed)
    audit = Audit(tmp_path)
    verify_seed_access(audit, tmp_path)
    assert all(row["status"] == "passed" for row in audit.checks)
    rows[0]["status"] = "retrieved"
    write_jsonl(replay / "access_manifest.jsonl", rows)
    audit = Audit(tmp_path)
    verify_seed_access(audit, tmp_path)
    assert any(row["check"] == "seed_access_replay" and row["status"] == "failed"
               for row in audit.checks)


def test_assay_metrics_ignore_only_offline_flag(tmp_path: Path) -> None:
    """Retain counts as exact values across the assay inventory replay."""
    for folder, offline in ((tmp_path / "assay_scope", False),
                            (tmp_path / "offline_replay/assay_scope", True)):
        write_jsonl(folder / "primary_fungal_assays.jsonl", [])
        write_jsonl(folder / "parasite_assays.jsonl", [])
        write_json(folder / "metrics.json", {"offline": offline, "parasite_assays_all_types": 0})
    audit = Audit(tmp_path)
    verify_seeded_assays(audit, tmp_path)
    assert all(row["status"] == "passed" for row in audit.checks)
    write_json(tmp_path / "offline_replay/assay_scope/metrics.json",
               {"offline": True, "parasite_assays_all_types": None})
    audit = Audit(tmp_path)
    verify_seeded_assays(audit, tmp_path)
    assert any(row["check"] == "assay_metrics_replay" and row["status"] == "failed"
               for row in audit.checks)


def preparation_fixture(root: Path) -> tuple[Path, Path]:
    """Create two prepared source copies and a complete eight-check compatibility report."""
    interim, results = root / "interim", root / "results"
    rows = [{"source_id": "SOURCE_ONE", "status": "ready"},
            {"source_id": "SOURCE_TWO", "status": "ready"}]
    decisions = [{"source_id": row["source_id"], "decision": "include", "reason": "Focal design"}
                 for row in rows]
    for suffix, completed in (("", "first"), ("offline_replay", "second")):
        output = interim / suffix
        write_jsonl(output / "corpus/manifest.jsonl", rows)
        for row in rows:
            write_json(output / "corpus/texts" / f"{row['source_id']}.json",
                       {"source_id": row["source_id"], "text": "Exact source text"})
        write_json(output / "screening.json", {"completed_at": completed, "decisions": decisions})
        write_json(results / suffix / "preparation.json", {
            "compatibility": {"compatible": True,
                              "checks": dict.fromkeys(sorted(COMPATIBILITY_CHECKS), True)},
        })
    return interim, results


def test_preparation_replay_checks_sources_screening_and_all_eight_checks(tmp_path: Path) -> None:
    """Accept matching source copies and screening despite the replay completion timestamp."""
    interim, results = preparation_fixture(tmp_path)
    audit = Audit(tmp_path)
    report = verify_seeded_preparation(audit, interim, results)
    assert report["ready_sources"] == report["screened_sources"] == 2
    assert report["compatibility_checks"] == 8
    assert all(row["status"] == "passed" for row in audit.checks)


@pytest.mark.parametrize("mutation", ["source", "screening", "compatibility"])
def test_preparation_replay_rejects_changed_evidence(tmp_path: Path, mutation: str) -> None:
    """Detect changed source bytes, changed decisions, and incomplete compatibility evidence."""
    interim, results = preparation_fixture(tmp_path)
    if mutation == "source":
        write_json(interim / "offline_replay/corpus/texts/SOURCE_ONE.json", {"text": "changed"})
        expected = "prepared_source_text_replay:SOURCE_ONE"
    elif mutation == "screening":
        path = interim / "offline_replay/screening.json"
        value = read_json(path)
        value["decisions"][0]["decision"] = "exclude"
        write_json(path, value)
        expected = "prepared_screening_replay"
    else:
        for path in (results / "preparation.json", results / "offline_replay/preparation.json"):
            value = read_json(path)
            value["compatibility"]["checks"].pop("model_matches_original")
            write_json(path, value)
        expected = "eight_original_adapter_compatibility_checks"
    audit = Audit(tmp_path)
    verify_seeded_preparation(audit, interim, results)
    assert any(row["check"] == expected and row["status"] == "failed" for row in audit.checks)


def local_pdf_verification_fixture(root: Path) -> tuple[Path, Path]:
    """Generate five offline PDF imports with immutable cached glyph-preserving source bytes."""
    interim = root / "data/interim/systems/monarch_seeded"
    results = root / "results/systems/monarch_seeded"
    access = [{**seed, "bibliography_verified": True, "indexed_doi": seed["doi"],
               "search_request_hash": digest(seed), "status": "not_open_access"} for seed in SEEDS]
    write_json(results / "seed_access.json", {
        "seeds": access, "metrics": {"retrieved": 0, "not_open_access": len(SEEDS)},
    })
    write_jsonl(interim / "corpus_targeted_monarch/access_manifest.jsonl", access)
    for seed in SEEDS:
        folder = interim / "reference_sources" / seed["seed_id"]
        folder.mkdir(parents=True)
        source = folder / "source.pdf"
        source.write_bytes(b"%PDF-1.4 Synthetic verification fixture " + seed["seed_id"].encode())
        bbox = folder / "source.bbox.xhtml"
        bbox.write_bytes((
            '<html><body><doc><page><flow><block xMin="1" yMin="2" xMax="30" yMax="40">'
            '<line><word>' + escape(seed["title"]) + '</word><word>doi:' + seed["doi"]
            + '</word><word>butterﬂy\x02</word></line></block>'
            '<block xMin="1" yMin="45" xMax="30" yMax="50"><line>'
            '<word>Downloaded from fixture repository</word></line></block>'
            '</flow></page></doc></body></html>'
        ).encode())
        write_json(folder / "source.extraction.json", {
            "extractor": "fixture-version", "pdf_sha256": file_hash(source), "bbox_sha256": file_hash(bbox),
        })
    import_seed_pdfs(root, root / "absent_Downloads", offline=True)
    live = interim / "corpus_targeted_monarch"
    replay = interim / "offline_replay/corpus_targeted_monarch"
    for source in replay.rglob("*"):
        if source.is_file():
            target = live / source.relative_to(replay)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    report = read_json(results / "offline_replay/local_pdf_access.json")
    write_json(results / "local_pdf_access.json", {**report, "offline": False})
    metrics = read_json(live / "metrics.json")
    write_json(live / "metrics.json", {**metrics, "offline": False})
    return interim, results


def test_local_pdf_verification_keeps_access_routes_and_raw_provenance_separate(tmp_path: Path) -> None:
    """Verify cached source bytes while keeping user-supplied PDFs distinct from Europe PMC access."""
    interim, results = local_pdf_verification_fixture(tmp_path)
    audit = Audit(tmp_path)
    report = verify_local_pdf_import(audit, interim, results)
    assert all(row["status"] == "passed" for row in audit.checks)
    assert report["sources_verified"] == report["pages"] == report["user_supplied_sources"] == 5
    assert report["europe_pmc_retrieved"] == 0
    assert report["downloads_accessed"] is report["poppler_invoked"] is False
    assert sum(len(row["raw_inventory"]) for row in report["documents"]) == 15
    assert sum(row["excluded_blocks"] for row in report["documents"]) == 5


@pytest.mark.parametrize("mutation", ["pdf", "bbox", "extractor", "text", "route"])
def test_local_pdf_verification_detects_changed_sources_and_access_claims(
    tmp_path: Path, mutation: str,
) -> None:
    """Detect drift even when live and replay copies have been changed together."""
    interim, results = local_pdf_verification_fixture(tmp_path)
    folder = interim / "reference_sources/lefevre_2010"
    if mutation in {"pdf", "bbox"}:
        path = folder / ("source.pdf" if mutation == "pdf" else "source.bbox.xhtml")
        path.write_bytes(path.read_bytes() + b"\n")
        expected = "local_pdf_cached_source_checksums"
    elif mutation == "extractor":
        path = folder / "source.extraction.json"
        metadata = read_json(path)
        write_json(path, {**metadata, "extractor": "changed-version"})
        expected = "local_pdf_document_rebuild"
    elif mutation == "text":
        for output in (interim, interim / "offline_replay"):
            path = output / "corpus_targeted_monarch/texts/LEFEVRE2010.json"
            document = read_json(path)
            document["blocks"][0]["text"] = document["blocks"][0]["text"].replace("ﬂ", "fl")
            write_json(path, document)
        expected = "local_pdf_document_rebuild"
    else:
        for output in (interim, interim / "offline_replay"):
            path = output / "corpus_targeted_monarch/manifest.jsonl"
            rows = read_jsonl(path)
            rows[0]["europe_pmc_fulltext_status"] = "retrieved"
            write_jsonl(path, rows)
        for output in (results, results / "offline_replay"):
            path = output / "local_pdf_access.json"
            report = read_json(path)
            report["seeds"][0]["europe_pmc_fulltext_status"] = "retrieved"
            write_json(path, report)
        expected = "historical_europepmc_pdf_access_separation"
    audit = Audit(tmp_path)
    verify_local_pdf_import(audit, interim, results)
    assert any(row["check"] == expected and row["status"] == "failed" for row in audit.checks)


def source_design_fixture(root: Path) -> tuple[Path, Path]:
    """Create one explicit source-only comparison with an exact anchored source quote."""
    interim, results = root / "interim", root / "results"
    quote = "Infected and uninfected females choose among Asclepias species."
    block = {"source_id": "SOURCE", "block_id": "b1", "section": "Methods", "text": quote}
    job = {"source_id": "SOURCE", "blocks": [block]}
    key = digest(job)
    job["input_hash"] = key
    write_json(interim / "extraction_payloads/index.json", {"jobs": [{"input_hash": key}]})
    write_json(interim / "extraction_payloads" / f"{key}.json", job)
    write_json(interim / "corpus/texts/SOURCE.json", {"source_id": "SOURCE", "blocks": [block]})
    anchor = {"input_hash": key, "source_id": "SOURCE", "block_id": "b1",
              "section": "Methods", "evidence_quote": quote}
    adjudications = {"comparison": {
        "source_id": "SOURCE", "infection_status": "unreported",
        "primary_oviposition_choice": True, "between_milkweed_species": True,
        "choosing_adult_female": True, "design_evidence": [anchor],
        "experiment_id": "same-experiment", "same_experiment_comparison": True,
        "compared_infection_groups": ["infected", "uninfected"], "comparison_evidence": [anchor],
    }}
    adjudication_path = results / "source_design_adjudications.json"
    write_json(adjudication_path, adjudications)
    validated = validate_source_design_annotations(adjudications, {key: job})
    write_json(results / "source_design_review.json", {
        "adjudications_path": str(adjudication_path), "adjudications_sha256": file_hash(adjudication_path),
        "adjudications_hash": digest(adjudications), "designs": validated,
        "source_design_count": 1, "primary_focal_design_source_count": 1,
    })
    return interim, results


def test_source_design_verification_preserves_source_and_record_scope(tmp_path: Path) -> None:
    """Verify both comparison groups without assigning infection to an unobserved model record."""
    interim, results = source_design_fixture(tmp_path)
    audit = Audit(tmp_path)
    report = verify_source_design_review(audit, interim, results)
    assert all(row["status"] == "passed" for row in audit.checks)
    assert report["source_designs"] == 1
    assert report["model_record_recovery"] is None
    assert report["compared_infection_groups"] == {"comparison": ["infected", "uninfected"]}


@pytest.mark.parametrize("mutation", ["quote", "record_status", "reported_scope"])
def test_source_design_verification_rejects_ungrounded_or_misclassified_claims(
    tmp_path: Path, mutation: str,
) -> None:
    """Reject altered quotes, inferred record infection, or changed reported focal eligibility."""
    interim, results = source_design_fixture(tmp_path)
    adjudication_path = results / "source_design_adjudications.json"
    report_path = results / "source_design_review.json"
    adjudications, report = read_json(adjudication_path), read_json(report_path)
    if mutation == "reported_scope":
        report["designs"][0]["focal_eligible"] = True
    else:
        if mutation == "quote":
            adjudications["comparison"]["design_evidence"][0]["evidence_quote"] = "Absent source quote"
        else:
            adjudications["comparison"]["infection_status"] = "infected"
        write_json(adjudication_path, adjudications)
        report["adjudications_sha256"] = file_hash(adjudication_path)
        report["adjudications_hash"] = digest(adjudications)
    write_json(report_path, report)
    audit = Audit(tmp_path)
    verify_source_design_review(audit, interim, results)
    assert any(row["check"] == "source_design_annotations_regenerated" and row["status"] == "failed"
               for row in audit.checks)


def extraction_verification_fixture(root: Path) -> tuple[Path, dict, dict]:
    """Create exact synthetic Gemini request, raw response, and envelope copies."""
    interim = root / "data/interim/systems/monarch_seeded"
    quote = "Infected adult females preferred Asclepias curassavica in a choice test."
    job = {"source_id": "SEED", "title": "Synthetic choice study", "prompt": "Extract exact source evidence.",
           "schema": {"type": "object"}, "source_url": "https://example.org/SEED",
           "blocks": [{"source_id": "SEED", "block_id": "b1", "section": "Results", "text": quote}]}
    job["input_hash"] = digest(job)
    candidate = {
        "behaving_organism_as_written": "Danaus plexippus", "target_name_as_written": "Asclepias curassavica",
        "taxonomic_rank": "species", "direction": "accept", "evidence_type": "lab_choice_assay",
        "quantitative_measure": None, "compound_name_as_written": None, "activity_target_as_written": None,
        "activity_outcome": "unknown", "source_id": "SEED", "section": "Results", "block_id": "b1",
        "evidence_quote": quote, "extraction_confidence": 0.95, "behavioural_choice": True,
        "study_context": "Female choice experiment", "original_source_id": None,
    }
    output = {"records": [candidate, {**candidate, "evidence_quote": "A quote absent from the source"}]}
    body = {
        "model": "gemini-3.8-flash", "store": False, "system_instruction": job["prompt"],
        "input": json.dumps({"source_id": job["source_id"], "title": job["title"], "blocks": job["blocks"]}),
        "response_format": {"type": "text", "mime_type": "application/json", "schema": job["schema"]},
        "generation_config": {"max_output_tokens": 32768, "thinking_level": "low", "thinking_summaries": "none"},
    }
    request = {"method": "POST", "url": ENDPOINT, "params": {}, "json": body}
    response = {"id": "synthetic-response", "model": "gemini-3.8-flash", "status": "completed", "created": "recorded-time",
                "usage": {"total_tokens": 20}, "steps": [{"type": "model_output", "content": [
                    {"type": "text", "text": json.dumps(output)}]}]}
    envelope = {"input_hash": job["input_hash"], "engine": "gemini-3.8-flash", "resolved_model": "gemini-3.8-flash",
                "provider": "gemini", "mode": "gemini_interactions_api", "created_at": response["created"],
                "response_id": response["id"], "request_hash": digest(request), "usage": response["usage"], "output": output}
    write_json(interim / "cache/extraction/http" / f"{digest(request)}.json", {
        "request": request, "request_hash": digest(request), "attempts": [{
            "status": 200, "body_base64": base64.b64encode(json.dumps(response).encode()).decode()}]})
    for folder in ("extraction/responses", "offline_replay/extraction/responses", "cache/extraction/envelopes"):
        write_json(interim / folder / f"{job['input_hash']}.json", envelope)
    return interim, job, envelope


def test_envelope_verification_binds_payload_to_raw_provider_response(tmp_path: Path) -> None:
    """Verify provider identity and every response field against its original HTTP body."""
    interim, job, envelope = extraction_verification_fixture(tmp_path)
    audit = Audit(tmp_path)
    assert verify_seeded_envelope(audit, interim, job, "gemini-3.8-flash", "gemini", "targeted_seed") == envelope
    assert all(row["status"] == "passed" for row in audit.checks)


@pytest.mark.parametrize("mutation", ["request", "raw_response", "status", "envelope", "engine", "empty_attempts"])
def test_envelope_verification_detects_drift_even_with_matching_export_copies(tmp_path: Path, mutation: str) -> None:
    """Catch altered request, response, provider, or envelope values independently of replay equality."""
    interim, job, envelope = extraction_verification_fixture(tmp_path)
    raw_path = interim / "cache/extraction/http" / f"{envelope['request_hash']}.json"
    raw = read_json(raw_path)
    if mutation == "request":
        raw["request"]["json"]["store"] = True
    elif mutation == "raw_response":
        response = json.loads(base64.b64decode(raw["attempts"][0]["body_base64"]))
        response["usage"]["total_tokens"] = 100
        raw["attempts"][0]["body_base64"] = base64.b64encode(json.dumps(response).encode()).decode()
    elif mutation == "status":
        raw["attempts"][0]["status"] = 403
    elif mutation == "empty_attempts":
        raw["attempts"] = []
    else:
        envelope["engine" if mutation == "engine" else "response_id"] = "changed"
        for folder in ("extraction/responses", "offline_replay/extraction/responses", "cache/extraction/envelopes"):
            write_json(interim / folder / f"{job['input_hash']}.json", envelope)
    write_json(raw_path, raw)
    audit = Audit(tmp_path)
    verify_seeded_envelope(audit, interim, job, "gemini-3.8-flash", "gemini", "targeted_seed")
    assert any(row["status"] == "failed" for row in audit.checks)


def test_grounding_regeneration_preserves_candidates_and_exact_rejection(tmp_path: Path) -> None:
    """Run the original single-quote validator without editing any saved candidate."""
    _, job, envelope = extraction_verification_fixture(tmp_path)
    before = deepcopy(envelope)
    config = load_system_config(Path("config/systems/monarch.json"))
    regenerated = regenerated_grounding([job], {job["input_hash"]: envelope}, config, 0.8)
    assert len(regenerated["candidates.jsonl"]) == 2
    assert len(regenerated["observations.jsonl"]) == 1
    assert regenerated["rejections.jsonl"][0]["reason"] == "ungrounded_quote"
    assert regenerated["observations.jsonl"][0]["activity_outcome"] == "unknown"
    assert regenerated["failures.jsonl"] == []
    assert envelope == before


def test_extraction_replay_allowances_preserve_all_scientific_counts_and_request_identity() -> None:
    """Allow operational acquisition differences while retaining request hashes and source cohorts."""
    live = {"offline": False, "started_at": "first", "metrics": {"retained_records": 9, "persisted_new_response_attempts": 5},
            "response_acquisition": [{"input_hash": "input", "request_hash": "request", "source_id": "SEED",
                                      "cohort": "targeted_seed", "origin": "seed_provider_response",
                                      "new_model_request_function_called": True, "new_persisted_response_attempts": 1}]}
    replay = deepcopy(live)
    replay.update(offline=True, started_at="second")
    replay["metrics"]["persisted_new_response_attempts"] = 0
    replay["response_acquisition"][0].update(origin="seeded_envelope_cache", new_model_request_function_called=False,
                                             new_persisted_response_attempts=0)
    assert extraction_scientific_manifest(live) == extraction_scientific_manifest(replay)
    replay["metrics"]["retained_records"] = 10
    assert extraction_scientific_manifest(live) != extraction_scientific_manifest(replay)
    replay["metrics"]["retained_records"] = 9
    replay["response_acquisition"][0]["request_hash"] = "another-request"
    assert extraction_scientific_manifest(live) != extraction_scientific_manifest(replay)


def semantic_verification_fixture(root: Path) -> tuple[Path, Path]:
    """Create deterministic retained unreported-status evidence and its isolated replay."""
    fixture, fixture_results = source_design_fixture(root / "fixture")
    interim = root / "data/interim/systems/monarch_seeded"
    results = root / "results/systems/monarch_seeded"
    shutil.copytree(fixture, interim)
    shutil.copytree(fixture_results, results)
    job_key = read_json(interim / "extraction_payloads/index.json")["jobs"][0]["input_hash"]
    job = read_json(interim / "extraction_payloads" / f"{job_key}.json")
    record = {"record_id": "raw-id", "input_hash": job_key, "source_id": "SOURCE", "block_id": "b1",
              "section": "Methods", "evidence_quote": job["blocks"][0]["text"], "target_name_as_written": "Asclepias",
              "taxonomic_rank": "genus", "direction": "unknown"}
    design = read_json(results / "source_design_adjudications.json")["comparison"]
    review = {key: value for key, value in design.items() if key != "source_id"}
    review.update(decision="include", note="Retain explicit choice with unreported record-level infection status.")
    write_json(results / "semantic_adjudications.json", {"raw-id": review})
    write_jsonl(interim / "extraction/observations.jsonl", [record])
    write_json(interim / "extraction/metrics.json", {"status": "complete", "incomplete_papers": 0, "retained_records": 1})
    run_seeded_semantic_review(root)
    run_seeded_semantic_review(root, offline=True)
    return interim, results


def test_semantic_verification_regenerates_unreported_status_without_claiming_focal_pair(tmp_path: Path) -> None:
    """Retain a flagged unreported group while leaving model pair recovery false."""
    interim, results = semantic_verification_fixture(tmp_path)
    audit = Audit(tmp_path)
    report = verify_seeded_semantic_review(audit, interim, results)
    assert all(row["status"] == "passed" for row in audit.checks)
    assert report["included"] == 1
    assert report["focal_recovery"]["source_design_recovered"] is True
    assert report["focal_recovery"]["model_infected_uninfected_pair_recovered"] is False
    assert report["focal_recovery"]["unreported_model_record_count"] == 1


@pytest.mark.parametrize("mutation", ["record", "adjudication", "metrics"])
def test_semantic_verification_detects_matching_live_replay_scientific_drift(tmp_path: Path, mutation: str) -> None:
    """Compare replay and fresh adjudication independently so matching corrupted copies fail."""
    interim, results = semantic_verification_fixture(tmp_path)
    if mutation == "record":
        for folder in (interim / "semantic_review", interim / "offline_replay/semantic_review"):
            rows = read_jsonl(folder / "observations.jsonl")
            rows[0]["infection_status"] = "infected"
            write_jsonl(folder / "observations.jsonl", rows)
    elif mutation == "adjudication":
        path = results / "semantic_adjudications.json"
        reviews = read_json(path)
        reviews["raw-id"]["design_evidence"][0]["evidence_quote"] = "Ungrounded fabricated quote"
        write_json(path, reviews)
    else:
        for folder in (interim / "semantic_review", interim / "offline_replay/semantic_review"):
            metrics = read_json(folder / "metrics.json")
            write_json(folder / "metrics.json", {**metrics, "included": 0})
    audit = Audit(tmp_path)
    verify_seeded_semantic_review(audit, interim, results)
    assert any(row["status"] == "failed" for row in audit.checks)


def test_downstream_operational_allowances_keep_infection_context_and_unknowns_exact() -> None:
    """Canonicalize isolated output paths while preserving scientific nulls and group provenance."""
    live = {"offline": False, "input_path": "/repo/monarch_seeded/behaviour/genera.jsonl", "completed_at": "first",
            "active": None, "unknown": 2, "groups": [{"infection_status": "unreported", "model_record_ids": ["raw-id"],
                                                       "experiment_ids": ["experiment1"], "record_origin_counts": {"model_record": 1}}]}
    replay = deepcopy(live)
    replay.update(offline=True, input_path="/repo/monarch_seeded/offline_replay/behaviour/genera.jsonl", completed_at="second")
    assert downstream_replay_value(live) == downstream_replay_value(replay)
    replay["active"] = 0
    assert downstream_replay_value(live) != downstream_replay_value(replay)
    replay["active"] = None
    replay["groups"][0]["record_origin_counts"] = {"curator_context_expansion": 1}
    assert downstream_replay_value(live) != downstream_replay_value(replay)


def test_input_hash_mapping_canonicalizes_paths_and_preserves_hash_values(tmp_path: Path) -> None:
    """Require actual input checksums even when live and replay report hashes match."""
    path = tmp_path / "monarch_seeded/chemistry/occurrences.jsonl"
    write_jsonl(path, [{"compound": "fixture"}])
    live = {"input_hashes": {str(path): file_hash(path)}}
    replay = {"input_hashes": {str(path).replace("/monarch_seeded/", "/monarch_seeded/offline_replay/"): file_hash(path)}}
    assert downstream_replay_value(live) == downstream_replay_value(replay)
    audit = Audit(tmp_path)
    verify_downstream_input_hashes(audit, live)
    assert all(row["status"] == "passed" for row in audit.checks)
    write_jsonl(path, [{"compound": "changed"}])
    audit = Audit(tmp_path)
    verify_downstream_input_hashes(audit, live)
    assert audit.checks[0]["status"] == "failed"
    replay["input_hashes"] = {key: "changed-hash" for key in replay["input_hashes"]}
    assert downstream_replay_value(live) != downstream_replay_value(replay)


@pytest.mark.parametrize("mutation", [None, "body", "version", "descriptor"])
def test_pinned_export_checks_whole_body_and_explicit_version(tmp_path: Path, mutation: str | None) -> None:
    """Verify cached bulk bytes, recorded checksums, pinned DOI, and the request descriptor."""
    descriptor = {"method": "GET", "url": "https://example.org/pinned-export.gz", "params": {}, "json": None}
    key = digest(descriptor)
    body = tmp_path / "cache/chemistry_export/downloads" / f"{key}.body"
    body.parent.mkdir(parents=True)
    body.write_bytes(b"synthetic export bytes")
    metadata = {"request": descriptor, "request_hash": key, "sha256": file_hash(body), "md5": file_hash(body, "md5"),
                "complete": True, "status": 200, "bytes": body.stat().st_size}
    report = {"download_request_hash": key, "download_url": descriptor["url"], "database_version": "zenodo:6582121:v4",
              "export_doi": "10.5281/zenodo.6582121", "checksum_verified": True, "file_sha256": metadata["sha256"],
              "published_checksum": "md5:" + metadata["md5"], "file_bytes": metadata["bytes"]}
    if mutation == "body":
        body.write_bytes(b"changed export bytes")
    elif mutation == "version":
        report["database_version"] = "latest"
    elif mutation == "descriptor":
        metadata["request"]["url"] = "https://example.org/changed-export.gz"
    write_json(body.with_suffix(".json"), metadata)
    audit = Audit(tmp_path)
    verify_pinned_lotus_export(audit, tmp_path, report)
    assert all(row["status"] == "passed" for row in audit.checks) is (mutation is None)
    cache_audit = Audit(tmp_path)
    inventory, hashes = verify_seed_cache(cache_audit, tmp_path / "cache")
    assert len(inventory) == 2
    assert len(hashes) == 1
    assert all(row["status"] == "passed" for row in cache_audit.checks) is (mutation in {None, "version"})
