"""Render the single exported figure supporting the enrichment argument."""

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_enrichment(summary: dict, null: np.ndarray, path: Path, n_compounds: int) -> None:
    """Plot the observed difference against the null with denominators visible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(8, 5), layout="constrained")
    axis.hist(null, bins=40, color="#91b3a1", edgecolor="white")
    axis.axvline(
        summary["observed_difference"],
        color="#b64c31",
        linewidth=2.5,
        label=f"Observed difference: {summary['observed_difference']:.3f}",
    )
    axis.set(
        xlabel="Rejected − accepted mean genus antifungal-hit fraction",
        ylabel="Permutations",
        title="Does leafcutter rejection enrich for measured antifungal activity?",
    )
    annotation = (
        f"{summary['n_genera']} genera ({summary['n_rejected']} rejected, "
        f"{summary['n_accepted']} accepted) · {n_compounds} classified structures\n"
        f"One-sided permutation p = {summary['p_one_sided']:.4g}"
    )
    if summary["status"] == "feasibility_failure":
        annotation += "\nBelow preregistered coverage trigger; exploratory estimate"
    axis.text(0.02, 0.98, annotation, transform=axis.transAxes, va="top", fontsize=9)
    axis.legend(loc="upper right", bbox_to_anchor=(1, -0.16), frameon=False)
    fig.savefig(path, dpi=180)
    fig.savefig(path.with_suffix(".svg"))
    plt.close(fig)
