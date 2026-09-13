"""Test stage orchestration on unavailable versus genuinely empty inputs."""

from pathlib import Path

import pandas as pd

from scripts.analyse import run_analysis
from src.common.io import read_json, write_json, write_jsonl


def test_missing_upstream_writes_explicit_blocked_artifacts(tmp_path: Path) -> None:
    """Keep unknown coverage counts null when input files do not exist."""
    metrics = run_analysis(
        tmp_path / "observations.jsonl", tmp_path / "occurrences.jsonl", tmp_path / "labels.jsonl",
        tmp_path / "results", tmp_path / "processed", offline=True,
    )
    assert metrics["status"] == "blocked"
    assert metrics["genera_with_chemistry"] is None
    summary = read_json(tmp_path / "results/primary/summary.json")
    assert summary["estimable"] is False
    assert summary["observed_difference"] is None
    assert summary["n_genera"] is None
    assert pd.read_csv(tmp_path / "results/primary/genera.csv").empty


def test_genuine_empty_inputs_report_zero_coverage(tmp_path: Path) -> None:
    """Complete empty inputs run all sensitivities with known zero counts."""
    paths = [tmp_path / f"{name}.jsonl" for name in ("observations", "occurrences", "labels")]
    for path in paths:
        write_jsonl(path, [])
    metrics = run_analysis(*paths, tmp_path / "results", tmp_path / "processed", offline=True)
    assert metrics["status"] == "complete"
    assert metrics["genera_available_for_primary_test"] == 0
    assert metrics["primary_status"] == "feasibility_failure"
    summary = read_json(tmp_path / "results/primary/summary.json")
    assert summary["n_genera"] == 0
    assert summary["permutations"] == 0
    assert summary["p_one_sided"] is None
    assert summary["mixed_effects"]["estimable"] is False
    assert not (tmp_path / "results/figures/enrichment.png").exists()


def test_blocked_chemistry_is_not_a_measured_empty_join(tmp_path: Path) -> None:
    """Propagate acquisition blockage even when placeholder output files exist."""
    paths = [tmp_path / f"{name}.jsonl" for name in ("observations", "occurrences", "labels")]
    for path in paths:
        write_jsonl(path, [])
    chemistry = tmp_path / "chemistry_metrics.json"
    write_json(chemistry, {"status": "blocked", "blocked_reason": "export_unverified"})
    metrics = run_analysis(*paths, tmp_path / "results", tmp_path / "processed", chemistry, offline=True)
    assert metrics["status"] == "blocked"
    assert "export_unverified" in metrics["blocked_reason"]
    assert metrics["genera_available_for_primary_test"] is None
