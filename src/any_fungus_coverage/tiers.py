"""Assign cached assays to the predeclared coverage tiers.

Tier membership is taxonomic. An assay belongs to a tier when its assay taxon
is the anchor node for that tier or a descendant of one, established through
the cached lineage identifiers rather than through organism names.
"""

from dataclasses import dataclass

from src.any_fungus_coverage.inputs import FUNGI_TAX_ID, Cache

TIERS = ("T4", "T1", "T2", "T3", "T5")
REPORT_ORDER = ("T4", "T1", "T2", "T3", "T5")


@dataclass(frozen=True)
class AssayTier:
    """The tier membership and flags resolved for one assay.

    Attributes:
        assay_chembl_id: The assay identifier.
        tiers: Tiers the assay belongs to, possibly more than one.
        organism: Assay organism name as recorded by ChEMBL.
        tax_id: Assay taxon identifier.
        scientific_name: Resolved scientific name of the assay taxon.
        fungal: Whether the taxon sits under the Fungi node.
        oomycete: Whether the taxon sits under the Oomycota node.
        model_organism: Whether the taxon is a declared model organism.
        ambiguous_role: Whether the taxon carries both human and crop roles.
        potential_cultivar: Whether the taxon is an unresolved broad record in
            a genus that can contain attine cultivars.
    """

    assay_chembl_id: str
    tiers: tuple[str, ...]
    organism: str
    tax_id: str
    scientific_name: str
    fungal: bool
    oomycete: bool
    model_organism: bool
    ambiguous_role: bool
    potential_cultivar: bool


@dataclass
class TierIndex:
    """Anchor taxon identifiers by tier and flag group.

    Attributes:
        groups: Anchor taxon identifiers by group name.
        unresolved: Anchor names that no taxonomy lookup resolved.
    """

    groups: dict[str, set[str]]
    unresolved: dict[str, list[str]]


def build_index(cache: Cache) -> TierIndex:
    """Resolve every anchor name to its taxon identifier.

    Args:
        cache: The loaded cache.

    Returns:
        The anchor index, recording anchors that did not resolve.
    """
    groups: dict[str, set[str]] = {}
    unresolved: dict[str, list[str]] = {}
    for group, names in cache.anchor_names.items():
        resolved: set[str] = set()
        missing: list[str] = []
        for name in names:
            anchor = cache.anchors.get(name)
            if anchor is not None and anchor.get("status") == "resolved":
                resolved.add(str(anchor["tax_id"]))
            else:
                missing.append(name)
        groups[group] = resolved
        if missing:
            unresolved[group] = missing
    return TierIndex(groups=groups, unresolved=unresolved)


def lineage_ids(cache: Cache, tax_id: str) -> set[str] | None:
    """Return the lineage identifiers of a taxon, including the taxon itself.

    Args:
        cache: The loaded cache.
        tax_id: Taxon identifier to resolve.

    Returns:
        The lineage identifiers, or None when the taxon did not resolve.
    """
    record = cache.taxonomy.get(f"id:{tax_id}")
    if record is None or record.get("status") != "resolved":
        return None
    return set(record["lineage_ids"])


def classify_assay(cache: Cache, index: TierIndex, assay: dict) -> AssayTier | None:
    """Assign one assay to its tiers.

    T1 membership excludes the assay from T2, as the amendment requires. An
    assay outside every named role tier joins T5 when its taxon is fungal.

    Args:
        cache: The loaded cache.
        index: The resolved anchor index.
        assay: The cached assay record.

    Returns:
        The tier assignment, or None when the assay has no resolved fungal or
        role-bearing taxon.
    """
    raw = assay.get("assay_tax_id")
    if raw is None:
        return None
    tax_id = str(raw)
    lineage = lineage_ids(cache, tax_id)
    if lineage is None:
        return None

    tiers: list[str] = []
    if lineage & index.groups["T1"]:
        tiers.append("T1")
    elif lineage & index.groups["T2"]:
        tiers.append("T2")
    if lineage & index.groups["T3"]:
        tiers.append("T3")
    if lineage & index.groups["T4"]:
        tiers.append("T4")
    fungal = FUNGI_TAX_ID in lineage
    if fungal and not tiers:
        tiers.append("T5")
    if not tiers:
        return None

    record = cache.taxonomy[f"id:{tax_id}"]
    in_t4 = "T4" in tiers
    return AssayTier(
        assay_chembl_id=assay["assay_chembl_id"],
        tiers=tuple(tiers),
        organism=assay.get("assay_organism") or "",
        tax_id=tax_id,
        scientific_name=record.get("scientific_name") or "",
        fungal=fungal,
        oomycete=bool(lineage & index.groups["oomycete"]),
        model_organism=bool(lineage & index.groups["model"]),
        ambiguous_role=bool(lineage & index.groups["fusarium"]),
        potential_cultivar=bool(lineage & index.groups["potential_cultivar"]) and not in_t4,
    )


def classify_assays(cache: Cache, index: TierIndex) -> dict[str, AssayTier]:
    """Assign every cached assay to its tiers.

    Args:
        cache: The loaded cache.
        index: The resolved anchor index.

    Returns:
        Tier assignment by assay ChEMBL identifier, omitting assays that carry
        no resolved fungal or role-bearing taxon.
    """
    assigned: dict[str, AssayTier] = {}
    for assay in cache.assays.values():
        result = classify_assay(cache, index, assay)
        if result is not None:
            assigned[result.assay_chembl_id] = result
    return assigned


def multi_tier_organisms(assigned: dict[str, AssayTier]) -> dict[str, tuple[str, ...]]:
    """Find assay taxa that carry more than one tier.

    Args:
        assigned: Tier assignment by assay ChEMBL identifier.

    Returns:
        Tiers by scientific name for every taxon in more than one tier.
    """
    by_taxon: dict[str, set[str]] = {}
    names: dict[str, str] = {}
    for item in assigned.values():
        by_taxon.setdefault(item.tax_id, set()).update(item.tiers)
        names[item.tax_id] = item.scientific_name or item.organism
    return {
        names[tax_id]: tuple(sorted(tiers))
        for tax_id, tiers in by_taxon.items()
        if len(tiers) > 1
    }
