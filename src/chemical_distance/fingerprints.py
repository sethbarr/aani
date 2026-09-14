"""Morgan fingerprints and Bemis-Murcko scaffolds computed with RDKit."""

from dataclasses import dataclass

from rdkit import Chem, RDLogger
from rdkit.Chem import rdFingerprintGenerator
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit.DataStructs.cDataStructs import ExplicitBitVect

MORGAN_RADIUS = 2
MORGAN_BITS = 2048

RDLogger.DisableLog("rdApp.*")


@dataclass(frozen=True)
class Structure:
    """A parsed structure with its fingerprint and scaffold.

    Attributes:
        compound_id: InChIKey used as the pipeline compound identifier.
        fingerprint: Morgan fingerprint as an explicit bit vector.
        scaffold: Bemis-Murcko scaffold SMILES, empty when the molecule has no
            ring system and therefore no Murcko scaffold.
        heavy_atoms: Heavy atom count, which bounds how many Morgan bits the
            structure can set and so how meaningful its similarity can be.
    """

    compound_id: str
    fingerprint: ExplicitBitVect
    scaffold: str
    heavy_atoms: int


def morgan_generator() -> rdFingerprintGenerator.FingerprintGenerator64:
    """Return the frozen Morgan fingerprint generator.

    Returns:
        A generator configured for radius 2 and 2048 bits.
    """
    return rdFingerprintGenerator.GetMorganGenerator(radius=MORGAN_RADIUS, fpSize=MORGAN_BITS)


def parse_molecule(smiles: str) -> Chem.Mol | None:
    """Parse a SMILES string into a sanitised molecule.

    Args:
        smiles: Canonical SMILES, possibly empty.

    Returns:
        The parsed molecule, or None when the structure is absent or RDKit
        cannot sanitise it.
    """
    if not smiles:
        return None
    return Chem.MolFromSmiles(smiles)


def murcko_scaffold(molecule: Chem.Mol) -> str:
    """Compute the Bemis-Murcko scaffold SMILES of a molecule.

    Args:
        molecule: A sanitised RDKit molecule.

    Returns:
        The scaffold SMILES, empty when the molecule yields no scaffold.
    """
    scaffold = MurckoScaffold.GetScaffoldForMol(molecule)
    if scaffold is None or scaffold.GetNumAtoms() == 0:
        return ""
    return Chem.MolToSmiles(scaffold)


def build_structure(
    compound_id: str,
    smiles: str,
    generator: rdFingerprintGenerator.FingerprintGenerator64,
) -> Structure | None:
    """Build the fingerprint and scaffold for one compound.

    Args:
        compound_id: InChIKey used as the pipeline compound identifier.
        smiles: Canonical SMILES, possibly empty.
        generator: The frozen Morgan fingerprint generator.

    Returns:
        The parsed structure, or None when the structure is unresolvable.
    """
    molecule = parse_molecule(smiles)
    if molecule is None:
        return None
    return Structure(
        compound_id=compound_id,
        fingerprint=generator.GetFingerprint(molecule),
        scaffold=murcko_scaffold(molecule),
        heavy_atoms=molecule.GetNumHeavyAtoms(),
    )


def build_structures(
    entries: list[tuple[str, str]],
    generator: rdFingerprintGenerator.FingerprintGenerator64,
) -> tuple[dict[str, Structure], list[str]]:
    """Build fingerprints and scaffolds for many compounds.

    Args:
        entries: Pairs of compound identifier and canonical SMILES.
        generator: The frozen Morgan fingerprint generator.

    Returns:
        A pair of the resolved structures by compound identifier and the
        identifiers whose structure could not be resolved.
    """
    resolved: dict[str, Structure] = {}
    unresolved: list[str] = []
    for compound_id, smiles in entries:
        structure = build_structure(compound_id, smiles, generator)
        if structure is None:
            unresolved.append(compound_id)
        else:
            resolved[compound_id] = structure
    return resolved, unresolved
