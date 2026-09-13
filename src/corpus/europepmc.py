"""Retrieve full texts and retain stable, quoteable JATS blocks."""

import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from src.common.cache import CachedHTTP, OfflineCacheMiss
from src.common.io import normalise_space, timestamp, write_json, write_jsonl

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
QUERY = (
    'TITLE_ABS:(Atta OR Acromyrmex OR attine OR "leaf-cutting ant" OR leafcutter) '
    'AND ("foraging preference" OR "plant selection" OR rejection OR avoidance '
    'OR "substrate choice" OR "host plant") AND OPEN_ACCESS:Y'
)


def local_name(tag: str) -> str:
    """Return an XML tag name without an optional namespace URI."""
    return tag.rsplit("}", 1)[-1]


def walk_blocks(element: ET.Element, section: str) -> list[dict]:
    """Extract paragraph and table blocks while excluding bibliographies.

    Args:
        element: Current JATS container.
        section: Current hierarchical section title.

    Returns:
        Text blocks with section labels, without duplicate table paragraphs.
    """
    blocks = []
    for child in element:
        tag = local_name(child.tag)
        if tag in {"ref-list", "back"}:
            continue
        if tag == "sec":
            title = next(
                (node for node in child if local_name(node.tag) == "title"),
                None,
            )
            heading = normalise_space("".join(title.itertext())) if title is not None else ""
            blocks.extend(walk_blocks(child, f"{section} / {heading}"))
        elif tag in {"p", "table-wrap"}:
            text = normalise_space("".join(child.itertext()))
            if text:
                blocks.append({"section": section, "kind": tag, "text": text})
        elif tag not in {"title", "label"}:
            blocks.extend(walk_blocks(child, section))
    return blocks


def parse_fulltext(content: bytes, source_id: str) -> list[dict]:
    """Parse abstract/body XML into stable source-local blocks."""
    root = ET.fromstring(content)
    blocks = []
    abstracts = [node for node in root.iter() if local_name(node.tag) == "abstract"]
    for abstract in abstracts:
        blocks.extend(walk_blocks(abstract, "Abstract"))
    bodies = [node for node in root if local_name(node.tag) == "body"]
    for body in bodies:
        blocks.extend(walk_blocks(body, "Body"))
    return [
        {"source_id": source_id, "block_id": f"b{index:05d}", **block}
        for index, block in enumerate(blocks)
    ]


def retrieve(cache: CachedHTTP, output: Path, limit: int = 30, query: str = QUERY) -> dict:
    """Retrieve a deterministic pilot and log failed full-text attempts.

    Args:
        cache: Cached HTTP transport.
        output: Corpus output directory.
        limit: Maximum number of successfully parsed full texts.
        query: Fully recorded Europe PMC query.

    Returns:
        Retrieval metrics including search hit count and manifest path.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    cursor = "*"
    manifest = []
    seen = set()
    successes = 0
    search_hashes = []
    while successes < limit:
        response, key = cache.get_json(
            f"{BASE}/search",
            {
                "query": query,
                "format": "json",
                "pageSize": 100,
                "cursorMark": cursor,
                "resultType": "core",
                "sort": "FIRST_PDATE_D desc",
            },
        )
        search_hashes.append(key)
        hits = response.get("resultList", {}).get("result", [])
        for hit in hits:
            pmcid = hit.get("pmcid")
            if not pmcid or pmcid in seen:
                continue
            seen.add(pmcid)
            record = {
                "source_id": pmcid,
                "title": hit.get("title", ""),
                "doi": hit.get("doi"),
                "publication_date": hit.get("firstPublicationDate"),
                "source_url": f"https://europepmc.org/articles/{pmcid}",
                "retrieved_at": timestamp(),
                "search_request_hash": key,
            }
            try:
                content, text_key = cache.request("GET", f"{BASE}/{pmcid}/fullTextXML")
                blocks = parse_fulltext(content, pmcid)
                if not blocks:
                    raise ValueError("No abstract or body text blocks")
                write_json(
                    output / "texts" / f"{pmcid}.json", {"source_id": pmcid, "blocks": blocks}
                )
                record.update(
                    {
                        "status": "ready",
                        "fulltext_request_hash": text_key,
                        "block_count": len(blocks),
                    }
                )
                successes += 1
            except (httpx.HTTPError, OfflineCacheMiss, ET.ParseError, ValueError) as error:
                record.update({"status": "unavailable", "reason": str(error)})
            manifest.append(record)
            write_jsonl(output / "manifest.jsonl", manifest)
            if successes >= limit:
                break
        next_cursor = response.get("nextCursorMark")
        if not hits or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
    metrics = {
        "query": query,
        "sort": "FIRST_PDATE_D desc",
        "limit": limit,
        "retrieved_fulltexts": successes,
        "attempted_fulltexts": len(manifest),
        "hit_count": response.get("hitCount"),
        "search_request_hashes": search_hashes,
        "completed_at": timestamp(),
    }
    write_json(output / "metrics.json", metrics)
    return metrics
