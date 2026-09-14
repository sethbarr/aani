"""Apply v2 grounding to saved v1 proposals without making a new model request."""

from collections import Counter
from pathlib import Path

from src.common.io import read_json, timestamp, write_json
from src.evaluation.comparison import reference_rows
from src.evaluation.recall import candidate_inventory, score_species, summarise_group
from src.extraction.multispan_v2 import validate_multispan_v2_candidate
from src.extraction.pipeline import make_jobs


def diagnose() -> dict:
    """Separate changed grounding decisions from changes in model-proposed observations."""
    corpus = Path("data/interim/corpus_targeted_saverschek")
    original = make_jobs(corpus, grounding_version="multispan_v1")
    changed = make_jobs(corpus, grounding_version="multispan_v2")
    job_by_old_hash = {old["input_hash"]: new for old, new in zip(original, changed, strict=True)}
    candidates, inventory = candidate_inventory(Path("data/interim/extraction_saverschek_multispan_v1"))
    if inventory["blocked_reason"]:
        raise ValueError(inventory["blocked_reason"])
    confidence = read_json(Path("config/analysis.json"))["extraction_confidence"]
    reassessed = []
    failures = Counter()
    routes = Counter()
    for candidate in candidates:
        record, reason = validate_multispan_v2_candidate(
            candidate["record"], job_by_old_hash[candidate["input_hash"]], confidence
        )
        if reason:
            failures[reason] += 1
        if record is not None:
            routes[record["ant_identity_route"]] += 1
        reassessed.append({
            **candidate, "v1_grounding_status": candidate["grounding_status"],
            "v1_grounding_failure_reason": candidate["grounding_failure_reason"],
            "grounding_status": "passed" if record is not None else "failed",
            "grounding_failure_reason": reason, "v2_grounded_record": record,
        })
    baseline = read_json(Path("results/recall_baseline.json"))
    rows = [score_species(reference, reassessed) for reference in reference_rows(baseline)]
    return {"status": "complete", "blocked_reason": None, "generated_at": timestamp(),
            "is_fresh_v2_model_run": False, "model_requests": 0,
            "scope": "Deterministic v2 grounding of the same seven saved v1 proposals. "
            "These counts are separate from the requested single fresh v2 model run.",
            "correctness_definition": "Unchanged baseline structured-direction matching.",
            "candidate_records": len(reassessed),
            "grounding_passes": sum(row["grounding_status"] == "passed" for row in reassessed),
            "failure_reasons": dict(failures), "ant_identity_routes": dict(routes),
            "groups": {group: summarise_group(rows, group) for group in ("PRIMARY", "CONTEXT")},
            "species": rows, "candidates": reassessed}


def main() -> None:
    """Save the diagnostic separately and expose actual failures if it cannot run."""
    try:
        report = diagnose()
    except (OSError, KeyError, ValueError) as error:
        report = {"status": "blocked", "blocked_reason": f"{type(error).__name__}: {error}"}
    write_json(Path("results/grounding_development_v2/saved_candidate_diagnostic.json"), report)
    print({key: report.get(key) for key in
           ("status", "candidate_records", "grounding_passes", "failure_reasons", "blocked_reason")})
    if report["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
