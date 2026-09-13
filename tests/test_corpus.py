from src.corpus.europepmc import parse_fulltext


def test_parse_namespaced_xml_and_skip_references() -> None:
    """Parse namespaced JATS and omit bibliography content."""
    xml = b"""<article xmlns='urn:jats'><front><article-meta><abstract><p>Abstract text.</p></abstract></article-meta></front><body><sec><title>Choice</title><p>Atta accepted a plant.</p></sec><back><ref-list><ref><p>Hidden reference.</p></ref></ref-list></back></body></article>"""
    blocks = parse_fulltext(xml, "PMC1")
    assert [block["text"] for block in blocks] == ["Abstract text.", "Atta accepted a plant."]
    assert blocks[1]["section"] == "Body / Choice"
