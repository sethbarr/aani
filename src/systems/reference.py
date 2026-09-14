"""Build offline, glyph-preserving source blocks for the fixed attine controls."""

import argparse
import base64
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from src.common.io import digest, read_json, write_json, write_jsonl
from src.systems.config import load_system_config
from src.systems.extraction import make_system_jobs

CURRIE_PDF_SHA256 = "4da1d9495dd70f2ec722ea64bf099ad746da30d87174b0753c27b8c151d8c824"
OH_CACHE_HASH = "e827b6bc341332e76294698e466ff9afe2fa12958b6cb9cb9a548a8113093585"
XHTML = {"h": "http://www.w3.org/1999/xhtml"}

# Rectangles use PDF points and select word origins: x0 <= xMin < x1,
# y0 <= yMin < y1. All five PDF pages were visually inspected to fix these
# boundaries. Adjacent sections partition the text without dropping glyphs.
CURRIE_REGIONS = [
    (1, "pdf:p701:front", "Front matter", (300, 280, 560, 444)),
    (1, "pdf:p701:abstract", "Abstract", (300, 444, 560, 655)),
    (1, "pdf:p701:introduction", "Body / Introduction", (300, 655, 560, 755)),
    (2, "pdf:p702:left_column", "Body / Results and Figure 1", (35, 45, 295, 755)),
    (2, "pdf:p702:right_column", "Body / Results and Figure 2", (295, 45, 560, 755)),
    (
        3,
        "pdf:p703:results_and_figure_3",
        "Body / Table 1, Results and Figure 3",
        (40, 45, 300, 755),
    ),
    (3, "pdf:p703:discussion", "Body / Discussion", (300, 45, 560, 510)),
    (3, "pdf:p703:methods", "Methods", (300, 510, 560, 667)),
    (
        3,
        "pdf:p703:antibiotic_bioassay_challenges",
        "Methods / Antibiotic-bioassay challenges",
        (300, 667, 560, 755),
    ),
    (
        4,
        "pdf:p704:antibiotic_bioassay_challenges",
        "Methods / Antibiotic-bioassay challenges",
        (35, 45, 295, 300),
    ),
    (
        4,
        "pdf:p704:growth_promotion_bioassays",
        "Methods / Growth-promotion bioassays",
        (35, 300, 295, 377),
    ),
    (4, "pdf:p704:back_matter", "References and acknowledgements", (35, 377, 295, 755)),
    (5, "pdf:p461:corrigendum", "Corrigendum (2003)", (40, 240, 298, 506)),
]


def sha256_bytes(value: bytes) -> str:
    """Hash source bytes or UTF-8 text without canonicalizing its content."""
    return hashlib.sha256(value).hexdigest()


def currie_document(pdf: Path) -> dict:
    """Isolate the source article and its correction without repairing glyphs."""
    pdf_hash = sha256_bytes(pdf.read_bytes())
    if pdf_hash != CURRIE_PDF_SHA256:
        raise ValueError("Currie PDF differs from the visually reviewed source")
    result = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf), "-"],
        check=True,
        capture_output=True,
    )
    pages = ET.fromstring(result.stdout).findall(".//h:page", XHTML)
    if len(pages) != 5:
        raise ValueError("Expected the four-page article plus corrigendum page")
    blocks = []
    selected_words: set[tuple[int, int]] = set()
    for page_number, block_id, section, region in CURRIE_REGIONS:
        x0, y0, x1, y1 = region
        page = pages[page_number - 1]
        words = list(page.findall(".//h:word", XHTML))
        word_indices = {id(word): index for index, word in enumerate(words)}
        lines = []
        for line in page.findall(".//h:line", XHTML):
            retained = []
            for word in line.findall("h:word", XHTML):
                if x0 <= float(word.attrib["xMin"]) < x1 and y0 <= float(word.attrib["yMin"]) < y1:
                    position = (page_number, word_indices[id(word)])
                    if position in selected_words:
                        raise ValueError(f"Overlapping Currie extraction regions: {position}")
                    selected_words.add(position)
                    retained.append(word.text or "")
            if retained:
                lines.append(" ".join(retained))
        text = "\n".join(lines)
        if not text:
            raise ValueError(f"Empty Currie source region: {block_id}")
        blocks.append(
            {
                "source_id": "CURRIE1999",
                "block_id": block_id,
                "section": section,
                "kind": "pdf_region",
                "text": text,
                "text_sha256": sha256_bytes(text.encode("utf-8")),
                "provenance": {
                    "pdf_page": page_number,
                    "region_points": list(region),
                    "source_sha256": pdf_hash,
                },
            }
        )
    all_text = "\n".join(block["text"] for block in blocks)
    for unrelated in (
        "Archaeopteris",
        "orbitofrontal",
        "HIV-1",
        "carbon nanotube",
        "cocaine seeking",
    ):
        if unrelated in all_text:
            raise ValueError(f"Unrelated adjacent article leaked into Currie blocks: {unrelated}")
    abstract = next(block["text"] for block in blocks if block["block_id"] == "pdf:p701:abstract")
    if not abstract.endswith("and of ancient origin.") or "®lamentous" not in abstract:
        raise ValueError("Currie abstract boundary or embedded glyphs changed")
    version = subprocess.run(["pdftotext", "-v"], check=True, capture_output=True, text=True)
    return {
        "source_id": "CURRIE1999",
        "blocks": blocks,
        "provenance": {
            "source_kind": "user_supplied_pdf",
            "source_sha256": pdf_hash,
            "extractor": (version.stdout + version.stderr).splitlines()[0],
            "bbox_output_sha256": sha256_bytes(result.stdout),
            "selected_word_count": len(selected_words),
            "visual_review": "All five pages reviewed; only Currie article pages 701-704 and its page 461 corrigendum retained.",
            "text_policy": "Preserve every selected pdftotext glyph; join words by spaces and lines by newlines; retain printed line-end hyphens; no glyph substitutions or Unicode normalization.",
            "limitations": [
                "Embedded PDF fonts produce artifacts including ® for fi, ¯ for fl, and some mathematical-symbol substitutions.",
                "Table 1 is supplied as text; figure captions are included and figure images are omitted.",
                "Printed line-end hyphens and page/column boundaries can prevent a quote spanning a word or sentence boundary.",
            ],
        },
    }


def oh_document(cache_path: Path) -> dict:
    """Copy every nonempty cached BioC passage, retaining its exact text."""
    envelope = read_json(cache_path)
    if envelope["request_hash"] != OH_CACHE_HASH:
        raise ValueError("Unexpected Oh BioC cache request")
    attempt = next(item for item in reversed(envelope["attempts"]) if item["status"] == 200)
    response = base64.b64decode(attempt["body_base64"])
    collection = json.loads(response)
    document = collection[0]["documents"][0]
    if document["id"] != "2748230":
        raise ValueError("BioC response is not the Oh positive-control source")
    blocks = []
    for passage in document["passages"]:
        text = passage.get("text", "")
        if not text:
            continue
        blocks.append(
            {
                "source_id": "PMC2748230",
                "block_id": f"bioc:passage_offset_{passage['offset']}",
                "section": passage["infons"]["section_type"],
                "kind": passage["infons"]["type"],
                "text": text,
                "text_sha256": sha256_bytes(text.encode("utf-8")),
                "provenance": {
                    "bioc_offset": passage["offset"],
                    "cache_request_hash": OH_CACHE_HASH,
                    "response_sha256": sha256_bytes(response),
                },
            }
        )
    if len({block["block_id"] for block in blocks}) != len(blocks):
        raise ValueError("Duplicate BioC passage offsets")
    return {
        "source_id": "PMC2748230",
        "blocks": blocks,
        "provenance": {
            "source_kind": "cached_ncbi_bioc_author_manuscript",
            "cache_request_hash": OH_CACHE_HASH,
            "cache_file_sha256": sha256_bytes(cache_path.read_bytes()),
            "response_sha256": sha256_bytes(response),
            "retrieved_at": attempt["retrieved_at"],
            "license": document["infons"].get("license"),
            "text_policy": "All nonempty BioC passage text is copied unchanged, with original Unicode code points and offsets.",
            "empty_passages": sum(not passage.get("text") for passage in document["passages"]),
            "limitations": [
                "BioC supplies the author manuscript; its 20 reference passages have metadata and empty text.",
                "The supplementary-material heading is present; the supplementary file contents and figure images are absent from this cached response.",
                "BioC labels main article paragraphs INTRO, including results; section labels are retained as supplied.",
            ],
        },
    }


def prepare_attine_reference_corpus(root: Path) -> dict:
    """Materialize local reference inputs and compute their exact shared jobs."""
    system_root = root / "data/interim/systems/attine_actino"
    reference_root = system_root / "reference_sources"
    config = load_system_config(root / "config/systems/attine_actino.json")
    fixed = read_json(root / "results/systems/attine_actino/reference_set.json")
    if fixed["scoring"]["recall_denominator"] != 2 or len(fixed["reference_items"]) != 2:
        raise ValueError("Expected the unchanged prospective two-item reference set")
    documents = [
        currie_document(reference_root / "currie_1999/source.pdf"),
        oh_document(system_root / "cache/http" / f"{OH_CACHE_HASH}.json"),
    ]
    papers = [
        {
            "source_id": "CURRIE1999",
            "title": "Fungus-growing ants use antibiotic-producing bacteria to control garden parasites",
            "doi": "10.1038/19519",
            "source_url": "https://doi.org/10.1038/19519",
            "status": "ready",
        },
        {
            "source_id": "PMC2748230",
            "title": "Dentigerumycin: a bacterial mediator of an ant-fungus symbiosis",
            "doi": "10.1038/nchembio.159",
            "source_url": "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/PMC2748230/unicode",
            "status": "ready",
        },
    ]
    corpus = reference_root / "corpus"
    for paper, document in zip(papers, documents, strict=True):
        paper["text_hash"] = digest(document)
        paper["selection_role"] = "prospectively_fixed_positive_control"
        write_json(corpus / "texts" / f"{paper['source_id']}.json", document)
    write_jsonl(corpus / "manifest.jsonl", papers)
    screening = reference_root / "screening.json"
    write_json(
        screening,
        {
            "decisions": [
                {
                    "source_id": paper["source_id"],
                    "decision": "include",
                    "reason": "Source fixed in the prospective two-item positive-control reference set.",
                }
                for paper in papers
            ]
        },
    )
    jobs, metrics = make_system_jobs(config, corpus, screening, maximum_characters=24000)
    original = read_json(system_root / "extraction_payloads/index.json")
    original_ids = {job["source_id"] for job in original["jobs"]}
    reference_ids = {paper["source_id"] for paper in papers}
    audit = {
        "schema_version": 1,
        "system": "attine_actino",
        "recall_denominator": 2,
        "reference_set_hash": digest(fixed),
        "status": "offline_reference_inputs_prepared",
        "external_payload_sent": False,
        "model_api_called": False,
        "corpus_path": str(corpus.relative_to(root)),
        "screening_path": str(screening.relative_to(root)),
        "reference_sources_are_separate_from_original_20_source_corpus": True,
        "original_prepared_jobs": len(original["jobs"]),
        "original_direct_reference_sources_exposed": sorted(original_ids & reference_ids),
        "original_direct_reference_sources_missing": sorted(reference_ids - original_ids),
        "original_payloads_changed": False,
        "maximum_characters": 24000,
        "reference_job_metrics": metrics,
        "reference_jobs": [
            {key: job[key] for key in ("source_id", "input_hash", "chunk_index", "chunk_count")}
            for job in jobs
        ],
        "sources": [
            {
                "source_id": doc["source_id"],
                "block_count": len(doc["blocks"]),
                "text_characters": sum(len(block["text"]) for block in doc["blocks"]),
                "document_hash": digest(doc),
                "provenance": doc["provenance"],
            }
            for doc in documents
        ],
        "adequacy": {
            "currie": "Full article text and relevant corrigendum supplied; abstract and Discussion each contain explicit Streptomyces-antibiotic-Escovopsis inhibitory statements. Embedded glyph artifacts are preserved.",
            "oh": "Every available nonempty author-manuscript passage supplied; abstract has Pseudonocardia, dentigerumycin and Escovopsis inhibition together, and offset 9487 supplies MIC results.",
            "reference_recall_status": "unmeasured_until_reference_jobs_run_and_grounded_records_scored",
            "required_before_scoring": "Expose both reference sources using whole-source jobs within the system cap, and score the unchanged two-item denominator.",
            "ground_truth_wording_caveat": "The frozen Currie abstract quote was visually transcribed and differs from embedded text glyphs and printed line-end hyphenation. A model record must quote the actual supplied blocks; semantic reference-item matching must not require verbatim equality to the visually transcribed ground-truth quote. The frozen Oh quantitative support uses micro sign U+00B5 while its source text uses Greek mu U+03BC; this support is outside the recall match criteria.",
        },
    }
    write_json(root / "results/systems/attine_actino/control_preflight.json", audit)
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    report = prepare_attine_reference_corpus(arguments.root.resolve())
    print(
        json.dumps(
            {
                "reference_jobs": report["reference_job_metrics"],
                "sources": [
                    {key: row[key] for key in ("source_id", "block_count", "text_characters")}
                    for row in report["sources"]
                ],
            },
            indent=2,
        )
    )
