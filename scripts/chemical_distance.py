"""Measure how far untested plant structures sit from tested compounds.

This run answers why most mapped plant structures carry no eligible antifungal
measurement, by measuring their chemical distance from the compounds that do.
It is offline, uses RDKit only, and produces no predicted activity of any kind.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import rdkit

from src.chemical_distance.convention import DOMAIN_CONVENTION
from src.chemical_distance.datasets import (
    CLASSIFIED_LABELS,
    GenusBehaviour,
    PlantCompound,
    TestedCompound,
    build_plant_compounds,
    build_tested_compounds,
    load_assay_inventory,
    load_genus_behaviour,
    load_labels,
    load_structures,
)
from src.chemical_distance.fingerprints import (
    MORGAN_BITS,
    MORGAN_RADIUS,
    Structure,
    build_structures,
    morgan_generator,
)
from src.chemical_distance.neighbours import (
    Distribution,
    Neighbour,
    describe,
    nearest_neighbours,
    scaffold_overlap,
)
from src.chemical_distance.summary import (
    GenusRow,
    Report,
    ScaffoldOverlap,
    write_summary,
)
from src.chemical_distance.tables import PriorityRow, write_priority_csv

ROOT = Path(__file__).resolve().parents[1]
CHEMISTRY = ROOT / "data/processed/chemistry/occurrences.jsonl"
LABELS = ROOT / "data/processed/bioactivity/labels.jsonl"
MEASUREMENTS = ROOT / "data/processed/bioactivity/measurements.jsonl"
ASSAYS = ROOT / "data/processed/bioactivity/eligible_assays.jsonl"
BEHAVIOUR = ROOT / "data/processed/behaviour/all_genera.csv"
OUTPUT = ROOT / "results/chemical_distance"

LOW_COMPLEXITY_FLOOR = 6

REQUESTED_ORGANISMS = (
    "Candida albicans",
    "Cryptococcus neoformans",
    "Candida auris",
    "Aspergillus fumigatus",
)


@dataclass
class Inputs:
    """Everything loaded from the frozen pipeline outputs.

    Attributes:
        plants: Every imported plant structure with its frozen label.
        tested: Compounds carrying an eligible antifungal measurement.
        behaviour: Behavioural direction by genus.
        organisms: Assay organisms present in the eligible inventory.
        eligible_assays: Size of the eligible functional assay inventory.
    """

    plants: list[PlantCompound]
    tested: list[TestedCompound]
    behaviour: dict[str, GenusBehaviour]
    organisms: tuple[str, ...]
    eligible_assays: int


def load_inputs() -> Inputs:
    """Load every frozen input this analysis reads.

    Returns:
        The loaded inputs.
    """
    inventory = load_assay_inventory(ASSAYS, REQUESTED_ORGANISMS)
    labels = load_labels(LABELS)
    smiles, genera = load_structures(CHEMISTRY)
    return Inputs(
        plants=build_plant_compounds(smiles, genera, labels),
        tested=build_tested_compounds(MEASUREMENTS, inventory, smiles, labels),
        behaviour=load_genus_behaviour(BEHAVIOUR),
        organisms=inventory.organisms(),
        eligible_assays=len(inventory.organism_by_assay),
    )


def select_structures(
    compound_ids: list[str], structures: dict[str, Structure]
) -> list[Structure]:
    """Select the resolved structures for a set of compounds.

    Args:
        compound_ids: Compound identifiers to select.
        structures: Resolved structures by compound identifier.

    Returns:
        The resolved structures, skipping unresolvable compounds.
    """
    return [structures[key] for key in compound_ids if key in structures]


def similarities(neighbours: dict[str, Neighbour], keys: list[str]) -> list[float]:
    """Collect nearest-neighbour similarities for a set of compounds.

    Args:
        neighbours: Nearest neighbour by compound identifier.
        keys: Compound identifiers to collect.

    Returns:
        The similarities, skipping compounds with no neighbour recorded.
    """
    return [neighbours[key].similarity for key in keys if key in neighbours]


def overlap_of(queries: list[Structure], references: list[Structure]) -> ScaffoldOverlap:
    """Compute scaffold overlap between a query set and a reference set.

    Args:
        queries: The query structures.
        references: The reference structures.

    Returns:
        The scaffold overlap summary.
    """
    total, shared, covered, acyclic = scaffold_overlap(queries, references)
    return ScaffoldOverlap(
        query_scaffolds=total,
        shared_scaffolds=shared,
        covered_compounds=covered,
        acyclic_compounds=acyclic,
    )


def genus_rows(
    unknown: list[PlantCompound],
    structures: dict[str, Structure],
    neighbours: dict[str, Neighbour],
    reference: list[Structure],
    behaviour: dict[str, GenusBehaviour],
) -> tuple[GenusRow, ...]:
    """Compute per-genus statistics for the unknown-activity compounds.

    Args:
        unknown: The unknown-activity compounds.
        structures: Resolved structures by compound identifier.
        neighbours: Nearest neighbour by compound identifier.
        reference: The tested reference structures.
        behaviour: Behavioural direction by genus.

    Returns:
        One row per source genus, ordered by genus name.
    """
    members: dict[str, list[str]] = {}
    for compound in unknown:
        for genus in compound.genera:
            members.setdefault(genus, []).append(compound.compound_id)
    rows: list[GenusRow] = []
    for genus in sorted(members):
        keys = members[genus]
        resolved = select_structures(keys, structures)
        total, shared, _, _ = scaffold_overlap(resolved, reference)
        direction = behaviour[genus].direction if genus in behaviour else "not_recorded"
        rows.append(
            GenusRow(
                genus=genus,
                direction=direction,
                distribution=describe(similarities(neighbours, keys)),
                scaffolds=total,
                shared_scaffolds=shared,
            )
        )
    return tuple(rows)


def build_verdict(
    never_tested: Distribution,
    already_tested: Distribution,
    classified: Distribution,
    overlap: int,
    overlap_total: int,
) -> str:
    """Compose the verdict on whether chemical novelty explains the gap.

    The verdict weighs the headline contrast against its own control. Compounds
    that were assayed but yielded no usable label belong to the reference set
    without carrying a label, so the distance between them and the classified
    compounds measures how much of the contrast is construction rather than
    discovery.

    Args:
        never_tested: Distribution for unknown compounds never assayed at all.
        already_tested: Distribution for unknown compounds assayed without a
            usable label.
        classified: Classified-compound distribution against the tested set.
        overlap: Distinct unknown scaffolds shared with the tested set.
        overlap_total: Distinct unknown scaffolds in total.

    Returns:
        One sentence stating the verdict, with the numbers it rests on.
    """
    gap = classified.median - never_tested.median
    control = abs(classified.median - already_tested.median)
    if gap <= 0.05:
        reading = (
            "chemical novelty does not explain the coverage gap, which is better "
            "attributed to where assay effort has historically been spent"
        )
    elif control < 0.5 * gap:
        reading = (
            "the distance tracks whether a compound has ever been assayed rather than "
            "whether its assay yielded a label, leaving the gap consistent with chemical "
            "novelty but not separable by this design from the tautology that co-assayed "
            "compounds resemble one another"
        )
    else:
        reading = (
            "the separation survives its own control, so chemical unfamiliarity is a "
            "credible part of why the untested structures went untested"
        )
    return (
        f"Never-assayed compounds sit at a median nearest-neighbour similarity of "
        f"{never_tested.median:.3f} to the tested set while classified compounds sit at "
        f"{classified.median:.3f}, a difference of {gap:+.3f}, but compounds that were "
        f"assayed and yielded no usable label sit at {already_tested.median:.3f}, and only "
        f"{overlap} of {overlap_total} distinct unknown scaffolds occur in the tested set "
        f"at all, so {reading}."
    )


def file_digest(path: Path) -> str:
    """Compute the SHA-256 digest of a file.

    Args:
        path: File to digest.

    Returns:
        The hexadecimal digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(path: Path, report: Report, rows: int) -> None:
    """Write the run manifest for this analysis.

    Args:
        path: Destination JSON path.
        report: The assembled report.
        rows: Number of ranked rows written.
    """
    inputs = [CHEMISTRY, LABELS, MEASUREMENTS, ASSAYS, BEHAVIOUR]
    manifest = {
        "analysis": "chemical_distance",
        "produces_activity_prediction": False,
        "offline": True,
        "rdkit_version": rdkit.__version__,
        "fingerprint": {
            "type": "Morgan",
            "radius": MORGAN_RADIUS,
            "bits": MORGAN_BITS,
        },
        "applicability_domain_convention": DOMAIN_CONVENTION,
        "self_excluded_from_reference": True,
        "requested_organisms": list(REQUESTED_ORGANISMS),
        "inventory_organisms": list(report.reference_organisms),
        "organisms_absent_from_inventory": list(report.missing_organisms),
        "reference_size": report.reference_size,
        "query_size": report.query_size,
        "ranked_rows": rows,
        "inputs": {
            str(item.relative_to(ROOT)): file_digest(item) for item in inputs
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def build_report(inputs: Inputs) -> tuple[Report, list[PriorityRow]]:
    """Run the whole measurement and assemble the report.

    Args:
        inputs: The loaded frozen inputs.

    Returns:
        The assembled report and the rows for the ranked table.
    """
    generator = morgan_generator()
    structures, _ = build_structures(
        [(item.compound_id, item.smiles) for item in inputs.plants], generator
    )
    unknown = [item for item in inputs.plants if item.label == "unknown"]
    classified = [item for item in inputs.plants if item.label in CLASSIFIED_LABELS]
    tested_ids = {item.compound_id for item in inputs.tested}
    chembl_by_id = {item.compound_id: item.molecule_chembl_id for item in inputs.tested}

    reference = select_structures(sorted(tested_ids), structures)
    classified_reference = select_structures([item.compound_id for item in classified], structures)
    unknown_structures = select_structures([item.compound_id for item in unknown], structures)
    classified_structures = classified_reference

    unknown_vs_tested = nearest_neighbours(unknown_structures, reference)
    classified_vs_tested = nearest_neighbours(classified_structures, reference)
    unknown_vs_classified = nearest_neighbours(unknown_structures, classified_reference)
    classified_vs_classified = nearest_neighbours(classified_structures, classified_reference)

    reference_scaffolds = {item.scaffold for item in reference if item.scaffold}
    rows = [
        PriorityRow(
            compound=item,
            structure=structures.get(item.compound_id),
            tested=unknown_vs_tested.get(item.compound_id),
            classified=unknown_vs_classified.get(item.compound_id),
            scaffold_in_reference=(
                item.compound_id in structures
                and bool(structures[item.compound_id].scaffold)
                and structures[item.compound_id].scaffold in reference_scaffolds
            ),
            already_tested=item.compound_id in tested_ids,
            chembl_id=chembl_by_id.get(
                unknown_vs_tested[item.compound_id].neighbour_id
                if item.compound_id in unknown_vs_tested
                else "",
                "",
            ),
        )
        for item in unknown
    ]

    unknown_distribution = describe([item.similarity for item in unknown_vs_tested.values()])
    never_tested_distribution = describe(
        [
            value.similarity
            for key, value in unknown_vs_tested.items()
            if key not in tested_ids
        ]
    )
    already_tested_distribution = describe(
        [value.similarity for key, value in unknown_vs_tested.items() if key in tested_ids]
    )
    classified_distribution = describe([item.similarity for item in classified_vs_tested.values()])
    unknown_overlap = overlap_of(unknown_structures, reference)
    labels = [item.label for item in inputs.tested]
    report = Report(
        reference_size=len(inputs.tested),
        reference_active=labels.count("active"),
        reference_inactive=labels.count("inactive"),
        reference_unknown=labels.count("unknown"),
        reference_resolved=len(reference),
        classified_resolved=len(classified_structures),
        reference_organisms=inputs.organisms,
        requested_organisms=REQUESTED_ORGANISMS,
        missing_organisms=tuple(
            item for item in REQUESTED_ORGANISMS if item not in inputs.organisms
        ),
        eligible_assays=inputs.eligible_assays,
        query_size=len(unknown),
        query_resolved=len(unknown_structures),
        query_unresolved=len(unknown) - len(unknown_structures),
        query_overlap=sum(1 for item in unknown if item.compound_id in tested_ids),
        query_low_complexity=sum(
            1 for item in unknown_structures if item.heavy_atoms < LOW_COMPLEXITY_FLOOR
        ),
        low_complexity_floor=LOW_COMPLEXITY_FLOOR,
        unknown_vs_tested=unknown_distribution,
        unknown_never_tested=never_tested_distribution,
        unknown_already_tested=already_tested_distribution,
        classified_vs_tested=classified_distribution,
        unknown_vs_classified=describe(
            [item.similarity for item in unknown_vs_classified.values()]
        ),
        classified_vs_classified=describe(
            [item.similarity for item in classified_vs_classified.values()]
        ),
        unknown_scaffolds=unknown_overlap,
        classified_scaffolds=overlap_of(classified_structures, reference),
        genus_rows=genus_rows(unknown, structures, unknown_vs_tested, reference, inputs.behaviour),
        verdict=build_verdict(
            never_tested_distribution,
            already_tested_distribution,
            classified_distribution,
            unknown_overlap.shared_scaffolds,
            unknown_overlap.query_scaffolds,
        ),
    )
    return report, rows


def main() -> None:
    """Run the analysis and write both outputs."""
    inputs = load_inputs()
    report, rows = build_report(inputs)
    written = write_priority_csv(rows, inputs.behaviour, OUTPUT / "test_priority.csv")
    write_summary(report, OUTPUT / "summary.md")
    write_manifest(OUTPUT / "run_manifest.json", report, written)
    print(f"reference={report.reference_size} query={report.query_size} ranked={written}")
    print(report.verdict)


if __name__ == "__main__":
    main()
