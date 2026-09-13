"""Import traceable LOTUS/COCONUT exports through a stable table contract."""

import hashlib
import shutil
from pathlib import Path

import pandas as pd

from src.common.io import digest, timestamp, write_json, write_jsonl

COLUMNS = [
    "database",
    "database_version",
    "database_record_id",
    "plant_name",
    "genus",
    "inchikey",
    "canonical_smiles",
    "reference_url",
    "aggregation_level",
]


def valid_inchikey(value: str) -> bool:
    """Validate the full InChIKey shape without collapsing chemical identity."""
    parts = value.split("-")
    return [len(part) for part in parts] == [14, 10, 1] and all(
        part.isascii() and part.isalpha() and part.isupper() for part in parts
    )


def import_occurrences(
    source: Path, raw: Path, output: Path, imported_at: str | None = None
) -> dict:
    """Archive an input export and validate its taxon–compound occurrences.

    Args:
        source: CSV conforming to the documented occurrence contract.
        raw: Immutable raw import storage.
        output: Output directory for occurrences and rejected records.
        imported_at: Stable acquisition timestamp for a reproducible export replay.

    Returns:
        Counts and content hash; no absent occurrence is treated as inactivity.
    """
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    archive = raw / "chemistry_imports" / f"{checksum}.csv"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        shutil.copyfile(source, archive)
    frame = pd.read_csv(source, dtype=str, keep_default_na=False)
    missing = set(COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing occurrence columns: {sorted(missing)}")
    accepted, review = [], []
    for row in frame.to_dict("records"):
        reason = None
        if row["database"] not in {"LOTUS", "COCONUT"}:
            reason = "unsupported_database"
        elif not all(row[column].strip() for column in COLUMNS):
            reason = "missing_provenance_or_structure"
        elif not valid_inchikey(row["inchikey"]):
            reason = "invalid_full_inchikey"
        elif not row["reference_url"].startswith(("https://", "http://")):
            reason = "missing_clickable_occurrence_reference"
        elif row["aggregation_level"] not in {"species", "genus"}:
            reason = "invalid_aggregation_level"
        if reason:
            review.append({**row, "reason": reason, "input_hash": checksum})
        else:
            row["compound_id"] = row["inchikey"]
            row["occurrence_id"] = digest(
                {key: row[key] for key in ("genus", "inchikey", "reference_url")}
            )
            row["input_hash"] = checksum
            accepted.append(row)
    write_jsonl(output / "occurrences.jsonl", accepted)
    write_jsonl(output / "review.jsonl", review)
    metrics = {
        "input_hash": checksum,
        "imported_at": imported_at or timestamp(),
        "accepted": len(accepted),
        "review": len(review),
        "unique_occurrences": len({row["occurrence_id"] for row in accepted}),
        "unique_compounds": len({row["compound_id"] for row in accepted}),
        "genera_with_chemistry": len({row["genus"] for row in accepted}),
    }
    write_json(output / "metrics.json", metrics)
    return metrics
