"""Aggregate cached measurements into per-compound and per-tier coverage."""

from collections import Counter
from dataclasses import dataclass, field

from src.any_fungus_coverage.endpoints import (
    ENDPOINT_GROUPS,
    endpoint_group,
    is_convertible,
)
from src.any_fungus_coverage.inputs import Cache, molecules_to_compounds
from src.any_fungus_coverage.tiers import AssayTier


@dataclass(frozen=True)
class Measurement:
    """One cached activity joined to one compound and one tier.

    Attributes:
        compound_id: Source structure InChIKey.
        tier: The tier this row counts towards.
        activity_id: ChEMBL activity identifier.
        assay_chembl_id: ChEMBL assay identifier.
        molecule_chembl_id: ChEMBL molecule identifier.
        organism: Assay organism as recorded by ChEMBL.
        scientific_name: Resolved scientific name of the assay taxon.
        standard_type: ChEMBL standard type.
        standard_value: ChEMBL standard value as recorded.
        standard_units: ChEMBL standard units.
        standard_relation: ChEMBL standard relation, retained unaltered.
        endpoint: The assigned endpoint group.
        convertible: Whether the value carries a frozen molar magnitude.
        model_organism: Whether the taxon is a declared model organism.
        oomycete: Whether the taxon is an oomycete rather than a true fungus.
        ambiguous_role: Whether the taxon carries both human and crop roles.
        potential_cultivar: Whether the taxon is an unresolved broad record in
            a genus that can contain attine cultivars.
    """

    compound_id: str
    tier: str
    activity_id: int
    assay_chembl_id: str
    molecule_chembl_id: str
    organism: str
    scientific_name: str
    standard_type: str
    standard_value: str
    standard_units: str
    standard_relation: str
    endpoint: str
    convertible: bool
    model_organism: bool
    oomycete: bool
    ambiguous_role: bool
    potential_cultivar: bool


@dataclass
class TierSummary:
    """Coverage of one tier within one population.

    Attributes:
        tier: The tier summarised.
        compounds: Distinct compounds with at least one measurement.
        measurements: Total measurement records.
        convertible: Measurements carrying a frozen molar magnitude.
        non_convertible: Measurements that do not.
        endpoints: Measurement count by endpoint group.
        organisms: Distinct assay taxa contributing.
        model_measurements: Measurements on declared model organisms.
        model_compounds: Distinct compounds measured on model organisms.
        non_model_measurements: Measurements on every other taxon in the tier.
        non_model_compounds: Distinct compounds on every other taxon.
        oomycete_measurements: Measurements on oomycete taxa.
        oomycete_compounds: Distinct compounds measured on oomycete taxa.
    """

    tier: str
    compounds: int = 0
    measurements: int = 0
    convertible: int = 0
    non_convertible: int = 0
    endpoints: Counter = field(default_factory=Counter)
    organisms: int = 0
    model_measurements: int = 0
    model_compounds: int = 0
    non_model_measurements: int = 0
    non_model_compounds: int = 0
    oomycete_measurements: int = 0
    oomycete_compounds: int = 0


def build_measurements(
    cache: Cache,
    assigned: dict[str, AssayTier],
) -> list[Measurement]:
    """Join cached activities to compounds and tiers.

    An activity on an assay assigned to several tiers yields one row per tier,
    so tier counts overlap by construction and need not sum.

    Args:
        cache: The loaded cache.
        assigned: Tier assignment by assay ChEMBL identifier.

    Returns:
        Every measurement row, one per compound per activity per tier.
    """
    inverse = molecules_to_compounds(cache.compound_to_molecules)
    rows: list[Measurement] = []
    for activity in cache.activities:
        tier_record = assigned.get(activity["assay_chembl_id"])
        if tier_record is None:
            continue
        molecule = activity.get("molecule_chembl_id") or ""
        compounds = inverse.get(molecule, set())
        if not compounds:
            continue
        standard_type = activity.get("standard_type") or ""
        standard_units = activity.get("standard_units") or ""
        group = endpoint_group(activity.get("standard_type"), activity.get("standard_units"))
        convertible = is_convertible(activity.get("standard_value"), activity.get("standard_units"))
        for compound in sorted(compounds):
            for tier in tier_record.tiers:
                rows.append(
                    Measurement(
                        compound_id=compound,
                        tier=tier,
                        activity_id=int(activity["activity_id"]),
                        assay_chembl_id=activity["assay_chembl_id"],
                        molecule_chembl_id=molecule,
                        organism=tier_record.organism,
                        scientific_name=tier_record.scientific_name,
                        standard_type=standard_type,
                        standard_value=str(activity.get("standard_value") or ""),
                        standard_units=standard_units,
                        standard_relation=str(activity.get("standard_relation") or ""),
                        endpoint=group,
                        convertible=convertible,
                        model_organism=tier_record.model_organism,
                        oomycete=tier_record.oomycete,
                        ambiguous_role=tier_record.ambiguous_role,
                        potential_cultivar=tier_record.potential_cultivar,
                    )
                )
    return rows


def summarise_tier(rows: list[Measurement], tier: str) -> TierSummary:
    """Summarise one tier within one population.

    Args:
        rows: Measurement rows already restricted to the population.
        tier: The tier to summarise.

    Returns:
        The tier summary, with zero-valued fields when the tier is empty.
    """
    selected = [row for row in rows if row.tier == tier]
    summary = TierSummary(tier=tier)
    summary.measurements = len(selected)
    summary.compounds = len({row.compound_id for row in selected})
    summary.organisms = len({row.scientific_name or row.organism for row in selected})
    summary.convertible = sum(1 for row in selected if row.convertible)
    summary.non_convertible = summary.measurements - summary.convertible
    summary.endpoints = Counter(row.endpoint for row in selected)
    for group in ENDPOINT_GROUPS:
        summary.endpoints.setdefault(group, 0)
    model = [row for row in selected if row.model_organism]
    other = [row for row in selected if not row.model_organism]
    summary.model_measurements = len(model)
    summary.model_compounds = len({row.compound_id for row in model})
    summary.non_model_measurements = len(other)
    summary.non_model_compounds = len({row.compound_id for row in other})
    oomycete = [row for row in selected if row.oomycete]
    summary.oomycete_measurements = len(oomycete)
    summary.oomycete_compounds = len({row.compound_id for row in oomycete})
    return summary


def restrict(rows: list[Measurement], compounds: set[str]) -> list[Measurement]:
    """Restrict measurement rows to a set of compounds.

    Args:
        rows: Measurement rows.
        compounds: Compound identifiers to retain.

    Returns:
        The rows whose compound is in the set.
    """
    return [row for row in rows if row.compound_id in compounds]


def taxon_counts(rows: list[Measurement], tier: str) -> list[tuple[str, int, int]]:
    """Count measurements and compounds per assay taxon within a tier.

    Args:
        rows: Measurement rows already restricted to the population.
        tier: The tier to break down.

    Returns:
        Triples of taxon name, measurement count and compound count, ordered by
        descending measurement count then by name.
    """
    selected = [row for row in rows if row.tier == tier]
    measurements: Counter = Counter()
    compounds: dict[str, set[str]] = {}
    for row in selected:
        name = row.scientific_name or row.organism or "unresolved"
        measurements[name] += 1
        compounds.setdefault(name, set()).add(row.compound_id)
    return sorted(
        ((name, count, len(compounds[name])) for name, count in measurements.items()),
        key=lambda item: (-item[1], item[0]),
    )
