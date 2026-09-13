"""Retrieve ChEMBL assay labels for eligible imported structures."""

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.bioactivity.chembl import retrieve_labels
from src.common.cache import CachedHTTP
from src.common.io import read_json, read_jsonl, timestamp, write_json, write_jsonl


def table_rows(path: Path) -> list[dict]:
    """Read a JSONL or CSV genus table with deterministic string columns."""
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False).to_dict("records")
    return read_jsonl(path)


def upstream_metrics(path: Path | None) -> dict:
    """Read explicitly supplied chemistry metrics or an explicit missing status."""
    if path is None:
        return {}
    if not path.is_file():
        return {"status": "blocked", "blocked_reason": f"metrics_file_missing:{path}"}
    return read_json(path)


def blocked_outputs(output: Path, reason: str) -> dict:
    """Write unavailable-stage artifacts without fabricating an input count."""
    for name in ("labels", "measurements", "retrieval_status"):
        write_jsonl(output / f"{name}.jsonl", [])
    metrics = {
        "status": "blocked", "blocked_reason": reason,
        "compounds": None, "matched_compounds": None, "active": None,
        "inactive": None, "unknown": None, "failed_compounds": None,
        "retrieved_measurements": None, "classified_measurements": None,
    }
    write_json(output / "metrics.json", metrics)
    return metrics


def run_bioactivity(
    occurrences_path: Path, output: Path, cache_path: Path, offline: bool = False,
    behaviour_genera_path: Path | None = None, chemistry_metrics_path: Path | None = None,
    primary_genera_path: Path | None = None,
) -> dict:
    """Classify eligible structures and preserve selection and retrieval provenance."""
    inputs = {"occurrences": occurrences_path}
    if behaviour_genera_path is not None:
        inputs["behaviour_genera"] = behaviour_genera_path
    if chemistry_metrics_path is not None:
        inputs["chemistry_metrics"] = chemistry_metrics_path
    if primary_genera_path is not None:
        inputs["primary_genera"] = primary_genera_path
    input_hashes = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        for path in inputs.values()
    }
    missing = [str(path) for path in inputs.values() if not path.is_file()]
    chemistry = upstream_metrics(chemistry_metrics_path)
    reason = f"input_files_missing:{','.join(missing)}" if missing else None
    if chemistry.get("status") == "blocked" or chemistry.get("blocked_reason"):
        reason = f"chemistry_stage_blocked:{chemistry.get('blocked_reason') or 'unknown_reason'}"
    selection = {}
    if reason:
        metrics = blocked_outputs(output, reason)
    else:
        occurrences = read_jsonl(occurrences_path)
        all_compounds = {row["compound_id"] for row in occurrences}
        genera = None
        if behaviour_genera_path is not None:
            genus_rows = table_rows(behaviour_genera_path)
            if any(row.get("outcome") == "conflict" or row.get("primary_eligible") is False for row in genus_rows):
                raise ValueError("The supplied behaviour genus table contains excluded conflicts")
            genera = {row["genus"] for row in genus_rows}
        selected = [row for row in occurrences if genera is None or row["genus"] in genera]
        compounds = sorted({row["compound_id"] for row in selected})
        selection = {
            "all_imported_compounds": len(all_compounds),
            "selected_compounds": len(compounds),
            "excluded_outside_eligible_genera_compounds": len(all_compounds - set(compounds)),
            "eligible_behaviour_genera": sorted(genera) if genera is not None else None,
            "selected_genera": sorted({row["genus"] for row in selected}),
            "selected_occurrences": len(selected),
            "selection_rule": (
                "Eligible unanimous behaviour genera, applied before activity retrieval."
                if genera is not None else
                "All imported genera, including conflict genera, to support prespecified sensitivity reaggregation. Conflicts remain excluded from primary inference."
            ),
        }
        if primary_genera_path is not None:
            primary_genera = {row["genus"] for row in table_rows(primary_genera_path)}
            primary_compounds = {
                row["compound_id"] for row in occurrences if row["genus"] in primary_genera
            }
            selection.update({
                "primary_scope_compounds": len(primary_compounds),
                "additional_sensitivity_scope_compounds": len(set(compounds) - primary_compounds),
                "primary_scope_genera": sorted(primary_genera),
            })
        write_json(output / "selection.json", selection)
        cache = CachedHTTP(cache_path, offline)
        try:
            config = read_json(Path("config/analysis.json"))
            metrics = retrieve_labels(compounds, cache, output, config)
        finally:
            cache.close()
        metrics.update(selection)
        write_json(output / "metrics.json", metrics)
    write_json(output / "run_manifest.json", {
        "completed_at": timestamp(), "offline": offline,
        "input_hashes": input_hashes, "chemistry_metrics": chemistry,
        "selection": selection, "blocked_reason": metrics.get("blocked_reason"),
        "network_cache": str(cache_path),
    })
    return metrics


def main() -> None:
    """Run exact-structure retrieval with an optional pre-activity genus filter."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--occurrences", type=Path, default=Path("data/interim/chemistry/occurrences.jsonl"))
    parser.add_argument("--behaviour-genera", type=Path)
    parser.add_argument("--primary-genera", type=Path, help="Audit primary versus sensitivity compound scope without filtering retrieval.")
    parser.add_argument("--chemistry-metrics", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/interim/bioactivity"))
    parser.add_argument("--cache", type=Path, default=Path("data/raw"))
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_bioactivity(
        args.occurrences, args.output, args.cache, args.offline,
        args.behaviour_genera, args.chemistry_metrics, args.primary_genera,
    ), indent=2))


if __name__ == "__main__":
    main()
