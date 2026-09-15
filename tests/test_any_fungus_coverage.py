"""Check the any-fungus coverage classification rules.

These bind the endpoint and convertibility rules and the tier precedence the
amendment declares. They import nothing that requires a network or RDKit.
"""

import pytest

from src.any_fungus_coverage.endpoints import (
    CONVERTIBLE_UNITS,
    IC50,
    MIC,
    OTHER,
    PERCENT_INHIBITION,
    ZONE_OF_INHIBITION,
    endpoint_group,
    is_convertible,
)
from src.any_fungus_coverage.tiers import REPORT_ORDER


def test_tier_four_is_reported_first() -> None:
    """T4 must lead the report order even though it is numbered fourth."""
    assert REPORT_ORDER[0] == "T4"
    assert set(REPORT_ORDER) == {"T1", "T2", "T3", "T4", "T5"}


def test_mic_and_ic50_need_only_their_standard_type() -> None:
    """The potency groups are keyed on standard type alone."""
    assert endpoint_group("MIC", None) == MIC
    assert endpoint_group("MIC", "ug.mL-1") == MIC
    assert endpoint_group("IC50", "nM") == IC50


def test_percent_and_zone_groups_require_compatible_units() -> None:
    """Percent and zone groups need an explicit type and compatible units."""
    assert endpoint_group("Inhibition", "%") == PERCENT_INHIBITION
    assert endpoint_group("IZ", "mm") == ZONE_OF_INHIBITION


def test_ambiguous_records_stay_in_other() -> None:
    """A right type with a wrong or missing unit must not be assumed."""
    assert endpoint_group("Inhibition", None) == OTHER
    assert endpoint_group("IZ", None) == OTHER
    assert endpoint_group("Activity", "%") == OTHER
    assert endpoint_group(None, "%") == OTHER
    assert endpoint_group("MIC50", "ug.mL-1") == OTHER


def test_only_frozen_molar_units_convert() -> None:
    """Conversion is restricted to the frozen molar units."""
    for unit in CONVERTIBLE_UNITS:
        assert is_convertible("10", unit)
    assert not is_convertible("10", "ug.mL-1")
    assert not is_convertible("10", "%")
    assert not is_convertible("10", "mm")
    assert not is_convertible("10", None)


def test_non_positive_and_non_finite_values_do_not_convert() -> None:
    """Only finite positive magnitudes convert."""
    assert not is_convertible("0", "nM")
    assert not is_convertible("-5", "nM")
    assert not is_convertible(None, "nM")
    assert not is_convertible("", "nM")
    assert not is_convertible("not-a-number", "nM")
    assert not is_convertible(float("inf"), "nM")
    assert not is_convertible(float("nan"), "nM")


def test_booleans_are_not_read_as_values() -> None:
    """A boolean must not be silently read as the number one."""
    assert not is_convertible(True, "nM")


def test_convertible_accepts_numeric_and_string_forms() -> None:
    """ChEMBL records values as strings and as numbers."""
    assert is_convertible(2.5, "uM")
    assert is_convertible("2.5", "uM")


@pytest.mark.parametrize("unit", ["uM", "µM", "μM"])
def test_every_spelling_of_micromolar_converts(unit: str) -> None:
    """The three micromolar spellings must all be recognised."""
    assert is_convertible("1", unit)
