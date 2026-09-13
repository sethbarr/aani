"""Check evidence preservation and exact taxonomy for the Trema supplement."""

from pathlib import Path

import pytest

from src.behaviour.aggregation import aggregate
from src.behaviour.pipeline import load_inputs, validate_taxonomy
from src.behaviour.supplement import load_supplement
from src.common.io import read_json, read_jsonl

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/interim/trema_resolution/manifest.json"


def test_trema_adds_all_supported_contexts_and_one_unanimous_genus() -> None:
    """Retain unchanged source directions and pass the existing GBIF rule."""
    rows, _, _, lineage = load_inputs(ROOT, [MANIFEST])
    trema = [row for row in rows if row["genus"] == "Trema"]
    assert len(trema) == 7
    assert lineage["taxonomy_supplement_context_records"] == 7
    assert {row["plant_name_as_written"] for row in trema} == {"Trema micrantha"}
    assert {row["accepted_name"] for row in trema} == {"Trema micranthum"}
    assert {row["outcome"] for row in trema} == {"rejected"}
    for row in trema:
        validate_taxonomy(row, ROOT / "data/raw", 95)
    genera, conflicts, review = aggregate(rows)
    assert len(genera) == 11 and len(conflicts) == 5 and not review
    assert sum(row["outcome"] == "rejected" for row in genera) == 5


def test_duplicate_trema_supplement_is_rejected() -> None:
    """Prevent adding the same curator contexts a second time."""
    with pytest.raises(ValueError) as caught:
        load_inputs(ROOT, [MANIFEST, MANIFEST])
    assert "duplicates existing observations" in str(caught.value)


def test_changed_direction_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Catch reference relabeling even when an artifact hash check is bypassed."""
    manifest = read_json(MANIFEST)
    original_path = ROOT / manifest["original_observations"]["path"]
    supplement_path = ROOT / manifest["observations"]["path"]
    original_rows = read_jsonl(original_path)
    changed = read_jsonl(supplement_path)
    changed[0]["outcome"] = "accepted"
    monkeypatch.setattr("src.behaviour.supplement.read_jsonl", InputRows(original_path, original_rows, changed))
    with pytest.raises(ValueError) as caught:
        load_supplement(ROOT, MANIFEST, [])
    assert "changed original evidence" in str(caught.value)


class InputRows:
    """Supply altered supplement rows while retaining the genuine source input."""

    def __init__(self, original_path: Path, original: list[dict], changed: list[dict]) -> None:
        """Keep distinct original and altered record collections."""
        self.original_path = original_path
        self.original = original
        self.changed = changed

    def __call__(self, path: Path) -> list[dict]:
        """Return original source rows or the deliberately changed supplement."""
        return self.original if path == self.original_path else self.changed
