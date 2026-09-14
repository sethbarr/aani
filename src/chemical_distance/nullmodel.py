"""Ask whether the tested compounds occupy a distinctive region of the corpus.

The headline contrast between classified and unknown compounds cannot separate
chemical novelty from the tautology that co-assayed compounds resemble one
another, because the classified compounds are themselves reference members.
This module removes that confound. It compares the real tested set against
random subsets of the same corpus, drawn at the same size, and scores every
subset by how far it leaves the compounds it does not contain.

Under the null of testing unrelated to chemistry, the tested set is an ordinary
random subset and the remainder sits no further away than chance. A tested set
concentrated on a narrow chemical region leaves the remainder further away than
chance, which is what the chemical-novelty explanation predicts.

Nothing here produces or approaches an activity value. Every quantity is a
distance between structures.
"""

from dataclasses import dataclass

import numpy as np

from src.chemical_distance.fingerprints import MORGAN_BITS, Structure


@dataclass(frozen=True)
class NullResult:
    """Outcome of the random-reference permutation control.

    Attributes:
        observed: Median nearest-neighbour similarity of the compounds outside
            the real tested set, measured against that tested set.
        null_median: Median of the permuted medians.
        null_low: 2.5th percentile of the permuted medians.
        null_high: 97.5th percentile of the permuted medians.
        draws: Number of random subsets drawn.
        at_or_below: Draws whose median was at or below the observed value.
        p_value: Proportion of draws at or below the observed value, computed
            with the conventional plus-one correction so it is never zero.
        seed: Seed the draws were generated from.
    """

    observed: float
    null_median: float
    null_low: float
    null_high: float
    draws: int
    at_or_below: int
    p_value: float
    seed: int


@dataclass(frozen=True)
class RarefactionPoint:
    """Median nearest-neighbour similarity at one reference-set size.

    Attributes:
        size: Number of reference compounds drawn.
        median: Mean across draws of the median nearest-neighbour similarity.
        draws: Number of draws averaged, one when the full set was used.
    """

    size: int
    median: float
    draws: int


def bit_matrix(structures: list[Structure]) -> np.ndarray:
    """Pack fingerprints into a dense bit matrix.

    Args:
        structures: Structures in the order their rows should take.

    Returns:
        An array of shape (n, MORGAN_BITS) holding one row per structure.
    """
    packed = np.zeros((len(structures), MORGAN_BITS), dtype=np.uint8)
    for row, structure in enumerate(structures):
        for bit in structure.fingerprint.GetOnBits():
            packed[row, bit] = 1
    return packed


def similarity_matrix(structures: list[Structure]) -> np.ndarray:
    """Compute the full pairwise Tanimoto similarity matrix.

    This reproduces RDKit's Tanimoto exactly while allowing the permutation
    control to reuse one matrix across every draw. The intersection is computed
    in float32, which represents every reachable bit count exactly and lets the
    product run through the platform's tuned linear algebra.

    Args:
        structures: Structures in the order their rows should take.

    Returns:
        A square float32 array of pairwise Tanimoto similarities.
    """
    packed = bit_matrix(structures)
    counts = packed.sum(axis=1).astype(np.int32)
    dense = packed.astype(np.float32)
    intersection = (dense @ dense.T).astype(np.int32)
    union = counts[:, None] + counts[None, :] - intersection
    return np.where(union > 0, intersection / np.maximum(union, 1), 0.0).astype(np.float32)


def median_max_similarity(
    matrix: np.ndarray,
    queries: np.ndarray,
    references: np.ndarray,
) -> float:
    """Median over queries of the maximum similarity to any reference.

    Args:
        matrix: The pairwise similarity matrix.
        queries: Row indices of the query compounds.
        references: Row indices of the reference compounds.

    Returns:
        The median nearest-neighbour similarity, or 0.0 when either set is
        empty.
    """
    if queries.size == 0 or references.size == 0:
        return 0.0
    return float(np.median(matrix[np.ix_(queries, references)].max(axis=1)))


def permutation_null(
    matrix: np.ndarray,
    references: np.ndarray,
    draws: int,
    seed: int,
) -> NullResult:
    """Compare the real tested set against random subsets of the same size.

    Each draw takes a random subset of the corpus the size of the real tested
    set and measures how far it leaves every compound it does not contain. The
    observed statistic is built the same way, so the two are exactly comparable
    and no compound is ever its own neighbour.

    Args:
        matrix: The pairwise similarity matrix over the whole corpus.
        references: Row indices of the real tested compounds.
        draws: Number of random subsets to draw.
        seed: Seed for the draws.

    Returns:
        The permutation result.
    """
    total = matrix.shape[0]
    everything = np.arange(total)
    membership = np.zeros(total, dtype=bool)
    membership[references] = True
    observed = median_max_similarity(matrix, everything[~membership], references)

    generator = np.random.default_rng(seed)
    medians = np.empty(draws, dtype=np.float64)
    for index in range(draws):
        sampled = generator.choice(total, size=references.size, replace=False)
        mask = np.zeros(total, dtype=bool)
        mask[sampled] = True
        medians[index] = median_max_similarity(matrix, everything[~mask], sampled)

    at_or_below = int(np.count_nonzero(medians <= observed))
    return NullResult(
        observed=observed,
        null_median=float(np.median(medians)),
        null_low=float(np.percentile(medians, 2.5)),
        null_high=float(np.percentile(medians, 97.5)),
        draws=draws,
        at_or_below=at_or_below,
        p_value=(at_or_below + 1) / (draws + 1),
        seed=seed,
    )


def rarefaction(
    matrix: np.ndarray,
    references: np.ndarray,
    sizes: tuple[int, ...],
    draws: int,
    seed: int,
) -> tuple[RarefactionPoint, ...]:
    """Measure how the similarity rises as the reference set grows.

    This quantifies how much of the observed distance is an artefact of a small
    reference set, which bounds how far the headline numbers can be read.

    Args:
        matrix: The pairwise similarity matrix over the whole corpus.
        references: Row indices of the real tested compounds.
        sizes: Reference-set sizes to subsample, ascending.
        draws: Number of subsamples averaged at each size below the full set.
        seed: Seed for the subsamples.

    Returns:
        One point per requested size that does not exceed the reference set.
    """
    total = matrix.shape[0]
    everything = np.arange(total)
    membership = np.zeros(total, dtype=bool)
    membership[references] = True
    queries = everything[~membership]

    generator = np.random.default_rng(seed)
    points: list[RarefactionPoint] = []
    for size in sizes:
        if size > references.size:
            continue
        if size == references.size:
            points.append(
                RarefactionPoint(
                    size=size,
                    median=median_max_similarity(matrix, queries, references),
                    draws=1,
                )
            )
            continue
        values = [
            median_max_similarity(
                matrix, queries, generator.choice(references, size=size, replace=False)
            )
            for _ in range(draws)
        ]
        points.append(RarefactionPoint(size=size, median=float(np.mean(values)), draws=draws))
    return tuple(points)
