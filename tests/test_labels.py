from src.bioactivity.labels import classify_measurement, label_compounds

CONFIG = {
    "organisms": ["Candida albicans"],
    "endpoints": ["MIC", "IC50"],
    "potency_threshold_um": 10.0,
}


def activity(**updates: object) -> dict:
    """Return a valid assay activity with optional field overrides."""
    row = {
        "assay": {"assay_organism": "Candida albicans", "assay_type": "F"},
        "standard_type": "MIC",
        "standard_units": "uM",
        "standard_value": "10",
        "standard_relation": "=",
    }
    row.update(updates)
    return row


def test_threshold_and_censoring_boundaries() -> None:
    """Apply the preregistered threshold and censoring rules."""
    assert classify_measurement(activity(), CONFIG)[0] == "active"
    assert classify_measurement(activity(standard_value="10000", standard_units="nM"), CONFIG)[0] == "active"
    assert classify_measurement(activity(standard_relation=">", standard_value="10"), CONFIG)[0] == "inactive"
    assert classify_measurement(activity(standard_relation=">=", standard_value="10"), CONFIG)[0] == "unknown"


def test_label_aggregation_preserves_discordance_and_unknowns() -> None:
    """Prefer activity while retaining discordance and missing labels."""
    labels, _ = label_compounds(
        ["A", "B"],
        [
            {"compound_id": "A", "activity_id": 1, "assay_chembl_id": "assay-1", **activity()},
            {
                "compound_id": "A",
                "activity_id": 2,
                "assay_chembl_id": "assay-2",
                **activity(standard_value="20"),
            },
        ],
        CONFIG,
    )
    assert labels[0]["label"] == "active"
    assert labels[0]["discordant"]
    assert labels[1]["label"] == "unknown"
