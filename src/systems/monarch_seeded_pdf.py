"""Import verified user-supplied monarch PDFs without changing extraction text glyphs."""

import argparse
import hashlib
import json
import subprocess
import unicodedata
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from src.chemistry.export_cache import file_hash
from src.common.io import digest, read_json, timestamp, write_json, write_jsonl
from src.systems.monarch_seeded_downstream import seeded_paths
from src.systems.monarch_seeded_prepare import verified_copy
from src.systems.monarch_seeded_sources import SEEDS, title_key

XHTML = {"h": "http://www.w3.org/1999/xhtml"}
PDF_NAMES = {
    "lefevre_2010": "Lefèvre et al. 2010 - Evidence for trans-generational medication in nature - Medication in the monarch butterfly.pdf",
    "lefevre_2012": "Lefèvre et al. 2012 - Behavioural resistance against a protozoan parasite in the monarch butterfly - Anti-parasite behaviours.pdf",
    "deroode_2008": "de Roode et al. 2008 - Host plant species affects virulence in monarch butterfly parasites.pdf",
    "sternberg_2012": "Sternberg et al. 2012 - Food plant derived disease tolerance and resista ... te interactions - Food plant-derived disease tolerance and resistance.pdf",
    "gowler_2015": "Gowler et al. 2015 - Secondary defense chemicals in milkweed reduce parasite infection in monarch butterflies, Danaus plexippus.pdf",
}
SOURCE_IDS = {
    "lefevre_2010": "LEFEVRE2010", "lefevre_2012": "LEFEVRE2012",
    "deroode_2008": "DEROODE2008", "sternberg_2012": "STERNBERG2012",
    "gowler_2015": "GOWLER2015",
}


class PopplerHTMLParser(HTMLParser):
    """Parse Poppler XHTML while preserving PDF control glyphs invalid in XML 1.0."""

    def __init__(self) -> None:
        """Initialize a namespace-aware element tree without source-glyph repair."""
        super().__init__(convert_charrefs=True)
        self.root = ET.Element("document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Add one XHTML node using the default Poppler namespace."""
        node = ET.SubElement(self.stack[-1], f"{{{XHTML['h']}}}{tag}",
                             {key: value or "" for key, value in attrs})
        self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        """Close exactly one matching node and reject malformed nesting."""
        if len(self.stack) < 2 or self.stack[-1].tag != f"{{{XHTML['h']}}}{tag}":
            raise ValueError("unbalanced_poppler_xhtml")
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        """Keep source character data, including embedded font-control glyphs."""
        node = self.stack[-1]
        if len(node):
            node[-1].tail = (node[-1].tail or "") + data
        else:
            node.text = (node.text or "") + data


def bbox_pages(content: bytes) -> list[ET.Element]:
    """Parse cached Poppler XHTML without deleting XML-invalid source characters."""
    parser = PopplerHTMLParser()
    parser.feed(content.decode("utf-8"))
    parser.close()
    if len(parser.stack) != 1:
        raise ValueError("incomplete_poppler_xhtml")
    return parser.root.findall(".//h:page", XHTML)


def metadata_identity_key(value: str) -> str:
    """Normalize title metadata solely for identity checking, leaving source text intact."""
    return title_key(unicodedata.normalize("NFKC", value))


def block_text(block: ET.Element) -> str:
    """Join Poppler words and lines while retaining every extracted glyph and hyphen."""
    return "\n".join(" ".join(word.text or "" for word in line.findall("h:word", XHTML))
                     for line in block.findall("h:line", XHTML)).strip()


def pdf_document(content: bytes, seed: dict, source_sha256: str) -> dict:
    """Parse cached Poppler blocks with page coordinates and first-page DOI validation.

    Args:
        content: Complete pdftotext bbox-layout XHTML output.
        seed: Independently verified seed bibliography.
        source_sha256: Hash of the complete supplied PDF.

    Returns:
        Source blocks with immutable page, coordinate and source-byte provenance.

    Raises:
        ValueError: The first page lacks the verified article DOI/title or source blocks.
    """
    pages = bbox_pages(content)
    if not pages:
        raise ValueError("pdf_pages_missing")
    first_page = "\n".join(block_text(block) for block in pages[0].findall(".//h:block", XHTML))
    doi_tokens = {word.strip(",.;()[]{}").removeprefix("doi:").removeprefix("https://doi.org/")
                  for word in first_page.casefold().split()}
    if seed["doi"].casefold() not in doi_tokens:
        raise ValueError("pdf_first_page_doi_mismatch")
    if metadata_identity_key(seed["title"]) not in metadata_identity_key(first_page):
        raise ValueError("pdf_first_page_title_mismatch")
    source_id = SOURCE_IDS[seed["seed_id"]]
    blocks, excluded = [], []
    for page_number, page in enumerate(pages, 1):
        for index, block in enumerate(page.findall(".//h:block", XHTML), 1):
            text = block_text(block)
            if not text:
                continue
            provenance = {
                "pdf_page": page_number,
                "bounds_points": [float(block.attrib[key]) for key in ("xmin", "ymin", "xmax", "ymax")],
                "source_sha256": source_sha256,
            }
            bounds = provenance["bounds_points"]
            rotated_download_margin = bounds[2] - bounds[0] < 20 and "Downloaded from https://" in text
            if text.startswith("Downloaded from ") or rotated_download_margin:
                excluded.append({"reason": "download_account_watermark", **provenance,
                                 "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
                continue
            blocks.append({
                "source_id": source_id, "block_id": f"pdf:p{page_number:02}:b{index:03}",
                "section": f"PDF / Page {page_number}", "kind": "pdf_text_block", "text": text,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "provenance": provenance,
            })
    if not blocks or {row["provenance"]["pdf_page"] for row in blocks} != set(range(1, len(pages) + 1)):
        raise ValueError("pdf_source_has_empty_pages")
    return {
        "source_id": source_id, "blocks": blocks,
        "provenance": {
            "source_kind": "user_supplied_pdf", "source_sha256": source_sha256,
            "bbox_sha256": hashlib.sha256(content).hexdigest(), "pages": len(pages),
            "doi_verified_on_first_page": seed["doi"], "title_verified_on_first_page": True,
            "text_policy": "All nonempty Poppler text blocks, including references and captions; words joined by spaces and lines by newlines; original glyphs and printed line-end hyphens preserved. Only download-account watermarks excluded with page/hash provenance.",
            "section_policy": "PDF page labels identify source sections; printed headings remain in source blocks.",
            "excluded_blocks": excluded,
            "limitations": ["Figure images are outside the text payload; figure captions and extracted axis labels are retained.",
                            "Printed line-end hyphens, embedded font glyphs and block boundaries can prevent single-quote matches."],
        },
    }


def import_seed_pdfs(root: Path, supplied_dir: Path, offline: bool = False) -> dict:
    """Cache all five supplied PDFs and replay their text into the isolated seed corpus.

    Args:
        root: Repository root.
        supplied_dir: Directory containing the five explicitly supplied file names.
        offline: Read cached source bytes and XHTML, without consulting supplied_dir.

    Returns:
        Local PDF access and identity provenance, separate from Europe PMC access.
    """
    paths = seeded_paths(root, offline)
    live_target = paths["live"] / "corpus_targeted_monarch"
    output = paths["interim"] / "corpus_targeted_monarch"
    reference_root = paths["live"] / "reference_sources"
    access = read_json(paths["root"] / "results/systems/monarch_seeded/seed_access.json")
    indexed = {row["seed_id"]: row for row in access["seeds"]}
    if not offline:
        for name in ("metrics.json", "manifest.jsonl"):
            archived = live_target / f"europepmc_{name}"
            if not archived.exists():
                verified_copy(live_target / name, archived, paths["live"])
    poppler_version = None
    if not offline:
        version = subprocess.run(["pdftotext", "-v"], check=True, capture_output=True, text=True)
        poppler_version = (version.stdout + version.stderr).splitlines()[0]
    rows, identities = [], []
    for seed in SEEDS:
        prior = indexed[seed["seed_id"]]
        if not prior["bibliography_verified"] or prior["indexed_doi"].casefold() != seed["doi"].casefold():
            raise ValueError("verified_europepmc_bibliography_required")
        folder = reference_root / seed["seed_id"]
        pdf, bbox = folder / "source.pdf", folder / "source.bbox.xhtml"
        extraction_metadata = folder / "source.extraction.json"
        if not offline:
            verified_copy(supplied_dir / PDF_NAMES[seed["seed_id"]], pdf, paths["live"])
            result = subprocess.run(["pdftotext", "-bbox-layout", str(pdf), "-"],
                                    check=True, capture_output=True)
            if bbox.exists() and bbox.read_bytes() != result.stdout:
                raise ValueError("cached_poppler_output_changed")
            if not bbox.exists():
                bbox.write_bytes(result.stdout)
            if not extraction_metadata.exists():
                write_json(extraction_metadata, {"extractor": poppler_version,
                                                 "pdf_sha256": file_hash(pdf),
                                                 "bbox_sha256": file_hash(bbox)})
        cached_extractor = read_json(extraction_metadata)
        if cached_extractor["pdf_sha256"] != file_hash(pdf) or cached_extractor["bbox_sha256"] != file_hash(bbox):
            raise ValueError("cached_pdf_or_bbox_checksum_changed")
        document = pdf_document(bbox.read_bytes(), seed, file_hash(pdf))
        document["provenance"]["extractor"] = cached_extractor["extractor"]
        write_json(output / "texts" / f"{document['source_id']}.json", document)
        row = {
            **seed, "source_id": document["source_id"], "title": seed["title"],
            "source_url": f"https://doi.org/{seed['doi']}", "status": "ready",
            "source_kind": "user_supplied_pdf", "bibliography_verified": True,
            "indexed_doi": prior["indexed_doi"], "bibliography_request_hash": prior["search_request_hash"],
            "europe_pmc_fulltext_status": prior["status"], "local_pdf_access_status": "retrieved",
            "open_access_status": "not_established_by_user_supply", "text_hash": digest(document),
            "source_pdf_sha256": file_hash(pdf), "pages": document["provenance"]["pages"],
            "block_count": len(document["blocks"]),
        }
        rows.append(row)
        identities.append({**row, "supplied_filename": PDF_NAMES[seed["seed_id"]],
                           "cached_pdf_path": str(pdf), "cached_bbox_sha256": file_hash(bbox),
                           "source_characters": sum(len(block["text"]) for block in document["blocks"])})
    write_jsonl(output / "manifest.jsonl", rows)
    metrics = {**access["metrics"], "offline": offline, "retrieved": len(rows),
               "europe_pmc_retrieved": access["metrics"]["retrieved"],
               "europe_pmc_not_open_access": access["metrics"]["not_open_access"],
               "not_open_access": None,
               "access_status_scope": "Full text supplied locally; global OA status remains unclassified.",
               "user_supplied_retrieved": len(rows), "not_found": 0,
               "unavailable_seed_texts": 0, "local_import_at": timestamp()}
    write_json(output / "metrics.json", metrics)
    report = {"system": "monarch_seeded", "offline": offline, "imported_at": timestamp(),
              "status": "complete", "user_supplied_seed_pdfs": len(rows),
              "external_payload_sent": False, "seeds": identities,
              "extra_supplied_paper": "Virulence-transmission trade-offs paper is outside the five-seed set and is not imported."}
    write_json(paths["results"] / "local_pdf_access.json", report)
    return report


def main() -> None:
    """Import the explicitly supplied PDFs or replay their cached source text."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--supplied-dir", type=Path, default=Path("/Users/seth/Downloads"))
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    report = import_seed_pdfs(args.root, args.supplied_dir, args.offline)
    print(json.dumps({"status": report["status"], "seeds": report["user_supplied_seed_pdfs"],
                      "documents": [{key: row[key] for key in ("source_id", "pages", "block_count", "source_characters")}
                                    for row in report["seeds"]]}, indent=2))


if __name__ == "__main__":
    main()
