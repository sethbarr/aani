"""Exploratory lineage tiers and frozen-unit convertibility."""

import math

SCALES = {"nM": 0.001, "uM": 1.0, "µM": 1.0, "μM": 1.0, "mM": 1000.0}
ENDPOINTS = ("MIC", "IC50", "percent inhibition", "zone of inhibition", "other")
TIERS = ("T1", "T2", "T3", "T4", "T5")


def interpretable_result(activity: dict) -> bool:
    """Flag numerical or explicit qualitative results without making activity labels."""
    for field in ("standard_value", "value"):
        try:
            if math.isfinite(float(activity.get(field))):
                return True
        except (ValueError, TypeError):
            pass
    reported = {
        "active", "not active", "inactive", "no inhibition", "toxic",
        "dose-dependent effect", "below limit of detection",
    }
    return any(
        str(activity.get(field) or "").strip().casefold() in reported
        for field in ("standard_text_value", "text_value", "activity_comment")
    )


def conversion(activity: dict) -> tuple[float | None, str]:
    """Apply only the numerical and unit portion of the frozen rules."""
    units = activity.get("standard_units")
    if units not in SCALES:
        return None, "unsupported_units"
    try:
        value = float(activity["standard_value"]) * SCALES[units]
    except (ValueError, TypeError, KeyError):
        return None, "missing_potency"
    if not math.isfinite(value) or value <= 0:
        return None, "invalid_potency"
    return value, "convertible"


def endpoint_group(activity: dict) -> str:
    """Group explicit standard endpoints, preserving ambiguous types as other."""
    name = (activity.get("standard_type") or "").strip()
    units = (activity.get("standard_units") or "").strip()
    if name in {"MIC", "IC50"}:
        return name
    normalized = name.casefold()
    if normalized in {
        "iz",
        "diz",
        "zone of inhibition",
        "inhibition zone",
        "inhibition zone diameter",
        "zone diameter",
    }:
        return "zone of inhibition" if units in {"", "mm", "cm", "um", "µm"} else "other"
    description = (activity.get("assay_description") or "").casefold()
    if units == "%" and (
        "inhibition" in normalized
        or normalized == "gi"
        or (normalized == "activity" and "inhibition" in description)
    ):
        return "percent inhibition"
    if normalized == "activity" and units in {"mm", "cm"} and (
        "inhibition zone" in description or "zone of inhibition" in description
    ):
        return "zone of inhibition"
    return "other"


def anchor_ids(names: dict[str, list[str]], resolved: dict[str, dict]) -> dict[str, set[str]]:
    """Compile resolved declared anchors into canonical taxon-ID sets."""
    return {
        group: {
            resolved[name]["tax_id"] for name in values if resolved[name]["status"] == "resolved"
        }
        for group, values in names.items()
    }


def classify_taxon(taxon: dict, anchors: dict[str, set[str]]) -> dict:
    """Classify authoritative ancestor IDs and expose ecological uncertainty."""
    lineage = set(taxon["lineage_ids"])
    fungal = bool(lineage & anchors["fungi"])
    phytophthora = bool(lineage & anchors["phytophthora"])
    oomycete = bool(lineage & anchors["oomycete"]) or phytophthora
    tiers = []
    if fungal:
        tiers = [tier for tier in TIERS[:4] if lineage & anchors[tier]]
        if "T1" in tiers and "T2" in tiers:
            tiers.remove("T2")
        if not tiers:
            tiers = ["T5"]
    elif phytophthora:
        tiers = ["T3"]
    return {
        "tiers": tiers,
        "is_fungus": fungal,
        "is_oomycete": oomycete,
        "is_phytophthora": phytophthora,
        "is_model_organism": bool(lineage & anchors["model"]),
        "fusarium_role_unspecified": bool(lineage & anchors["fusarium"]),
        "potential_cultivar": bool(lineage & anchors["potential_cultivar"]) and "T4" not in tiers,
        "role_status": "pathogen_associated_lineage"
        if set(tiers) & {"T1", "T2", "T3"}
        else "attine_cultivar"
        if "T4" in tiers
        else "other_or_unknown",
    }


def assay_taxonomy(assay: dict, taxonomy: dict) -> dict:
    """Join by assay taxon ID, using a name fallback only if its ID is absent."""
    if assay.get("assay_tax_id"):
        key = f"id:{assay['assay_tax_id']}"
    elif assay.get("assay_organism"):
        key = f"name:{assay['assay_organism']}"
    else:
        return {"status": "unresolved", "error": "Assay has neither organism nor taxon ID"}
    return taxonomy.get(key, {"status": "unqueried", "error": f"Taxonomy unqueried: {key}"})
