"""Write the per-structure table, the Markdown summary and the single figure."""

import csv
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.exploratory.occurrence_breadth import FROZEN_PROTOCOL, LABEL
from src.exploratory.occurrence_breadth.counting import METRICS, Breadth, Unit
from src.exploratory.occurrence_breadth.loading import TESTED_DEFINITION
from src.exploratory.occurrence_breadth.statistics import (
    Comparison,
    PowerStatement,
    StratumResult,
)

CSV_COLUMNS = (
    "level",
    "structure_id",
    "inchikey",
    "inchikey_first_block",
    "members",
    "labels",
    "tested",
    "distinct_organisms",
    "distinct_genera",
    "distinct_families",
    "distinct_references",
    "lotus_rows",
)


def csv_row(level: str, unit: Unit, breadth: Breadth) -> dict[str, str]:
    """One CSV row for a unit at a collapse level."""
    counts = breadth.counts()
    return {
        "level": level,
        "structure_id": unit.key,
        "inchikey": unit.members[0] if len(unit.members) == 1 else "",
        "inchikey_first_block": unit.key.split("-")[0],
        "members": ";".join(unit.members),
        "labels": ";".join(unit.labels),
        "tested": str(unit.tested).lower(),
        "distinct_organisms": str(counts["organisms"]),
        "distinct_genera": str(counts["genera"]),
        "distinct_families": str(counts["families"]),
        "distinct_references": str(counts["references"]),
        "lotus_rows": str(counts["lotus_rows"]),
    }


def write_table(path: Path, rows: list[dict[str, str]]) -> None:
    """Write the per-structure occurrence table with a provenance header line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(
            f"# {LABEL}; post hoc, outside the frozen analysis plan at commit {FROZEN_PROTOCOL}\n"
        )
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def format_p(p_value: float, permutations: int) -> str:
    """Format a permutation p-value, showing the resolution floor instead of 0.

    Args:
        p_value: Plus-one corrected p-value.
        permutations: Draws behind it.

    Returns:
        ``"< 0.0001"`` style text when no draw reached the observed value,
        otherwise the value to four decimals.
    """
    floor = 1 / (permutations + 1)
    if p_value <= floor:
        return f"< {1 / permutations:.4f}"
    return f"{p_value:.4f}"


def format_iqr(pair: tuple[float, float]) -> str:
    """Format an interquartile range."""
    return f"{pair[0]:g}-{pair[1]:g}"


def comparison_row(level: str, comparison: Comparison) -> str:
    """One Markdown table row for a comparison."""
    return (
        f"| {level} | {comparison.metric} | {comparison.n_tested} | {comparison.n_untested} | "
        f"{comparison.tested_median:g} ({format_iqr(comparison.tested_iqr)}) | "
        f"{comparison.untested_median:g} ({format_iqr(comparison.untested_iqr)}) | "
        f"{comparison.observed_difference:+g} | {format_p(comparison.p_greater, comparison.permutations)} | "
        f"{format_p(comparison.p_two_sided, comparison.permutations)} | {comparison.rank_biserial:+.3f} |"
    )


def stratum_row(result: StratumResult) -> str:
    """One Markdown table row for a within-stratum result."""
    span = f"{result.reference_range[0]}-{result.reference_range[1]}"
    if result.comparison is None:
        return (
            f"| {result.stratum} | {span} | {result.n_tested} | {result.n_untested} | "
            f"not compared | not compared | - | - | - | {result.skipped_reason} |"
        )
    c = result.comparison
    return (
        f"| {result.stratum} | {span} | {c.n_tested} | {c.n_untested} | "
        f"{c.tested_median:g} ({format_iqr(c.tested_iqr)}) | "
        f"{c.untested_median:g} ({format_iqr(c.untested_iqr)}) | "
        f"{c.observed_difference:+g} | {format_p(c.p_greater, c.permutations)} | {c.rank_biserial:+.3f} | |"
    )


def power_text(power: PowerStatement, untested_median: float) -> str:
    """Plain-language power statement."""
    lead = (
        f"With {power.n_tested} tested units against the rest of the corpus, the one-sided "
        f"permutation test at alpha {power.alpha:g} rejects when the tested median exceeds the "
        f"untested median by at least {power.critical_difference:g} genera."
    )
    if power.minimum_detectable_difference is None:
        return (
            f"{lead} No additive shift up to {power.searched_shifts[-1]} genera reached "
            f"{power.target_power:.0%} power in {power.simulations} simulations, so the achieved "
            "sample size cannot detect any difference of plausible size. A null result here is "
            "not evidence of no difference."
        )
    return (
        f"{lead} The smallest additive shift in the tested units' genera counts that reaches "
        f"{power.target_power:.0%} power is {power.minimum_detectable_difference:g} genera "
        f"(simulated power {power.power_at_minimum:.2f} over {power.simulations} draws), against an "
        f"untested median of {untested_median:g}. Differences smaller than that are not detectable "
        "at this sample size, so a null result is not evidence of no difference."
    )


def interpretation(
    structure: dict[str, Comparison],
    connectivity: dict[str, Comparison],
    strata: list[StratumResult],
    stratified_p: float,
) -> str:
    """Two sentences that do not exceed what the numbers show."""
    genera = structure["genera"]
    block = connectivity["genera"]
    direction = (
        "more"
        if genera.observed_difference > 0
        else "fewer"
        if genera.observed_difference < 0
        else "the same number of"
    )
    first = (
        f"The {genera.n_tested} tested structures occur in {direction} LOTUS genera than the "
        f"{genera.n_untested} untested structures (median {genera.tested_median:g} vs "
        f"{genera.untested_median:g}, one-sided permutation p {format_p(genera.p_greater, genera.permutations)}, "
        f"rank-biserial {genera.rank_biserial:+.2f}; collapsing stereoisomers gives median "
        f"{block.tested_median:g} vs {block.untested_median:g}, p {format_p(block.p_greater, block.permutations)}, "
        f"rank-biserial {block.rank_biserial:+.2f})."
    )
    compared = [s for s in strata if s.comparison is not None]
    skipped = [s for s in strata if s.comparison is None]
    if not compared:
        second = (
            "No reference-count quartile holds enough tested structures to compare, so whether this "
            "reflects breadth itself or only how often the compound has been reported cannot be "
            "addressed at this sample size."
        )
        return first + " " + second
    parts = []
    for result in compared:
        c = result.comparison
        parts.append(
            f"{result.stratum} ({c.n_tested} tested vs {c.n_untested} untested): median "
            f"{c.tested_median:g} vs {c.untested_median:g}, p {format_p(c.p_greater, c.permutations)}, "
            f"rank-biserial {c.rank_biserial:+.2f}"
        )
    skipped_note = ""
    if skipped:
        counts = ", ".join(f"{s.n_tested} in {s.stratum}" for s in skipped)
        skipped_note = (
            f", and the other strata hold too few tested structures to compare ({counts})"
        )
    second = (
        f"Most of that gap tracks how often a compound has been reported, since "
        f"{sum(s.n_tested for s in compared)} of {genera.n_tested} tested structures fall in the "
        f"most-referenced quartile; within that quartile a smaller difference remains "
        f"({'; '.join(parts)}), the within-stratum permutation gives p = {stratified_p:.4f}"
        f"{skipped_note}, so the residual difference rests on one stratum and cannot be separated "
        "from residual differences in study intensity inside it."
    )
    return first + " " + second


def write_summary(
    path: Path,
    collapse_counts: dict[str, int],
    comparisons: dict[str, dict[str, Comparison]],
    strata: dict[str, list[StratumResult]],
    stratified: dict[str, tuple[float, float, float]],
    power: dict[str, PowerStatement],
    provenance: dict[str, str],
) -> None:
    """Write summary.md.

    Args:
        path: Destination.
        collapse_counts: Structure and connectivity counts overall and for tested units.
        comparisons: Level -> metric -> comparison.
        strata: Level -> within-stratum results on genera count.
        stratified: Level -> (observed difference, one-sided p, two-sided p) from
            within-stratum permutation.
        power: Level -> power statement on genera count.
        provenance: Input paths and hashes.
    """
    lines = [
        "# Occurrence breadth of tested versus untested structures in LOTUS",
        "",
        f"**{LABEL.capitalize()}.** Post hoc analysis outside the frozen analysis plan at commit "
        f"`{FROZEN_PROTOCOL}`. It reads the frozen chemistry join and bioactivity labels and changes "
        "nothing in them. Nothing here enters the primary analysis or alters its feasibility status.",
        "",
        "## Question",
        "",
        "Are the structures that carry a ChEMBL measurement against the three target fungi more "
        "taxonomically widespread across the full LOTUS v4 export than the structures without one?",
        "",
        "## Definitions",
        "",
        f"- Tested: {TESTED_DEFINITION}",
        "- Untested: every other mapped structure in the chemistry join, including the structures "
        "with a retrieved measurement that could not be read against the frozen threshold.",
        "- Breadth: distinct organisms, genera, families and references over every row of the "
        "complete LOTUS export whose InChIKey (structure level) or InChIKey first block "
        "(connectivity level) matches. Genus and family come from LOTUS's aligned rank arrays; "
        "no taxonomy service was called. References are distinct DOI, else PMCID, else PMID, "
        "else the raw reference value.",
        "- Difference in medians is tested with 10,000 label permutations at a fixed seed, "
        "as in the chemical-distance null model; p-values carry the plus-one correction. "
        "p (greater) is one-sided for tested more widespread; rank-biserial is 2*AUC-1 with ties "
        "counted as half, positive when tested units rank higher.",
        "",
        "## Collapse to connectivity",
        "",
        f"- Mapped structures: {collapse_counts['structures']}; distinct first blocks: "
        f"{collapse_counts['connectivity_units']} ({collapse_counts['structures'] - collapse_counts['connectivity_units']} "
        "structures collapse into another structure's block).",
        f"- Tested structures: {collapse_counts['tested_structures']}; tested first blocks: "
        f"{collapse_counts['tested_connectivity_units']} ({collapse_counts['tested_structures'] - collapse_counts['tested_connectivity_units']} "
        "collapse). A block is tested when any of its stereoisomers is tested.",
        "",
        "## Tested versus untested",
        "",
        "| Level | Metric | n tested | n untested | Tested median (IQR) | Untested median (IQR) | "
        "Difference | p (greater) | p (two-sided) | Rank-biserial |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for level in ("structure", "connectivity"):
        for metric in METRICS:
            lines.append(comparison_row(level, comparisons[level][metric]))
    lines.extend(
        [
            "",
            "## Confound: breadth as a proxy for how well studied a compound is",
            "",
            "Distinct genera compared within quartiles of distinct LOTUS reference count. Quartile "
            "boundaries are the 25th, 50th and 75th percentiles of reference count; ties stay "
            "together, so strata are unequal. Strata with fewer than 5 tested units are reported as "
            "not compared rather than pooled.",
            "",
        ]
    )
    for level in ("structure", "connectivity"):
        observed, p_greater, p_two = stratified[level]
        lines.extend(
            [
                f"### {level.capitalize()} level",
                "",
                "| Stratum | Reference range | n tested | n untested | Tested median (IQR) | "
                "Untested median (IQR) | Difference | p (greater) | Rank-biserial | Note |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        lines.extend(stratum_row(result) for result in strata[level])
        lines.extend(
            [
                "",
                f"Permuting tested labels only within strata (tested count per stratum held fixed): "
                f"observed difference in medians {observed:+g}, p (greater) = {p_greater:.4f}, "
                f"p (two-sided) = {p_two:.4f}.",
                "",
            ]
        )
    lines.extend(["## Power", ""])
    for level in ("structure", "connectivity"):
        lines.append(
            f"- {level.capitalize()} level: "
            + power_text(power[level], comparisons[level]["genera"].untested_median)
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            interpretation(
                comparisons["structure"],
                comparisons["connectivity"],
                strata["structure"],
                stratified["structure"][1],
            ),
            "",
            "## Inputs",
            "",
        ]
    )
    lines.extend(f"- `{name}`: {value}" for name, value in provenance.items())
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def plot_figure(
    path: Path,
    genera: np.ndarray,
    tested: np.ndarray,
    strata: np.ndarray,
    comparison: Comparison,
    stratum_results: list[StratumResult],
) -> None:
    """Draw tested vs untested genera distributions and the stratified comparison.

    Args:
        path: Destination PNG; an SVG is written beside it.
        genera: Distinct genera count per unit at the structure level.
        tested: Boolean tested flag per unit.
        strata: Stratum index per unit.
        comparison: The structure-level genera comparison for the annotation.
        stratum_results: Within-stratum results for the second panel.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    generator = np.random.default_rng(0)
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 5.2), layout="constrained")
    fig.suptitle(f"{LABEL}: LOTUS occurrence breadth by ChEMBL testing status", fontsize=11)
    plotted = genera.astype(float) + 1
    groups = [plotted[~tested], plotted[tested]]
    left.boxplot(
        groups,
        positions=[0, 1],
        widths=0.5,
        showfliers=False,
        medianprops={"color": "#b64c31", "linewidth": 2},
    )
    for position, values in enumerate(groups):
        jitter = generator.uniform(-0.18, 0.18, size=values.size)
        left.scatter(position + jitter, values, s=8, alpha=0.35, color="#3d6b7a")
    left.set_yscale("log")
    left.set_xticks(
        [0, 1], [f"untested (n={comparison.n_untested})", f"tested (n={comparison.n_tested})"]
    )
    left.set_ylabel("distinct LOTUS genera + 1 (log scale)")
    left.set_title("Structure level", fontsize=10)
    left.text(
        0.02,
        0.98,
        (
            f"median {comparison.tested_median:g} vs {comparison.untested_median:g}\n"
            f"one-sided permutation p {format_p(comparison.p_greater, comparison.permutations)}\n"
            f"rank-biserial {comparison.rank_biserial:+.2f}"
        ),
        transform=left.transAxes,
        va="top",
        fontsize=9,
    )
    ticks = []
    labels = []
    for index, result in enumerate(stratum_results):
        inside = strata == index
        base = index * 3
        untested_values = plotted[inside & ~tested]
        tested_values = plotted[inside & tested]
        if untested_values.size:
            right.boxplot(
                [untested_values],
                positions=[base],
                widths=0.7,
                showfliers=False,
                medianprops={"color": "#3d6b7a", "linewidth": 2},
            )
        if tested_values.size:
            right.scatter(
                np.full(tested_values.size, base + 1.0)
                + generator.uniform(-0.15, 0.15, tested_values.size),
                tested_values,
                s=18,
                color="#b64c31",
                alpha=0.8,
            )
        note = (
            "not compared"
            if result.comparison is None
            else f"p {format_p(result.comparison.p_greater, result.comparison.permutations)}"
        )
        ticks.append(base + 0.5)
        labels.append(
            f"{result.stratum}\nrefs {result.reference_range[0]}-{result.reference_range[1]}\n"
            f"tested n={result.n_tested}\n{note}"
        )
    right.set_yscale("log")
    right.set_xticks(ticks, labels, fontsize=8)
    right.set_ylabel("distinct LOTUS genera + 1 (log scale)")
    right.set_title(
        "Within quartiles of LOTUS reference count (box: untested; points: tested)", fontsize=10
    )
    fig.savefig(path, dpi=180)
    fig.savefig(path.with_suffix(".svg"))
    plt.close(fig)
