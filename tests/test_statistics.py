import pandas as pd
import pytest

from src.analysis.statistics import permutation_test


def config() -> dict:
    """Return a small deterministic configuration for a fast test."""
    return {"seed": 1729, "permutations": 100, "bootstrap_resamples": 100, "minimum_genera": 25}


def test_underpowered_result_has_no_primary_statistic() -> None:
    """Do not calculate an endpoint when the coverage trigger fails."""
    frame = pd.DataFrame(
        {
            "genus": ["A", "B", "C", "D"],
            "family": ["F1", "F1", "F2", "F2"],
            "rejected": [1, 1, 0, 0],
            "hit_fraction": [0.8, 0.6, 0.2, 0.4],
        }
    )
    first, null = permutation_test(frame, config())
    assert first["status"] == "feasibility_failure"
    assert first["estimable"] is False
    assert first["observed_difference"] is None
    assert first["p_one_sided"] is None
    assert first["variable_families"] == 0
    assert first["variable_genera"] == 0
    assert len(null) == 0


def test_permutation_is_seeded_after_feasibility_passes() -> None:
    """Calculate seeded permutations only on a sufficiently covered sample."""
    frame = pd.DataFrame({
        "genus": [f"G{index}" for index in range(26)],
        "family": ["F"] * 26,
        "rejected": [1] * 13 + [0] * 13,
        "hit_fraction": [0.8] * 13 + [0.2] * 13,
    })
    first, null = permutation_test(frame, config())
    second, repeat = permutation_test(frame, config())
    assert first["estimable"] is True
    assert first["observed_difference"] == pytest.approx(0.6)
    assert first["p_one_sided"] == second["p_one_sided"]
    assert (null == repeat).all()


def test_empty_frame_reports_both_feasibility_failures() -> None:
    """Keep valid empty input distinct from a missing upstream table."""
    summary, null = permutation_test(pd.DataFrame(), config())
    assert summary["n_genera"] == 0
    assert summary["feasibility_failures"] == [
        "fewer_than_minimum_joined_genera", "need_two_genera_per_direction"
    ]
    assert not len(null)


def test_family_coverage_is_counted_before_feasibility_gate() -> None:
    """Report exchangeable family membership without running an underpowered test."""
    frame = pd.DataFrame({
        "genus": ["A", "B", "C", "D"],
        "family": ["F1", "F1", "F2", "F2"],
        "rejected": [1, 0, 0, 0],
        "hit_fraction": [0.8, 0.3, 0.2, 0.4],
    })
    summary, null = permutation_test(frame, config(), within_family=True)
    assert summary["status"] == "feasibility_failure"
    assert summary["variable_families"] == 1
    assert summary["variable_genera"] == 2
    assert summary["permutations"] == 0
    assert summary["observed_difference"] is None
    assert summary["p_one_sided"] is None
    assert len(null) == 0
