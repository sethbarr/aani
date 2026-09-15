"""Exploratory, not prespecified: LOTUS occurrence breadth of tested versus untested structures.

Post hoc analysis outside the frozen analysis plan. Reads the chemistry join, the
bioactivity labels and the cached LOTUS export; writes only to its own results
directory. No network access.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from src.exploratory.occurrence_breadth import FROZEN_PROTOCOL, LABEL
from src.exploratory.occurrence_breadth.counting import (
    METRICS,
    Breadth,
    Unit,
    collapse,
    count_breadth,
    first_block,
)
from src.exploratory.occurrence_breadth.loading import (
    TESTED_DEFINITION,
    file_sha256,
    iter_lotus,
    load_structures,
    locate_lotus_export,
)
from src.exploratory.occurrence_breadth.reporting import (
    csv_row,
    plot_figure,
    write_summary,
    write_table,
)
from src.exploratory.occurrence_breadth.statistics import (
    Comparison,
    compare,
    power_statement,
    reference_quartiles,
    stratified,
    within_stratum_permutation,
)

ROOT = Path(__file__).resolve().parents[1]
METRIC_FIELDS = {
    "organisms": "organisms",
    "genera": "genera",
    "families": "families",
    "references": "references",
}


def display_path(path: Path) -> str:
    """Show a path relative to the project root when it lies inside it."""
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT):
        return str(resolved.relative_to(ROOT))
    return str(resolved)


def metric_arrays(
    units: list[Unit], breadth: dict[str, Breadth]
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Arrange counts per metric and the tested flag in unit order."""
    tested = np.array([unit.tested for unit in units], dtype=bool)
    arrays = {}
    for metric in METRICS:
        arrays[metric] = np.array(
            [breadth[unit.key].counts()[metric] for unit in units], dtype=np.int64
        )
    return arrays, tested


def analyse_level(
    level: str,
    units: list[Unit],
    breadth: dict[str, Breadth],
    permutations: int,
    seed: int,
) -> dict:
    """Run every comparison for one collapse level."""
    arrays, tested = metric_arrays(units, breadth)
    comparisons: dict[str, Comparison] = {}
    for metric in METRICS:
        comparisons[metric] = compare(
            metric, arrays[metric][tested], arrays[metric][~tested], permutations, seed
        )
    strata = stratified(
        "genera", arrays["genera"], tested, arrays["references"], permutations, seed
    )
    pooled = within_stratum_permutation(
        arrays["genera"], tested, arrays["references"], permutations, seed
    )
    power = power_statement(arrays["genera"], int(tested.sum()), permutations, seed)
    return {
        "arrays": arrays,
        "tested": tested,
        "comparisons": comparisons,
        "strata": strata,
        "stratified": pooled,
        "power": power,
        "quartiles": reference_quartiles(arrays["references"]),
    }


def comparison_record(comparison: Comparison) -> dict:
    """JSON-ready view of a comparison."""
    return {
        "metric": comparison.metric,
        "n_tested": comparison.n_tested,
        "n_untested": comparison.n_untested,
        "tested_median": comparison.tested_median,
        "tested_iqr": list(comparison.tested_iqr),
        "untested_median": comparison.untested_median,
        "untested_iqr": list(comparison.untested_iqr),
        "difference_in_medians": comparison.observed_difference,
        "p_greater": comparison.p_greater,
        "p_two_sided": comparison.p_two_sided,
        "rank_biserial": comparison.rank_biserial,
        "permutations": comparison.permutations,
        "seed": comparison.seed,
    }


def main() -> None:
    """Run the exploratory analysis and write its outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--occurrences", type=Path, default=ROOT / "data/processed/chemistry/occurrences.jsonl"
    )
    parser.add_argument(
        "--labels", type=Path, default=ROOT / "data/processed/bioactivity/labels.jsonl"
    )
    parser.add_argument(
        "--chemistry-manifest",
        type=Path,
        default=ROOT / "data/processed/chemistry/run_manifest.json",
    )
    parser.add_argument("--raw", type=Path, default=ROOT / "data/raw")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "results/exploratory/occurrence_breadth"
    )
    parser.add_argument("--permutations", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=1729)
    args = parser.parse_args()

    structures = load_structures(args.occurrences, args.labels)
    export = locate_lotus_export(args.raw, args.chemistry_manifest)
    full_keys = {structure.inchikey for structure in structures}
    blocks = {first_block(key) for key in full_keys}
    tally: dict[str, int] = {}
    by_key, by_block = count_breadth(iter_lotus(export, tally), full_keys, blocks)
    metrics_path = args.occurrences.parent / "metrics.json"
    chemistry_metrics = (
        json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    )

    levels = {
        "structure": collapse(structures, "structure"),
        "connectivity": collapse(structures, "connectivity"),
    }
    breadth = {"structure": by_key, "connectivity": by_block}
    results = {
        level: analyse_level(level, levels[level], breadth[level], args.permutations, args.seed)
        for level in levels
    }

    rows = []
    for level, units in levels.items():
        rows.extend(csv_row(level, unit, breadth[level][unit.key]) for unit in units)
    write_table(args.output / "per_structure_occurrence.csv", rows)

    collapse_counts = {
        "structures": len(levels["structure"]),
        "connectivity_units": len(levels["connectivity"]),
        "tested_structures": sum(unit.tested for unit in levels["structure"]),
        "tested_connectivity_units": sum(unit.tested for unit in levels["connectivity"]),
    }
    provenance = {
        "occurrences": f"{display_path(args.occurrences)} sha256 {file_sha256(args.occurrences)}",
        "labels": f"{display_path(args.labels)} sha256 {file_sha256(args.labels)}",
        "lotus_export": f"{display_path(export)} sha256 {file_sha256(export)}",
        "chemistry_join": (
            f"input_hash {chemistry_metrics.get('input_hash', 'unknown')}; "
            f"unique_compounds {chemistry_metrics.get('unique_compounds', 'unknown')}"
        ),
        "lotus_rows_scanned": f"{tally.get('scanned', 0)} ({tally.get('malformed', 0)} malformed rows skipped)",
        "input_note": (
            "The chemistry join and labels were produced by the frozen chemistry and bioactivity "
            "stages replayed offline from the committed genus list; the input_hash above should equal "
            "the committed data/processed/chemistry/metrics.json."
        ),
        "seed": str(args.seed),
        "permutations": str(args.permutations),
    }
    write_summary(
        args.output / "summary.md",
        collapse_counts,
        {level: results[level]["comparisons"] for level in levels},
        {level: results[level]["strata"] for level in levels},
        {level: results[level]["stratified"] for level in levels},
        {level: results[level]["power"] for level in levels},
        provenance,
    )
    structure = results["structure"]
    plot_figure(
        args.output / "genera_breadth.png",
        structure["arrays"]["genera"],
        structure["tested"],
        structure["quartiles"],
        structure["comparisons"]["genera"],
        structure["strata"],
    )
    manifest = {
        "label": LABEL,
        "frozen_protocol": FROZEN_PROTOCOL,
        "generated_at": datetime.now(UTC).isoformat(),
        "tested_definition": TESTED_DEFINITION,
        "collapse": collapse_counts,
        "inputs": provenance,
        "comparisons": {
            level: {
                metric: comparison_record(c) for metric, c in results[level]["comparisons"].items()
            }
            for level in levels
        },
        "stratified_genera": {
            level: [
                {
                    "stratum": s.stratum,
                    "reference_range": list(s.reference_range),
                    "n_tested": s.n_tested,
                    "n_untested": s.n_untested,
                    "skipped_reason": s.skipped_reason,
                    "comparison": comparison_record(s.comparison) if s.comparison else None,
                }
                for s in results[level]["strata"]
            ]
            for level in levels
        },
        "within_stratum_permutation_genera": {
            level: dict(
                zip(
                    ("difference_in_medians", "p_greater", "p_two_sided"),
                    results[level]["stratified"],
                    strict=True,
                )
            )
            for level in levels
        },
        "power_genera": {
            level: {
                "n_tested": p.n_tested,
                "alpha": p.alpha,
                "target_power": p.target_power,
                "critical_difference": p.critical_difference,
                "minimum_detectable_difference": p.minimum_detectable_difference,
                "power_at_minimum": p.power_at_minimum,
                "simulations": p.simulations,
            }
            for level, p in ((level, results[level]["power"]) for level in levels)
        },
    }
    (args.output / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "label": LABEL,
                "output": str(args.output),
                "collapse": collapse_counts,
                "genera": {
                    level: comparison_record(results[level]["comparisons"]["genera"])
                    for level in levels
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
