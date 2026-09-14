"""Guard the chemical-distance outputs against leaking an activity prediction.

These checks bind the published surface of the analysis and deliberately import
nothing that requires RDKit, so the constraint is enforced in any environment.
"""

import csv
from pathlib import Path

import pytest

from src.chemical_distance.convention import DOMAIN_CONVENTION
from src.chemical_distance.tables import COLUMNS, DISCLAIMER

PREDICTION_TOKENS = (
    "predict",
    "probab",
    "likelihood",
    "imputed",
    "impute",
    "p_active",
    "activity_score",
    "expected_activity",
    "estimated_activity",
    "confidence",
)

CSV_PATH = Path("results/chemical_distance/test_priority.csv")


def test_no_column_can_be_read_as_a_predicted_activity() -> None:
    """No declared column name may suggest a predicted activity."""
    for column in COLUMNS:
        for token in PREDICTION_TOKENS:
            assert token not in column.lower(), f"{column} reads as a prediction"


def test_no_column_carries_a_neighbour_activity_label() -> None:
    """The table must not transfer any label from the reference set."""
    for column in COLUMNS:
        lowered = column.lower()
        assert not lowered.endswith("_label")
        assert "active" not in lowered
        assert "inactive" not in lowered


def test_disclaimer_states_the_table_is_not_a_prediction() -> None:
    """The written disclaimer must carry the required wording."""
    assert DISCLAIMER.startswith("#")
    assert "NOT an activity prediction" in DISCLAIMER


def test_the_domain_threshold_stays_a_stated_convention() -> None:
    """The applicability-domain threshold must remain the frozen convention."""
    assert DOMAIN_CONVENTION == 0.4


@pytest.mark.skipif(not CSV_PATH.exists(), reason="analysis has not been run")
def test_written_table_carries_no_activity_label() -> None:
    """The written table must rank unknown compounds and label none of them."""
    with CSV_PATH.open(encoding="utf-8") as handle:
        first = handle.readline().strip()
        rows = list(csv.DictReader(handle))
    assert first == DISCLAIMER
    assert rows
    for column in rows[0]:
        assert not any(token in column.lower() for token in PREDICTION_TOKENS)
    values = {value.lower() for row in rows for value in row.values()}
    assert "active" not in values
    assert "inactive" not in values


@pytest.mark.skipif(not CSV_PATH.exists(), reason="analysis has not been run")
def test_written_table_is_ranked_by_descending_novelty() -> None:
    """Ranks must follow descending distance from the tested set."""
    with CSV_PATH.open(encoding="utf-8") as handle:
        handle.readline()
        rows = list(csv.DictReader(handle))
    distances = [
        float(row["chemical_novelty_distance_to_tested_set"])
        for row in rows
        if row["chemical_novelty_distance_to_tested_set"]
    ]
    assert distances == sorted(distances, reverse=True)
    assert [int(row["rank"]) for row in rows] == list(range(1, len(rows) + 1))


@pytest.mark.skipif(not CSV_PATH.exists(), reason="analysis has not been run")
def test_written_table_reports_distance_as_one_minus_similarity() -> None:
    """Distance and similarity must stay exact complements."""
    with CSV_PATH.open(encoding="utf-8") as handle:
        handle.readline()
        rows = list(csv.DictReader(handle))
    for row in rows:
        similarity = row["nearest_tested_tanimoto"]
        distance = row["chemical_novelty_distance_to_tested_set"]
        if similarity and distance:
            assert float(similarity) + float(distance) == pytest.approx(1.0)
