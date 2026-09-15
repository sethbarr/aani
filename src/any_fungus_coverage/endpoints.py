"""Classify measurement endpoints and molar convertibility.

Convertibility is assessed independently of organism, endpoint, assay type,
validity flag and potency. It records only whether a value carries a finite
positive magnitude in one of the frozen molar units. Convertibility alone does
not establish a frozen active or inactive label.
"""

import math

CONVERTIBLE_UNITS = ("nM", "uM", "µM", "μM", "mM")

MIC = "MIC"
IC50 = "IC50"
PERCENT_INHIBITION = "percent inhibition"
ZONE_OF_INHIBITION = "zone of inhibition"
OTHER = "other"

ENDPOINT_GROUPS = (MIC, IC50, PERCENT_INHIBITION, ZONE_OF_INHIBITION, OTHER)

PERCENT_UNITS = ("%",)
ZONE_UNITS = ("mm",)


def endpoint_group(standard_type: str | None, standard_units: str | None) -> str:
    """Assign a measurement to an endpoint group.

    MIC and IC50 require those standard types. The percent and zone groups
    additionally require compatible units, so records with the right type but
    an incompatible or missing unit stay in the other group rather than being
    assumed.

    Args:
        standard_type: The ChEMBL standard type, possibly absent.
        standard_units: The ChEMBL standard units, possibly absent.

    Returns:
        One of the declared endpoint groups.
    """
    if standard_type == MIC:
        return MIC
    if standard_type == IC50:
        return IC50
    if standard_type == "Inhibition" and standard_units in PERCENT_UNITS:
        return PERCENT_INHIBITION
    if standard_type == "IZ" and standard_units in ZONE_UNITS:
        return ZONE_OF_INHIBITION
    return OTHER


def numeric_value(standard_value: object) -> float | None:
    """Read a standard value as a finite number.

    Args:
        standard_value: The raw standard value, which ChEMBL may record as a
            string, a number or nothing at all.

    Returns:
        The finite numeric value, or None when it is absent or not finite.
    """
    if standard_value is None or isinstance(standard_value, bool):
        return None
    try:
        value = float(standard_value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def is_convertible(standard_value: object, standard_units: str | None) -> bool:
    """Decide whether a measurement carries a convertible molar magnitude.

    Args:
        standard_value: The raw standard value.
        standard_units: The ChEMBL standard units.

    Returns:
        True when the value is finite and positive and the units are one of the
        frozen molar units. Mass concentrations, percentages, zones, missing
        values and unsupported units are not convertible, and no mass-to-molar
        conversion is inferred.
    """
    if standard_units not in CONVERTIBLE_UNITS:
        return False
    value = numeric_value(standard_value)
    return value is not None and value > 0.0
