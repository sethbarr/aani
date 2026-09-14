"""Audit actual isolated system artifacts and offline replays without network access."""

import base64
import hashlib
import json
import subprocess
from pathlib import Path

from src.chemistry.export_cache import file_hash
from src.common.io import digest, read_json, read_jsonl, timestamp, write_json
from src.extraction.gemini import gemini_output
from src.systems.config import SystemConfig, load_system_config
from src.systems.extraction import validate_system_candidate
from src.systems.schema import SystemObservation

FROZEN_COMMIT = "98b5e09"
FROZEN_FILES = ("docs/analysis_plan.md", "config/analysis.json")
# This explicit allowlist applies to metrics and execution manifests only.
# Data rows, source documents, model responses, and scientific counts stay exact.
PROVENANCE_FIELDS = frozenset({
    "input_path", "output_path", "cache_path", "config_path", "genus_input_path",
    "contract_path", "selected_source_rows_path", "semantic_input_path", "funnel_path",
    "offline", "started_at", "completed_at", "generated_at", "prepared_at",
    "retrieved_at", "imported_at", "deadline",
})
EXTRACTION_FILES = (
    "observations.jsonl", "rejections.jsonl", "failures.jsonl", "job_status.jsonl",
    "partial_observations.jsonl", "observations_progress.jsonl", "metrics.json",
)
STAGE_FILES = {
    "taxonomy": ("observations.jsonl", "review.jsonl"),
    "behaviour": ("observations.jsonl", "genera.jsonl", "conflicts.jsonl",
                  "genus_coverage.jsonl", "review.jsonl", "duplicates.jsonl"),
    "chemistry": ("occurrences.jsonl", "review.jsonl", "genus_coverage.jsonl"),
    "bioactivity": ("labels.jsonl", "measurements.jsonl", "retrieval_status.jsonl"),
    "assay_scope": ("primary_fungal_assays.jsonl", "parasite_assays.jsonl"),
}


def scientific_value(value: object) -> object:
    """Remove only named execution provenance fields from comparison values."""
    if isinstance(value, dict):
        return {key: scientific_value(item) for key, item in value.items()
                if key not in PROVENANCE_FIELDS}
    if isinstance(value, list):
        return [scientific_value(item) for item in value]
    return value


class Audit:
    """Collect passed, failed, and unavailable checks with concrete evidence."""

    def __init__(self, root: Path) -> None:
        """Initialize a repository-scoped collection of verification evidence."""
        self.root = root
        self.checks: list[dict] = []

    def path(self, path: Path) -> str:
        """Prefer repository-relative report paths when the file is inside it."""
        return str(path.relative_to(self.root)) if path.is_relative_to(self.root) else str(path)

    def add(self, name: str, passed: bool | None, **details: object) -> None:
        """Record unavailable evidence distinctly from a failed comparison."""
        status = "unavailable" if passed is None else "passed" if passed else "failed"
        self.checks.append({"check": name, "status": status, **details})

    def load(self, path: Path, name: str, jsonl: bool = False) -> object | None:
        """Read one required artifact and retain parse failures in the report."""
        if not path.is_file():
            self.add(name, None, path=self.path(path), reason="required_artifact_missing")
            return None
        try:
            return read_jsonl(path) if jsonl else read_json(path)
        except (OSError, ValueError, TypeError) as error:
            self.add(name, False, path=self.path(path), reason=str(error))
            return None

    def compare(self, live: Path, replay: Path, name: str, scientific: bool = False) -> None:
        """Compare actual files and count JSONL records, including empty outputs."""
        details = {"live_path": self.path(live), "replay_path": self.path(replay),
                   "comparison": "scientific_json" if scientific else "byte_exact"}
        if not live.is_file() or not replay.is_file():
            self.add(name, None, **details,
                     missing=[self.path(p) for p in (live, replay) if not p.is_file()])
            return
        details.update(live_sha256=file_hash(live), replay_sha256=file_hash(replay))
        try:
            if live.suffix == ".jsonl":
                details.update(live_records=len(read_jsonl(live)),
                               replay_records=len(read_jsonl(replay)))
            if scientific:
                a, b = scientific_value(read_json(live)), scientific_value(read_json(replay))
                details.update(live_scientific_hash=digest(a), replay_scientific_hash=digest(b))
                if isinstance(a, dict):
                    details["live_scientific_metrics"] = a
                    details["replay_scientific_metrics"] = b
                matched = a == b
            else:
                matched = details["live_sha256"] == details["replay_sha256"]
            self.add(name, matched, **details)
        except (OSError, ValueError, TypeError) as error:
            self.add(name, False, **details, reason=str(error))


def cache_inventory(audit: Audit, cache: Path) -> tuple[list[dict], dict[str, list[Path]]]:
    """Hash every cache file and validate every cached HTTP request descriptor."""
    inventory, requests = [], {}
    if not cache.is_dir():
        audit.add("cache_inventory", None, reason="cache_directory_missing")
        return inventory, requests
    for path in sorted(cache.rglob("*")):
        if not path.is_file():
            continue
        item = {"path": audit.path(path), "bytes": path.stat().st_size,
                "sha256": file_hash(path)}
        inventory.append(item)
        if path.parent.name != "http" or path.suffix != ".json":
            continue
        stored = audit.load(path, "cached_request_parse")
        if not isinstance(stored, dict):
            continue
        key = digest(stored.get("request"))
        good = path.stem == stored.get("request_hash") == key
        audit.add("cached_request_hash", good, path=audit.path(path), request_hash=key)
        requests.setdefault(key, []).append(path)
        attempts = stored.get("attempts", [])
        audit.add("cached_response_attempts", bool(attempts), path=audit.path(path),
                  attempts=len(attempts))
        item["attempts"] = len(attempts)
    audit.add("cache_inventory", bool(inventory), files=len(inventory),
              bytes=sum(item["bytes"] for item in inventory))
    return inventory, requests


def verify_corpus(audit: Audit, live: Path, replay: Path) -> dict:
    """Compare all ready discovery texts and source-status manifests."""
    a = audit.load(live / "manifest.jsonl", "live_corpus_manifest", jsonl=True)
    b = audit.load(replay / "manifest.jsonl", "replay_corpus_manifest", jsonl=True)
    if a is None or b is None:
        return {"status": "unavailable", "texts_compared": 0}
    live_identities = [(row["source_id"], row["status"]) for row in a]
    replay_identities = [(row["source_id"], row["status"]) for row in b]
    audit.add("corpus_source_statuses", live_identities == replay_identities,
              live_sources=len(a), replay_sources=len(b))
    ready = [row for row in a if row["status"] == "ready"]
    replay_ready = [row for row in b if row["status"] == "ready"]
    audit.add("corpus_ready_source_set", {r["source_id"] for r in ready}
              == {r["source_id"] for r in replay_ready})
    inventory = []
    for row in ready:
        source = row["source_id"]
        path = live / "texts" / f"{source}.json"
        audit.compare(path, replay / "texts" / path.name, f"corpus_text:{source}")
        document = audit.load(path, f"corpus_document:{source}")
        if not isinstance(document, dict):
            continue
        blocks = document.get("blocks", [])
        ids = [block["block_id"] for block in blocks]
        audit.add("corpus_block_identity", len(ids) == len(set(ids))
                  and document.get("source_id") == source, source_id=source)
        inventory.append({"source_id": source, "path": audit.path(path),
                          "sha256": file_hash(path), "document_digest": digest(document),
                          "blocks_digest": digest(blocks), "blocks": len(blocks)})
    return {"live_ready_texts": len(ready), "replay_ready_texts": len(replay_ready),
            "texts_compared": len(inventory), "documents": inventory}


def approved_jobs(audit: Audit, interim: Path, results: Path, config: SystemConfig) -> list[dict]:
    """Validate exact payload hashes, approved ordering, and source block copies."""
    selection = interim / "execution_selection.json"
    if not selection.is_file():
        selection = interim / "extraction_payloads/index.json"
    index = audit.load(selection, "execution_selection")
    approval = audit.load(results / "payload_approval.json", "payload_approval")
    if not isinstance(index, dict) or not isinstance(approval, dict):
        return []
    selected = index.get("jobs", [])
    hashes = [row["input_hash"] for row in selected]
    audit.add("payload_approval_scope", approval.get("approved") is True
              and hashes == approval.get("input_hashes")
              and len(hashes) == len(set(hashes))
              and len(hashes) <= config.extraction_job_limit,
              approved_jobs=len(approval.get("input_hashes", [])), selected_jobs=len(hashes))
    jobs = []
    for row in selected:
        path = (interim / row.get("path", f"extraction_payloads/{row['input_hash']}.json")).resolve()
        if not path.is_relative_to(interim.resolve()):
            audit.add("payload_isolation", False, path=str(path))
            continue
        job = audit.load(path, "payload_read")
        if not isinstance(job, dict):
            continue
        expected = digest({key: value for key, value in job.items() if key != "input_hash"})
        audit.add("payload_hash", expected == row["input_hash"] == job.get("input_hash")
                  == path.stem and job.get("system_slug") == config.slug,
                  path=audit.path(path), input_hash=expected)
        corpus = interim / ("reference_sources/corpus" if row.get("cohort")
                            == "reference_control" else "corpus")
        document = audit.load(corpus / "texts" / f"{job['source_id']}.json", "payload_source")
        if isinstance(document, dict):
            blocks = {block["block_id"]: block for block in document.get("blocks", [])}
            audit.add("payload_blocks_match_source", all(blocks.get(b["block_id"]) == b
                      for b in job.get("blocks", [])), source_id=job["source_id"],
                      input_hash=expected, blocks_digest=digest(job.get("blocks", [])))
        jobs.append(job)
    return jobs


def verify_extraction(audit: Audit, interim: Path, jobs: list[dict],
                      requests: dict[str, list[Path]]) -> None:
    """Compare saved extraction output and link it to exact cached request bodies."""
    live, replay = interim / "extraction", interim / "offline_replay/extraction"
    for name in EXTRACTION_FILES:
        audit.compare(live / name, replay / name, f"extraction_replay:{name}")
    audit.compare(live / "run_manifest.json", replay / "run_manifest.json",
                  "extraction_replay:run_manifest", scientific=True)
    expected_hashes = [job["input_hash"] for job in jobs]
    statuses = audit.load(live / "job_status.jsonl", "extraction_job_status", jsonl=True)
    if isinstance(statuses, list):
        audit.add("extraction_jobs_match_selection", [r["input_hash"] for r in statuses]
                  == expected_hashes, completed=sum(r["status"] == "complete" for r in statuses),
                  total=len(statuses))
    for job in jobs:
        key = job["input_hash"]
        path = live / "responses" / f"{key}.json"
        audit.compare(path, replay / "responses" / path.name, f"model_response_replay:{key}")
        envelope = audit.load(path, "model_response")
        if not isinstance(envelope, dict):
            continue
        request_hash = envelope.get("request_hash")
        audit.add("model_response_input_identity", envelope.get("input_hash") == key,
                  input_hash=key)
        cached_paths = requests.get(request_hash, [])
        if not cached_paths:
            audit.add("model_response_cache", None, input_hash=key, request_hash=request_hash)
            continue
        try:
            cached = read_json(cached_paths[0])
            body = cached["request"]["json"]
            payload = json.loads(body["input"])
            expected = {"source_id": job["source_id"], "title": job["title"],
                        "blocks": job["blocks"]}
            audit.add("model_request_matches_payload", payload == expected
                      and body["system_instruction"] == job["prompt"]
                      and body["response_format"]["schema"] == job["schema"]
                      and body["model"] == envelope.get("engine"), input_hash=key)
            attempt = cached["attempts"][-1]
            response = json.loads(base64.b64decode(attempt["body_base64"], validate=True))
            audit.add("model_response_matches_cache", attempt["status"] == 200
                      and gemini_output(response) == envelope["output"]
                      and response.get("id") == envelope.get("response_id")
                      and response.get("model", envelope["engine"]) == envelope.get("resolved_model"),
                      input_hash=key, request_hash=request_hash,
                      cached_response_sha256=hashlib.sha256(base64.b64decode(
                          attempt["body_base64"])).hexdigest())
        except (KeyError, TypeError, ValueError) as error:
            audit.add("model_response_cache", False, input_hash=key, reason=str(error))
    for side in (live, replay):
        names = {path.stem for path in (side / "responses").glob("*.json")}
        expected = set(expected_hashes)
        match = False if names - expected else None if expected - names else True
        audit.add("model_response_file_set", match,
                  path=audit.path(side), files=len(names), expected=len(expected_hashes))


def verify_semantics(audit: Audit, interim: Path, jobs: list[dict], config: SystemConfig) -> None:
    """Check every retained raw quote and immutable fields in semantic inclusions."""
    raw = audit.load(interim / "extraction/observations.jsonl", "grounded_records", jsonl=True)
    retained = audit.load(interim / "semantic_review/observations.jsonl", "semantic_records",
                          jsonl=True)
    if not isinstance(raw, list) or not isinstance(retained, list):
        return
    by_job = {job["input_hash"]: job for job in jobs}
    fields = set(SystemObservation.model_fields)
    envelopes = {}
    for row in raw:
        job = by_job.get(row.get("input_hash"))
        if job is None:
            audit.add("retained_quote_grounding", False, record_id=row.get("record_id"),
                      reason="unapproved_job")
            continue
        candidate = {key: row[key] for key in fields if key in row}
        valid, reason = validate_system_candidate(candidate, job, config, 0.8)
        audit.add("retained_quote_grounding", valid is not None and reason is None
                  and valid["record_id"] == row.get("record_id"),
                  record_id=row.get("record_id"), reason=reason)
        key = row["input_hash"]
        if key not in envelopes:
            envelopes[key] = audit.load(interim / "extraction/responses" / f"{key}.json",
                                        "grounded_record_response")
        envelope = envelopes[key]
        if isinstance(envelope, dict):
            audit.add("grounded_record_response_provenance",
                      candidate in envelope.get("output", {}).get("records", [])
                      and row.get("response_hash") == digest(envelope)
                      and row.get("extraction_request_hash") == envelope.get("request_hash")
                      and row.get("engine") == envelope.get("engine"),
                      record_id=row.get("record_id"), input_hash=key)
    originals = {row["record_id"]: row for row in raw}
    audit.add("semantic_record_ids_unique", len({r["record_id"] for r in retained}) == len(retained))
    for row in retained:
        original = originals.get(row.get("record_id"))
        unchanged = original is not None and all(row.get(key) == value
                                                for key, value in original.items())
        audit.add("semantic_raw_fields_unchanged", unchanged
                  and row.get("semantic_decision") == "include", record_id=row.get("record_id"))
    audit.add("semantic_review_actual_counts", True, raw_grounded=len(raw),
              semantic_included=len(retained))


def verify_downstream(audit: Audit, interim: Path, config: SystemConfig) -> None:
    """Compare deterministic data and scientific metrics for every downstream stage."""
    for stage, required in STAGE_FILES.items():
        live, replay = interim / stage, interim / "offline_replay" / stage
        audit.compare(live / "metrics.json", replay / "metrics.json",
                      f"downstream_metrics:{stage}", scientific=True)
        metrics = audit.load(live / "metrics.json", f"downstream_status:{stage}")
        applicable = not (stage == "chemistry" and not config.run_chemistry
                          or stage == "bioactivity" and not config.run_bioactivity
                          or stage == "assay_scope" and config.slug != "monarch")
        names = {path.name for folder in (live, replay) for path in folder.glob("*.jsonl")}
        if applicable and isinstance(metrics, dict) and metrics.get("status") in {
            "complete", "completed"
        }:
            names.update(required)
        for name in sorted(names):
            audit.compare(live / name, replay / name, f"downstream_records:{stage}/{name}")


def verify_references(audit: Audit, interim: Path, requests: dict[str, list[Path]]) -> None:
    """Check supplied PDF and cached BioC provenance for the two control documents."""
    corpus = interim / "reference_sources/corpus"
    manifest = audit.load(corpus / "manifest.jsonl", "control_manifest", jsonl=True)
    if not isinstance(manifest, list):
        return
    for row in manifest:
        document = audit.load(corpus / "texts" / f"{row['source_id']}.json", "control_document")
        if not isinstance(document, dict):
            continue
        provenance = document.get("provenance", {})
        audit.add("control_document_digest", digest(document) == row.get("text_hash"),
                  source_id=row["source_id"], document_digest=digest(document),
                  blocks_digest=digest(document.get("blocks", [])))
        if provenance.get("source_kind") == "user_supplied_pdf":
            pdf = interim / "reference_sources/currie_1999/source.pdf"
            audit.add("control_pdf_checksum", file_hash(pdf) == provenance.get("source_sha256")
                      if pdf.is_file() else None, path=audit.path(pdf))
        elif provenance.get("source_kind") == "cached_ncbi_bioc_author_manuscript":
            paths = requests.get(provenance.get("cache_request_hash"), [])
            if not paths:
                audit.add("control_bioc_cache", None, source_id=row["source_id"])
                continue
            cached = read_json(paths[0])
            content = base64.b64decode(cached["attempts"][-1]["body_base64"], validate=True)
            audit.add("control_bioc_cache", file_hash(paths[0]) == provenance.get("cache_file_sha256")
                      and hashlib.sha256(content).hexdigest() == provenance.get("response_sha256"),
                      source_id=row["source_id"], path=audit.path(paths[0]))
        else:
            audit.add("control_source_provenance", False, source_id=row["source_id"],
                      source_kind=provenance.get("source_kind"))


def verify_primary(audit: Audit) -> None:
    """Check frozen Git bytes and each input checksum recorded by the primary funnel."""
    for relative in FROZEN_FILES:
        result = subprocess.run(["git", "show", f"{FROZEN_COMMIT}:{relative}"],
                                cwd=audit.root, capture_output=True, check=False)
        path = audit.root / relative
        expected = hashlib.sha256(result.stdout).hexdigest() if result.returncode == 0 else None
        actual = file_hash(path) if path.is_file() else None
        audit.add("frozen_primary_file", actual == expected if actual and expected else None,
                  path=relative, commit=FROZEN_COMMIT, expected_sha256=expected, sha256=actual)
    funnel = audit.load(audit.root / "results/funnel.json", "primary_funnel")
    if not isinstance(funnel, dict):
        return
    manifests = funnel.get("input_manifests", []) + funnel.get("frozen_files", [])
    audit.add("primary_recorded_hashes_available", bool(manifests), inputs=len(manifests))
    for item in manifests:
        path = Path(item["path"])
        path = path if path.is_absolute() else audit.root / path
        actual = file_hash(path) if path.is_file() else None
        audit.add("primary_recorded_input_checksum", actual == item.get("sha256")
                  if actual is not None else None, path=audit.path(path),
                  expected_sha256=item.get("sha256"), sha256=actual)


def verify_system(slug: str, root: Path) -> dict:
    """Write a concrete local verification report; missing replay artifacts stay unavailable."""
    root = Path(root).resolve()
    if slug not in {"propolis", "monarch", "attine_actino"}:
        raise ValueError("Unknown exploratory system")
    audit = Audit(root)
    interim, results = root / "data/interim/systems" / slug, root / "results/systems" / slug
    config = load_system_config(root / "config/systems" / f"{slug}.json")
    inventory, requests = cache_inventory(audit, interim / "cache")
    replay_corpus = interim / "offline_replay" / ("" if slug == "propolis" else "corpus")
    corpus = verify_corpus(audit, interim / "corpus", replay_corpus)
    jobs = approved_jobs(audit, interim, results, config)
    verify_extraction(audit, interim, jobs, requests)
    verify_semantics(audit, interim, jobs, config)
    verify_downstream(audit, interim, config)
    if slug == "attine_actino":
        verify_references(audit, interim, requests)
    verify_primary(audit)
    failed = sum(row["status"] == "failed" for row in audit.checks)
    unavailable = sum(row["status"] == "unavailable" for row in audit.checks)
    result = {
        "schema_version": 1, "system": slug, "verified_at": timestamp(),
        "status": "failed" if failed else "unavailable" if unavailable else "passed",
        "failed_checks": failed, "unavailable_checks": unavailable,
        "passed_checks": sum(row["status"] == "passed" for row in audit.checks),
        "network_calls": 0, "model_calls": 0, "approved_jobs": len(jobs),
        "ignored_provenance_fields": sorted(PROVENANCE_FIELDS), "corpus_replay": corpus,
        "cache_inventory": inventory, "checks": audit.checks,
    }
    write_json(results / "verification.json", result)
    return result
