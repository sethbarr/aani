"""Exercise source-level identity resolution without model requests or taxonomy guesses."""

from pathlib import Path

import pytest

from src.common.io import digest, read_json, read_jsonl
from src.extraction.ant_identity import resolve_source_ant_identity


def document_with_text(text: str) -> dict:
    """Build one complete cached source with a stable block identifier."""
    return {
        "source_id": "SOURCE",
        "blocks": [{"block_id": "b0", "section": "Introduction", "text": text}],
    }


def test_first_full_binomial_has_exact_anchor_and_source_hash() -> None:
    """Preserve the printed whitespace while returning canonical scientific names."""
    paper = {"source_id": "SOURCE"}
    document = document_with_text("Keywords: (Atta\ncolombica), learning.")
    identity = resolve_source_ant_identity(paper, document)
    assert identity["status"] == "resolved"
    assert identity["scientific_name"] == "Atta colombica"
    assert identity["abbreviated_forms"] == ["A. colombica", "A.colombica"]
    assert identity["source_hash"] == digest(document)
    assert identity["source_metadata_hash"] == digest(paper)
    assert identity["provenance"] == {
        "method": "first_full_binomial", "block_id": "b0", "section": "Introduction",
        "evidence_quote": "Atta\ncolombica",
    }
    assert identity["blocked_reason"] is None


def test_first_identity_precedes_later_species_mentions() -> None:
    """Keep the early source identity when later blocks mention another study's ants."""
    document = document_with_text("We studied Atta colombica.")
    document["blocks"].append({"block_id": "b1", "section": "Discussion", "text": "Atta sexdens."})
    identity = resolve_source_ant_identity({"source_id": "SOURCE"}, document)
    assert identity["scientific_name"] == "Atta colombica"
    assert identity["provenance"]["block_id"] == "b0"


@pytest.mark.parametrize("generic", [
    "Atta species", "Atta spp.", "Atta sp.", "Atta workers", "Atta ants",
    "Atta leaf-cutting ants", "A. colombica", "NotAtta colombica", "Atta Colombica",
])
def test_generic_or_abbreviated_mentions_are_unresolved(generic: str) -> None:
    """Require a full binomial and exclude generic ant descriptions."""
    identity = resolve_source_ant_identity({"source_id": "SOURCE"}, document_with_text(generic))
    assert identity["status"] == "blocked"
    assert identity["scientific_name"] is None
    assert identity["abbreviated_forms"] == []
    assert identity["blocked_reason"] == "no_full_ant_binomial_in_source"


def test_first_qualifying_block_with_two_identities_requires_review() -> None:
    """Do not guess which of two ant species is the source-level study subject."""
    document = document_with_text("Atta colombica and Acromyrmex octospinosus were compared.")
    identity = resolve_source_ant_identity({"source_id": "SOURCE"}, document)
    assert identity["status"] == "blocked"
    assert identity["blocked_reason"].startswith("ambiguous_ant_identity:first_full_binomial:")
    assert len(identity["provenance"]["candidates"]) == 2


def test_metadata_precedes_abstract_and_first_block() -> None:
    """Record explicit metadata separately from document text provenance."""
    paper = {"source_id": "SOURCE", "ant_species": "Acromyrmex octospinosus"}
    document = document_with_text("Atta sexdens was described previously.")
    document["abstract"] = "Atta colombica was observed."
    identity = resolve_source_ant_identity(paper, document)
    assert identity["scientific_name"] == "Acromyrmex octospinosus"
    assert identity["provenance"]["method"] == "metadata"
    assert identity["provenance"]["metadata_field"] == "paper.ant_species"
    assert identity["provenance"]["block_id"] is None


def test_matching_nested_metadata_has_corroboration() -> None:
    """Record agreement between the corpus and cached document metadata."""
    paper = {"source_id": "SOURCE", "metadata": {"ant_species": "Atta colombica"}}
    document = document_with_text("A. colombica")
    document["metadata"] = {"ant_species": "Atta colombica"}
    identity = resolve_source_ant_identity(paper, document)
    assert identity["status"] == "resolved"
    assert len(identity["provenance"]["corroborating_anchors"]) == 1


def test_conflicting_metadata_is_blocked() -> None:
    """Expose contradictory explicit source identity fields."""
    paper = {"source_id": "SOURCE", "ant_species": "Atta colombica"}
    document = document_with_text("Atta colombica.")
    document["ant_species"] = "Atta sexdens"
    identity = resolve_source_ant_identity(paper, document)
    assert identity["status"] == "blocked"
    assert identity["blocked_reason"].startswith("ambiguous_ant_identity:metadata:")


@pytest.mark.parametrize("value", ["A. colombica", "Atta species", ["Atta colombica"], 12])
def test_malformed_explicit_metadata_requires_review(value: object) -> None:
    """Do not silently replace malformed explicit metadata with a text inference."""
    identity = resolve_source_ant_identity(
        {"source_id": "SOURCE", "ant_species": value}, document_with_text("Atta colombica."),
    )
    assert identity["blocked_reason"] == "invalid_ant_identity_metadata:paper.ant_species"


def test_abstract_precedes_other_blocks() -> None:
    """Prefer a dedicated abstract over unrelated full names in earlier text."""
    document = document_with_text("Atta sexdens appears in related research.")
    document["blocks"].append({
        "block_id": "abstract", "section": "Abstract", "text": "We studied Atta colombica.",
    })
    identity = resolve_source_ant_identity({"source_id": "SOURCE"}, document)
    assert identity["scientific_name"] == "Atta colombica"
    assert identity["provenance"]["method"] == "abstract"
    assert identity["provenance"]["block_id"] == "abstract"


def test_conflicting_abstracts_are_blocked() -> None:
    """Require review when explicit abstract fields disagree on ant identity."""
    paper = {"source_id": "SOURCE", "abstract": "Atta colombica was studied."}
    document = document_with_text("Atta colombica.")
    document["abstract"] = "Atta sexdens was studied."
    identity = resolve_source_ant_identity(paper, document)
    assert identity["blocked_reason"].startswith("ambiguous_ant_identity:abstract:")


def test_override_precedes_conflicting_metadata_and_records_reason() -> None:
    """Allow a documented external override with no fabricated block attribution."""
    paper = {"source_id": "SOURCE", "ant_species": "Atta sexdens"}
    override = {"scientific_name": "Atta colombica", "reason": "Curator checked the source PDF."}
    identity = resolve_source_ant_identity(paper, document_with_text("A. colombica"), override)
    assert identity["scientific_name"] == "Atta colombica"
    assert identity["provenance"]["reason"] == override["reason"]
    assert identity["provenance"]["block_id"] is None
    assert identity["provenance"]["override_hash"] == digest(override)


def test_override_validates_supplied_block_and_quote() -> None:
    """Keep an exact block anchor when the override provides text evidence."""
    override = {
        "scientific_name": "Atta colombica", "reason": "Explicit study species.",
        "block_id": "b0", "evidence_quote": "studied Atta colombica",
    }
    identity = resolve_source_ant_identity(
        {"source_id": "SOURCE"}, document_with_text("We studied Atta colombica."), override,
    )
    assert identity["status"] == "resolved"
    assert identity["provenance"]["evidence_quote"] == override["evidence_quote"]


@pytest.mark.parametrize(("override", "reason"), [
    ({"scientific_name": "A. colombica", "reason": "Checked."}, "invalid_ant_identity_override"),
    ({"scientific_name": "Atta colombica"}, "invalid_ant_identity_override"),
    ({"scientific_name": "Atta colombica", "reason": " "}, "invalid_ant_identity_override"),
    ({"scientific_name": "Atta colombica", "reason": "Checked.", "source_id": "OTHER"},
     "override_source_id_mismatch"),
    ({"scientific_name": "Atta colombica", "reason": "Checked.", "evidence_quote": "Atta colombica"},
     "override_quote_requires_block_id"),
    ({"scientific_name": "Atta colombica", "reason": "Checked.", "block_id": "missing"},
     "override_block_not_unique"),
    ({"scientific_name": "Atta colombica", "reason": "Checked.", "block_id": "b0",
      "evidence_quote": "Atta colombica was found"}, "override_quote_not_in_block"),
    ({"scientific_name": "Atta colombica", "reason": "Checked.", "block_id": "b0",
      "evidence_quote": "We studied"}, "override_name_not_in_quote"),
])
def test_malformed_overrides_are_blocked(override: dict, reason: str) -> None:
    """Report invalid override identities, source links and quotations explicitly."""
    identity = resolve_source_ant_identity(
        {"source_id": "SOURCE"}, document_with_text("We studied Atta colombica."), override,
    )
    assert identity["status"] == "blocked"
    assert identity["blocked_reason"] == reason


def test_malformed_document_is_blocked() -> None:
    """Keep a source with missing text anchors explicitly unscorable."""
    identity = resolve_source_ant_identity(
        {"source_id": "SOURCE"}, {"source_id": "SOURCE", "blocks": [{}]},
    )
    assert identity["blocked_reason"] == "malformed_source_blocks"


def test_saverschek_resolves_from_first_page_keywords() -> None:
    """Resolve the actual cached paper before its three extraction jobs are split."""
    corpus = Path("data/interim/corpus_targeted_saverschek")
    paper = read_jsonl(corpus / "manifest.jsonl")[0]
    document = read_json(corpus / "texts/SAVERSCHEK2010.json")
    identity = resolve_source_ant_identity(paper, document)
    assert identity["scientific_name"] == "Atta colombica"
    assert identity["provenance"]["method"] == "first_full_binomial"
    assert identity["provenance"]["block_id"] == "b00000"
    assert identity["provenance"]["evidence_quote"] == "Atta colombica"
