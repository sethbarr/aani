"""Synthetic fixtures for glyph-preserving seeded PDF import and cached replay."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

import pytest

from src.chemistry.export_cache import file_hash
from src.common.io import digest, read_json, read_jsonl, write_json, write_jsonl
from src.systems import monarch_seeded_pdf as pdf
from src.systems.monarch_seeded_sources import SEEDS

SOURCE_HASH = "a" * 64
BODY = "Infected butterﬂies\x02 prefer high-cardenolide milkweeds."
WATERMARK = "Downloaded from example.org by fixture-account on 13 September 2026"
SEED_BY_ID = {seed["seed_id"]: seed for seed in SEEDS}


def bbox_block(text: str, x: float = 10.0, y: float = 20.0) -> str:
    """Construct one Poppler-like positioned block without changing source characters."""
    lines = []
    for line in text.split("\n"):
        words = "".join(f"<word>{escape(word)}</word>" for word in line.split(" "))
        lines.append(f"<line>{words}</line>")
    return (f'<block xMin="{x}" yMin="{y}" xMax="200.5" yMax="300.25">'
            + "".join(lines) + "</block>")


def bbox_fixture(
    seed: dict, doi: str | None = None, title: str | None = None,
    body: str = BODY, second_page: str = "Second-page source text.",
) -> bytes:
    """Build a two-page XHTML fixture with an excluded watermark between source blocks."""
    identity = (title if title is not None else seed["title"]) + "\n" + (
        doi if doi is not None else "doi:" + seed["doi"]
    )
    first = bbox_block(identity) + bbox_block(WATERMARK, 5, 700) + bbox_block(body, 30, 80)
    second = bbox_block(second_page, 40, 90)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><meta name="fixture" /></head>'
        '<body><doc><page width="612" height="792"><flow>' + first + "</flow></page>"
        '<page width="612" height="792"><flow>' + second + "</flow></page>"
        "</doc></body></html>"
    ).encode("utf-8")


def test_parser_preserves_control_glyphs_invalid_in_xml_10() -> None:
    """Keep the U+0002 source glyph that an ordinary XML 1.0 parser rejects."""
    content = bbox_fixture(SEEDS[0])
    with pytest.raises(ET.ParseError):
        ET.fromstring(content)
    pages = pdf.bbox_pages(content)
    assert len(pages) == 2
    blocks = pages[0].findall(".//h:block", pdf.XHTML)
    assert pdf.block_text(blocks[2]) == BODY
    assert "\x02" in pdf.block_text(blocks[2])


def test_metadata_nfkc_accepts_ligature_without_rewriting_payload() -> None:
    """Normalize title identity only while retaining ligatures and printed hyphens in evidence."""
    seed = SEEDS[1]
    source_title = seed["title"].replace("butterfly", "butterﬂy")
    body = "butterﬂy trans-\ngenerational\x02 medication"
    document = pdf.pdf_document(bbox_fixture(seed, title=source_title, body=body), seed, SOURCE_HASH)
    texts = [block["text"] for block in document["blocks"]]
    assert source_title in texts[0]
    assert texts[1] == body
    assert "butterfly" not in texts[1]
    assert pdf.metadata_identity_key(source_title) == pdf.metadata_identity_key(seed["title"])


@pytest.mark.parametrize("wrapper", ["doi:{}", "DOI: {}", "https://doi.org/{}", "({})."])
def test_first_page_accepts_exact_doi_tokens_with_supported_punctuation(wrapper: str) -> None:
    """Accept exact verified DOI tokens in the supported printed citation forms."""
    seed = SEEDS[0]
    document = pdf.pdf_document(bbox_fixture(seed, doi=wrapper.format(seed["doi"])), seed, SOURCE_HASH)
    assert document["provenance"]["doi_verified_on_first_page"] == seed["doi"]


@pytest.mark.parametrize("wrong_doi", ["10.9999/wrong", "suffix", "nested"])
def test_first_page_rejects_wrong_longer_and_nested_doi_tokens(wrong_doi: str) -> None:
    """Reject a verified DOI appearing only inside another token or on the second page."""
    seed = SEEDS[0]
    value = seed["doi"] + "999" if wrong_doi == "suffix" else wrong_doi
    if wrong_doi == "nested":
        value = "10.9999/" + seed["doi"]
    content = bbox_fixture(seed, doi=value, second_page=seed["doi"])
    with pytest.raises(ValueError, match="pdf_first_page_doi_mismatch"):
        pdf.pdf_document(content, seed, SOURCE_HASH)


def test_first_page_rejects_wrong_title_despite_matching_doi() -> None:
    """Require title identity independently of the printed first-page DOI."""
    seed = SEEDS[0]
    content = bbox_fixture(seed, title="A different paper", second_page=seed["title"])
    with pytest.raises(ValueError, match="pdf_first_page_title_mismatch"):
        pdf.pdf_document(content, seed, SOURCE_HASH)


def test_page_coordinates_and_block_hashes_preserve_original_positions() -> None:
    """Retain page/block identities and hash every emitted source block."""
    seed = SEEDS[0]
    content = bbox_fixture(seed)
    document = pdf.pdf_document(content, seed, SOURCE_HASH)
    assert document["provenance"]["pages"] == 2
    assert document["provenance"]["bbox_sha256"] == hashlib.sha256(content).hexdigest()
    assert [row["block_id"] for row in document["blocks"]] == [
        "pdf:p01:b001", "pdf:p01:b003", "pdf:p02:b001",
    ]
    block = document["blocks"][1]
    assert block["provenance"] == {
        "pdf_page": 1, "bounds_points": [30.0, 80.0, 200.5, 300.25],
        "source_sha256": SOURCE_HASH,
    }
    assert document["blocks"][2]["section"] == "PDF / Page 2"
    assert all(row["text_sha256"] == hashlib.sha256(row["text"].encode()).hexdigest()
               for row in document["blocks"])


def test_download_watermark_is_excluded_with_position_and_hash_provenance() -> None:
    """Omit the account watermark text while preserving an auditable exclusion record."""
    seed = SEEDS[0]
    document = pdf.pdf_document(bbox_fixture(seed), seed, SOURCE_HASH)
    excluded = document["provenance"]["excluded_blocks"]
    assert len(excluded) == 1
    assert excluded[0] == {
        "reason": "download_account_watermark", "pdf_page": 1,
        "bounds_points": [5.0, 700.0, 200.5, 300.25], "source_sha256": SOURCE_HASH,
        "text_sha256": hashlib.sha256(WATERMARK.encode()).hexdigest(),
    }
    assert "fixture-account" not in json.dumps(document)


def test_empty_and_watermark_only_pages_fail_closed() -> None:
    """Reject page loss when a source page yields only an excluded account watermark."""
    seed = SEEDS[0]
    with pytest.raises(ValueError, match="pdf_source_has_empty_pages"):
        pdf.pdf_document(bbox_fixture(seed, second_page=WATERMARK), seed, SOURCE_HASH)
    with pytest.raises(ValueError, match="pdf_pages_missing"):
        pdf.pdf_document(b"<html><body></body></html>", seed, SOURCE_HASH)


@pytest.mark.parametrize("markup", [b"<html><body></html>", b"<html><body>"])
def test_parser_rejects_unbalanced_or_incomplete_nesting(markup: bytes) -> None:
    """Keep malformed HTML nesting distinguishable from valid Poppler extraction."""
    with pytest.raises(ValueError, match="poppler_xhtml"):
        pdf.bbox_pages(markup)


def fake_poppler(
    args: list[str], check: bool, capture_output: bool, text: bool = False,
) -> subprocess.CompletedProcess:
    """Supply deterministic Poppler fixtures without invoking an external program."""
    assert args[0] == "pdftotext" and check and capture_output
    if args == ["pdftotext", "-v"]:
        assert text
        return subprocess.CompletedProcess(args, 0, "pdftotext version fixture-1\n", "")
    assert args[1] == "-bbox-layout" and args[-1] == "-" and not text
    seed = SEED_BY_ID[Path(args[2]).parent.name]
    return subprocess.CompletedProcess(args, 0, bbox_fixture(seed), b"")


def forbid_subprocess(*args: object, **kwargs: object) -> None:
    """Reject any subprocess use during an offline import fixture."""
    raise AssertionError("Offline import attempted an external program")


def forbid_supplied_copy(*args: object, **kwargs: object) -> None:
    """Reject archive or Downloads copy access during offline import."""
    raise AssertionError("Offline import attempted a supplied-source copy")


def import_fixture(root: Path) -> Path:
    """Create five supplied byte fixtures and independently verified seed-access metadata."""
    supplied = root / "Downloads"
    supplied.mkdir()
    target = root / "data/interim/systems/monarch_seeded/corpus_targeted_monarch"
    write_json(target / "metrics.json", {"retrieved": 0})
    write_jsonl(target / "manifest.jsonl", [])
    rows = []
    for seed in SEEDS:
        (supplied / pdf.PDF_NAMES[seed["seed_id"]]).write_bytes(
            b"%PDF-1.4\nSynthetic source-byte fixture: " + seed["seed_id"].encode()
        )
        rows.append({**seed, "bibliography_verified": True, "indexed_doi": seed["doi"],
                     "search_request_hash": digest(seed), "status": "not_open_access"})
    write_json(root / "results/systems/monarch_seeded/seed_access.json", {
        "metrics": {"retrieved": 0, "not_open_access": 5, "seeds": 5}, "seeds": rows,
    })
    return supplied


def test_raw_pdf_bbox_text_and_manifest_replay_are_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replay cached sources with absent Downloads and no Poppler invocation."""
    supplied = import_fixture(tmp_path)
    monkeypatch.setattr(pdf.subprocess, "run", fake_poppler)
    live_report = pdf.import_seed_pdfs(tmp_path, supplied)
    live = tmp_path / "data/interim/systems/monarch_seeded"
    cached = {str(path.relative_to(live)): file_hash(path)
              for path in (live / "reference_sources").rglob("*") if path.is_file()}
    assert len(cached) == 15
    monkeypatch.setattr(pdf.subprocess, "run", forbid_subprocess)
    monkeypatch.setattr(pdf, "verified_copy", forbid_supplied_copy)
    missing_downloads = tmp_path / "unavailable_Downloads"
    assert not missing_downloads.exists()
    replay_report = pdf.import_seed_pdfs(tmp_path, missing_downloads, offline=True)
    assert live_report["seeds"] == replay_report["seeds"]
    assert live_report["user_supplied_seed_pdfs"] == replay_report["user_supplied_seed_pdfs"] == 5
    assert cached == {str(path.relative_to(live)): file_hash(path)
                      for path in (live / "reference_sources").rglob("*") if path.is_file()}
    target = live / "corpus_targeted_monarch"
    replay = live / "offline_replay/corpus_targeted_monarch"
    assert (target / "manifest.jsonl").read_bytes() == (replay / "manifest.jsonl").read_bytes()
    assert (target / "europepmc_manifest.jsonl").read_bytes() == b""
    for row in read_jsonl(target / "manifest.jsonl"):
        name = f"{row['source_id']}.json"
        assert (target / "texts" / name).read_bytes() == (replay / "texts" / name).read_bytes()
        document = read_json(target / "texts" / name)
        assert row["text_hash"] == digest(document)
        assert document["provenance"]["extractor"] == "pdftotext version fixture-1"
        assert row["open_access_status"] == "not_established_by_user_supply"


@pytest.mark.parametrize("target_name", ["source.pdf", "source.bbox.xhtml"])
def test_offline_import_rejects_cached_source_byte_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target_name: str,
) -> None:
    """Validate cached PDF and XHTML hashes before parsing an offline source."""
    supplied = import_fixture(tmp_path)
    monkeypatch.setattr(pdf.subprocess, "run", fake_poppler)
    pdf.import_seed_pdfs(tmp_path, supplied)
    path = tmp_path / "data/interim/systems/monarch_seeded/reference_sources/lefevre_2010" / target_name
    path.write_bytes(path.read_bytes() + b"changed")
    monkeypatch.setattr(pdf.subprocess, "run", forbid_subprocess)
    with pytest.raises(ValueError, match="cached_pdf_or_bbox_checksum_changed"):
        pdf.import_seed_pdfs(tmp_path, tmp_path / "missing_Downloads", offline=True)


def test_import_requires_verified_bibliographic_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject a seed whose cached Europe PMC DOI differs from the verified request."""
    supplied = import_fixture(tmp_path)
    path = tmp_path / "results/systems/monarch_seeded/seed_access.json"
    access = read_json(path)
    access["seeds"][0]["indexed_doi"] = "10.9999/different"
    write_json(path, access)
    monkeypatch.setattr(pdf.subprocess, "run", fake_poppler)
    with pytest.raises(ValueError, match="verified_europepmc_bibliography_required"):
        pdf.import_seed_pdfs(tmp_path, supplied)
