"""Load the chemistry join, the bioactivity labels and the pinned LOTUS export.

Nothing here touches the network. The LOTUS export is the checksum-verified
gzip TSV already cached by the chemistry stage.
"""

import csv
import gzip
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

TESTED_LABELS = frozenset({"active", "inactive"})
TESTED_DEFINITION = (
    "A structure is tested when the bioactivity stage assigned it an active or inactive "
    "label: at least one ChEMBL measurement on a functional assay against Candida albicans, "
    "Cryptococcus neoformans or Aspergillus fumigatus, with an eligible endpoint, a molar "
    "unit and a potency readable against the frozen threshold (labels.jsonl, label != unknown)."
)
LOTUS_FIELDS = (
    "structureCleanedInchikey",
    "organismCleaned",
    "organismCleaned_dbTaxoTaxonRanks",
    "organismCleaned_dbTaxoTaxonomy",
    "referenceType",
    "referenceValue",
    "referenceCleanedDoi",
    "referenceCleanedPmcid",
    "referenceCleanedPmid",
)


@dataclass(frozen=True)
class Structure:
    """One mapped structure from the chemistry join.

    Attributes:
        compound_id: Identifier used by the bioactivity stage (the full InChIKey).
        inchikey: Full standard InChIKey.
        tested: Whether the bioactivity stage classified the structure.
        label: The bioactivity stage label: active, inactive or unknown.
    """

    compound_id: str
    inchikey: str
    tested: bool
    label: str


@dataclass(frozen=True)
class LotusRow:
    """The fields of one LOTUS structure-organism-reference row that matter here.

    Attributes:
        inchikey: Cleaned full InChIKey.
        organism: Cleaned organism name.
        genus: Genus from the aligned rank arrays, empty when absent.
        family: Family from the aligned rank arrays, empty when absent.
        reference: One identifier per distinct reference.
    """

    inchikey: str
    organism: str
    genus: str
    family: str
    reference: str


def file_sha256(path: Path) -> str:
    """Hash a file for the run manifest."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        block = stream.read(1 << 20)
        while block:
            digest.update(block)
            block = stream.read(1 << 20)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    """Read nonempty JSON Lines records."""
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def load_structures(occurrences: Path, labels: Path) -> list[Structure]:
    """Join the distinct structures of the chemistry stage to their bioactivity labels.

    Args:
        occurrences: The chemistry stage's occurrences.jsonl.
        labels: The bioactivity stage's labels.jsonl.

    Returns:
        One record per distinct InChIKey, in first-seen order.

    Raises:
        ValueError: If a structure has no bioactivity label, which would mean the
            two inputs come from different runs.
    """
    label_by_id = {row["compound_id"]: row["label"] for row in read_jsonl(labels)}
    structures: dict[str, Structure] = {}
    for row in read_jsonl(occurrences):
        key = row["inchikey"]
        if key in structures:
            continue
        compound_id = row.get("compound_id", key)
        if compound_id not in label_by_id:
            raise ValueError(
                f"No bioactivity label for {compound_id}; inputs are from different runs"
            )
        label = label_by_id[compound_id]
        structures[key] = Structure(compound_id, key, label in TESTED_LABELS, label)
    return list(structures.values())


def clean_value(value: str) -> str:
    """Treat LOTUS missing-value sentinels as missing."""
    text = value.strip()
    return "" if text in {"NA", "N/A", "NULL", "null"} else text


def reference_key(doi: str, pmcid: str, pmid: str, kind: str, value: str) -> str:
    """Identify a reference by its best curated identifier, falling back to the raw one.

    Args:
        doi: Cleaned DOI column.
        pmcid: Cleaned PMCID column.
        pmid: Cleaned PMID column.
        kind: Raw reference type column.
        value: Raw reference value column.

    Returns:
        A string that is equal for rows citing the same reference.
    """
    doi = clean_value(doi)
    if doi:
        return "doi:" + doi.lower()
    pmcid = clean_value(pmcid)
    if pmcid:
        return "pmcid:" + pmcid
    pmid = clean_value(pmid)
    if pmid:
        return "pmid:" + pmid
    return kind.strip() + ":" + value.strip()


def lineage_rank(ranks: str, taxa: str, rank: str) -> str:
    """Read one rank from LOTUS's aligned rank and taxon arrays without any lookup."""
    rank_list = ranks.split("|")
    taxon_list = taxa.split("|")
    if len(rank_list) != len(taxon_list):
        return ""
    for name, taxon in zip(rank_list, taxon_list, strict=True):
        if name == rank:
            return clean_value(taxon)
    return ""


def parse_lotus_row(row: list[str], index: dict[str, int]) -> LotusRow:
    """Convert one raw TSV row into the fields used for counting."""
    ranks = row[index["organismCleaned_dbTaxoTaxonRanks"]]
    taxa = row[index["organismCleaned_dbTaxoTaxonomy"]]
    return LotusRow(
        inchikey=clean_value(row[index["structureCleanedInchikey"]]),
        organism=clean_value(row[index["organismCleaned"]]),
        genus=lineage_rank(ranks, taxa, "genus"),
        family=lineage_rank(ranks, taxa, "family"),
        reference=reference_key(
            row[index["referenceCleanedDoi"]],
            row[index["referenceCleanedPmcid"]],
            row[index["referenceCleanedPmid"]],
            row[index["referenceType"]],
            row[index["referenceValue"]],
        ),
    )


def iter_lotus(export: Path, tally: dict[str, int] | None = None) -> Iterator[LotusRow]:
    """Stream every row of the complete LOTUS export.

    Args:
        export: The gzip TSV body cached by the chemistry stage.
        tally: Optional counter updated in place with ``scanned`` and
            ``malformed`` row counts, so the caller can report scan coverage.

    Yields:
        Parsed rows in file order. Rows whose field count differs from the
        header are counted as malformed and skipped.

    Raises:
        ValueError: If a required column is missing.
    """
    with gzip.open(export, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        header = next(reader)
        index = {name: position for position, name in enumerate(header)}
        missing = [name for name in LOTUS_FIELDS if name not in index]
        if missing:
            raise ValueError(f"LOTUS export is missing columns: {missing}")
        width = len(header)
        counts = tally if tally is not None else {}
        counts.setdefault("scanned", 0)
        counts.setdefault("malformed", 0)
        for row in reader:
            counts["scanned"] += 1
            if len(row) != width:
                counts["malformed"] += 1
                continue
            yield parse_lotus_row(row, index)


def locate_lotus_export(raw: Path, chemistry_manifest: Path) -> Path:
    """Find the cached export body named by the chemistry stage's run manifest.

    Args:
        raw: The data/raw directory.
        chemistry_manifest: The chemistry stage's run_manifest.json.

    Returns:
        Path to the cached gzip body.

    Raises:
        FileNotFoundError: If the cache does not hold the file.
        ValueError: If the cached bytes do not match the manifest checksum.
    """
    manifest = json.loads(chemistry_manifest.read_text(encoding="utf-8"))
    request_hash = manifest["download_request_hash"]
    path = raw / "chemistry_export" / "downloads" / f"{request_hash}.body"
    if not path.exists():
        raise FileNotFoundError(f"Cached LOTUS export not found: {path}")
    if file_sha256(path) != manifest["file_sha256"]:
        raise ValueError("Cached LOTUS export does not match the chemistry manifest checksum")
    return path
