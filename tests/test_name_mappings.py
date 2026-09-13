"""Guard source-specific name expansion and immutable extraction provenance."""

from copy import deepcopy
from functools import partial
from pathlib import Path

import httpx
import pytest

from src.common.cache import CachedHTTP
from src.common.io import digest, read_jsonl, write_json
from src.taxonomy.gbif import CHECKLIST, normalise
from src.taxonomy.names import apply_name_mappings


@pytest.fixture
def mapping_document() -> dict:
    """Return a synthetic source that explicitly defines a plant alias."""
    return {
        "source_id": "paper-one",
        "blocks": [
            {
                "block_id": "b00001",
                "text": "Annual grass (Poa annua) was collected by the ants.",
            }
        ],
    }


@pytest.fixture
def mapping_corpus(tmp_path: Path, mapping_document: dict) -> Path:
    """Write the synthetic document into the corpus directory contract."""
    corpus = tmp_path / "corpus"
    write_json(corpus / "texts" / "paper-one.json", mapping_document)
    return corpus


@pytest.fixture
def mapping_observations() -> list[dict]:
    """Return an extraction record whose original genus rank must survive."""
    return [
        {
            "source_id": "paper-one",
            "plant_name_as_written": "annual grass",
            "taxonomic_rank": "genus",
            "ant_species": "Atta cephalotes",
            "outcome": "accepted",
            "evidence_quote": "Annual grass (Poa annua) was collected by the ants.",
            "record_id": "immutable-extraction-record",
            "input_hash": "original-model-input",
            "response_hash": "original-model-response",
            "semantic_review_hash": "original-review-manifest",
        }
    ]


@pytest.fixture
def mapping_manifest(mapping_document: dict) -> dict:
    """Return a reviewed species expansion anchored in the synthetic source."""
    return {
        "version": 1,
        "mappings": [
            {
                "source_id": "paper-one",
                "plant_name_as_written": "annual grass",
                "scientific_name": "Poa annua",
                "taxonomic_rank": "species",
                "source_document_hash": digest(mapping_document),
                "evidence": [
                    {
                        "block_id": "b00001",
                        "quote": "Annual grass (Poa annua)",
                    }
                ],
            }
        ],
    }


def test_mapping_preserves_original_record_and_separates_query_rank(
    mapping_corpus: Path, mapping_observations: list[dict], mapping_manifest: dict
) -> None:
    """Retain extraction identity while recording the source-supported refinement."""
    original = deepcopy(mapping_observations)
    rows = apply_name_mappings(mapping_observations, mapping_manifest, mapping_corpus)

    assert mapping_observations == original
    assert rows[0] is not mapping_observations[0]
    assert {key: rows[0][key] for key in original[0]} == original[0]
    assert rows[0]["taxonomic_rank"] == "genus"
    assert rows[0]["taxonomy_query_name"] == "Poa annua"
    assert rows[0]["taxonomy_query_rank"] == "species"
    assert rows[0]["name_resolution"] == {
        "method": "source_specific_reviewed_mapping",
        "mapping_manifest_hash": digest(mapping_manifest),
        "mapping_hash": digest(mapping_manifest["mappings"][0]),
        "mapping": mapping_manifest["mappings"][0],
    }


def test_alias_mapping_cannot_leak_to_another_source(
    mapping_corpus: Path, mapping_observations: list[dict], mapping_manifest: dict
) -> None:
    """Leave another paper's identical alias unresolved without its own evidence."""
    other_paper = {
        **mapping_observations[0],
        "source_id": "paper-two",
        "record_id": "another-extraction-record",
    }
    rows = apply_name_mappings(
        [*mapping_observations, other_paper], mapping_manifest, mapping_corpus
    )

    assert rows[0]["taxonomy_query_name"] == "Poa annua"
    assert rows[1] == other_paper
    assert rows[1] is not other_paper
    assert "name_resolution" not in rows[1]


def test_mapping_rejects_changed_document_even_when_anchor_remains(
    mapping_corpus: Path,
    mapping_document: dict,
    mapping_observations: list[dict],
    mapping_manifest: dict,
) -> None:
    """Invalidate an old mapping when any pinned source content changes."""
    mapping_document["blocks"].append(
        {"block_id": "b00002", "text": "A correction changes the source interpretation."}
    )
    write_json(mapping_corpus / "texts" / "paper-one.json", mapping_document)

    with pytest.raises(ValueError) as caught:
        apply_name_mappings(mapping_observations, mapping_manifest, mapping_corpus)
    assert "document has changed" in str(caught.value)


@pytest.mark.parametrize(
    "anchor",
    [
        {"block_id": "b00001", "quote": "Annual grass (Poa annua) was rejected"},
        {"block_id": "missing-block", "quote": "Annual grass (Poa annua)"},
    ],
)
def test_mapping_rejects_ungrounded_evidence(
    mapping_corpus: Path,
    mapping_observations: list[dict],
    mapping_manifest: dict,
    anchor: dict,
) -> None:
    """Require each purported anchor to exist verbatim in its identified block."""
    mapping_manifest["mappings"][0]["evidence"] = [anchor]

    with pytest.raises(ValueError) as caught:
        apply_name_mappings(mapping_observations, mapping_manifest, mapping_corpus)
    assert "not grounded" in str(caught.value)


def test_mapping_rejects_duplicate_source_alias(
    mapping_corpus: Path, mapping_observations: list[dict], mapping_manifest: dict
) -> None:
    """Reject ambiguous precedence even when duplicate mapping entries agree."""
    mapping_manifest["mappings"].append(deepcopy(mapping_manifest["mappings"][0]))

    with pytest.raises(ValueError) as caught:
        apply_name_mappings(mapping_observations, mapping_manifest, mapping_corpus)
    assert "Duplicate" in str(caught.value)


def test_mapping_rejects_scientific_name_absent_from_anchor(
    mapping_corpus: Path, mapping_observations: list[dict], mapping_manifest: dict
) -> None:
    """Do not accept a grounded quote as support for an unrelated species name."""
    mapping_manifest["mappings"][0]["scientific_name"] = "Poa pratensis"

    with pytest.raises(ValueError) as caught:
        apply_name_mappings(mapping_observations, mapping_manifest, mapping_corpus)
    assert "scientific_name is absent" in str(caught.value)


def respond_to_mapped_query(
    requests: list[httpx.Request], request: httpx.Request
) -> httpx.Response:
    """Record the GBIF query and return a synthetic exact species match.

    Args:
        requests: Mutable log used to verify that aliases share one request.
        request: Outgoing HTTP request to the mocked GBIF endpoint.

    Returns:
        A complete botanical match using the documented GBIF v2 shape.
    """
    requests.append(request)
    assert str(request.url).startswith("https://api.gbif.org/v2/species/match?")
    assert dict(request.url.params) == {
        "scientificName": "Poa annua",
        "taxonRank": "SPECIES",
        "kingdom": "Plantae",
        "checklistKey": CHECKLIST,
    }
    return httpx.Response(
        200,
        json={
            "usage": {
                "key": "synthetic-poa-annua",
                "canonicalName": "Poa annua",
                "rank": "SPECIES",
                "status": "ACCEPTED",
            },
            "classification": [
                {"name": "Plantae", "rank": "KINGDOM"},
                {"name": "Poaceae", "rank": "FAMILY"},
                {"name": "Poa", "rank": "GENUS"},
            ],
            "diagnostics": {"matchType": "EXACT", "confidence": 99},
        },
    )


def test_gbif_uses_mapped_species_and_memoizes_distinct_aliases(
    tmp_path: Path,
    mapping_corpus: Path,
    mapping_observations: list[dict],
    mapping_manifest: dict,
) -> None:
    """Resolve aliases once while retaining each extraction and mapping provenance."""
    second_observation = {
        **mapping_observations[0],
        "plant_name_as_written": "Annual grass",
        "record_id": "second-extraction-record",
    }
    second_mapping = {
        **mapping_manifest["mappings"][0],
        "plant_name_as_written": "Annual grass",
    }
    mapping_manifest["mappings"].append(second_mapping)
    prepared = apply_name_mappings(
        [*mapping_observations, second_observation], mapping_manifest, mapping_corpus
    )
    requests: list[httpx.Request] = []
    cache = CachedHTTP(
        tmp_path / "raw",
        interval=0,
        client=httpx.Client(
            transport=httpx.MockTransport(partial(respond_to_mapped_query, requests))
        ),
    )
    output = tmp_path / "taxonomy"
    try:
        summary = normalise(prepared, cache, output)
    finally:
        cache.close()

    assert summary == {"matched_observations": 2, "review_observations": 0, "unique_names": 1}
    assert len(requests) == 1
    rows = read_jsonl(output / "observations.jsonl")
    for expected, actual in zip(prepared, rows, strict=True):
        assert {key: actual[key] for key in expected} == expected
        assert actual["accepted_name"] == "Poa annua"
        assert actual["taxonomic_rank"] == "genus"
        assert actual["taxonomy_query_rank"] == "species"
    assert rows[0]["name_resolution"]["mapping_hash"] != rows[1]["name_resolution"]["mapping_hash"]
    assert rows[0]["taxonomy_request_hash"] == rows[1]["taxonomy_request_hash"]
    request_hash = rows[0]["taxonomy_request_hash"]
    assert (tmp_path / "raw" / "http" / f"{request_hash}.json").exists()
