"""Run the committed chemical-distance sensitivity grid with immutable input evidence."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import rdkit

from scripts.chemical_distance import (
    ASSAYS,
    BEHAVIOUR,
    CHEMISTRY,
    LABELS,
    MEASUREMENTS,
    load_inputs,
)
from scripts.verify_day2 import frozen_checks
from src.chemical_distance.fingerprints import build_structures, morgan_generator
from src.chemical_distance.nullmodel import similarity_matrix
from src.chemical_distance.robustness import (
    DRAWS,
    POPULATIONS,
    SCHEMES,
    SEED,
    Unit,
    build_populations,
    compound_units,
    interpretation,
    run_cell,
)
from src.common.io import read_json, timestamp, write_json

ROOT = Path.cwd()
OUTPUT = ROOT / "results/chemical_distance_robustness"
PRIVATE = ROOT / "data/interim/chemical_distance_robustness"
DECLARATION = ROOT / "docs/amendment_2026-09-14_chemical_robustness.md"
COMMIT = "e61139a5a431dd8d179c11634f722cae3c07e08e"


def sha256(path: Path) -> str:
    """Hash one file's exact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare() -> None:
    """Verify the committed declaration and freeze source, labels, and biological outputs."""
    if (OUTPUT / "protocol.json").exists():
        raise ValueError("robustness_already_prepared")
    original = subprocess.check_output(["git", "show", f"{COMMIT}:{DECLARATION.relative_to(ROOT)}"])
    if original != DECLARATION.read_bytes():
        raise ValueError("declaration_differs_from_committed_bytes")
    paths = {DECLARATION, CHEMISTRY, LABELS, MEASUREMENTS, ASSAYS, BEHAVIOUR,
             ROOT / "scripts/chemical_distance.py", ROOT / "scripts/chemical_robustness.py",
             ROOT / "tests/test_chemical_robustness.py"}
    for folder in ("src/chemical_distance", "src/extraction", "src/evaluation", "src/common"):
        paths.update(ROOT.joinpath(folder).glob("*.py"))
    for folder in ("data/processed", "results/primary", "results/experimental", "results/delayed",
                   "results/nondiscordant", "results/detection_variance"):
        paths.update(path for path in ROOT.joinpath(folder).rglob("*") if path.is_file())
    paths.update(ROOT / name for name in (
        "results/summary.json", "results/metrics.json", "results/recall_baseline.json",
        "docs/analysis_plan.md", "config/analysis.json"))
    checks = frozen_checks()
    if not all(row["matches_frozen_commit"] for row in checks):
        raise ValueError("biological_protocol_changed")
    protocol = {
        "prepared_at": timestamp(), "declaration_commit": COMMIT,
        "declaration_committed_at": subprocess.check_output(
            ["git", "show", "-s", "--format=%cI", COMMIT], text=True).strip(),
        "populations": POPULATIONS, "schemes": SCHEMES, "draws_per_cell": DRAWS,
        "cells": 16, "total_draws": 16 * DRAWS, "base_seed": SEED,
        "rdkit_version": rdkit.__version__, "numpy_version": np.__version__,
        "frozen_protocol": checks,
        "files": [{"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
                  for path in sorted(paths)],
    }
    write_json(OUTPUT / "protocol.json", protocol)
    print(json.dumps({"status": "prepared", "frozen_files": len(paths),
                      "prepared_at": protocol["prepared_at"]}), flush=True)


def verify() -> dict:
    """Check that every recorded input, rule, and biological artifact remains unchanged."""
    protocol = read_json(OUTPUT / "protocol.json")
    changed = [row["path"] for row in protocol["files"] if not (ROOT / row["path"]).is_file()
               or sha256(ROOT / row["path"]) != row["sha256"]]
    if changed:
        raise ValueError(f"robustness_input_drift:{changed}")
    return {"verified_at": timestamp(), "frozen_files": len(protocol["files"]),
            "all_unchanged": True, "model_calls": 0}


def describe_population(name: str, units: list[Unit]) -> dict:
    """Expose removed multiplicity, reference counts, and membership provenance."""
    members = sum(len(unit.members) for unit in units)
    report = {
        "population": name, "units": len(units), "source_compounds": members,
        "reference_units": sum(unit.measured for unit in units),
        "measured_source_compounds": sum(len(unit.measured_members) for unit in units),
        "duplicate_classes": sum(len(unit.members) > 1 for unit in units),
        "mixed_measurement_classes": sum(
            0 < len(unit.measured_members) < len(unit.members) for unit in units),
        "collapsed_compound_count": members - len(units),
        "arabidopsis_units": sum("Arabidopsis" in unit.genera for unit in units),
    }
    membership = [{"representative": unit.structure.compound_id, "members": unit.members,
                   "measured_members": unit.measured_members, "genera": unit.genera,
                   "heavy_atoms": unit.heavy_atoms} for unit in units]
    write_json(PRIVATE / f"{name}_membership.json", membership)
    report["membership_path"] = str((PRIVATE / f"{name}_membership.json").relative_to(ROOT))
    report["membership_sha256"] = sha256(PRIVATE / f"{name}_membership.json")
    return report


def run() -> None:
    """Execute the exact sixteen cells once, saving each result before continuing."""
    verify()
    if (OUTPUT / "execution.json").exists():
        raise ValueError("robustness_run_already_started")
    execution = {"status": "running", "started_at": timestamp(), "completed_cells": 0}
    write_json(OUTPUT / "execution.json", execution)
    try:
        inputs = load_inputs()
        structures, unresolved = build_structures(
            [(plant.compound_id, plant.smiles) for plant in inputs.plants], morgan_generator())
        measured = {item.compound_id for item in inputs.tested}
        units = compound_units(inputs.plants, structures, measured)
        populations = build_populations(units)
        descriptions = [describe_population(name, population)
                        for name, population in populations.items()]
        write_json(OUTPUT / "populations.json", {"unresolved": unresolved,
                                                  "populations": descriptions})
        matrix = similarity_matrix([unit.structure for unit in units])
        indices = {unit.structure.compound_id: index for index, unit in enumerate(units)}
        for population_index, (name, population) in enumerate(populations.items()):
            selection = [indices[unit.structure.compound_id] for unit in population]
            selected = matrix[np.ix_(selection, selection)]
            for scheme_index, scheme in enumerate(SCHEMES):
                verify()
                seed = SEED + 100 * population_index + scheme_index
                result, values = run_cell(selected, population, scheme, seed)
                result.update(population=name, finished_at=timestamp())
                draws_path = OUTPUT / "draws" / f"{name}_{scheme}.json"
                write_json(draws_path, {"seed": seed, "null_statistics": values})
                result.update(null_statistics_path=str(draws_path.relative_to(ROOT)),
                              null_statistics_sha256=sha256(draws_path))
                write_json(OUTPUT / "cells" / f"{name}_{scheme}.json", result)
                execution["completed_cells"] += 1
                write_json(OUTPUT / "execution.json", execution)
                print(json.dumps({key: result.get(key) for key in (
                    "population", "scheme", "status", "observed", "null_median", "difference",
                    "forced_reference_units", "degenerate")}), flush=True)
        execution.update(status="complete", finished_at=timestamp(), verification=verify())
    except Exception as error:
        execution.update(status="failed", finished_at=timestamp(),
                         error=f"{type(error).__name__}: {error}")
        raise
    finally:
        write_json(OUTPUT / "execution.json", execution)
    report()


def report() -> None:
    """Render all declared cells, population changes, and the descriptive verdict."""
    cells = []
    for population in POPULATIONS:
        for scheme in SCHEMES:
            path = OUTPUT / "cells" / f"{population}_{scheme}.json"
            cells.append(read_json(path) if path.exists() else {
                "population": population, "scheme": scheme, "status": "missing"})
    verdict = interpretation(cells)
    descriptions = read_json(OUTPUT / "populations.json")
    lines = ["# Chemical-distance robustness", "",
             f"Predeclared in commit `{COMMIT}` before sensitivity draws. "
             "This exploratory analysis follows inspection of the original result.", "",
             verdict, "", "## Population accounting", "",
             "| Population | Units | Reference units | Source compounds | Collapsed compounds | Mixed measured/unmeasured classes |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in descriptions["populations"]:
        lines.append(f"| {row['population']} | {row['units']} | {row['reference_units']} | "
                     f"{row['source_compounds']} | {row['collapsed_compound_count']} | "
                     f"{row['mixed_measurement_classes']} |")
    lines += ["", "## All sixteen controls", "",
              "Difference is observed minus null median similarity. Negative values mean the "
              "retrieved reference leaves its complement further away than the median matched selection.",
              "", "| Population | Match | Observed | Null median | Difference | Null 2.5–97.5% | Draws ≤ observed /2000 | Forced refs | Distinct sets |",
              "| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |"]
    for row in cells:
        if row["status"] != "complete":
            lines.append(f"| {row['population']} | {row['scheme']} | {row['status']} | — | — | — | — | — | — |")
            continue
        lines.append(f"| {row['population']} | {row['scheme']} | {row['observed']:.4f} | "
                     f"{row['null_median']:.4f} | {row['difference']:+.4f} | "
                     f"{row['null_low']:.4f}–{row['null_high']:.4f} | "
                     f"{row['draws_at_or_below_observed']} | {row['forced_reference_units']} | "
                     f"{row['distinct_reference_sets']} |")
    lines += ["", "## Interpretation limits", "",
              "The rule requires negative differences and nondegenerate nulls in all sixteen cells, "
              "plus observed similarity below the 2.5th null percentile in the collapsed and "
              "Arabidopsis-excluded jointly matched populations. This is a descriptive sensitivity "
              "rule. The percentile ranges describe random selections; they are not confidence "
              "intervals for an effect. No new hypothesis-test p-values are computed.", "",
              "Reference membership means an eligible assay measurement was retrieved. A compound "
              "outside the reference may have assay evidence absent from this retrieval. Size and "
              "genus matching conditions on observed corpus properties and cannot identify why "
              "coverage is uneven. Exact genus-membership strata retain multi-genus compounds "
              "without selecting an arbitrary genus. Forced reference units remain visible.", "",
              "Fingerprint collapse treats identical bit vectors as equally weighted classes. A class "
              "is measured if any member is measured; every member is removed together from the query "
              "set. These classes can combine stereoisomers or fingerprint collisions. They do not "
              "change the source labels or establish molecular identity. The Arabidopsis exclusion "
              "removes every class linked to that genus and changes the population described.", "",
              "All references come from this plant corpus. A larger external assay reference could "
              "change the absolute similarities and the observed-versus-null comparison. These "
              "results supply no activity prediction or biological enrichment estimate.", "",
              "Every null statistic is saved under draws/, matching strata under cells/, and membership "
              "provenance under data/interim/chemical_distance_robustness. protocol.json and execution.json "
              "record hashes, versions, timestamps, and preservation checks.", ""]
    OUTPUT.joinpath("summary.md").write_text("\n".join(lines), encoding="utf-8")
    write_json(OUTPUT / "comparison.json", {"verdict": verdict, "cells": cells,
                                             "populations": descriptions, "verification": verify()})
    print(verdict, flush=True)


def main() -> None:
    """Select preflight, one execution, or report regeneration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "report"))
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "run":
        run()
    else:
        report()


if __name__ == "__main__":
    main()
