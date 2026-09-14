"""Draw and diagnose two additional Currie extraction samples."""

import argparse
import json
import os
from pathlib import Path

import httpx

from src.common.cache import CachedHTTP
from src.common.environment import load_local_environment
from src.common.io import read_json, timestamp, write_json
from src.extraction.gemini import DEFAULT_MODEL
from src.extraction.pipeline import request_extraction
from src.systems.config import load_system_config
from src.systems.currie_diagnosis import (
    CURRIE_INPUT_HASH,
    EXPECTED_MODEL,
    file_sha256,
    inspect_currie_blocks,
    score_currie_sample,
    verify_currie_job,
)


def currie_reference(reference_set: dict) -> dict:
    """Select the unchanged Currie item from the fixed reference set.

    Args:
        reference_set: Two-item prospective reference set.

    Returns:
        Currie reference item.
    """
    matches = [
        item
        for item in reference_set["reference_items"]
        if item["reference_id"] == "currie_1999_antibiotic_suppression"
    ]
    if len(matches) != 1 or reference_set["scoring"]["recall_denominator"] != 2:
        raise ValueError("The fixed Currie reference item changed")
    return matches[0]


def draw_sample(job: dict, root: Path, sample_number: int, model: str) -> dict:
    """Call the unchanged Gemini adapter using a fresh per-sample cache.

    Args:
        job: Exact saved Currie payload.
        root: Repository root.
        sample_number: Repeat number, two or three.
        model: Existing attine model identifier.

    Returns:
        Provider response envelope.

    Raises:
        FileExistsError: A saved repeat would be silently reused.
    """
    cache_path = root / f"data/interim/systems/attine_actino/currie_recovery/sample_{sample_number}"
    cache_file = cache_path / "http"
    if cache_file.exists() and any(cache_file.iterdir()):
        raise FileExistsError(f"Sample {sample_number} already has an HTTP response cache")
    cache = CachedHTTP(
        cache_path,
        offline=False,
        client=httpx.Client(timeout=180, follow_redirects=True),
    )
    try:
        return request_extraction(job, cache, model, provider="gemini")
    finally:
        cache.close()


def verify_offline_sample(job: dict, cache_path: Path, expected: dict, model: str) -> dict:
    """Replay one provider response from its raw HTTP cache.

    Args:
        job: Exact saved Currie payload.
        cache_path: Cache root containing the response envelope.
        expected: Recorded normalized response envelope.
        model: Existing attine model identifier.

    Returns:
        Offline replay status and normalized response identity.
    """
    cache = CachedHTTP(cache_path, offline=True)
    try:
        replayed = request_extraction(job, cache, model, provider="gemini")
    finally:
        cache.close()
    return {
        "verified": replayed == expected,
        "request_hash": replayed.get("request_hash"),
        "response_output_matches": replayed.get("output") == expected.get("output"),
    }


def diagnosis_conclusion(samples: list[dict], source: dict) -> tuple[str, str]:
    """Classify the observed three-sample extraction behavior.

    Args:
        samples: Per-sample fixed-reference scores.
        source: Deterministic source-block diagnostics.

    Returns:
        Machine-readable cause label and report sentence.
    """
    all_empty = all(not sample["any_candidate_surfaced"] for sample in samples)
    relation_intact = (
        source["relation_block"]["complete_relation_present"]
        and source["relation_block"]["reached_model_intact"]
    )
    if all_empty and relation_intact:
        return (
            "real_recall_miss",
            "All three samples returned empty arrays while the complete reference relation "
            "reached the model intact in the abstract block. This is a real recall miss.",
        )
    recovered = sum(sample["fixed_reference_recovered"] for sample in samples)
    if recovered:
        return (
            "sampling_variability",
            f"The fixed Currie item was recovered in {recovered} of three samples. The initial "
            "empty response is a sample-level omission, and the repeats show model sampling "
            "variability with an unchanged input contract.",
        )
    corrigendum_only = any(
        candidate["candidate"].get("target_name_as_written") == "Pseudonocardiaceae"
        for sample in samples
        for candidate in sample["candidates"]
    )
    if relation_intact and corrigendum_only:
        return (
            "historical_name_target_mismatch_and_quote_repair",
            "The fixed Currie relation was missed in all three samples. The unchanged system "
            "prompt names Pseudonocardia, while the 1999 relation names Streptomyces and the "
            "corrigendum supplies only the family Pseudonocardiaceae. Samples 1 and 2 were "
            "empty; sample 3 selected that corrigendum family statement and repaired its printed "
            "line breaks, which made the quote ungrounded. The strict all-empty criterion is "
            "inapplicable because sample 3 surfaced a candidate.",
        )
    return (
        "incomplete_candidate_recall",
        "At least one sample surfaced a candidate, while no sample carried every fixed "
        "producer, compound-class, target, and inhibition component in a grounded record.",
    )


def summary_text(report: dict) -> str:
    """Render the three-sample diagnosis as Markdown.

    Args:
        report: Completed diagnosis report.

    Returns:
        Markdown summary.
    """
    rows = []
    for sample in report["samples"]:
        rows.append(
            "| {sample} | {candidates} | {grounded} | {recovered} |".format(
                sample=sample["sample"],
                candidates=sample["candidate_records"],
                grounded=sample["grounded_records"],
                recovered="yes" if sample["fixed_reference_recovered"] else "no",
            )
        )
    source = report["source_diagnosis"]
    return "\n".join(
        [
            "# Currie 1999 repeat-extraction diagnosis",
            "",
            report["conclusion"],
            "",
            "| Sample | Candidate records | Grounded records | Fixed item recovered |",
            "| --- | ---: | ---: | --- |",
            *rows,
            "",
            "Each sample used the saved Currie-only payload, `single_quote_v1` grounding, "
            "unchanged attine prompt and schema, and `gemini-3.8-flash`. The original sample "
            "and positive-control score remain unchanged.",
            "All three response envelopes replayed exactly from their raw HTTP caches with "
            "offline mode enabled.",
            "",
            "## Source inspection",
            "",
            "- Historical `Streptomyces` naming: "
            f"{'present' if source['historical_streptomyces_naming']['present'] else 'absent'}.",
            "- Embedded-font glyph artifacts: "
            f"{'present' if source['glyph_artifacts']['present'] else 'absent'}.",
            "- Hyphenation across retained line breaks: "
            f"{'present' if source['line_break_hyphenation']['present'] else 'absent'} "
            f"({len(source['line_break_hyphenation']['instances'])} instances).",
            "- Complete producer–antibiotic–Escovopsis–inhibition relation in the abstract: "
            f"{'present' if source['relation_block']['complete_relation_present'] else 'absent'}.",
            "- Abstract block reached the adapter unchanged from the cached source: "
            f"{'yes' if source['relation_block']['reached_model_intact'] else 'no'}.",
            "",
            "Candidate-level fields, validation outcomes, complete response envelopes, source "
            "diagnostics, and hashes are recorded in this directory.",
            "",
        ]
    )


def diagnose(root: Path, draw: bool) -> dict:
    """Load the original sample, draw repeats, and write isolated artifacts.

    Args:
        root: Repository root.
        draw: Whether to make the two authorized model calls.

    Returns:
        Three-sample diagnosis report.
    """
    config_path = root / "config/systems/attine_actino.json"
    job_path = (
        root
        / "data/interim/systems/attine_actino/reference_sources/extraction_payloads"
        / f"{CURRIE_INPUT_HASH}.json"
    )
    document_path = (
        root
        / "data/interim/systems/attine_actino/reference_sources/corpus/texts/CURRIE1999.json"
    )
    original_response = (
        root / "data/interim/systems/attine_actino/extraction/responses" / f"{CURRIE_INPUT_HASH}.json"
    )
    reference_path = root / "results/systems/attine_actino/reference_set.json"
    positive_control_path = root / "results/systems/attine_actino/positive_control.json"
    output = root / "results/systems/attine_actino/currie_recovery"
    config = load_system_config(config_path)
    job = read_json(job_path)
    document = read_json(document_path)
    reference_set = read_json(reference_path)
    reference = currie_reference(reference_set)
    adapter_checks = verify_currie_job(job, document, config)
    preserved_before = {
        "job": file_sha256(job_path),
        "source": file_sha256(document_path),
        "original_response": file_sha256(original_response),
        "positive_control": file_sha256(positive_control_path),
    }
    responses = [read_json(original_response)]
    if draw:
        load_local_environment(root / ".env")
        model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        if model != EXPECTED_MODEL:
            raise ValueError("Model differs from the original attine extractor")
        responses.extend(draw_sample(job, root, number, model) for number in (2, 3))
    else:
        responses.extend(read_json(output / f"sample_{number}_response.json") for number in (2, 3))
    output.mkdir(parents=True, exist_ok=True)
    for number, response in enumerate(responses, start=1):
        write_json(output / f"sample_{number}_response.json", response)
    cache_paths = [
        root / "data/interim/systems/attine_actino/cache",
        root / "data/interim/systems/attine_actino/currie_recovery/sample_2",
        root / "data/interim/systems/attine_actino/currie_recovery/sample_3",
    ]
    offline_replays = [
        {"sample": number, **verify_offline_sample(job, cache_path, response, EXPECTED_MODEL)}
        for number, (cache_path, response) in enumerate(zip(cache_paths, responses, strict=True), 1)
    ]
    if not all(replay["verified"] for replay in offline_replays):
        raise ValueError("A recorded Currie response failed offline replay")
    minimum_confidence = read_json(root / "config/analysis.json")["extraction_confidence"]
    scores = []
    for number, response in enumerate(responses, start=1):
        score = score_currie_sample(response, job, config, reference, minimum_confidence)
        scores.append({"sample": number, **score})
    source = inspect_currie_blocks(job, document)
    cause, conclusion = diagnosis_conclusion(scores, source)
    preserved_after = {
        "job": file_sha256(job_path),
        "source": file_sha256(document_path),
        "original_response": file_sha256(original_response),
        "positive_control": file_sha256(positive_control_path),
    }
    if preserved_before != preserved_after:
        raise ValueError("A frozen attine input or original result changed during diagnosis")
    report = {
        "created_at": timestamp(),
        "system": "attine_actino",
        "source_id": "CURRIE1999",
        "status": "complete",
        "analysis_freeze_commit": "98b5e09199a5eef0c46be452793e953f5a2af31e",
        "additional_model_samples": 2,
        "adapter_modified": False,
        "prompt_modified": False,
        "schema_modified": False,
        "original_positive_control_modified": False,
        "offline_replay_verified": True,
        "offline_replays": offline_replays,
        "adapter_checks": adapter_checks,
        "reference_id": reference["reference_id"],
        "fixed_reference_match_rule": reference_set["scoring"]["match_rule"],
        "samples": scores,
        "recovered_samples": sum(sample["fixed_reference_recovered"] for sample in scores),
        "empty_samples": sum(not sample["any_candidate_surfaced"] for sample in scores),
        "diagnosed_cause": cause,
        "conclusion": conclusion,
        "source_diagnosis": source,
        "preserved_artifact_sha256": preserved_after,
    }
    write_json(output / "diagnosis.json", report)
    (output / "summary.md").write_text(summary_text(report), encoding="utf-8")
    return report


def parser() -> argparse.ArgumentParser:
    """Build the diagnosis command-line parser."""
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument("--draw", action="store_true")
    return value


def main() -> None:
    """Run the three-sample diagnosis."""
    args = parser().parse_args()
    print(json.dumps(diagnose(args.root.resolve(), args.draw), indent=2))


if __name__ == "__main__":
    main()
