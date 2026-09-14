"""Export, execute or import reproducible structured extraction requests."""

import hashlib
import json
import os
from pathlib import Path

import httpx
from pydantic import ValidationError

from src.common.cache import CachedHTTP, OfflineCacheMiss, response_error_code
from src.common.io import (
    digest,
    normalise_space,
    read_json,
    read_jsonl,
    write_json,
    write_jsonl,
)
from src.extraction.ant_identity import resolve_source_ant_identity
from src.extraction.errors import ExtractionServiceUnavailable
from src.extraction.gemini import request_gemini
from src.extraction.identity_prompt import source_identity_prompt
from src.extraction.multispan import MultiSpanExtraction, validate_multispan_candidate
from src.extraction.multispan_v2 import validate_multispan_v2_candidate
from src.extraction.multispan_v3 import candidate_grounding_audit, validate_multispan_v3_candidate
from src.extraction.multispan_v4 import (
    candidate_grounding_audit_v4,
    validate_multispan_v4_candidate,
)
from src.extraction.multispan_v5 import (
    candidate_grounding_audit_v5,
    validate_multispan_v5_candidate,
)
from src.extraction.multispan_v6 import (
    candidate_grounding_audit_v6,
    validate_multispan_v6_candidate,
)
from src.extraction.prompts import MULTISPAN_PROMPT
from src.extraction.schema import PROMPT, Extraction, Observation


def make_jobs(
    corpus: Path,
    maximum_characters: int = 24000,
    screening: Path | None = None,
    limit_papers: int | None = None,
    grounding_version: str = "single_quote_v1",
    ant_identity_overrides: dict | None = None,
    glyph_policy: dict | None = None,
) -> list[dict]:
    """Partition complete source blocks without silently truncating paper text."""
    if grounding_version not in {"single_quote_v1", "multispan_v1", "multispan_v2", "multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"}:
        raise ValueError(f"Unsupported grounding version: {grounding_version}")
    if ant_identity_overrides is not None and grounding_version not in {"multispan_v2", "multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"}:
        raise ValueError("Ant identity overrides require multispan_v2")
    if glyph_policy is not None and grounding_version not in {"multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"}:
        raise ValueError("Glyph policy requires multispan_v3")
    if grounding_version in {"multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"} and glyph_policy is None:
        policy_name = f"grounding_glyphs_{grounding_version.split('_')[-1]}.json"
        policy_path = Path(__file__).resolve().parents[2] / "config" / policy_name
        glyph_policy = read_json(policy_path)
    papers = read_jsonl(corpus / "manifest.jsonl")
    if screening is not None:
        decisions = read_json(screening)["decisions"]
        by_source = {row["source_id"]: row for row in decisions}
        if len(by_source) != len(decisions):
            raise ValueError("Duplicate source IDs in screening decisions")
        if set(by_source) != {paper["source_id"] for paper in papers}:
            raise ValueError("Screening must cover exactly the corpus manifest")
        if any(row["decision"] not in {"include", "exclude"} for row in decisions):
            raise ValueError("Screening decision must be include or exclude")
        papers = [
            paper for paper in papers if by_source[paper["source_id"]]["decision"] == "include"
        ]
    papers = [paper for paper in papers if paper["status"] == "ready"]
    if limit_papers is not None:
        if limit_papers < 1:
            raise ValueError("limit_papers must be positive")
        papers = papers[:limit_papers]
    jobs = []
    for paper in papers:
        document = read_json(corpus / "texts" / f"{paper['source_id']}.json")
        identity = None
        if grounding_version in {"multispan_v2", "multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"}:
            identity = resolve_source_ant_identity(
                paper, document, (ant_identity_overrides or {}).get(paper["source_id"])
            )
        chunks = []
        current = []
        size = 0
        for block in document["blocks"]:
            if current and size + len(block["text"]) > maximum_characters:
                chunks.append(current)
                current, size = [], 0
            current.append(block)
            size += len(block["text"])
        if current:
            chunks.append(current)
        for index, blocks in enumerate(chunks):
            job = {
                "source_id": paper["source_id"],
                "title": paper["title"],
                "source_url": paper["source_url"],
                "chunk_index": index,
                "chunk_count": len(chunks),
                "prompt": PROMPT,
                "schema": Extraction.model_json_schema(),
                "blocks": blocks,
            }
            if grounding_version == "multispan_v1":
                job.update({"prompt": MULTISPAN_PROMPT,
                            "schema": MultiSpanExtraction.model_json_schema(),
                            "grounding_version": grounding_version})
            elif grounding_version in {"multispan_v2", "multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"}:
                job.update({"prompt": source_identity_prompt(identity),
                            "schema": MultiSpanExtraction.model_json_schema(),
                            "grounding_version": grounding_version,
                            "source_ant_identity": identity})
                if grounding_version in {"multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"}:
                    job["glyph_policy"] = glyph_policy
                if grounding_version in {"multispan_v4", "multispan_v5", "multispan_v6"}:
                    job["glyph_source_hashes"] = {
                        "source_id": paper["source_id"],
                        "blocks": {block["block_id"]: hashlib.sha256(
                            block["text"].encode("utf-8")
                        ).hexdigest() for block in blocks},
                    }
            job["input_hash"] = digest(job)
            jobs.append(job)
    return jobs


def export_jobs(jobs: list[dict], destination: Path) -> None:
    """Write exact inputs so API and interactive imports share a contract."""
    for job in jobs:
        write_json(destination / f"{job['input_hash']}.json", job)
    write_json(
        destination / "index.json",
        [
            {key: job[key] for key in ("input_hash", "source_id", "chunk_index", "chunk_count")}
            for job in jobs
        ],
    )


def request_extraction(
    job: dict,
    cache: CachedHTTP,
    model: str,
    provider: str = "openai",
) -> dict:
    """Call the selected provider with the fixed extraction schema.

    Args:
        job: Versioned, hashed extraction input.
        cache: Cache transport supporting credential-free offline replay.
        model: Explicit model identifier chosen for this run.
        provider: Explicit service name, openai or gemini.

    Returns:
        Import-compatible output envelope with API request provenance.
    """
    if provider == "gemini":
        return request_gemini(job, cache, model)
    if provider != "openai":
        raise ExtractionServiceUnavailable(f"Unknown extraction provider: {provider}")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key and not cache.offline:
        raise ExtractionServiceUnavailable(
            "Set OPENAI_API_KEY locally, or use exported jobs and --responses"
        )
    body = {
        "model": model,
        "store": False,
        "instructions": job.get("prompt", PROMPT),
        "input": json.dumps(
            {"source_id": job["source_id"], "title": job["title"], "blocks": job["blocks"]}
        ),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "observations",
                "strict": True,
                "schema": job["schema"],
            }
        },
    }
    try:
        content, request_hash = cache.request(
            "POST",
            "https://api.openai.com/v1/responses",
            body=body,
            headers={"Authorization": f"Bearer {api_key}"},
        )
    except httpx.HTTPStatusError as error:
        code = response_error_code(error.response)
        if error.response.status_code in {400, 401, 403, 404} or code in {
            "credit_balance_exhausted",
            "insufficient_quota",
        }:
            raise ExtractionServiceUnavailable(
                f"OpenAI service unavailable: HTTP {error.response.status_code}; {code}"
            ) from error
        raise
    response = json.loads(content)
    if response.get("status") != "completed":
        raise ValueError(f"Incomplete model response: {response.get('status')}")
    pieces = [
        part["text"]
        for output in response.get("output", [])
        for part in output.get("content", [])
        if part.get("type") == "output_text"
    ]
    parsed = json.loads("".join(pieces))
    return {
        "input_hash": job["input_hash"],
        "engine": model,
        "provider": "openai",
        "resolved_model": response.get("model", model),
        "response_id": response.get("id"),
        "mode": "responses_api",
        "created_at": response.get("created_at"),
        "request_hash": request_hash,
        "usage": response.get("usage", {}),
        "output": parsed,
    }


def validate_candidate(
    candidate: dict, job: dict, minimum_confidence: float
) -> tuple[dict | None, str | None]:
    """Check schema, source identity and verbatim quote grounding.

    Args:
        candidate: Proposed record from a model response.
        job: Exact source blocks shown to the model.
        minimum_confidence: Frozen extraction-confidence threshold.

    Returns:
        Validated record or a rejection reason. Grounding does not prove semantics.
    """
    try:
        observation = Observation.model_validate(candidate)
    except ValidationError as error:
        return None, f"schema: {error}"
    record = observation.model_dump()
    blocks = {block["block_id"]: block for block in job["blocks"]}
    block = blocks.get(record["block_id"])
    if record["source_id"] != job["source_id"] or block is None:
        return None, "unknown_source_or_block"
    quote = normalise_space(record["evidence_quote"])
    if quote not in normalise_space(block["text"]):
        return None, "ungrounded_quote"
    if normalise_space(record["plant_name_as_written"]) not in quote:
        return None, "plant_not_in_quote"
    if record["section"] != block["section"]:
        return None, "section_mismatch"
    ant_words = record["ant_species"].split()
    if len(ant_words) < 2 or ant_words[0] not in {"Atta", "Acromyrmex"}:
        return None, "ant_requires_review"
    if record["extraction_confidence"] < minimum_confidence:
        return None, "low_confidence"
    record["record_id"] = digest(record)
    record["source_url"] = job["source_url"]
    record["input_hash"] = job["input_hash"]
    return record, None


def run_extraction(
    jobs: list[dict],
    cache: CachedHTTP,
    output: Path,
    responses: Path | None = None,
    model: str | None = None,
    minimum_confidence: float = 0.8,
    provider: str = "openai",
) -> dict:
    """Validate API or imported answers and separately count incomplete papers."""
    accepted, rejected, failures, status = [], [], [], []
    glyph_audits: list[dict] = []
    blocked_reason = None
    for job_index, job in enumerate(jobs):
        try:
            if responses is not None:
                path = responses / f"{job['input_hash']}.json"
                if not path.exists():
                    status.append(
                        {
                            "source_id": job["source_id"],
                            "input_hash": job["input_hash"],
                            "status": "pending",
                        }
                    )
                    continue
                envelope = read_json(path)
                if envelope.get("input_hash") != job["input_hash"] or not envelope.get("engine"):
                    raise ValueError("Imported response lacks matching input_hash or engine")
                write_json(cache.root / "imports" / f"{digest(envelope)}.json", envelope)
            elif model:
                envelope = request_extraction(job, cache, model, provider)
            else:
                raise ValueError("Specify --responses or --model")
            write_json(output / "responses" / f"{job['input_hash']}.json", envelope)
            records = envelope["output"]["records"]
            if not isinstance(records, list):
                raise ValueError("output.records must be an array")
            for candidate_index, candidate in enumerate(records):
                if job.get("grounding_version") == "multispan_v1":
                    valid, reason = validate_multispan_candidate(candidate, job, minimum_confidence)
                elif job.get("grounding_version") == "multispan_v2":
                    valid, reason = validate_multispan_v2_candidate(candidate, job, minimum_confidence)
                elif job.get("grounding_version") == "multispan_v3":
                    valid, reason = validate_multispan_v3_candidate(candidate, job, minimum_confidence)
                    glyph_audits.append({
                        "source_id": job["source_id"], "input_hash": job["input_hash"],
                        "candidate_index": candidate_index, "raw_candidate_hash": digest(candidate),
                        "survived": valid is not None, "rejection_reason": reason,
                        **candidate_grounding_audit(candidate, job),
                    })
                elif job.get("grounding_version") == "multispan_v4":
                    valid, reason = validate_multispan_v4_candidate(candidate, job, minimum_confidence)
                    glyph_audits.append({
                        "source_id": job["source_id"], "input_hash": job["input_hash"],
                        "candidate_index": candidate_index, "raw_candidate_hash": digest(candidate),
                        "survived": valid is not None, "rejection_reason": reason,
                        **candidate_grounding_audit_v4(candidate, job),
                    })
                elif job.get("grounding_version") == "multispan_v5":
                    valid, reason = validate_multispan_v5_candidate(candidate, job, minimum_confidence)
                    glyph_audits.append({
                        "source_id": job["source_id"], "input_hash": job["input_hash"],
                        "candidate_index": candidate_index, "raw_candidate_hash": digest(candidate),
                        "survived": valid is not None, "rejection_reason": reason,
                        **candidate_grounding_audit_v5(candidate, job),
                    })
                elif job.get("grounding_version") == "multispan_v6":
                    valid, reason = validate_multispan_v6_candidate(candidate, job, minimum_confidence)
                    glyph_audits.append({
                        "source_id": job["source_id"], "input_hash": job["input_hash"],
                        "candidate_index": candidate_index, "raw_candidate_hash": digest(candidate),
                        "survived": valid is not None, "rejection_reason": reason,
                        **candidate_grounding_audit_v6(candidate, job),
                    })
                else:
                    valid, reason = validate_candidate(candidate, job, minimum_confidence)
                if reason:
                    rejected.append(
                        {
                            "source_id": job["source_id"],
                            "input_hash": job["input_hash"],
                            "candidate": candidate,
                            "reason": reason,
                        }
                    )
                else:
                    valid["engine"] = envelope["engine"]
                    valid["provider"] = envelope.get("provider", "imported_unspecified")
                    valid["resolved_model"] = envelope.get("resolved_model", envelope["engine"])
                    valid["extraction_request_hash"] = envelope.get("request_hash")
                    valid["response_hash"] = digest(envelope)
                    accepted.append(valid)
            status.append(
                {
                    "source_id": job["source_id"],
                    "input_hash": job["input_hash"],
                    "status": "complete",
                }
            )
        except (
            ValueError,
            KeyError,
            TypeError,
            httpx.HTTPError,
            OfflineCacheMiss,
            RuntimeError,
        ) as error:
            failures.append(
                {
                    "source_id": job["source_id"],
                    "input_hash": job["input_hash"],
                    "reason": str(error),
                }
            )
            status.append(
                {"source_id": job["source_id"], "input_hash": job["input_hash"], "status": "failed"}
            )
            if isinstance(error, ExtractionServiceUnavailable):
                blocked_reason = str(error)
        write_jsonl(output / "chunk_status.jsonl", status)
        write_jsonl(output / "failures.jsonl", failures)
        print(
            json.dumps(
                {
                    "completed_chunks": len(status),
                    "total_chunks": len(jobs),
                    "source_id": job["source_id"],
                    "status": status[-1]["status"],
                    "validated_candidates": len(accepted),
                    "rejected_candidates": len(rejected),
                }
            ),
            flush=True,
        )
        if blocked_reason:
            status.extend(
                {
                    "source_id": pending["source_id"],
                    "input_hash": pending["input_hash"],
                    "status": "blocked",
                }
                for pending in jobs[job_index + 1 :]
            )
            break
    incomplete = {row["source_id"] for row in status if row["status"] != "complete"}
    unique = {row["record_id"]: row for row in accepted}
    complete_records = [row for row in unique.values() if row["source_id"] not in incomplete]
    partial_records = [row for row in unique.values() if row["source_id"] in incomplete]
    total = len(accepted) + len(rejected)
    source_ids = {job["source_id"] for job in jobs}
    metrics = {
        "papers": len(source_ids),
        "chunks": len(jobs),
        "complete_papers": len(source_ids - incomplete),
        "incomplete_papers": len(incomplete),
        "candidate_records": total,
        "validated_candidates": len(accepted),
        "rejected_candidates": len(rejected),
        "rejection_rate": len(rejected) / total if total else None,
        "response_failures": len(failures),
        "blocked_reason": blocked_reason,
        "unattempted_chunks": sum(row["status"] in {"blocked", "pending"} for row in status),
        "complete_paper_records": len(complete_records),
        "partial_paper_records": len(partial_records),
        "complete_papers_without_valid_records": len(
            source_ids - incomplete - {r["source_id"] for r in complete_records}
        ),
    }
    write_jsonl(output / "observations.jsonl", complete_records)
    write_jsonl(output / "partial_observations.jsonl", partial_records)
    write_jsonl(output / "rejections.jsonl", rejected)
    write_jsonl(output / "failures.jsonl", failures)
    write_jsonl(output / "chunk_status.jsonl", status)
    write_json(output / "metrics.json", metrics)
    if any(job.get("grounding_version") in {"multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"} for job in jobs):
        write_jsonl(output / "glyph_grounding_audit.jsonl", glyph_audits)
    return metrics
