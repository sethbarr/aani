"""Offline source-identity and access-classification checks for monarch seeds."""

import base64
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx
import pytest

from src.common.cache import CachedHTTP
from src.common.io import digest, read_json, write_json
from src.corpus.europepmc import BASE
from src.systems.monarch_seeded_sources import (
    SEEDS,
    retrieve_seed,
    title_key,
    verify_doi_record,
)

type Record = dict[str, Any]


def prohibit_network(request: httpx.Request) -> httpx.Response:
    """Fail immediately if any fixture attempts an uncached network request."""
    raise AssertionError(f"Unexpected network request: {request.method} {request.url}")


@pytest.fixture
def seed() -> Record:
    """Copy one known seed without editing the prospective source list."""
    return dict(SEEDS[0])


@pytest.fixture
def metadata(seed: Record) -> Record:
    """Provide a matching synthetic Europe PMC core bibliographic record."""
    return {
        "source": "MED", "id": seed["pmid"], "doi": seed["doi"],
        "title": seed["title"], "pubYear": seed["year"],
        "pmcid": "PMC123456", "isOpenAccess": "Y", "inPMC": "Y",
        "authorString": "Synthetic source fixture",
    }


@pytest.fixture
def cache(tmp_path: Path, request: pytest.FixtureRequest) -> CachedHTTP:
    """Use disk fixtures and a transport that rejects every network request."""
    result = CachedHTTP(tmp_path / "cache", offline=True, interval=0,
                        client=httpx.Client(transport=httpx.MockTransport(prohibit_network)))
    request.addfinalizer(result.close)
    return result


def search_params(seed: Record) -> Record:
    """Reproduce the documented DOI-verification request descriptor."""
    return {"query": f'DOI:"{seed["doi"]}"', "format": "json",
            "resultType": "core", "pageSize": 100}


def cache_response(
    cache: CachedHTTP, url: str, content: bytes, params: Record | None = None, status: int = 200
) -> str:
    """Write one deterministic synthetic cached response without issuing HTTP.

    Args:
        cache: Offline cache receiving a fixture response.
        url: Exact request URL.
        content: Encoded response bytes.
        params: Request query parameters.
        status: Persisted HTTP status code.

    Returns:
        Deterministic request hash used by the production cache reader.
    """
    descriptor = {"method": "GET", "url": url, "params": params or {}, "json": None}
    request_hash = digest(descriptor)
    write_json(cache.root / "http" / f"{request_hash}.json", {
        "request": descriptor, "request_hash": request_hash,
        "attempts": [{"status": status, "retrieved_at": "2026-09-13T00:00:00+00:00",
                      "body_base64": base64.b64encode(content).decode("ascii"),
                      "content_type": "application/xml"}],
    })
    return request_hash


def cache_metadata(cache: CachedHTTP, seed: Record, rows: list[Record]) -> str:
    """Cache a DOI-search response with explicitly supplied bibliographic rows."""
    payload = {"resultList": {"result": rows}, "hitCount": len(rows)}
    return cache_response(cache, f"{BASE}/search", json.dumps(payload).encode("utf-8"),
                          search_params(seed))


def fulltext_xml(doi: str, body: bool = True, namespace: bool = False) -> bytes:
    """Build a minimal JATS fixture with a top-level article DOI."""
    article = ET.Element("article", {"xmlns": "urn:test-jats"} if namespace else {})
    front = ET.SubElement(article, "front")
    article_meta = ET.SubElement(front, "article-meta")
    ET.SubElement(article_meta, "article-id", {"pub-id-type": "doi"}).text = doi
    abstract = ET.SubElement(article_meta, "abstract")
    ET.SubElement(abstract, "p").text = "Synthetic abstract with no scientific data."
    if body:
        section = ET.SubElement(ET.SubElement(article, "body"), "sec")
        ET.SubElement(section, "title").text = "Methods"
        ET.SubElement(section, "p").text = "Synthetic complete body paragraph."
    return ET.tostring(article, encoding="utf-8")


@pytest.mark.parametrize("field,value,reason", [
    ("doi", "10.0000/different", "seed_doi_mismatch"),
    ("pubYear", "2009", "seed_publication_year_mismatch"),
    ("title", "An unrelated paper", "seed_title_mismatch"),
])
def test_bibliography_mismatches_are_rejected(
    seed: Record, metadata: Record, field: str, value: str, reason: str,
) -> None:
    """Require independent DOI, title and publication-year agreement."""
    metadata[field] = value
    with pytest.raises(ValueError) as error:
        verify_doi_record(seed, {"resultList": {"result": [metadata]}})
    assert str(error.value) == reason


@pytest.mark.parametrize("field,value", [("id", "999999"), ("source", "PMC")])
def test_unmatched_pubmed_identity_is_not_accepted(
    seed: Record, metadata: Record, field: str, value: str,
) -> None:
    """Keep another PMID or an alternative source record outside verified MED identity."""
    metadata[field] = value
    assert verify_doi_record(seed, {"resultList": {"result": [metadata]}}) is None


def test_duplicate_matching_pubmed_records_are_ambiguous(seed: Record, metadata: Record) -> None:
    """Require one matching PubMed identity in the verification response."""
    with pytest.raises(ValueError) as error:
        verify_doi_record(seed, {"resultList": {"result": [metadata, dict(metadata)]}})
    assert str(error.value) == "ambiguous_seed_identity"


def test_harmless_title_punctuation_and_doi_case_preserve_identity(
    seed: Record, metadata: Record,
) -> None:
    """Allow punctuation and case differences without accepting different title words."""
    metadata["title"] = seed["title"].upper().replace("-", " ") + "."
    metadata["doi"] = seed["doi"].upper()
    assert verify_doi_record(seed, {"resultList": {"result": [metadata]}}) == metadata
    assert title_key("A title: one.") == title_key("a TITLE one")


@pytest.mark.parametrize("is_open_access", ["N", "Y"])
def test_no_indexed_pmc_route_is_scoped_access_gap(
    seed: Record, metadata: Record, cache: CachedHTTP, tmp_path: Path, is_open_access: str,
) -> None:
    """Report the missing Europe PMC route even if an external OA flag is present."""
    metadata.pop("pmcid")
    metadata.update(isOpenAccess=is_open_access, fullTextUrlList={
        "fullTextUrl": [{"url": "https://example.invalid/external", "availability": "Open access"}]
    })
    search_hash = cache_metadata(cache, seed, [metadata])
    row = retrieve_seed(seed, cache, tmp_path / "output")
    assert row["status"] == "not_open_access"
    assert row["bibliography_verified"] is True
    assert row["search_request_hash"] == search_hash
    assert row["fulltext_attempt"] == "no_indexed_pmcid_route"
    assert row["access_scope"] == "Europe PMC fullTextXML"
    assert row["is_open_access"] == is_open_access
    assert "fulltext_request_hash" not in row
    assert not (tmp_path / "output/texts").exists()
    assert len(list((cache.root / "http").glob("*.json"))) == 1


@pytest.mark.parametrize("kind", ["doi", "title", "year", "pmid", "empty"])
def test_retrieval_classifies_identity_failures_without_fulltext_access(
    seed: Record, metadata: Record, cache: CachedHTTP, tmp_path: Path, kind: str,
) -> None:
    """Keep unverified search results out of the target corpus and fulltext stage."""
    if kind == "doi":
        metadata["doi"] = "10.0000/unrelated"
    elif kind == "title":
        metadata["title"] = "Unrelated title"
    elif kind == "year":
        metadata["pubYear"] = "2020"
    elif kind == "pmid":
        metadata["id"] = "999999"
    search_hash = cache_metadata(cache, seed, [] if kind == "empty" else [metadata])
    row = retrieve_seed(seed, cache, tmp_path / "output")
    assert row["status"] == "not_found"
    assert row["bibliography_verified"] is False
    assert row["search_request_hash"] == search_hash
    assert "fulltext_attempt" not in row
    assert not (tmp_path / "output/texts").exists()


@pytest.mark.parametrize("namespace", [False, True])
def test_verified_fulltext_replays_from_cache_with_stable_text_and_hashes(
    seed: Record, metadata: Record, cache: CachedHTTP, tmp_path: Path, namespace: bool,
) -> None:
    """Replay source bytes without HTTP or changes to the response cache."""
    search_hash = cache_metadata(cache, seed, [metadata])
    fulltext_hash = cache_response(cache, f"{BASE}/{metadata['pmcid']}/fullTextXML",
                                   fulltext_xml(seed["doi"], namespace=namespace))
    before = {path.name: path.read_bytes() for path in (cache.root / "http").glob("*.json")}
    first = retrieve_seed(seed, cache, tmp_path / "first")
    replay = retrieve_seed(seed, cache, tmp_path / "replay")
    assert first["status"] == replay["status"] == "retrieved"
    assert first["bibliography_verified"] is True
    assert first["search_request_hash"] == search_hash
    assert first["fulltext_request_hash"] == fulltext_hash
    assert first["text_hash"] == replay["text_hash"]
    assert first["block_count"] == replay["block_count"] == 2
    relative = Path("texts") / f"{metadata['pmcid']}.json"
    assert (tmp_path / "first" / relative).read_bytes() == (
        tmp_path / "replay" / relative
    ).read_bytes()
    assert read_json(tmp_path / "first" / relative)["blocks"][1]["section"] == "Body / Methods"
    assert before == {path.name: path.read_bytes()
                      for path in (cache.root / "http").glob("*.json")}


def test_fulltext_doi_mismatch_keeps_fetched_response_provenance(
    seed: Record, metadata: Record, cache: CachedHTTP, tmp_path: Path,
) -> None:
    """Reject a different article while retaining the failed fulltext request hash."""
    cache_metadata(cache, seed, [metadata])
    fulltext_hash = cache_response(cache, f"{BASE}/{metadata['pmcid']}/fullTextXML",
                                   fulltext_xml("10.0000/unrelated"))
    row = retrieve_seed(seed, cache, tmp_path / "output")
    assert row["status"] == "not_found"
    assert row["bibliography_verified"] is True
    assert row["reason"] == "ValueError: retrieved_fulltext_doi_mismatch"
    assert row["fulltext_request_hash"] == fulltext_hash
    assert row["blocked_reason"] == "retrieval_or_identity_verification_failed"
    assert not (tmp_path / "output/texts").exists()


def test_nested_article_doi_cannot_validate_the_main_article(
    seed: Record, metadata: Record, cache: CachedHTTP, tmp_path: Path,
) -> None:
    """Prevent a matching DOI in nested article metadata from validating unrelated text."""
    document = ET.fromstring(fulltext_xml("10.0000/unrelated"))
    nested_front = ET.SubElement(ET.SubElement(document, "sub-article"), "front")
    nested_meta = ET.SubElement(nested_front, "article-meta")
    ET.SubElement(nested_meta, "article-id", {"pub-id-type": "doi"}).text = seed["doi"]
    cache_metadata(cache, seed, [metadata])
    cache_response(cache, f"{BASE}/{metadata['pmcid']}/fullTextXML", ET.tostring(document))
    row = retrieve_seed(seed, cache, tmp_path / "output")
    assert row["status"] == "not_found"
    assert row["reason"] == "ValueError: retrieved_fulltext_doi_mismatch"


@pytest.mark.parametrize("kind", ["abstract_only", "invalid_xml"])
def test_incomplete_or_malformed_fulltext_is_not_a_retrieved_seed(
    seed: Record, metadata: Record, cache: CachedHTTP, tmp_path: Path, kind: str,
) -> None:
    """Require a parsed article body and preserve failure provenance."""
    content = fulltext_xml(seed["doi"], body=False) if kind == "abstract_only" else b"<article>"
    cache_metadata(cache, seed, [metadata])
    fulltext_hash = cache_response(cache, f"{BASE}/{metadata['pmcid']}/fullTextXML", content)
    row = retrieve_seed(seed, cache, tmp_path / "output")
    assert row["status"] == "not_found"
    assert row["bibliography_verified"] is True
    assert row["fulltext_request_hash"] == fulltext_hash
    assert not (tmp_path / "output/texts").exists()
    if kind == "abstract_only":
        assert row["reason"] == "ValueError: retrieved_fulltext_body_missing"
    else:
        assert row["reason"].startswith("ParseError:")


@pytest.mark.parametrize("search_cached", [False, True])
def test_offline_cache_miss_is_explicitly_classified_without_network(
    seed: Record, metadata: Record, cache: CachedHTTP, tmp_path: Path, search_cached: bool,
) -> None:
    """Report the missing cached stage without inventing access or fulltext results."""
    if search_cached:
        cache_metadata(cache, seed, [metadata])
    row = retrieve_seed(seed, cache, tmp_path / "output")
    assert row["status"] == "not_found"
    assert row["bibliography_verified"] is search_cached
    assert row["reason"].startswith("OfflineCacheMiss: Missing cached request")
    assert row["blocked_reason"] == "retrieval_or_identity_verification_failed"
    assert "fulltext_request_hash" not in row
    assert not (tmp_path / "output/texts").exists()


def test_cached_http_failure_remains_an_access_failure_during_replay(
    seed: Record, metadata: Record, cache: CachedHTTP, tmp_path: Path,
) -> None:
    """Replay a recorded service error without manufacturing a retrieved seed."""
    cache_metadata(cache, seed, [metadata])
    failed_hash = cache_response(cache, f"{BASE}/{metadata['pmcid']}/fullTextXML",
                                 b"No full text available", status=404)
    failure_path = cache.root / "http" / f"{failed_hash}.json"
    before = failure_path.read_bytes()
    row = retrieve_seed(seed, cache, tmp_path / "output")
    assert row["status"] == "not_found"
    assert row["bibliography_verified"] is True
    assert row["reason"].startswith("HTTPStatusError:")
    assert row["fulltext_attempt"] == "requested"
    assert row["blocked_reason"] == "retrieval_or_identity_verification_failed"
    assert failure_path.read_bytes() == before
    assert not (tmp_path / "output/texts").exists()
