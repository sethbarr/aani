"""Write the Saverschek development baseline without rerunning extraction."""

import hashlib
from pathlib import Path

from src.common.io import read_json, timestamp, write_json
from src.evaluation.recall import build_baseline


def file_record(path: Path) -> dict:
    """Record the exact local bytes used by the measurement."""
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def render_report(report: dict) -> str:
    """Render counts and limitations for a small, contaminated development panel."""
    primary = report["groups"]["PRIMARY"]
    context = report["groups"]["CONTEXT"]
    lines = [
        "# Saverschek recall baseline — DEVELOPMENT SET", "",
        "This is one panel from one paper and is not a sample from any population. "
        "The unit is the species-direction pair: PRIMARY has six species with six pairs; "
        "CONTEXT has five species with ten pairs. The groups remain separate.", "",
        "| Stage | PRIMARY species / pairs recovered | CONTEXT both directions | CONTEXT collapsed to one | CONTEXT absent | CONTEXT pairs recovered |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for stage in ("detection", "survival", "correctness"):
        p = primary["stages"][stage]
        c = context["stages"][stage]
        coverage = c["direction_coverage"]
        lines.append(f"| {stage} | {p['species_count']} of 6 | "
                     f"{coverage['both_directions_surfaced']} of 5 | "
                     f"{coverage['collapsed_to_one']} of 5 | {coverage['absent']} of 5 | "
                     f"{c['species_direction_pair_count']} of 10 |")
    lines += [
        "", "Detection means a candidate was proposed for the species; survival means a candidate "
        "passed the original grounding checks; correctness means a surviving structured outcome "
        "matches a reference direction. Direction coverage uses emitted outcome fields. "
        "Hymenaea's failed delayed-rejection record mentions acceptance in its quote, but its "
        "structured outcome is rejection, so acceptance receives no credit.", "",
        "| Species | Group | Reference directions | Detection | Survival | Correct directions | Reference provenance |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["species"]:
        mixed = len({s["provenance_strength"] for s in row["reference_support"]}) > 1
        suffix = "; printed Table 1 heading" if row["table_membership_dependency"] else ""
        if suffix and mixed:
            suffix += " plus prose acceptance"
        provenance = row["provenance_strength"] + suffix
        lines.append(f"| {row['species']} | {row['group']} | {', '.join(row['reference_directions'])} | "
                     f"{row['detection']} | {row['survival']} | "
                     f"{', '.join(row['correct_directions']) or 'absent'} | {provenance} |")
    lines += [
        "", "Reference provenance distinguishes explicit `author_prose` from the stronger "
        "`author_table_grouping`, which records species placed under a printed author heading "
        "in Table 1. PRIMARY has 2 `author_prose` and 4 `author_table_grouping` species; "
        "CONTEXT has 4 `author_prose` and 1 `author_table_grouping`. Overall this is 6 prose "
        "and 5 author-grouped species, or 11 prose and 5 author-grouped direction pairs. "
        "Miconia has prose acceptance and author-grouped rejection, so its species tag records "
        "`author_table_grouping`.", "",
        "Reference directions were manually checked against Table 1 of the original PDF and "
        "follow its printed author headings: `Acceptance`, `Immediate rejection`, and "
        "`Habitat-related rejection`. These are author-assigned groupings; numerical signs do "
        "not determine directions. Semantic support for individual rows and captions remains "
        "unverified. Group/complement prose also supports these five labels: nine species "
        "except Spondias and Miconia were avoided on simultaneous day 2; all ten except "
        "Spondias were rejected in individual p-habitat tests. Miconia is grouped under "
        "`Immediate rejection` in Table 1 and accepted in both habitats in the "
        "simultaneous-choice tests, so it remains in CONTEXT. Reference directions and the "
        "6 PRIMARY / 5 CONTEXT denominators stay fixed. Exact anchors and source hashes are "
        "in JSON.", "",
        "Contamination risk: the curator matrix was produced by reading the same text blocks "
        "the extractor read, so shared blind spots would inflate apparent recall. The curator "
        "had the complete cached text including tables; the extractor worked chunk-wise under "
        "a strict quote constraint. This difference partly mitigates the risk, but both depend "
        "on the same source representation. Subsequent improvements measured here are development results.", "",
        f"Unscorable species: {len(primary['unscorable_species'])} of 6 PRIMARY; "
        f"{len(context['unscorable_species'])} of 5 CONTEXT. Every panel member remains in its "
        "denominator, including Trema under the original spelling. Outstanding taxonomy does "
        "not prevent scoring its extraction. Any unscorable row has a blocked_reason in JSON.", "",
        "The existing inventory reconciles 14 candidates: 11 panel candidates and three "
        "outside this panel. The complete run has six grounding passes and eight failures; "
        "three passes concern this panel. Desmopsis and Spondias supply the two correct PRIMARY "
        "pairs. Hymenaea supplies one correct CONTEXT rejection pair. Miconia is absent from "
        "the candidates. These counts measure the original extraction, with curator records "
        "used only for reference labels. The broader nine-of-41 semantic-retention count is a stage yield.", "",
        "Rebuild offline with `.venv/bin/python -m scripts.recall_baseline`. "
        "The JSON includes input hashes and record-level scoring. Extraction prompts, outputs "
        "and grounding rules are unchanged.", "",
    ]
    return "\n".join(lines)


def main() -> None:
    """Measure the saved run and write the requested JSON and Markdown artifacts."""
    audit_path = Path("data/interim/saverschek_audit/natural_audit.json")
    notes_path = audit_path.with_name("natural_notes.md")
    audit = read_json(audit_path)
    source_path = Path(audit["source_path"])
    extraction = Path("data/interim/extraction_saverschek")
    report = build_baseline(audit, read_json(source_path), extraction)
    paths = [audit_path, notes_path, source_path, Path(__file__),
             Path("src/evaluation/recall.py"), extraction / "observations.jsonl",
             extraction / "rejections.jsonl", extraction / "metrics.json",
             extraction / "run_manifest.json", *sorted((extraction / "responses").glob("*.json"))]
    report["generated_at"] = timestamp()
    report["inputs"] = [file_record(path) for path in paths]
    report["cached_source_matches_audit_hash"] = (
        file_record(source_path)["sha256"] == audit["source_file_sha256"]
    )
    if not report["cached_source_matches_audit_hash"]:
        raise ValueError("Cached source differs from the curator audit source hash")
    output = Path("results")
    write_json(output / "recall_baseline.json", report)
    (output / "recall_baseline.md").write_text(render_report(report), encoding="utf-8")
    print({"status": report["status"], "groups": report["groups"]})


if __name__ == "__main__":
    main()
