"""Run the predeclared reader experiment in an isolated measurement directory."""

import argparse
import base64
import hashlib
import json
import signal
import subprocess
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from types import FrameType

import httpx

from scripts.verify_day2 import file_hash, frozen_checks
from src.common.environment import load_local_environment
from src.common.io import digest, read_json, timestamp, write_json, write_jsonl
from src.evaluation.comparison import reference_rows
from src.evaluation.recall import score_species, summarise_group
from src.extraction.gemini import DEFAULT_MODEL, ENDPOINT, request_gemini
from src.extraction.multispan_v6 import validate_multispan_v6_candidate
from src.extraction.pipeline import make_jobs
from src.extraction.single_attempt_transport import SingleAttemptHTTP

PRIVATE = Path("data/interim/detection_variance")
REPORT = Path("results/detection_variance")
CORPUS = Path("data/interim/corpus_targeted_saverschek")
AMENDMENT = Path("docs/amendment_2026-09-14_detection_variance.md")
COMMIT = "3a29ebd8622b3c47af95eb6b9846328a27c86bd8"
DEADLINE = datetime(2026, 9, 14, 16, 34, 12, tzinfo=UTC)
DRAWS = [f"{arm}{number}" for arm in "AB" for number in range(1, 5)]
REMOVED = {"name_evidence", "supporting_evidence"}


def single_span_job(original: dict) -> dict:
    """Remove the second-span contract while retaining other source instructions."""
    job = deepcopy(original)
    schema = job["schema"]["$defs"]["MultiSpanObservation"]
    for name in REMOVED:
        del schema["properties"][name]
    schema["required"] = [name for name in schema["required"] if name not in REMOVED]
    del job["schema"]["$defs"]["EvidenceSpan"]
    replacements = [
        ("Evidence may occupy several spans. Each evidence_quote or quote must be copied as",
         "Return one evidence span per record. The evidence_quote must be copied as"),
        ("name_evidence separately quotes the full plant name found in these blocks, with\n"
         "its block_id and section. Set plant_name_as_written to that exact full name. Set",
         "Read the full plant name from these blocks; it may occur outside the primary span.\n"
         "Set plant_name_as_written to that exact full name. Set"),
        ("supporting_evidence supplies exact spans establishing direction and experimental\n"
         "context. For tabular evidence, include the author-assigned category heading, the\n"
         "row containing this plant, and the caption or prose needed to connect category,\n"
         "habitat and time. A heading applies only to rows within its group before the next\n"
         "heading; retain a span that establishes this relationship across the relevant rows.",
         "Use the supplied blocks to establish direction and experimental context. For tabular\n"
         "evidence, use the author-assigned category heading, the row containing this plant,\n"
         "and the caption or prose needed to connect category, habitat and time. A heading\n"
         "applies only to rows within its group before the next heading. Return one primary\n"
         "span anchoring the behavioural event or this plant's table row."),
        ("several named plants, each species record must retain the statement and its identity\n"
         "anchor.",
         "several named plants, use the statement and each plant's identity in the supplied\n"
         "blocks to interpret each species record; return its one primary span."),
    ]
    for old, new in replacements:
        if job["prompt"].count(old) != 1:
            raise ValueError("single_span_prompt_patch_ambiguous")
        job["prompt"] = job["prompt"].replace(old, new)
    job.pop("input_hash")
    job["input_hash"] = digest(job)
    return job


def adapt_candidate(candidate: dict, arm: str) -> dict:
    """Duplicate only the returned primary span for the frozen v6 input contract."""
    adapted = deepcopy(candidate)
    if arm == "B":
        if REMOVED.intersection(candidate):
            raise ValueError("single_span_response_has_forbidden_span_fields")
        adapted["name_evidence"] = {
            "block_id": candidate.get("block_id"), "section": candidate.get("section"),
            "quote": candidate.get("evidence_quote"),
        }
        adapted["supporting_evidence"] = []
    return adapted


def descriptor(job: dict) -> dict:
    """Declare the exact body enforced by the existing single-attempt transport."""
    return {
        "method": "POST", "url": ENDPOINT, "params": {}, "json": {
            "model": DEFAULT_MODEL, "store": False, "system_instruction": job["prompt"],
            "input": json.dumps({key: job[key] for key in ("source_id", "title", "blocks")}),
            "response_format": {"type": "text", "mime_type": "application/json",
                                "schema": job["schema"]},
            "generation_config": {"max_output_tokens": 32768, "thinking_level": "low",
                                  "thinking_summaries": "none"},
        },
    }


def git_output(arguments: list[str]) -> str:
    """Read repository provenance without modifying Git state."""
    return subprocess.run(["git", *arguments], check=True, capture_output=True,
                          text=True).stdout.strip()


def prepare() -> None:
    """Freeze jobs and evidence hashes before any live model request."""
    if (PRIVATE / "protocol.json").exists():
        raise ValueError("experiment_already_prepared")
    committed = subprocess.run(["git", "show", f"{COMMIT}:{AMENDMENT}"], check=True,
                               capture_output=True).stdout
    if committed != AMENDMENT.read_bytes():
        raise ValueError("predeclaration_differs_from_commit")
    old = read_json(Path("results/grounding_development_v6/heldout_sample4_protocol.json"))
    historical = [row for row in old["frozen_inputs"]
                  if row["path"].startswith(("src/extraction/", "src/evaluation/", "src/common/"))
                  or row["path"] == "config/grounding_glyphs_v6.json"]
    for row in historical:
        if file_hash(Path(row["path"])) != row["sha256"]:
            raise ValueError(f"historical_v6_changed:{row['path']}")
    jobs_a = make_jobs(CORPUS, grounding_version="multispan_v2")
    jobs_v6 = make_jobs(CORPUS, grounding_version="multispan_v6")
    if len(jobs_a) != 3:
        raise ValueError("expected_three_jobs")
    if [job["input_hash"] for job in jobs_a] != [row["input_hash"] for row in old["requests"]]:
        raise ValueError("arm_a_changed_from_historical_v2_jobs")
    comparisons = []
    for original, validation in zip(jobs_a, jobs_v6, strict=True):
        alternative = single_span_job(original)
        for key in original.keys() - {"prompt", "schema", "input_hash"}:
            if original[key] != alternative[key]:
                raise ValueError(f"unrelated_job_field_changed:{key}")
        suffix = "\nSource-level ant identity context follows."
        if original["prompt"].split(suffix)[1] != alternative["prompt"].split(suffix)[1]:
            raise ValueError("identity_context_changed")
        idx = original["chunk_index"]
        write_json(PRIVATE / "jobs" / f"A_{idx}.json", original)
        write_json(PRIVATE / "jobs" / f"B_{idx}.json", alternative)
        write_json(PRIVATE / "jobs" / f"v6_{idx}.json", validation)
        comparisons.append({"chunk_index": idx, "source_blocks_identical": True,
                            "identity_context_identical": True,
                            "non_evidence_job_fields_identical": True,
                            "A_request_hash": digest(descriptor(original)),
                            "B_request_hash": digest(descriptor(alternative))})
    paths = {Path(row["path"]) for row in historical}
    paths.update(PRIVATE.joinpath("jobs").glob("*.json"))
    paths.update(CORPUS.rglob("*.json"))
    paths.add(CORPUS / "manifest.jsonl")
    paths.update([AMENDMENT, Path(__file__).relative_to(Path.cwd()),
                  Path("results/recall_baseline.json"), Path("tests/test_detection_variance.py")])
    protected = [path for root in (Path("data/processed"), Path("results"))
                 for path in root.rglob("*") if path.is_file() and REPORT not in path.parents]
    paths.update(protected)
    frozen = frozen_checks()
    if not all(row["matches_frozen_commit"] for row in frozen):
        raise ValueError("original_protocol_changed")
    protocol = {
        "prepared_at": timestamp(), "deadline": DEADLINE.isoformat(),
        "predeclaration_commit": COMMIT,
        "predeclaration_committed_at": git_output(["show", "-s", "--format=%cI", COMMIT]),
        "predeclaration_sha256": file_hash(AMENDMENT), "draw_order": DRAWS,
        "model": DEFAULT_MODEL, "planned_calls": 24, "attempts_per_job": 1,
        "transport_retries": 0, "arm_checks": comparisons,
        "historical_v6_hashes_verified": historical, "frozen_protocol_files": frozen,
        "files": [{"path": str(path), "sha256": file_hash(path)} for path in sorted(paths)],
    }
    write_json(PRIVATE / "protocol.json", protocol)
    write_json(REPORT / "provenance.json", protocol)
    print(json.dumps({"status": "prepared", "frozen_files": len(paths),
                      "commit": COMMIT, "prepared_at": protocol["prepared_at"]}), flush=True)


def verify() -> dict:
    """Require byte-identical frozen code, jobs, reference, and biological outputs."""
    protocol = read_json(PRIVATE / "execution_protocol.json")
    changed = [row["path"] for row in protocol["files"]
               if not Path(row["path"]).is_file() or file_hash(Path(row["path"])) != row["sha256"]]
    if changed:
        raise ValueError(f"frozen_files_changed:{changed}")
    checks = frozen_checks()
    if not all(row["matches_frozen_commit"] for row in checks):
        raise ValueError("frozen_protocol_changed")
    return {"verified_at": timestamp(), "files_checked": len(protocol["files"]),
            "all_unchanged": True, "frozen_protocol_files": checks}


def deadline_alarm(signum: int, frame: FrameType | None) -> None:
    """Interrupt an in-flight request at the task's hard deadline."""
    raise TimeoutError("detection_variance_deadline")


def draw_one(draw: str) -> dict:
    """Persist three independent single attempts with no replacement response."""
    destination = PRIVATE / draw
    marker = destination / "started.json"
    if marker.exists():
        raise ValueError(f"draw_already_started:{draw}")
    verify()
    write_json(marker, {"draw": draw, "started_at": timestamp()})
    jobs = [read_json(PRIVATE / "jobs" / f"{draw[0]}_{idx}.json") for idx in range(3)]
    expected = {digest(descriptor(job)): descriptor(job) for job in jobs}
    client = httpx.Client(timeout=240, follow_redirects=False,
                          transport=httpx.HTTPTransport(retries=0))
    cache = SingleAttemptHTTP(destination / "cache", expected, client)
    outcomes = []
    try:
        for job in jobs:
            remaining = (DEADLINE - datetime.now(UTC)).total_seconds()
            outcome = {"chunk_index": job["chunk_index"], "input_hash": job["input_hash"]}
            if remaining <= 0:
                outcome.update(status="missing", reason="time_box_expired")
            else:
                signal.setitimer(signal.ITIMER_REAL, remaining)
                try:
                    envelope = request_gemini(job, cache, DEFAULT_MODEL)
                    path = destination / "responses" / f"{job['chunk_index']}.json"
                    write_json(path, envelope)
                    outcome.update(status="complete", response_path=str(path),
                                   response_sha256=file_hash(path),
                                   candidate_count=len(envelope["output"]["records"]))
                except (OSError, RuntimeError, ValueError, KeyError, httpx.HTTPError) as error:
                    outcome.update(status="failed", reason=f"{type(error).__name__}: {error}")
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
            outcomes.append(outcome)
            write_json(destination / "sampling.json", {
                "draw": draw, "outcomes": outcomes, "attempt_log": cache.attempt_log,
                "retries": 0, "updated_at": timestamp(),
            })
            print(json.dumps({"draw": draw, **outcome}), flush=True)
    finally:
        cache.close()
    verify()
    return score_draw(draw)


def score_draw(draw: str) -> dict:
    """Score saved raw proposals with the frozen validator and baseline functions."""
    verify()
    destination = PRIVATE / draw
    sampling_path = destination / "sampling.json"
    sampling = read_json(sampling_path) if sampling_path.exists() else {"outcomes": [],
                                                                       "attempt_log": []}
    complete = len(sampling["outcomes"]) == 3 and all(
        row["status"] == "complete" for row in sampling["outcomes"])
    candidates = []
    validation_rows = []
    response_hashes = []
    for idx in range(3):
        path = destination / "responses" / f"{idx}.json"
        if not path.exists():
            continue
        envelope = read_json(path)
        job = read_json(PRIVATE / "jobs" / f"v6_{idx}.json")
        response_hashes.append({"chunk_index": idx, "sha256": file_hash(path),
                                "response_id": envelope.get("response_id"),
                                "resolved_model": envelope.get("resolved_model")})
        for number, raw in enumerate(envelope["output"]["records"]):
            candidate_id = f"{draw}:{idx}:{number}"
            try:
                adapted = adapt_candidate(raw, draw[0])
                valid, reason = validate_multispan_v6_candidate(adapted, job, 0.8)
            except (ValueError, TypeError) as error:
                adapted, valid, reason = None, None, f"adapter:{error}"
            candidates.append({"candidate_id": candidate_id, "record": raw,
                               "record_digest": digest(raw),
                               "grounding_status": "passed" if valid is not None else "failed",
                               "grounding_failure_reason": reason, "blocked_reason": None})
            validation_rows.append({"candidate_id": candidate_id, "raw": raw,
                                    "adapted": adapted, "validated": valid, "reason": reason})
    references = reference_rows(read_json(Path("results/recall_baseline.json")))
    species = [score_species(reference, candidates) for reference in references]
    groups = {group: summarise_group(species, group) for group in ("PRIMARY", "CONTEXT")}
    primary = [row for row in species if row["group"] == "PRIMARY"]
    report = {
        "draw": draw, "arm": draw[0], "status": "complete" if complete else "incomplete",
        "scored_at": timestamp(), "within_deadline": datetime.now(UTC) <= DEADLINE,
        "total_candidates": len(candidates),
        "candidate_passes": sum(row["grounding_status"] == "passed" for row in candidates),
        "candidate_failures": sum(row["grounding_status"] == "failed" for row in candidates),
        "primary": {stage: groups["PRIMARY"]["stages"][stage]["species_count"]
                    if complete else None for stage in ("detection", "survival", "correctness")},
        "primary_reference_pairs": {stage: value["species_direction_pair_count"]
                                    if complete else None
                                    for stage, value in groups["PRIMARY"]["stages"].items()},
        "omitted_species": [row["species"] for row in primary if row["detection"] is False]
                           if complete else None,
        "primary_species": [{key: row[key] for key in (
            "species", "detection", "survival", "correctness", "proposed_directions",
            "surviving_directions", "correct_directions")}
            for row in primary] if complete else None,
        "failure_reasons": dict(Counter(row["grounding_failure_reason"] for row in candidates
                                        if row["grounding_status"] == "failed")),
        "sampling": sampling, "responses": response_hashes,
    }
    write_jsonl(destination / "validation.jsonl", validation_rows)
    write_json(destination / "baseline_scores.json", {"complete": complete, "species": species,
                                                       "groups": groups})
    write_json(REPORT / f"{draw}.json", report)
    return report


def arm_summary(rows: list[dict], arm: str) -> dict:
    """Describe complete draws without imputing missing measurements."""
    selected = [row for row in rows if row["arm"] == arm and row["status"] == "complete"]
    result = {"arm": arm, "complete_draws": len(selected),
              "missing_draws": [row["draw"] for row in rows
                                if row["arm"] == arm and row["status"] != "complete"],
              "total_candidates": sum(row["total_candidates"] for row in selected),
              "candidate_passes": sum(row["candidate_passes"] for row in selected)}
    for stage in ("detection", "survival", "correctness"):
        values = [row["primary"][stage] for row in selected]
        result[stage] = {"counts": values, "mean": mean(values) if values else None,
                         "range": [min(values), max(values)] if values else None}
    names = [row["species"] for row in read_json(Path("results/recall_baseline.json"))["species"]
             if row["group"] == "PRIMARY"]
    result["omissions"] = {name: sum(name in row["omitted_species"] for row in selected)
                           for name in names}
    return result


def verdict(arms: dict) -> str:
    """Apply only the committed descriptive interpretation criteria."""
    a, b = arms["A"], arms["B"]
    if a["complete_draws"] == b["complete_draws"] == 4:
        av, bv = a["detection"]["counts"], b["detection"]["counts"]
        if min(bv) > max(av):
            return "The data support H2 under the predeclared descriptive criterion at n=4 per arm."
        overlap = max(min(av), min(bv)) <= min(max(av), max(bv))
        if max(av) - min(av) >= 2 and overlap and abs(mean(av) - mean(bv)) <= 0.5:
            return "The data support H1 under the predeclared descriptive criterion at n=4 per arm."
    return "The data cannot distinguish H1 and H2 at n=4 per arm under the predeclared criteria."


def render_summary(rows: list[dict], arms: dict, interpretation: str) -> str:
    """Render all draws, arm yields and limitations without source quotations."""
    lines = ["# Detection variance — DEVELOPMENT SET", "",
             f"Predeclaration: `{COMMIT}`; committed 2026-09-14T08:15:33-04:00. "
             f"Execution deadline: {DEADLINE.isoformat()}. See the committed restart addendum.", "",
             "A uses the current two-span v2+ contract. B requests one span with identical "
             "source-level identity context. Every candidate uses frozen v6 (confidence 0.8); "
             "B's sole span is mechanically duplicated into name_evidence with empty support.", "",
             "PRIMARY scores are species counts out of six. Correctness uses the baseline "
             "structured species/outcome match. Proposed candidates and passes include all species.",
             "", "| Draw | Status | Detection /6 | Survival /6 | Correctness /6 | Proposed | Passed | Omitted PRIMARY species |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in rows:
        values = [str(row["primary"][stage]) if row["primary"][stage] is not None else "unavailable"
                  for stage in ("detection", "survival", "correctness")]
        omissions = ", ".join(row["omitted_species"] or []) or (
            "none" if row["status"] == "complete" else "unavailable")
        lines.append(f"| {row['draw']} | {row['status']} | {' | '.join(values)} | "
                     f"{row['total_candidates']} | {row['candidate_passes']} | {omissions} |")
    lines += ["", "| Arm | Detection counts | Mean | Range | Survival counts | Mean | Range | Total proposed | Total passed |",
              "| --- | --- | ---: | --- | --- | ---: | --- | ---: | ---: |"]
    for arm in arms.values():
        d, s = arm["detection"], arm["survival"]
        lines.append(f"| {arm['arm']} | {d['counts']} | {d['mean']} | {d['range']} | "
                     f"{s['counts']} | {s['mean']} | {s['range']} | {arm['total_candidates']} | "
                     f"{arm['candidate_passes']} |")
    lines += ["", "| PRIMARY species | A omissions | B omissions |",
              "| --- | ---: | ---: |"]
    for name in arms["A"]["omissions"]:
        lines.append(f"| {name} | {arms['A']['omissions'][name]} | {arms['B']['omissions'][name]} |")
    attempts = sum(len(row["sampling"]["attempt_log"]) for row in rows)
    missing = [row["draw"] for row in rows if row["status"] != "complete"]
    lines += ["", interpretation, "",
              f"Recorded transport attempts: {attempts}; retries: 0. "
              f"Incomplete draws: {', '.join(missing) or 'none'}.", "",
              "The H2 criterion requires min(B) > max(A); the H1 criterion requires an A "
              "range of at least two species, overlapping ranges, and a mean gap at most 0.5. "
              "These are descriptive criteria. No statistical test or p-value was computed.", "",
              "The single-span adapter can reduce survival when the one returned span lacks "
              "the full plant name. It adds no evidence and preserves all v6 gates. Per-draw "
              "JSON files retain failure reasons and reference-pair counts; raw responses and "
              "candidate validation are isolated under data/interim/detection_variance.", "",
              "This is one paper and one panel; implementers know the reference. Table-derived "
              "labels retain the baseline's unverified numerical transcription caveat. Arms ran "
              "A first, so provider changes during execution remain a limitation. These results "
              "measure this reader on this development source. Arm B records were excluded from "
              "every primary and exploratory biological output.", ""]
    if missing:
        lines += ["Arm A is the complete-arm result if all its draws completed. Available B "
                  "rows are partial-arm observations; missing draws are excluded from means.", ""]
    return "\n".join(lines)


def report() -> None:
    """Replay measurement offline and verify immutable inputs after scoring."""
    rows = [score_draw(draw) for draw in DRAWS]
    arms = {arm: arm_summary(rows, arm) for arm in "AB"}
    interpretation = verdict(arms)
    integrity = verify()
    bodies = []
    for path in sorted(PRIVATE.glob("*/cache/http/*.json")):
        cache = read_json(path)
        bodies.append({"path": str(path), "request_hash": cache["request_hash"],
                       "attempts": len(cache["transport_attempts"]),
                       "response_bytes_sha256": hashlib.sha256(base64.b64decode(
                           cache["attempts"][0]["body_base64"])).hexdigest()
                       if cache["attempts"] else None})
    write_json(REPORT / "verification.json", {**integrity, "transport": bodies,
                                               "all_single_attempt": all(
                                                   row["attempts"] == 1 for row in bodies)})
    write_json(REPORT / "comparison.json", {"arms": arms, "verdict": interpretation,
                                             "draws": rows})
    (REPORT / "summary.md").write_text(render_summary(rows, arms, interpretation), encoding="utf-8")
    print(json.dumps({"arms": arms, "verdict": interpretation}), flush=True)


def main() -> None:
    """Prepare, execute once, or rebuild reports solely from saved responses."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "report", "verify"))
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "verify":
        print(verify())
    elif args.action == "report":
        report()
    else:
        load_local_environment()
        signal.signal(signal.SIGALRM, deadline_alarm)
        for draw in DRAWS:
            if (PRIVATE / draw / "started.json").exists():
                continue
            draw_one(draw)
        report()


if __name__ == "__main__":
    main()
