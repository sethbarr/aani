"""Classify only measurements that establish the preregistered threshold."""

import math


def classify_measurement(activity: dict, config: dict) -> tuple[str, str]:
    """Interpret assay identity, endpoint, units and censored potency.

    Args:
        activity: ChEMBL activity plus its separately fetched assay object.
        config: Frozen organism, endpoint and potency constants.

    Returns:
        Active/inactive/unknown label and an auditable reason.
    """
    assay = activity.get("assay", {})
    if assay.get("assay_organism") not in config["organisms"] or assay.get("assay_type") != "F":
        return "unknown", "ineligible_assay"
    if activity.get("data_validity_comment") or activity.get("potential_duplicate"):
        return "unknown", "flagged_measurement"
    if activity.get("standard_type") not in config["endpoints"]:
        return "unknown", "ineligible_endpoint"
    scales = {"nM": 0.001, "uM": 1.0, "µM": 1.0, "μM": 1.0, "mM": 1000.0}
    if activity.get("standard_units") not in scales:
        return "unknown", "unsupported_units"
    try:
        value = float(activity["standard_value"]) * scales[activity["standard_units"]]
    except (ValueError, TypeError, KeyError):
        return "unknown", "missing_potency"
    if not math.isfinite(value) or value <= 0:
        return "unknown", "invalid_potency"
    threshold = config["potency_threshold_um"]
    relation = activity.get("standard_relation")
    if relation == "=":
        return ("active" if value <= threshold else "inactive"), "exact_potency"
    if relation in {"<", "<="} and value <= threshold:
        return "active", "upper_bound"
    if (relation == ">" and value >= threshold) or (relation == ">=" and value > threshold):
        return "inactive", "lower_bound"
    return "unknown", "indeterminate_censoring"


def label_compounds(
    compound_ids: list[str], measurements: list[dict], config: dict
) -> tuple[list[dict], list[dict]]:
    """Aggregate measured activity while preserving unknowns and discordance."""
    audit = []
    by_compound = {compound: [] for compound in compound_ids}
    for measurement in measurements:
        label, reason = classify_measurement(measurement, config)
        record = {**measurement, "label": label, "label_reason": reason}
        audit.append(record)
        by_compound.setdefault(measurement["compound_id"], []).append(record)
    rows = []
    for compound in dict.fromkeys(compound_ids):
        records = by_compound[compound]
        labels = {record["label"] for record in records}
        state = (
            "active" if "active" in labels else "inactive" if "inactive" in labels else "unknown"
        )
        rows.append(
            {
                "compound_id": compound,
                "label": state,
                "discordant": {"active", "inactive"}.issubset(labels),
                "eligible_measurements": sum(row["label"] != "unknown" for row in records),
                "activity_ids": sorted(
                    {str(row["activity_id"]) for row in records if row["label"] != "unknown"}
                ),
                "assay_ids": sorted(
                    {row["assay_chembl_id"] for row in records if row["label"] != "unknown"}
                ),
            }
        )
    return rows, audit
