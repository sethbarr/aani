"""Verify composition matching, duplicate handling, and empty or forced controls."""

from dataclasses import replace

import numpy as np
import pytest

pytest.importorskip("rdkit", reason="RDKit is an optional chemistry dependency")

from src.chemical_distance.fingerprints import build_structures, morgan_generator  # noqa: E402
from src.chemical_distance.robustness import (  # noqa: E402
    Unit,
    build_populations,
    build_strata,
    collapse_fingerprints,
    complement_score,
    interpretation,
    run_cell,
    sample_reference,
    size_bin,
)


def fixture_units() -> list[Unit]:
    """Create structures spanning genus overlap, size boundaries, and duplicate identities."""
    specs = [("a", "c1ccccc1O"), ("b", "c1ccccc1O"), ("c", "CCCCCC"),
             ("d", "c1ccncc1"), ("e", "N"), ("f", "CCCCCCCCCCCC")]
    structures, _ = build_structures(specs, morgan_generator())
    genera = [("Arabidopsis",), ("Randia",), ("Randia",), ("Randia",), (), ("Arabidopsis",)]
    return [Unit(structures[key], (key,), (key,) if key in {"b", "c", "f"} else (),
                 genus, float(structures[key].heavy_atoms))
            for (key, _), genus in zip(specs, genera, strict=True)]


@pytest.mark.parametrize(("value", "expected"), [(0, 0), (5, 0), (6, 1), (10, 1),
                                                  (11, 2), (20.5, 2), (61, 6)])
def test_size_bins_are_half_open(value: float, expected: int) -> None:
    """Place declared boundaries consistently, including class-median atom counts."""
    assert size_bin(value) == expected


def test_duplicate_class_combines_provenance_and_removes_measured_siblings() -> None:
    """Retain an unmeasured representative while marking its entire class as measured."""
    units = fixture_units()
    collapsed = collapse_fingerprints(units)
    group = next(unit for unit in collapsed if unit.members == ("a", "b"))
    assert group.structure.compound_id == "a"
    assert group.measured_members == ("b",)
    assert group.measured
    assert group.genera == ("Arabidopsis", "Randia")
    assert sum(unit.measured for unit in collapsed) == 3
    assert units[0].measured is False


def test_population_filter_excludes_multigenus_arabidopsis_classes() -> None:
    """Remove small structures before collapse and exclude any Arabidopsis membership."""
    populations = build_populations(fixture_units())
    assert len(populations["original"]) == 6
    assert len(populations["size_filtered"]) == 5
    assert len(populations["fingerprint_collapsed"]) == 4
    assert {unit.members for unit in populations["without_arabidopsis"]} == {("c",), ("d",)}


@pytest.mark.parametrize("scheme", ["unrestricted", "size", "genus", "joint"])
def test_every_draw_preserves_exact_stratum_counts(scheme: str) -> None:
    """Keep without-replacement sampling and all observed matching margins."""
    units = fixture_units()
    strata = build_strata(units, scheme)
    generator = np.random.default_rng(7)
    for _ in range(50):
        reference = sample_reference(strata, generator)
        assert len(reference) == len(set(reference)) == 3
        for stratum in strata:
            assert len(set(reference) & set(stratum.indices)) == stratum.picks


def test_genus_strata_use_membership_tuple() -> None:
    """Keep a multi-genus unit separate from either singleton genus."""
    units = collapse_fingerprints(fixture_units())
    keys = {stratum.key for stratum in build_strata(units, "genus")}
    assert ("Arabidopsis", "Randia") in keys
    assert ("Arabidopsis",) in keys
    assert ("Randia",) in keys


def test_complement_statistic_excludes_reference_units() -> None:
    """Exclude unit diagonal values and recompute queries for each new selection."""
    matrix = np.array([[1, 0.1, 0.2], [0.1, 1, 0.9], [0.2, 0.9, 1]])
    assert complement_score(matrix, np.array([0])) == pytest.approx(0.15)
    assert complement_score(matrix, np.array([1])) == pytest.approx(0.5)


def test_forced_strata_are_explicitly_degenerate() -> None:
    """Expose a fixed reference selection instead of treating it as an informative null."""
    units = [replace(unit, genera=(f"genus_{index}",))
             for index, unit in enumerate(fixture_units())]
    result, values = run_cell(np.eye(len(units)), units, "genus", 7, draws=16)
    assert result["forced_reference_units"] == 3
    assert result["exchangeable_reference_units"] == 0
    assert result["distinct_reference_sets"] == 1
    assert result["degenerate"] is True
    assert values == [0.0] * 16


def test_empty_reference_stays_unscorable() -> None:
    """Keep missing comparisons out of numerical and interpretive conclusions."""
    units = [replace(unit, measured_members=()) for unit in fixture_units()]
    result, values = run_cell(np.eye(len(units)), units, "size", 7, draws=16)
    assert result["status"] == "unscorable"
    assert values == []


def test_randomized_control_is_reproducible() -> None:
    """Reproduce complete draws from a fixed generator seed."""
    units = fixture_units()
    matrix = np.random.default_rng(8).random((len(units), len(units)))
    first = run_cell(matrix, units, "unrestricted", 7, draws=16)
    second = run_cell(matrix, units, "unrestricted", 7, draws=16)
    assert first == second
    assert first[0]["completed_draws"] == 16


def test_interpretation_requires_all_sixteen_cells() -> None:
    """Prohibit a complete robustness verdict for a selected subset of analyses."""
    assert "incomplete" in interpretation([])


def test_randomization_reading_does_not_claim_every_draw_exceeds_observation() -> None:
    """A lower-tail observation can still exceed individual random draws."""
    from src.chemical_distance.nullmodel import NullResult, coverage_reading

    result = NullResult(0.2, 0.4, 0.3, 0.5, 2000, 20, 21 / 2001, 7)
    reading = coverage_reading(result)
    assert "below the central 95% range" in reading
    assert "every" not in reading
    assert "cause" not in reading


@pytest.mark.parametrize("violation", ["positive", "degenerate", "joint_inside"])
def test_one_failed_control_prevents_robustness_claim(violation: str) -> None:
    """Require every declared condition even when the other controls look favorable."""
    from src.chemical_distance.robustness import POPULATIONS, SCHEMES

    cells = [{"population": population, "scheme": scheme, "status": "complete",
              "difference": -0.1, "degenerate": False, "below_null_low": True}
             for population in POPULATIONS for scheme in SCHEMES]
    assert "is descriptively robust" in interpretation(cells)
    if violation == "positive":
        cells[0]["difference"] = 0.01
    elif violation == "degenerate":
        cells[0]["degenerate"] = True
    else:
        cells[-1]["below_null_low"] = False
    assert "does not satisfy" in interpretation(cells)
