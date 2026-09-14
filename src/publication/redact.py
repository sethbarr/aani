"""Project private source-bearing artifacts into public references."""

import json
import os
from pathlib import Path

from src.common.io import read_json, write_json
from src.publication.audit import inspect_file
from src.publication.source_index import SourceIndex, sha256

PRIVATE = Path("data/interim/publication_safety")
NOTICE = "Full text is retained locally and is not redistributed. Source fields are private " \
         "references; scientific counts and decisions retain their original values. Historical " \
         "artifact hashes identify the byte-exact private originals."


def skip_space(text: str, offset: int) -> int:
    """Advance past JSON whitespace without changing byte coordinates."""
    while offset < len(text) and text[offset].isspace():
        offset += 1
    return offset


def value_offsets(text: str, offset: int, path: tuple, output: dict) -> int:
    """Collect exact character ranges for every JSON value recursively."""
    offset = skip_space(text, offset)
    start = offset
    decoder = json.JSONDecoder()
    if text[offset] == "{":
        offset = skip_space(text, offset + 1)
        while text[offset] != "}":
            key, offset = decoder.raw_decode(text, offset)
            offset = skip_space(text, offset)
            if text[offset] != ":":
                raise ValueError("invalid_json_member")
            offset = value_offsets(text, offset + 1, (*path, key), output)
            offset = skip_space(text, offset)
            if text[offset] == ",":
                offset = skip_space(text, offset + 1)
            elif text[offset] != "}":
                raise ValueError("invalid_json_object")
        offset += 1
    elif text[offset] == "[":
        offset = skip_space(text, offset + 1)
        position = 0
        while text[offset] != "]":
            offset = value_offsets(text, offset, (*path, position), output)
            position += 1
            offset = skip_space(text, offset)
            if text[offset] == ",":
                offset = skip_space(text, offset + 1)
            elif text[offset] != "]":
                raise ValueError("invalid_json_array")
        offset += 1
    else:
        _, offset = decoder.raw_decode(text, offset)
    output[path] = (start, offset)
    return offset


def private_reference(name: str, raw: bytes, text: str, finding: dict,
                      span: tuple[int, int]) -> dict:
    """Create exact private-file byte and structural references for one removed field."""
    start, end = span
    encoded = text[start:end].encode()
    sources = sorted({row["source_id"] for row in finding["references"]})
    if finding.get("source_id") and not str(finding["source_id"]).startswith("SYNTHETIC"):
        sources = [finding["source_id"]]
    return {
        "private_path": str(PRIVATE / "originals" / name),
        "private_file_sha256": sha256(raw),
        "json_path": list(finding["path"]),
        "private_utf8_byte_start": len(text[:start].encode()),
        "private_utf8_byte_end": len(text[:end].encode()),
        "encoded_span_sha256": sha256(encoded),
        "value_utf8_sha256": sha256(finding["text"].encode()),
        "source_ids": sources,
        "source_spans": finding["references"],
        "reason": finding["reason"],
    }


def set_value(document: object, path: tuple, value: object) -> None:
    """Replace one existing JSON leaf without modifying adjacent values."""
    target = document
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value


def merge_ranges(matches: list[dict]) -> list[tuple[int, int]]:
    """Merge overlapping copied-text ranges before replacing them."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted((row["start"], row["end"]) for row in matches):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def replace_overlaps(text: str, matches: list[dict], reference_id: str) -> str:
    """Replace copied prose while preserving the surrounding authored explanation."""
    for start, end in reversed(merge_ranges(matches)):
        text = text[:start] + f"[Private source reference {reference_id}]" + text[end:]
    return text


def redact_file(root: Path, name: str, findings: list[dict]) -> dict:
    """Replace paper passages with references, preserving the original snapshot."""
    path = root / name
    original = root / PRIVATE / "originals" / name
    current = path.read_bytes()
    raw = original.read_bytes()
    if current != raw:
        audit = read_json(root / "results/publication_safety/audit.json")
        previous = [row for row in audit["files"] if row["path"] == name]
        if len(previous) != 1 or sha256(current) != previous[0]["after_sha256"]:
            raise ValueError(f"public_file_changed_since_snapshot:{name}")
    text = raw.decode()
    references = []
    offsets: dict[tuple, tuple[int, int]] = {}
    if path.suffix == ".json":
        value_offsets(text, 0, (), offsets)
        document = json.loads(text)
        for number, finding in enumerate(findings):
            reference_id = f"r{number:05d}"
            reference = private_reference(name, raw, text, finding, offsets[finding["path"]])
            references.append({"reference_id": reference_id, **reference})
            value = {"private_reference": reference_id} if finding["whole_field"] else \
                replace_overlaps(finding["text"], finding["matches"], reference_id)
            set_value(document, finding["path"], value)
        document["publication"] = {"notice": NOTICE, "private_original": str(
            PRIVATE / "originals" / name), "original_sha256": sha256(raw),
            "retained_source_quotations": 0, "redactions": references}
        write_json(path, document)
    elif path.suffix == ".md":
        for number, finding in enumerate(findings):
            reference_id = f"r{number:05d}"
            for start, end in merge_ranges(finding["matches"]):
                span_finding = {**finding, "text": text[start:end]}
                reference = private_reference(name, raw, text, span_finding, (start, end))
                references.append({"reference_id": reference_id, **reference})
            text = replace_overlaps(text, finding["matches"], reference_id)
        notice = "\n\n## Publication source references\n\n" + NOTICE + "\n\n"
        audit_path = os.path.relpath(root / "results/publication_safety/audit.json", path.parent)
        notice += f"Full-text locators for this file are in [the publication audit]({audit_path}).\n"
        path.write_text(text.rstrip() + notice)
    else:
        raise ValueError(f"unsupported_source_redaction_format:{name}")
    return {"path": name, "action": "source_text_replaced_with_private_references",
            "before_bytes": len(raw), "after_bytes": path.stat().st_size,
            "before_sha256": sha256(raw), "after_sha256": sha256(path.read_bytes()),
            "source_bearing_words_before": sum(row["source_words"] for row in findings),
            "source_bearing_bytes_before": sum(row["source_bytes"] for row in findings),
            "source_bearing_words_after": 0, "redacted_fields": len(findings),
            "source_ids": sorted({source for row in references for source in row["source_ids"]}),
            "private_original": str(PRIVATE / "originals" / name),
            "redactions": references}


def sanitize(root: Path, names: list[str], index: SourceIndex) -> list[dict]:
    """Apply the publication-only policy to reviewed artifact paths."""
    snapshot = read_json(root / PRIVATE / "snapshot.json")
    original_names = {row["path"] for row in snapshot["files"]}
    changed = []
    for name in names:
        findings = inspect_file(root / name, index)
        if not findings:
            continue
        if name not in original_names:
            raise ValueError(f"private_snapshot_missing:{name}")
        if not name.startswith(("docs/", "results/")):
            violations = [row for row in findings if len(row["text"].split()) > 15]
            if violations:
                raise ValueError(f"outside_artifact_quote_requires_review:{name}")
            continue
        changed.append(redact_file(root, name, findings))
    return changed
