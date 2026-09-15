"""Load the cached any-fungus retrieval from disk."""

import json
from dataclasses import dataclass, field
from pathlib import Path

FUNGI_TAX_ID = "4751"


@dataclass
class Cache:
    """Everything the aggregation reads from the cached retrieval.

    Attributes:
        activities: Every retrieved activity record.
        assays: Assay record by assay ChEMBL identifier.
        taxonomy: Resolved taxonomy record by taxon identifier.
        anchors: Resolved anchor record by anchor name.
        anchor_names: Anchor names by tier or flag group.
        compound_to_molecules: Molecule identifiers by compound InChIKey.
        service: The ChEMBL service descriptor recorded at retrieval.
        incomplete_pages: Cached pages whose status was not complete.
    """

    activities: list[dict]
    assays: dict[str, dict]
    taxonomy: dict[str, dict]
    anchors: dict[str, dict]
    anchor_names: dict[str, list[str]]
    compound_to_molecules: dict[str, list[str]]
    service: dict
    incomplete_pages: list[str] = field(default_factory=list)


def read_json(path: Path) -> dict | list:
    """Read a JSON document.

    Args:
        path: File to read.

    Returns:
        The decoded document.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def read_pages(directory: Path) -> tuple[list[dict], list[str]]:
    """Read every cached page in a directory.

    Args:
        directory: Directory holding numbered page files.

    Returns:
        A pair of the concatenated rows and the names of pages whose status was
        not complete.
    """
    rows: list[dict] = []
    incomplete: list[str] = []
    for path in sorted(directory.glob("*.json")):
        page = read_json(path)
        if page.get("status") != "complete":
            incomplete.append(path.name)
        rows.extend(page.get("rows", []))
    return rows, incomplete


def load_cache(base: Path) -> Cache:
    """Load the whole cached retrieval.

    Args:
        base: The any_fungus_coverage interim directory.

    Returns:
        The loaded cache.
    """
    activities, activity_gaps = read_pages(base / "activities")
    assay_rows, assay_gaps = read_pages(base / "assays")
    retrieval = read_json(base / "retrieval.json")
    return Cache(
        activities=activities,
        assays={row["assay_chembl_id"]: row for row in assay_rows},
        taxonomy=read_json(base / "taxonomy.json"),
        anchors=read_json(base / "anchors.json"),
        anchor_names=read_json(base / "anchor_names.json"),
        compound_to_molecules=retrieval["compound_to_molecules"],
        service=retrieval["service"],
        incomplete_pages=activity_gaps + assay_gaps,
    )


def molecules_to_compounds(compound_to_molecules: dict[str, list[str]]) -> dict[str, set[str]]:
    """Invert the compound-to-molecule mapping.

    A ChEMBL molecule can carry more than one source compound when distinct
    InChIKeys resolve to it, so the inverse maps to a set.

    Args:
        compound_to_molecules: Molecule identifiers by compound InChIKey.

    Returns:
        Compound InChIKeys by molecule identifier.
    """
    inverse: dict[str, set[str]] = {}
    for compound, molecules in compound_to_molecules.items():
        for molecule in molecules:
            inverse.setdefault(molecule, set()).add(compound)
    return inverse
