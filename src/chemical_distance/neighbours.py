"""Nearest-neighbour similarity between query and reference structures."""

from dataclasses import dataclass

import numpy as np
from rdkit import DataStructs

from src.chemical_distance.convention import DOMAIN_CONVENTION
from src.chemical_distance.fingerprints import Structure


@dataclass(frozen=True)
class Neighbour:
    """The closest reference structure found for one query structure.

    Attributes:
        compound_id: Query compound identifier.
        similarity: Maximum Tanimoto similarity to any reference structure.
        neighbour_id: Identifier of the reference structure attaining it.
        comparisons: Number of reference structures actually compared.
    """

    compound_id: str
    similarity: float
    neighbour_id: str
    comparisons: int


@dataclass(frozen=True)
class Distribution:
    """Summary of a set of nearest-neighbour similarities.

    Attributes:
        count: Number of query structures summarised.
        median: Median nearest-neighbour Tanimoto similarity.
        first_quartile: Lower quartile of the similarities.
        third_quartile: Upper quartile of the similarities.
        minimum: Smallest nearest-neighbour similarity.
        maximum: Largest nearest-neighbour similarity.
        below_convention: Count of similarities below the domain convention.
        below_convention_percent: That count as a percentage of count.
    """

    count: int
    median: float
    first_quartile: float
    third_quartile: float
    minimum: float
    maximum: float
    below_convention: int
    below_convention_percent: float


def nearest_neighbour(
    query: Structure,
    references: list[Structure],
) -> Neighbour:
    """Find the most similar reference structure to one query structure.

    The query structure is excluded from its own reference set, so a compound
    that is itself part of the reference set is never its own neighbour.

    Args:
        query: The query structure.
        references: Candidate reference structures.

    Returns:
        The nearest neighbour found. The neighbour identifier is empty when no
        comparison is possible, and also when the best similarity is exactly
        zero, because a query sharing no fingerprint bit with any reference
        structure has no meaningful nearest neighbour to name.
    """
    candidates = [item for item in references if item.compound_id != query.compound_id]
    if not candidates:
        return Neighbour(
            compound_id=query.compound_id, similarity=0.0, neighbour_id="", comparisons=0
        )
    similarities = DataStructs.BulkTanimotoSimilarity(
        query.fingerprint, [item.fingerprint for item in candidates]
    )
    best = int(np.argmax(similarities))
    score = float(similarities[best])
    if score == 0.0:
        return Neighbour(
            compound_id=query.compound_id,
            similarity=0.0,
            neighbour_id="",
            comparisons=len(candidates),
        )
    return Neighbour(
        compound_id=query.compound_id,
        similarity=score,
        neighbour_id=candidates[best].compound_id,
        comparisons=len(candidates),
    )


def nearest_neighbours(
    queries: list[Structure],
    references: list[Structure],
) -> dict[str, Neighbour]:
    """Find the nearest reference structure for every query structure.

    Args:
        queries: The query structures.
        references: Candidate reference structures.

    Returns:
        Query compound identifier mapped to its nearest neighbour.
    """
    return {item.compound_id: nearest_neighbour(item, references) for item in queries}


def describe(similarities: list[float], convention: float = DOMAIN_CONVENTION) -> Distribution:
    """Summarise nearest-neighbour similarities.

    Args:
        similarities: Nearest-neighbour Tanimoto similarities.
        convention: Similarity below which a query is conventionally called
            outside the applicability domain of the reference set.

    Returns:
        The distribution summary. An empty input yields zero-valued fields.
    """
    if not similarities:
        return Distribution(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0.0)
    values = np.asarray(similarities, dtype=float)
    below = int(np.count_nonzero(values < convention))
    return Distribution(
        count=int(values.size),
        median=float(np.median(values)),
        first_quartile=float(np.percentile(values, 25)),
        third_quartile=float(np.percentile(values, 75)),
        minimum=float(values.min()),
        maximum=float(values.max()),
        below_convention=below,
        below_convention_percent=100.0 * below / float(values.size),
    )


def scaffold_overlap(
    queries: list[Structure],
    references: list[Structure],
) -> tuple[int, int, int, int]:
    """Count Bemis-Murcko scaffolds shared between query and reference sets.

    Args:
        queries: The query structures.
        references: The reference structures.

    Returns:
        A tuple of the number of distinct query scaffolds, the number of those
        also present in the reference set, the number of query structures whose
        scaffold is present in the reference set, and the number of query
        structures that yield no Murcko scaffold.
    """
    reference_scaffolds = {item.scaffold for item in references if item.scaffold}
    query_scaffolds = {item.scaffold for item in queries if item.scaffold}
    shared = query_scaffolds & reference_scaffolds
    covered = sum(1 for item in queries if item.scaffold and item.scaffold in reference_scaffolds)
    acyclic = sum(1 for item in queries if not item.scaffold)
    return len(query_scaffolds), len(shared), covered, acyclic
