"""Permutation tests, effect sizes, stratification and power for occurrence breadth.

The permutation test follows the chemical-distance null model: a fixed seed,
``numpy.random.default_rng``, and a plus-one corrected p-value that is never zero.
"""

from dataclasses import dataclass

import numpy as np

MINIMUM_TESTED_PER_STRATUM = 5
STRATUM_LABELS = ("Q1 fewest references", "Q2", "Q3", "Q4 most references")


@dataclass(frozen=True)
class Comparison:
    """Tested versus untested on one occurrence metric.

    Attributes:
        metric: Name of the count compared.
        n_tested: Tested units.
        n_untested: Untested units.
        tested_median: Median of the tested counts.
        tested_iqr: 25th and 75th percentiles of the tested counts.
        untested_median: Median of the untested counts.
        untested_iqr: 25th and 75th percentiles of the untested counts.
        observed_difference: Tested median minus untested median.
        p_greater: One-sided permutation p for tested more widespread.
        p_two_sided: Two-sided permutation p on the absolute difference.
        rank_biserial: Rank-biserial correlation, positive when tested ranks higher.
        permutations: Number of label permutations drawn.
        seed: Seed of the draws.
    """

    metric: str
    n_tested: int
    n_untested: int
    tested_median: float
    tested_iqr: tuple[float, float]
    untested_median: float
    untested_iqr: tuple[float, float]
    observed_difference: float
    p_greater: float
    p_two_sided: float
    rank_biserial: float
    permutations: int
    seed: int


def iqr(values: np.ndarray) -> tuple[float, float]:
    """Return the 25th and 75th percentiles."""
    return float(np.percentile(values, 25)), float(np.percentile(values, 75))


def rank_biserial(tested: np.ndarray, untested: np.ndarray) -> float:
    """Rank-biserial correlation from the Mann-Whitney U with ties counted as half.

    Args:
        tested: Counts for tested units.
        untested: Counts for untested units.

    Returns:
        A value in [-1, 1]; positive when tested units tend to rank higher.
    """
    if tested.size == 0 or untested.size == 0:
        return float("nan")
    greater = np.count_nonzero(tested[:, None] > untested[None, :])
    equal = np.count_nonzero(tested[:, None] == untested[None, :])
    auc = (greater + 0.5 * equal) / (tested.size * untested.size)
    return float(2 * auc - 1)


def permuted_differences(
    values: np.ndarray, n_tested: int, permutations: int, seed: int
) -> np.ndarray:
    """Null distribution of the difference in medians under exchangeable labels.

    Args:
        values: Counts for every unit.
        n_tested: How many units carry the tested label.
        permutations: Number of draws.
        seed: Seed for the draws.

    Returns:
        Tested median minus untested median for each relabelling.
    """
    generator = np.random.default_rng(seed)
    total = values.size
    differences = np.empty(permutations, dtype=np.float64)
    for index in range(permutations):
        order = generator.permutation(total)
        sampled = values[order[:n_tested]]
        remainder = values[order[n_tested:]]
        differences[index] = np.median(sampled) - np.median(remainder)
    return differences


def compare(
    metric: str, tested: np.ndarray, untested: np.ndarray, permutations: int, seed: int
) -> Comparison:
    """Run the permutation test on the difference in medians and the effect size.

    Args:
        metric: Name of the count.
        tested: Counts for tested units.
        untested: Counts for untested units.
        permutations: Number of label permutations.
        seed: Seed for the draws.

    Returns:
        The comparison record.
    """
    observed = float(np.median(tested) - np.median(untested))
    values = np.concatenate([tested, untested])
    null = permuted_differences(values, tested.size, permutations, seed)
    at_or_above = int(np.count_nonzero(null >= observed))
    as_extreme = int(np.count_nonzero(np.abs(null) >= abs(observed)))
    return Comparison(
        metric=metric,
        n_tested=int(tested.size),
        n_untested=int(untested.size),
        tested_median=float(np.median(tested)),
        tested_iqr=iqr(tested),
        untested_median=float(np.median(untested)),
        untested_iqr=iqr(untested),
        observed_difference=observed,
        p_greater=(at_or_above + 1) / (permutations + 1),
        p_two_sided=(as_extreme + 1) / (permutations + 1),
        rank_biserial=rank_biserial(tested, untested),
        permutations=permutations,
        seed=seed,
    )


def reference_quartiles(references: np.ndarray) -> np.ndarray:
    """Assign every unit to a quartile of reference count, keeping ties together.

    Args:
        references: Distinct reference counts per unit.

    Returns:
        Stratum index 0-3 per unit. Boundaries are the 25th, 50th and 75th
        percentiles of the counts; units on a boundary go to the lower stratum,
        so strata can be unequal when the counts are heavily tied.
    """
    bounds = np.percentile(references, [25, 50, 75])
    return np.searchsorted(bounds, references, side="left").astype(int)


@dataclass(frozen=True)
class StratumResult:
    """Comparison within one reference-count stratum, or the reason it was skipped.

    Attributes:
        stratum: Human-readable stratum label.
        reference_range: Minimum and maximum reference count in the stratum.
        n_tested: Tested units in the stratum.
        n_untested: Untested units in the stratum.
        comparison: The within-stratum comparison, or None when not comparable.
        skipped_reason: Why the comparison was not run, empty otherwise.
    """

    stratum: str
    reference_range: tuple[int, int]
    n_tested: int
    n_untested: int
    comparison: Comparison | None
    skipped_reason: str


def stratified(
    metric: str,
    values: np.ndarray,
    tested: np.ndarray,
    references: np.ndarray,
    permutations: int,
    seed: int,
) -> list[StratumResult]:
    """Repeat the comparison inside quartiles of LOTUS reference count.

    Args:
        metric: Name of the count being compared.
        values: The count per unit.
        tested: Boolean tested flag per unit.
        references: Distinct reference count per unit, used only for stratifying.
        permutations: Number of permutations within each stratum.
        seed: Base seed; stratum ``k`` uses ``seed + k``.

    Returns:
        One result per quartile. Strata with fewer than
        ``MINIMUM_TESTED_PER_STRATUM`` tested units are reported as skipped
        rather than pooled.
    """
    strata = reference_quartiles(references)
    results = []
    for index, label in enumerate(STRATUM_LABELS):
        inside = strata == index
        n_tested = int(np.count_nonzero(inside & tested))
        n_untested = int(np.count_nonzero(inside & ~tested))
        if inside.any():
            span = (int(references[inside].min()), int(references[inside].max()))
        else:
            span = (0, 0)
        reason = ""
        comparison = None
        if n_tested < MINIMUM_TESTED_PER_STRATUM:
            reason = f"only {n_tested} tested units; fewer than {MINIMUM_TESTED_PER_STRATUM}"
        elif n_untested == 0:
            reason = "no untested units"
        else:
            comparison = compare(
                metric,
                values[inside & tested],
                values[inside & ~tested],
                permutations,
                seed + index,
            )
        results.append(StratumResult(label, span, n_tested, n_untested, comparison, reason))
    return results


def within_stratum_permutation(
    values: np.ndarray,
    tested: np.ndarray,
    references: np.ndarray,
    permutations: int,
    seed: int,
) -> tuple[float, float, float]:
    """Permute tested labels only within reference-count strata.

    This keeps the number of tested units per stratum fixed, so the null
    distribution reflects a world where being tested depends on how well
    studied a compound is but not on its breadth.

    Args:
        values: The count per unit.
        tested: Boolean tested flag per unit.
        references: Distinct reference count per unit.
        permutations: Number of draws.
        seed: Seed for the draws.

    Returns:
        Observed difference in medians, one-sided p (tested greater), two-sided p.
    """
    strata = reference_quartiles(references)
    observed = float(np.median(values[tested]) - np.median(values[~tested]))
    generator = np.random.default_rng(seed)
    members = [np.flatnonzero(strata == index) for index in range(len(STRATUM_LABELS))]
    tested_per_stratum = [int(np.count_nonzero(tested[group])) for group in members]
    null = np.empty(permutations, dtype=np.float64)
    for draw in range(permutations):
        mask = np.zeros(values.size, dtype=bool)
        for group, count in zip(members, tested_per_stratum, strict=True):
            if count:
                mask[generator.choice(group, size=count, replace=False)] = True
        null[draw] = np.median(values[mask]) - np.median(values[~mask])
    p_greater = (int(np.count_nonzero(null >= observed)) + 1) / (permutations + 1)
    p_two = (int(np.count_nonzero(np.abs(null) >= abs(observed))) + 1) / (permutations + 1)
    return observed, p_greater, p_two


@dataclass(frozen=True)
class PowerStatement:
    """Minimum detectable shift in median genera count at the achieved sample size.

    Attributes:
        n_tested: Tested units.
        alpha: One-sided significance level.
        target_power: Power sought.
        critical_difference: Null 95th percentile of the difference in medians.
        minimum_detectable_difference: Smallest additive shift in the tested
            units' genera counts that reaches the target power, or None when no
            shift in the searched range does.
        power_at_minimum: Simulated power at that shift.
        simulations: Draws per candidate shift.
        searched_shifts: The candidate shifts examined.
    """

    n_tested: int
    alpha: float
    target_power: float
    critical_difference: float
    minimum_detectable_difference: float | None
    power_at_minimum: float | None
    simulations: int
    searched_shifts: tuple[int, ...]


def simulated_power(
    values: np.ndarray,
    n_tested: int,
    critical: float,
    shift: int,
    simulations: int,
    generator: np.random.Generator,
) -> float:
    """Power of the median-difference test for an additive shift of the tested units.

    Args:
        values: The count per unit, used as the sampling population.
        n_tested: Units drawn as tested in each simulation.
        critical: Rejection threshold for the observed difference.
        shift: Constant added to every drawn tested unit's count.
        simulations: Number of draws.
        generator: Random generator, so the power search is reproducible.

    Returns:
        Fraction of simulations whose difference in medians reaches the threshold.
    """
    rejections = 0
    for _ in range(simulations):
        order = generator.permutation(values.size)
        sampled = values[order[:n_tested]] + shift
        remainder = values[order[n_tested:]]
        if np.median(sampled) - np.median(remainder) >= critical:
            rejections += 1
    return rejections / simulations


def power_statement(
    values: np.ndarray,
    n_tested: int,
    permutations: int,
    seed: int,
    alpha: float = 0.05,
    target_power: float = 0.8,
    simulations: int = 2000,
    max_shift: int = 50,
) -> PowerStatement:
    """Find the smallest additive shift in median genera count the test can detect.

    Args:
        values: Distinct genera count per unit.
        n_tested: Tested units.
        permutations: Draws for the null distribution.
        seed: Seed for both the null draws and the power simulations.
        alpha: One-sided significance level.
        target_power: Power sought.
        simulations: Draws per candidate shift.
        max_shift: Largest shift searched.

    Returns:
        The power statement.
    """
    null = permuted_differences(values, n_tested, permutations, seed)
    critical = float(np.percentile(null, 100 * (1 - alpha)))
    generator = np.random.default_rng(seed)
    shifts = tuple(range(1, max_shift + 1))
    for shift in shifts:
        power = simulated_power(values, n_tested, critical, shift, simulations, generator)
        if power >= target_power:
            return PowerStatement(
                n_tested, alpha, target_power, critical, float(shift), power, simulations, shifts
            )
    return PowerStatement(n_tested, alpha, target_power, critical, None, None, simulations, shifts)
