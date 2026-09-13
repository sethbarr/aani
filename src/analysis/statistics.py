"""Genus-level enrichment with explicit exchangeability assumptions."""

import numpy as np
import pandas as pd


def difference(values: np.ndarray, labels: np.ndarray) -> float:
    """Return the unweighted rejected-minus-accepted mean hit fraction."""
    return float(values[labels == 1].mean() - values[labels == 0].mean())


def feasibility(genera: pd.DataFrame, config: dict) -> dict:
    """Gate inference before any statistic using the fixed coverage thresholds.

    Args:
        genera: Genera having at least one classified compound.
        config: Frozen minimum-genus requirement.

    Returns:
        Coverage counts and explicit null endpoints when inference is unavailable.
    """
    usable = genera.dropna(subset=["hit_fraction"]) if not genera.empty else genera
    rejected = int((usable["rejected"] == 1).sum()) if not usable.empty else 0
    accepted = int((usable["rejected"] == 0).sum()) if not usable.empty else 0
    reasons = []
    if len(usable) < config["minimum_genera"]:
        reasons.append("fewer_than_minimum_joined_genera")
    if min(rejected, accepted) < 2:
        reasons.append("need_two_genera_per_direction")
    return {
        "status": "feasibility_failure" if reasons else "ok",
        "estimable": not reasons,
        "reason": ";".join(reasons) if reasons else None,
        "feasibility_failures": reasons,
        "minimum_genera": config["minimum_genera"],
        "minimum_per_direction": 2,
        "n_genera": len(usable),
        "n_rejected": rejected,
        "n_accepted": accepted,
        "observed_difference": None,
        "rejected_mean": None,
        "accepted_mean": None,
        "p_one_sided": None,
        "descriptive_bootstrap_95_interval": None,
        "permutations": 0,
    }


def permutation_test(
    genera: pd.DataFrame, config: dict, within_family: bool = False
) -> tuple[dict, np.ndarray]:
    """Generate a seeded null and use the plus-one one-sided p-value.

    Args:
        genera: Genus-level hit fractions and behavioural labels.
        config: Frozen seed, permutation count and feasibility threshold.
        within_family: Restrict label exchanges to their original family.

    Returns:
        Summary with explicit non-estimable statuses and null draws.
    """
    base = feasibility(genera, config)
    usable = (
        genera.dropna(subset=["hit_fraction"]).reset_index(drop=True)
        if not genera.empty else genera
    )
    labels = usable["rejected"].to_numpy(dtype=int) if not usable.empty else np.array([], dtype=int)
    groups = (
        [group.index.to_numpy() for _, group in usable.groupby("family", sort=True)]
        if not usable.empty else []
    )
    variable = [indices for indices in groups if len(set(labels[indices])) > 1]
    base.update({
        "within_family": within_family,
        "variable_families": len(variable),
        "variable_genera": sum(map(len, variable)),
    })
    if not base["estimable"]:
        return base, np.array([])
    values = usable["hit_fraction"].to_numpy(dtype=float)
    n_rejected, n_accepted = int((labels == 1).sum()), int((labels == 0).sum())
    if within_family and not variable:
        return {
            **base,
            "status": "not_estimable",
            "estimable": False,
            "reason": "no_within_family_label_variation",
            "within_family": True,
            "variable_families": 0,
            "variable_genera": 0,
        }, np.array([])
    rng = np.random.default_rng(config["seed"])
    null = np.empty(config["permutations"])
    observed = difference(values, labels)
    for index in range(len(null)):
        shuffled = labels.copy()
        if within_family:
            for indices in variable:
                shuffled[indices] = rng.permutation(labels[indices])
        else:
            shuffled = rng.permutation(labels)
        null[index] = difference(values, shuffled)
    bootstrap_rng = np.random.default_rng(config["seed"] + 1)
    bootstrap = np.empty(config["bootstrap_resamples"])
    for index in range(len(bootstrap)):
        bootstrap[index] = (
            bootstrap_rng.choice(values[labels == 1], n_rejected).mean()
            - bootstrap_rng.choice(values[labels == 0], n_accepted).mean()
        )
    interval = np.quantile(bootstrap, [0.025, 0.975]).tolist()
    result = {
        **base,
        "status": "ok",
        "observed_difference": observed,
        "rejected_mean": float(values[labels == 1].mean()),
        "accepted_mean": float(values[labels == 0].mean()),
        "p_one_sided": float((1 + (null >= observed).sum()) / (len(null) + 1)),
        "descriptive_bootstrap_95_interval": interval,
        "permutations": len(null),
        "seed": config["seed"],
        "within_family": within_family,
        "variable_families": len(variable),
        "variable_genera": sum(map(len, variable)),
    }
    return result, null
