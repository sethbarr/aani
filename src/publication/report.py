"""Write a source-by-file publication audit and preserve license uncertainty."""

from pathlib import Path

from src.common.io import read_json, timestamp, write_json
from src.publication.audit import inspect_file, public_finding, tracked_paths
from src.publication.redact import PRIVATE, redact_file
from src.publication.source_index import SourceIndex, sha256

PUBLIC = Path("results/publication_safety")


def licence_map(root: Path) -> dict[str, dict]:
    """Load source-specific licence evidence without assuming public access permits reuse."""
    data = read_json(root / PRIVATE / "licence_inventory.json")
    return {row["source_id"]: row for row in data["sources"]}


def licence_label(source_id: str, licences: dict[str, dict]) -> str:
    """Summarize a source's recorded licence and conservative redistribution status."""
    row = licences.get(source_id, {})
    return f"{row.get('licence_identifier') or 'unverified'}; " \
           f"redistribution {row.get('redistributable_for_public_repository', 'unclear')}"


def file_source_ids(findings: list[dict]) -> list[str]:
    """Collect explicit source attribution and source-span identifiers."""
    ids = set()
    for finding in findings:
        if finding.get("source_id"):
            ids.add(finding["source_id"])
        else:
            ids.update(row["source_id"] for row in finding["references"])
    return sorted(ids)


def index_differences(root: Path, index: SourceIndex, snapshot: dict) -> list[dict]:
    """Audit staged bytes separately where they differ from the working copy."""
    rows = []
    for row in snapshot["files"]:
        if row["sha256"] == row["index_sha256"]:
            continue
        path = root / PRIVATE / "index_originals" / row["path"]
        findings = inspect_file(path, index)
        rows.append({"path": row["path"], "before_index_sha256": row["index_sha256"],
                     "source_field_count": len(findings),
                     "findings": [public_finding(finding) for finding in findings]})
    return rows


def publish(root: Path) -> dict:
    """Create public references and an exhaustive tracked docs/results audit."""
    snapshot = read_json(root / PRIVATE / "snapshot.json")
    index = SourceIndex(root)
    licences = licence_map(root)
    original_rows = {row["path"]: row for row in snapshot["files"]}
    rows = []
    for name in tracked_paths(root):
        if name not in original_rows:
            continue
        findings = inspect_file(root / name, index)
        sources = file_source_ids(findings)
        original = original_rows[name]
        row = {"path": name, "source_ids": sources, "before_bytes": original["bytes"],
               "before_sha256": original["sha256"], "after_bytes": original["bytes"],
               "after_sha256": original["sha256"],
               "source_bearing_words_before": sum(item["source_words"] for item in findings),
               "source_bearing_bytes_before": sum(item["source_bytes"] for item in findings),
               "source_bearing_words_after": 0, "redacted_fields": 0,
               "action": "no_retrieved_source_prose_found", "licences": {
                   source: licence_label(source, licences) for source in sources}}
        if findings and name.startswith(("docs/", "results/")):
            row.update(redact_file(root, name, findings))
            if name.endswith(".json"):
                row.pop("redactions")
        elif findings:
            if any(len(finding["text"].split()) > 15 or not finding["source_id"]
                   for finding in findings):
                raise ValueError(f"unresolved_nonartifact_source_quote:{name}")
            row.update({"action": "retained_attributed_quotes_within_15_words",
                        "retained_quotes": len(findings),
                        "maximum_quote_words": max(len(item["text"].split()) for item in findings),
                        "source_bearing_words_after": row["source_bearing_words_before"]})
        rows.append(row)
    private_sources = {block.path: block.file_sha256 for block in index.blocks}
    licence_inventory = read_json(root / PRIVATE / "licence_inventory.json")
    public_licences = {key: value for key, value in licence_inventory.items() if key != "sources"}
    public_licences["sources"] = [{key: value for key, value in row.items()
                                   if key not in {"represented_public_files"}}
                                  for row in licence_inventory["sources"]]
    write_json(root / PUBLIC / "licences.json", public_licences)
    report = {
        "audited_at": timestamp(), "scope": "Every file in the initial index, including every "
        "tracked or staged docs/ and results/ file; working and differing index bytes audited.",
        "quotation_policy": "Source-bearing prose and table strings in docs/results are removed "
        "entirely. Attributed quotations elsewhere have at most 15 whitespace-delimited words. "
        "Bibliographic titles, author lists, identifiers, derived findings and invented synthetic "
        "test strings are separate from retrieved paper prose.",
        "volume_definition": "Duplicate-inclusive words and UTF-8 bytes in source-bearing fields. "
        "Raw request totals count cached block bodies only. Model quotes may contain copying "
        "errors. This is a carriage inventory, not a count of unique paper words.",
        "private_originals": str(PRIVATE / "originals"),
        "private_index_originals": str(PRIVATE / "index_originals"),
        "full_text_policy": "Full text is retained locally and is not redistributed.",
        "private_original_count": len(snapshot["files"]), "source_blocks_checked": len(index.blocks),
        "files": rows, "differing_index_bytes": index_differences(root, index, snapshot),
        "moved_out_of_tracking": [],
        "existing_private_source_checks": [{"path": path, "sha256": expected,
            "unchanged": sha256((root / path).read_bytes()) == expected}
            for path, expected in sorted(private_sources.items())],
        "history_scope": "Current index and working files only. Historical Git blobs are not "
        "rewritten; earlier committed quotations require separate history review before release.",
    }
    write_json(root / PUBLIC / "audit.json", report)
    write_audit_markdown(root, report)
    return {"status": "projected", "audited_files": len(rows), "changed_files": [
        row["path"] for row in rows if row["redacted_fields"]],
        "retained_short_quote_files": [row["path"] for row in rows if row.get("retained_quotes")],
        "output": str(PUBLIC / "audit.md")}


def write_audit_markdown(root: Path, report: dict) -> None:
    """Write every audited docs/results file and all other source-bearing files."""
    lines = ["# Publication source-text audit", "", report["scope"], "",
             report["quotation_policy"], "", report["volume_definition"], "",
             "The [JSON audit](audit.json) records exact before/after hashes, byte counts and "
             "private locators. The [licence inventory](licences.json) records all represented "
             "sources, including metadata-only mentions, with evidence URLs and uncertainty.", "",
             "Saverschek 2010 (Animal Behaviour, Elsevier) has an all-rights-reserved publisher "
             "notice and no recorded redistribution permission. Its full text remains private.", "",
             "| File | Source | Licence / redistribution | Source words before → after | File bytes "
             "before → after | Action |", "| --- | --- | --- | --- | --- | --- |"]
    for row in report["files"]:
        if (not row["path"].startswith(("docs/", "results/")) and not row["source_ids"]
                and row["before_sha256"] == row["after_sha256"]):
            continue
        sources = ", ".join(row["source_ids"]) or "None (derived results or metadata)"
        labels = "; ".join(f"{source}: {label}" for source, label in row["licences"].items()) or "N/A"
        represented = row.get("represented_sources", [])
        if represented and not row["source_ids"]:
            sources = f"{len(represented)} cited sources; no verbatim prose (IDs in JSON)"
            labels = "Source-specific licence status in JSON audit and licence inventory"
        action = row["action"].replace("_", " ")
        lines.append(f"| `{row['path']}` | {sources} | {labels} | "
                     f"{row['source_bearing_words_before']} → {row['source_bearing_words_after']} | "
                     f"{row['before_bytes']} → {row['after_bytes']} | {action} |")
    lines += ["", "All affected source-bearing originals retain their exact pre-edit bytes under "
              "`data/interim/publication_safety/originals/`; initial index copies are preserved "
              "separately under `index_originals/`. Both are ignored. No files were moved out of "
              "tracking; public paths now contain references.", "", report["history_scope"], "",
              "Full text is retained locally and is not redistributed. Local replay uses the "
              "private mirror described in [the publication guide](../../docs/publication_safety.md).", ""]
    if report.get("new_publication_files"):
        lines += ["## Added publication files", "",
                  "These files had no pre-cleanup counterpart. Hashes and sizes are in the JSON "
                  "audit; the audit's own two files are excluded from self-hashing. The final "
                  "source-text check includes these files.", "",
                  "| File | Source | Licence / redistribution | Source words before → after | "
                  "File bytes before → after | Action |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for row in report["new_publication_files"]:
            size = row["after_bytes"] if row["after_bytes"] is not None else "self-size excluded"
            lines.append(f"| `{row['path']}` | Publication metadata, references or synthetic "
                         f"fixtures | Source-specific status in licence inventory; no paper prose "
                         f"| 0 → 0 | 0 → {size} | Added publication-safety file |")
        lines.append("")
    (root / PUBLIC / "audit.md").write_text("\n".join(lines))


def refresh_audit(root: Path) -> dict:
    """Update before/after packaging metadata without changing scientific audit evidence."""
    path = root / PUBLIC / "audit.json"
    report = read_json(path)
    licences = licence_map(root)
    represented: dict[str, list[dict]] = {}
    for source_id, licence in licences.items():
        for name in licence.get("represented_public_files", []):
            represented.setdefault(name, []).append({"source_id": source_id,
                "licence": licence_label(source_id, licences),
                "licence_url": licence.get("licence_url"),
                "flag_not_clearly_redistributable": licence["flag_not_clearly_redistributable"]})
    original_names = {row["path"] for row in report["files"]}
    for row in report["files"]:
        current = (root / row["path"]).read_bytes()
        row["after_bytes"] = len(current)
        row["after_sha256"] = sha256(current)
        row["represented_sources"] = represented.get(row["path"], [])
        if not row["redacted_fields"] and row["before_sha256"] != row["after_sha256"]:
            row["action"] = "publication_notice_or_pitch_updated_source_prose_unchanged"
    own_reports = {str(PUBLIC / "audit.json"), str(PUBLIC / "audit.md")}
    report["new_publication_files"] = [{"path": name, "before_bytes": 0,
        "after_bytes": None if name in own_reports else (root / name).stat().st_size,
        "after_sha256": None if name in own_reports else sha256((root / name).read_bytes()),
        "self_hash_excluded": name in own_reports}
        for name in tracked_paths(root) if name not in original_names]
    report["packaging_refreshed_at"] = timestamp()
    report["licence_source_count"] = len(licences)
    write_json(path, report)
    write_audit_markdown(root, report)
    return {"status": "refreshed", "original_files": len(report["files"]),
            "new_files": len(report["new_publication_files"])}
