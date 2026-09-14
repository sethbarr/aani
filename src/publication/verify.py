"""Check public source limits, private span references, and publication links."""

import json
import subprocess
import tempfile
from pathlib import Path

from src.common.io import read_json, timestamp
from src.publication.audit import inspect_file, tracked_paths
from src.publication.redact import PRIVATE
from src.publication.replay import frozen_protocol_checks, private_snapshot_checks
from src.publication.source_index import SourceIndex, sha256


def value_at(document: object, path: tuple | list) -> object:
    """Resolve an existing structural path in a JSON artifact."""
    value = document
    for part in path:
        value = value[part]
    return value


def count_checks(root: Path, name: str, document: dict, ledger: list[dict]) -> list[dict]:
    """Require all original non-source values to remain unchanged after projection."""
    private = read_json(root / PRIVATE / "originals" / name)
    redacted = {tuple(row["json_path"]) for row in ledger}
    checks = []
    stack = [((), private)]
    while stack:
        path, original = stack.pop()
        if path in redacted:
            continue
        if isinstance(original, dict):
            stack.extend(((*path, key), value) for key, value in original.items())
        elif isinstance(original, list):
            stack.extend(((*path, index), value) for index, value in enumerate(original))
        else:
            checks.append({"path": list(path), "identical": value_at(document, path) == original})
    return checks


def reference_checks(root: Path, name: str, ledger: list[dict]) -> list[dict]:
    """Resolve each private byte interval and every asserted cached source span."""
    files: dict[str, bytes] = {}
    blocks: dict[str, dict] = {}
    checks = []
    for row in ledger:
        path = row["private_path"]
        if path not in files:
            files[path] = (root / path).read_bytes()
        raw = files[path]
        span = raw[row["private_utf8_byte_start"]:row["private_utf8_byte_end"]]
        passed = (sha256(raw) == row["private_file_sha256"]
                  and sha256(span) == row["encoded_span_sha256"])
        if name.endswith(".json"):
            decoded = json.loads(span)
            passed = passed and sha256(decoded.encode()) == row["value_utf8_sha256"]
        for reference in row["source_spans"]:
            source_path = reference["private_source_path"]
            if source_path not in files:
                files[source_path] = (root / source_path).read_bytes()
                blocks[source_path] = {block["block_id"]: block["text"] for block in
                                       json.loads(files[source_path])["blocks"]}
            block = blocks[source_path][reference["block_id"]].encode()
            source_span = block[reference["block_utf8_byte_start"]:
                                reference["block_utf8_byte_end"]]
            passed = passed and all((
                sha256(files[source_path]) == reference["source_file_sha256"],
                sha256(block) == reference["block_text_sha256"],
                sha256(source_span) == reference["span_sha256"],
            ))
        checks.append({"file": name, "reference_id": row["reference_id"], "resolved": passed})
    return checks


def local_links(root: Path, name: str, tracked: set[str]) -> list[dict]:
    """Resolve inline and reference-style local Markdown file links."""
    path = root / name
    targets = []
    for line in path.read_text().splitlines():
        for segment in line.split("](")[1:]:
            targets.append(segment.split(")", 1)[0].strip("<>"))
        if line.startswith("[") and "]:" in line:
            targets.append(line.split("]:", 1)[1].strip().strip("<>"))
    checks = []
    for target in sorted(set(targets)):
        if "://" in target or target.startswith("mailto:"):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        destination = (path.parent / target).resolve()
        try:
            relative = str(destination.relative_to(root))
        except ValueError:
            relative = str(destination)
        checks.append({"document": name, "target": target, "resolved_path": relative,
                       "exists": destination.is_file(), "tracked": relative in tracked})
    return checks


def private_ignore_checks(root: Path, tracked: set[str]) -> list[dict]:
    """Check private paths stay ignored and absent from the index."""
    checks = []
    for name in (".env", ".venv", "data/raw", "data/interim", "research", ".DS_Store"):
        ignored = subprocess.run(["git", "check-ignore", "-q", name], cwd=root,
                                 check=False).returncode == 0
        matching = [path for path in tracked if path == name or path.startswith(name + "/")
                    or (name == ".DS_Store" and Path(path).name == name)]
        checks.append({"path": name, "ignored": ignored, "tracked_files": matching})
    return checks


def staged_source_checks(root: Path, tracked: set[str], index: SourceIndex) -> list[dict]:
    """Inspect distinct staged bytes so working-copy cleanup cannot mask index disclosure."""
    checks = []
    with tempfile.TemporaryDirectory(prefix="aani-index-audit-") as temporary:
        directory = Path(temporary)
        for name in sorted(tracked):
            staged = subprocess.check_output(["git", "show", ":" + name], cwd=root)
            working = (root / name).read_bytes()
            if staged == working:
                continue
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(staged)
            findings = inspect_file(path, index)
            violations = [{"json_path": list(row["path"]), "words": len(row["text"].split())}
                          for row in findings if len(row["text"].split()) > 15
                          or not row["source_id"]]
            checks.append({"path": name, "index_sha256": sha256(staged),
                           "working_sha256": sha256(working), "source_violations": violations})
    return checks


def verify_public(root: Path) -> dict:
    """Audit current tracked files and verify every source-redaction locator."""
    root = root.resolve()
    tracked = set(tracked_paths(root))
    index = SourceIndex(root)
    violations = []
    retained = []
    projections = []
    for name in sorted(tracked):
        path = root / name
        try:
            findings = inspect_file(path, index)
        except UnicodeDecodeError:
            violations.append({"path": name, "reason": "unreviewed_binary"})
            continue
        for finding in findings:
            count = len(finding["text"].split())
            row = {"path": name, "json_path": list(finding["path"]),
                   "words": count, "source_id": finding["source_id"]}
            if count > 15 or not finding["source_id"]:
                violations.append(row)
            else:
                retained.append(row)
        if name.endswith(".json"):
            document = read_json(path)
            if isinstance(document, dict) and "publication" in document:
                ledger = document["publication"]["redactions"]
                values = count_checks(root, name, document, ledger)
                references = reference_checks(root, name, ledger)
                projections.append({"file": name, "source_fields_replaced": len(ledger),
                                    "non_source_values_checked": len(values),
                                    "non_source_values_unchanged": all(row["identical"] for row in values),
                                    "private_references_resolved": all(row["resolved"] for row in references)})
    audit = read_json(root / "results/publication_safety/audit.json")
    markdown_refs = [check for row in audit["files"] if row.get("redactions")
                     for check in reference_checks(root, row["path"], row["redactions"])]
    links = []
    for name in ("README.md", "results/business_case/judges_submission_v2.md"):
        links.extend(local_links(root, name, tracked))
    ignores = private_ignore_checks(root, tracked)
    originals = private_snapshot_checks(root, root / PRIVATE)
    frozen = frozen_protocol_checks(root)
    staged = staged_source_checks(root, tracked, index)
    passed = all((not violations,
        all(row["non_source_values_unchanged"] and row["private_references_resolved"]
            for row in projections), all(row["resolved"] for row in markdown_refs),
        all(row["exists"] and row["tracked"] for row in links),
        all(row["ignored"] and not row["tracked_files"] for row in ignores),
        all(row["unchanged"] for row in originals + frozen),
        all(not row["source_violations"] for row in staged)))
    return {"verified_at": timestamp(), "status": "passed" if passed else "failed",
            "blocked_reason": None if passed else "publication_safety_checks_failed",
            "scope": "Current indexed paths and their working bytes; Git history is separate.",
            "tracked_files_checked": len(tracked), "source_blocks_checked": len(index.blocks),
            "source_prose_violations": violations, "retained_attributed_quotes": retained,
            "maximum_retained_quote_words": max((row["words"] for row in retained), default=0),
            "projections": projections, "markdown_references": markdown_refs,
            "local_file_links": links, "private_ignore_checks": ignores,
            "distinct_staged_byte_checks": staged,
            "private_original_count": len(originals),
            "private_originals_unchanged": all(row["unchanged"] for row in originals),
            "frozen_files": frozen, "model_requests": 0,
            "history_rewritten": False, "full_text_policy": "Full text is retained locally "
            "and is not redistributed in current public projections."}
