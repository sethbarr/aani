"""Build the ranked test-priority table.

The table carries no activity label, probability or transferred annotation of
any kind. It reports distance from the tested reference set and nothing that
could be read as a prediction of antifungal activity.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from src.chemical_distance.convention import DOMAIN_CONVENTION
from src.chemical_distance.datasets import GenusBehaviour, PlantCompound

if TYPE_CHECKING:
    from src.chemical_distance.fingerprints import Structure
    from src.chemical_distance.neighbours import Neighbour

DISCLAIMER = (
    "# Ranked by chemical novelty relative to tested compounds. "
    "This is NOT an activity prediction."
)

COLUMNS = (
    "rank",
    "compound_id",
    "chemical_novelty_distance_to_tested_set",
    "nearest_tested_tanimoto",
    "nearest_tested_compound_id",
    "nearest_tested_chembl_id",
    "nearest_classified_tanimoto",
    "outside_conventional_domain_below_0.4",
    "heavy_atom_count",
    "murcko_scaffold",
    "scaffold_present_in_tested_set",
    "source_genera",
    "genus_behavioural_directions",
    "structure_available",
    "already_has_eligible_measurement",
    "tested_compounds_compared",
)


@dataclass(frozen=True)
class PriorityRow:
    """One ranked unknown-activity compound.

    Attributes:
        compound: The imported plant compound.
        structure: Its parsed structure, or None when unresolvable.
        tested: Nearest neighbour in the tested reference set, or None.
        classified: Nearest neighbour in the classified subset, or None.
        scaffold_in_reference: Whether its scaffold occurs in the tested set.
        already_tested: Whether it already carries an eligible measurement.
        chembl_id: ChEMBL identifier of the nearest tested neighbour.
    """

    compound: PlantCompound
    structure: Structure | None
    tested: Neighbour | None
    classified: Neighbour | None
    scaffold_in_reference: bool
    already_tested: bool
    chembl_id: str


def sort_key(row: PriorityRow) -> tuple[int, float, str]:
    """Order rows by descending chemical novelty.

    Rows without a resolvable structure carry no distance and are placed last.

    Args:
        row: The row to order.

    Returns:
        A sort key of resolvability, similarity and compound identifier.
    """
    if row.tested is None:
        return (1, 0.0, row.compound.compound_id)
    return (0, row.tested.similarity, row.compound.compound_id)


def format_row(row: PriorityRow, rank: int, behaviour: dict[str, GenusBehaviour]) -> dict[str, str]:
    """Render one ranked row as CSV fields.

    Args:
        row: The row to render.
        rank: Its one-based rank.
        behaviour: Behavioural direction by genus.

    Returns:
        A mapping of column name to formatted value.
    """
    genera = row.compound.genera
    directions = [
        behaviour[genus].direction if genus in behaviour else "not_recorded" for genus in genera
    ]
    similarity = "" if row.tested is None else f"{row.tested.similarity:.4f}"
    distance = "" if row.tested is None else f"{1.0 - row.tested.similarity:.4f}"
    outside = "" if row.tested is None else str(row.tested.similarity < DOMAIN_CONVENTION)
    classified = "" if row.classified is None else f"{row.classified.similarity:.4f}"
    return {
        "rank": str(rank),
        "compound_id": row.compound.compound_id,
        "chemical_novelty_distance_to_tested_set": distance,
        "nearest_tested_tanimoto": similarity,
        "nearest_tested_compound_id": "" if row.tested is None else row.tested.neighbour_id,
        "nearest_tested_chembl_id": row.chembl_id,
        "nearest_classified_tanimoto": classified,
        "outside_conventional_domain_below_0.4": outside,
        "heavy_atom_count": "" if row.structure is None else str(row.structure.heavy_atoms),
        "murcko_scaffold": "" if row.structure is None else row.structure.scaffold,
        "scaffold_present_in_tested_set": str(row.scaffold_in_reference),
        "source_genera": ";".join(genera),
        "genus_behavioural_directions": ";".join(directions),
        "structure_available": str(row.structure is not None),
        "already_has_eligible_measurement": str(row.already_tested),
        "tested_compounds_compared": "" if row.tested is None else str(row.tested.comparisons),
    }


def write_priority_csv(
    rows: list[PriorityRow],
    behaviour: dict[str, GenusBehaviour],
    path: Path,
) -> int:
    """Write the ranked test-priority table.

    Args:
        rows: The rows to rank and write.
        behaviour: Behavioural direction by genus.
        path: Destination CSV path.

    Returns:
        The number of data rows written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=sort_key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(f"{DISCLAIMER}\n")
        writer = csv.DictWriter(handle, fieldnames=list(COLUMNS))
        writer.writeheader()
        for rank, row in enumerate(ordered, start=1):
            writer.writerow(format_row(row, rank, behaviour))
    return len(ordered)
