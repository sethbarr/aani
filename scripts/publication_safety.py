"""Audit and sanitize public evidence while preserving private originals."""

import argparse
import json
import subprocess
from pathlib import Path

from src.common.io import timestamp, write_json
from src.publication.audit import inspect_file, public_finding, tracked_paths
from src.publication.source_index import SourceIndex, sha256

PRIVATE = Path("data/interim/publication_safety")


def capture(root: Path) -> dict:
    """Preserve current and index bytes once before publication edits."""
    destination = root / PRIVATE
    manifest = destination / "snapshot.json"
    if manifest.exists():
        raise ValueError("publication_snapshot_already_exists")
    files = []
    for name in tracked_paths(root):
        path = root / name
        if not path.is_file():
            raise ValueError(f"tracked_file_missing:{name}")
        raw = path.read_bytes()
        indexed = subprocess.check_output(["git", "show", ":" + name], cwd=root)
        for folder, content in (("originals", raw), ("index_originals", indexed)):
            target = destination / folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        files.append({"path": name, "sha256": sha256(raw), "bytes": len(raw),
                      "index_sha256": sha256(indexed), "index_bytes": len(indexed)})
    report = {"captured_at": timestamp(), "files": files,
              "git_status_before": subprocess.check_output(
                  ["git", "status", "--short"], cwd=root).decode()}
    write_json(manifest, report)
    return {"status": "captured", "files": len(files), "path": str(manifest)}


def audit(root: Path) -> dict:
    """Inventory source text across every indexed file using the local corpus."""
    index = SourceIndex(root)
    rows = []
    for name in tracked_paths(root):
        path = root / name
        try:
            findings = inspect_file(path, index)
        except UnicodeDecodeError:
            rows.append({"path": name, "status": "binary_requires_review"})
            continue
        rows.append({"path": name, "status": "source_text_found" if findings else "clear",
                     "file_bytes": path.stat().st_size,
                     "source_field_count": len(findings),
                     "source_bearing_words": sum(row["source_words"] for row in findings),
                     "source_bearing_bytes": sum(row["source_bytes"] for row in findings),
                     "source_ids": sorted({ref["source_id"] for row in findings
                                           for ref in row["references"]}),
                     "findings": [public_finding(row) for row in findings]})
    report = {"audited_at": timestamp(), "files": rows, "source_blocks": len(index.blocks),
              "source_ids": sorted({row.source_id for row in index.blocks}),
              "source_files": [{"path": path, "sha256": digest} for path, digest in sorted(
                  {(block.path, block.file_sha256) for block in index.blocks})],
              "volume_definition": "Duplicate-inclusive source-bearing field words and UTF-8 bytes; "
                                   "request-input totals count cached block bodies only. "
                                   "Model quotations can include substitutions or stitched text."}
    write_json(root / PRIVATE / "audit_before.json", report)
    return {"files": len(rows), "source_blocks": len(index.blocks), "findings": [
        {key: value for key, value in row.items() if key != "findings"}
        for row in rows if row["status"] != "clear"]}


def main() -> None:
    """Run one explicitly selected publication operation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["capture", "audit", "publish", "replay", "verify",
                                             "test", "refresh-audit"])
    args = parser.parse_args()
    root = Path.cwd()
    if args.command == "capture":
        result = capture(root)
    elif args.command == "audit":
        result = audit(root)
    elif args.command == "publish":
        from src.publication.report import publish

        result = publish(root)
    elif args.command == "replay":
        from src.publication.replay import verify

        result = verify(root)
        write_json(root / "results/publication_safety/replay_verification.json", result)
        result = {key: result.get(key) for key in ("status", "blocked_reason")}
    elif args.command == "verify":
        from src.publication.verify import verify_public

        result = verify_public(root)
        write_json(root / "results/publication_safety/verification.json", result)
        result = {key: result.get(key) for key in ("status", "blocked_reason")}
    elif args.command == "test":
        from src.publication.replay import run_tests

        result = run_tests(root)
        write_json(root / "results/publication_safety/test_verification.json", result)
        result = {key: result.get(key) for key in ("status", "blocked_reason", "counts")}
    else:
        from src.publication.report import refresh_audit

        result = refresh_audit(root)
    print(json.dumps(result, indent=2))
    if result.get("status") in {"failed", "blocked"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
