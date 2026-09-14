"""Load the frozen chemistry and bioactivity outputs into plain records."""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

ELIGIBLE_VERIFICATION = "exact_assay_organism_and_type"
CLASSIFIED_LABELS = ("active", "inactive")


@dataclass(frozen=True)
class PlantCompound:
    """A structure imported from the plant occurrence stage.

    Attributes:
        compound_id: InChIKey used as the pipeline compound identifier.
        smiles: Canonical SMILES recorded with the occurrence.
        genera: Source genera the structure was reported from.
        label: Frozen activity label, one of active, inactive or unknown.
        discordant: Whether the frozen labelling flagged discordant evidence.
    """

    compound_id: str
    smiles: str
    genera: tuple[str, ...]
    label: str
    discordant: bool


@dataclass(frozen=True)
class TestedCompound:
    """A compound carrying at least one eligible antifungal measurement.

    Attributes:
        compound_id: InChIKey used as the pipeline compound identifier.
        smiles: Canonical SMILES recorded with the occurrence.
        molecule_chembl_id: ChEMBL molecule identifier seen in the retrieval.
        organisms: Fungal assay organisms the compound was measured against.
        label: Frozen activity label, one of active, inactive or unknown.
    """

    compound_id: str
    smiles: str
    molecule_chembl_id: str
    organisms: tuple[str, ...]
    label: str


@dataclass
class GenusBehaviour:
    """Behavioural direction recorded for a source genus.

    Attributes:
        genus: Accepted genus name.
        direction: Behavioural outcome, one of accepted, rejected or conflict.
        primary_eligible: Whether the genus enters primary inference.
    """

    genus: str
    direction: str
    primary_eligible: bool


@dataclass
class AssayInventory:
    """The complete eligible functional assay inventory.

    Attributes:
        organism_by_assay: Assay ChEMBL identifier mapped to assay organism.
        requested_organisms: Organisms the retrieval asked ChEMBL for.
    """

    organism_by_assay: dict[str, str] = field(default_factory=dict)
    requested_organisms: tuple[str, ...] = ()

    def organisms(self) -> tuple[str, ...]:
        """Return the distinct assay organisms present in the inventory."""
        return tuple(sorted(set(self.organism_by_assay.values())))


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSON Lines file into a list of dictionaries.

    Args:
        path: File to read.

    Returns:
        One dictionary per non-empty line.
    """
    records: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def load_assay_inventory(path: Path, requested: tuple[str, ...]) -> AssayInventory:
    """Load the frozen eligible functional assay inventory.

    Args:
        path: Path to eligible_assays.jsonl.
        requested: Organisms the analysis brief asked for.

    Returns:
        The assay inventory keyed by assay ChEMBL identifier.
    """
    organism_by_assay = {
        record["assay_chembl_id"]: record["assay_organism"] for record in read_jsonl(path)
    }
    return AssayInventory(organism_by_assay=organism_by_assay, requested_organisms=requested)


def load_labels(path: Path) -> dict[str, dict]:
    """Load the frozen per-compound activity labels.

    Args:
        path: Path to labels.jsonl.

    Returns:
        Compound identifier mapped to its frozen label record.
    """
    return {record["compound_id"]: record for record in read_jsonl(path)}


def load_structures(path: Path) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    """Load canonical SMILES and source genera from the occurrence stage.

    Args:
        path: Path to occurrences.jsonl.

    Returns:
        A pair of the SMILES by compound identifier and the sorted genera by
        compound identifier. Compounds without any SMILES are absent from the
        first mapping and still present in the second.
    """
    smiles: dict[str, str] = {}
    genera: dict[str, set[str]] = {}
    for record in read_jsonl(path):
        compound_id = record["compound_id"]
        genera.setdefault(compound_id, set()).add(record["genus"])
        candidate = record.get("canonical_smiles")
        if candidate and compound_id not in smiles:
            smiles[compound_id] = candidate
    sorted_genera = {key: tuple(sorted(value)) for key, value in genera.items()}
    return smiles, sorted_genera


def load_genus_behaviour(path: Path) -> dict[str, GenusBehaviour]:
    """Load the behavioural direction recorded for each source genus.

    Args:
        path: Path to the behaviour all_genera.csv table.

    Returns:
        Genus name mapped to its behavioural record.
    """
    behaviour: dict[str, GenusBehaviour] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            behaviour[row["genus"]] = GenusBehaviour(
                genus=row["genus"],
                direction=row["outcome"],
                primary_eligible=row["primary_eligible"].strip().lower() == "true",
            )
    return behaviour


def build_plant_compounds(
    smiles: dict[str, str],
    genera: dict[str, tuple[str, ...]],
    labels: dict[str, dict],
) -> list[PlantCompound]:
    """Assemble every imported plant structure with its frozen label.

    Args:
        smiles: Canonical SMILES by compound identifier.
        genera: Source genera by compound identifier.
        labels: Frozen label records by compound identifier.

    Returns:
        One record per imported compound, sorted by identifier.
    """
    compounds = [
        PlantCompound(
            compound_id=compound_id,
            smiles=smiles.get(compound_id, ""),
            genera=genera.get(compound_id, ()),
            label=labels[compound_id]["label"],
            discordant=bool(labels[compound_id]["discordant"]),
        )
        for compound_id in sorted(labels)
    ]
    return compounds


def build_tested_compounds(
    measurements_path: Path,
    inventory: AssayInventory,
    smiles: dict[str, str],
    labels: dict[str, dict],
) -> list[TestedCompound]:
    """Assemble the compounds carrying an eligible antifungal measurement.

    A compound qualifies when the bioactivity stage retrieved at least one
    measurement whose assay was verified against the complete eligible
    functional assay inventory for the target fungi.

    Args:
        measurements_path: Path to measurements.jsonl.
        inventory: The eligible functional assay inventory.
        smiles: Canonical SMILES by compound identifier.
        labels: Frozen label records by compound identifier.

    Returns:
        One record per tested compound, sorted by identifier.
    """
    organisms: dict[str, set[str]] = {}
    chembl_ids: dict[str, str] = {}
    for record in read_jsonl(measurements_path):
        if record.get("assay_verification") != ELIGIBLE_VERIFICATION:
            continue
        compound_id = record["compound_id"]
        organism = inventory.organism_by_assay[record["assay_chembl_id"]]
        organisms.setdefault(compound_id, set()).add(organism)
        chembl_ids.setdefault(compound_id, record.get("molecule_chembl_id") or "")
    return [
        TestedCompound(
            compound_id=compound_id,
            smiles=smiles.get(compound_id, ""),
            molecule_chembl_id=chembl_ids[compound_id],
            organisms=tuple(sorted(organisms[compound_id])),
            label=labels[compound_id]["label"],
        )
        for compound_id in sorted(organisms)
    ]
