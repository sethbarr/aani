"""Tests for source-text auditing and byte-exact public references."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.publication.audit import inspect_file, inspect_leaf, leaves
from src.publication.redact import PRIVATE, redact_file, value_offsets
from src.publication.source_index import SourceIndex, sha256
from src.publication.verify import count_checks, local_links


def make_index(tmp_path: Path) -> SourceIndex:
    """Create a private corpus containing invented test prose."""
    path = tmp_path / "data/interim/corpus/texts/example.json"
    path.parent.mkdir(parents=True)
    source = {"source_id": "TEST_SOURCE", "blocks": [{"block_id": "b1", "kind": "paragraph",
        "text": "One two three four five six seven eight nine ten eleven twelve thirteen "
                "fourteen fifteen sixteen seventeen eighteen nineteen twenty ± ¼"}]}
    path.write_text(json.dumps(source, ensure_ascii=False))
    return SourceIndex(tmp_path)


def test_offsets_follow_duplicate_values_and_unicode() -> None:
    """Each JSON path identifies its actual occurrence even with duplicate quotes."""
    raw = '{"first": "± word", "next": ["± word", "last"]}'
    spans = {}
    value_offsets(raw, 0, (), spans)
    assert raw[slice(*spans[("first",)])] == '"± word"'
    assert raw[slice(*spans[("next", 0)])] == '"± word"'
    assert spans[("first",)] != spans[("next", 0)]


def test_encoded_input_exposes_only_block_references(tmp_path: Path) -> None:
    """JSON-encoded requests are inspected beyond their outer string wrapper."""
    index = make_index(tmp_path)
    payload = {"source_id": "TEST_SOURCE", "blocks": [{"text": index.blocks[0].text}]}
    finding = inspect_leaf({"path": ("input",), "text": json.dumps(payload),
                            "source_id": None}, index)
    assert finding["reason"] == "encoded_request_contains_source_blocks"
    assert finding["source_words"] == 22
    assert finding["references"][0]["block_id"] == "b1"


def test_short_table_fragment_and_hex_are_removed(tmp_path: Path) -> None:
    """Short reconstruction fragments receive the same private-only treatment."""
    index = make_index(tmp_path)
    for key, text in (("literal_prefix", "one two"), ("hex", "6f6e652074776f")):
        assert inspect_leaf({"path": (key,), "text": text, "source_id": "TEST_SOURCE"}, index)


def test_synthetic_examples_are_identified(tmp_path: Path) -> None:
    """Invented adversarial cases are distinct from retrieved paper quotations."""
    index = make_index(tmp_path)
    leaf = leaves({"exercise_type": "synthetic algorithm check", "quote": "synthetic text"})[-1]
    assert inspect_leaf(leaf, index) is None


def test_long_prose_detected_and_metadata_preserved(tmp_path: Path) -> None:
    """Body prose above the quotation limit is detected; citation metadata is excluded."""
    index = make_index(tmp_path)
    quote = index.blocks[0].text
    assert inspect_leaf({"path": ("rationale",), "text": quote, "source_id": None}, index)
    assert inspect_leaf({"path": ("title",), "text": quote, "source_id": None}, index) is None


def test_redaction_preserves_counts_and_private_bytes(tmp_path: Path) -> None:
    """Publication projection changes source fields and retains all count values."""
    index = make_index(tmp_path)
    path = tmp_path / "results/example.json"
    path.parent.mkdir()
    original = {"source_id": "TEST_SOURCE", "count": 6, "direction": "rejected",
                "quote": index.blocks[0].text}
    raw = json.dumps(original, ensure_ascii=False, indent=2).encode()
    path.write_bytes(raw)
    private = tmp_path / PRIVATE / "originals/results/example.json"
    private.parent.mkdir(parents=True)
    private.write_bytes(raw)
    findings = inspect_file(path, index)
    report = redact_file(tmp_path, "results/example.json", findings)
    result = json.loads(path.read_text())
    assert result["count"] == 6
    assert result["direction"] == "rejected"
    assert private.read_bytes() == raw
    reference = result["publication"]["redactions"][0]
    span = raw[reference["private_utf8_byte_start"]:reference["private_utf8_byte_end"]]
    assert sha256(span) == reference["encoded_span_sha256"]
    assert json.loads(span) == original["quote"]
    assert report["source_bearing_words_after"] == 0
    assert not inspect_file(path, index)


def test_markdown_redaction_has_exact_source_offset(tmp_path: Path) -> None:
    """A removed Markdown quote points to its exact private byte interval."""
    index = make_index(tmp_path)
    path = tmp_path / "docs/example.md"
    path.parent.mkdir()
    text = "# Report\n\n> " + index.blocks[0].text + "\n"
    path.write_text(text)
    original = tmp_path / PRIVATE / "originals/docs/example.md"
    original.parent.mkdir(parents=True)
    original.write_text(text)
    report = redact_file(tmp_path, "docs/example.md", inspect_file(path, index))
    reference = report["redactions"][0]
    span = text.encode()[reference["private_utf8_byte_start"]:reference["private_utf8_byte_end"]]
    assert sha256(span) == reference["encoded_span_sha256"]
    assert len(span.split()) >= 16
    assert "Full text is retained locally" in path.read_text()


def test_publication_links_require_tracking(tmp_path: Path) -> None:
    """A local file existing on disk does not satisfy the tracked-link requirement."""
    (tmp_path / "README.md").write_text("[inline](report.md)\n[reference]: report.md\n")
    (tmp_path / "report.md").write_text("Derived report")
    checks = local_links(tmp_path, "README.md", {"README.md"})
    assert checks == [{"document": "README.md", "target": "report.md",
                       "resolved_path": "report.md", "exists": True, "tracked": False}]


def test_numeric_change_cannot_hide_behind_redaction(tmp_path: Path) -> None:
    """Changing a scientific count fails comparison with the private original."""
    path = tmp_path / PRIVATE / "originals/results/example.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"count": 6, "quote": "private invented text"}))
    public = {"count": 7, "quote": {"private_reference": "r1"}}
    checks = count_checks(tmp_path, "results/example.json", public, [{"json_path": ["quote"]}])
    assert checks == [{"path": ["count"], "identical": False}]


def test_failed_verification_has_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed publication gate must fail its shell command."""
    from scripts.publication_safety import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["publication_safety", "verify"])
    monkeypatch.setattr("src.publication.verify.verify_public", Mock(return_value={
        "status": "failed", "blocked_reason": "test_failure"}))
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
