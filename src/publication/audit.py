"""Inspect tracked artifacts for paper prose and encoded source payloads."""

import json
import subprocess
from pathlib import Path

from src.publication.source_index import SourceIndex

SOURCE_FIELDS = {
    "quote", "evidence_quote", "emitted_quote", "matched_source_quote", "source_text",
    "raw_model_quote", "raw_cached_quote", "literal_prefix", "literal_suffix", "utf8_text",
    "excerpt", "source_excerpt", "text", "block_text", "raw_text", "caption", "table_text",
    "left_fragment", "right_fragment", "joined_display",
}
BIBLIOGRAPHIC_FIELDS = {"title", "source_title", "article_title", "citation", "doi", "url",
                        "source_url", "public_full_text_lead", "author_string", "authors"}


def tracked_paths(root: Path) -> list[str]:
    """Return the current index inventory, including staged additions."""
    data = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    return sorted(path for path in data.decode().split("\0") if path)


def source_context(value: dict, inherited: str | None) -> str | None:
    """Carry an explicit source identifier into nested evidence fields."""
    if "synthetic" in str(value.get("exercise_type", "")).lower():
        return "SYNTHETIC_GENERATED"
    for key in ("source_id", "source_pmcid", "pmcid"):
        if isinstance(value.get(key), str):
            return value[key]
    return inherited


def leaves(value: object, path: tuple = (), source: str | None = None) -> list[dict]:
    """Return string leaves with structural pointers and inherited source IDs."""
    result = []
    if isinstance(value, dict):
        source = source_context(value, source)
        for key, child in value.items():
            result.extend(leaves(child, (*path, key), source))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(leaves(child, (*path, index), source))
    elif isinstance(value, str):
        result.append({"path": path, "text": value, "source_id": source})
    return result


def payload_sources(text: str, index: SourceIndex) -> list[dict]:
    """Find full source blocks inside a JSON-encoded request input."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
    found = []
    for leaf in leaves(parsed):
        if leaf["path"] and leaf["path"][-1] == "text":
            found.extend(index.exact_references(leaf["text"], leaf["source_id"]))
    return found


def inspect_leaf(leaf: dict, index: SourceIndex) -> dict | None:
    """Classify source-bearing fields without treating findings as quotations."""
    text = leaf["text"]
    key = str(leaf["path"][-1]) if leaf["path"] else ""
    if key in BIBLIOGRAPHIC_FIELDS or not text:
        return None
    if key == "input":
        references = payload_sources(text, index)
        if references:
            return {**leaf, "reason": "encoded_request_contains_source_blocks",
                    "references": references, "whole_field": True,
                    "source_words": sum(row["source_words"] for row in references),
                    "source_bytes": sum(row["block_utf8_byte_end"] - row["block_utf8_byte_start"]
                                        for row in references)}
    explicit = key in SOURCE_FIELDS or key.endswith("_evidence_quote")
    hexadecimal = key == "hex" and len(text) > 4
    if str(leaf["source_id"]).startswith("SYNTHETIC"):
        return None
    if explicit or hexadecimal:
        source_text = text
        if hexadecimal:
            try:
                source_text = bytes.fromhex(text).decode()
            except (ValueError, UnicodeDecodeError):
                source_text = text
        references = index.exact_references(source_text, leaf["source_id"])
        if not references:
            references = [row["reference"] for row in index.matches(source_text)]
        return {**leaf, "reason": "source_field_or_reconstruction_fragment",
                "references": references, "whole_field": True,
                "source_words": len(source_text.split()), "source_bytes": len(source_text.encode())}
    matches = [row for row in index.matches(text, minimum_words=16)
               if len(text[row["start"]:row["end"]].split()) > 15]
    if matches:
        return {**leaf, "reason": "long_source_overlap", "references": [
                    row["reference"] for row in matches], "whole_field": False,
                "matches": matches,
                "source_words": sum(len(text[row["start"]:row["end"]].split()) for row in matches),
                "source_bytes": sum(len(text[row["start"]:row["end"]].encode()) for row in matches)}
    return None


def inspect_file(path: Path, index: SourceIndex) -> list[dict]:
    """Audit JSON fields, JSON Lines and prose without emitting paper text."""
    text = path.read_text(encoding="utf-8")
    default_source = "SAVERSCHEK2010" if (
        "grounding_development_" in str(path) or path.name == "recall_baseline.json"
        or "saverschek_audit" in str(path)) else None
    if path.suffix == ".json":
        candidates = leaves(json.loads(text), source=default_source)
    elif path.suffix == ".jsonl":
        candidates = []
        for number, line in enumerate(text.splitlines()):
            if line.strip():
                candidates.extend(leaves(json.loads(line), (number,)))
    else:
        candidates = [{"path": (), "text": text, "source_id": None}]
    findings = []
    for leaf in candidates:
        finding = inspect_leaf(leaf, index)
        if finding:
            findings.append(finding)
    return findings


def public_finding(finding: dict) -> dict:
    """Keep audit counts and locators while withholding the inspected prose."""
    return {key: value for key, value in finding.items()
            if key not in {"text", "matches"}}
