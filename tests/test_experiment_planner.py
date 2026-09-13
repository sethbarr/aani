"""Scientific provenance and layout failure cases for prospective experiment planning."""

import ast
import copy
import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from src.experiments.planner import build_plan, export_plan

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def inputs() -> tuple[list[dict], dict]:
    """Use small source fixtures so unit tests do not depend on research snapshots."""
    config = json.loads((ROOT / "config/experiment_panel.json").read_text())
    evidence = [{
        "record_id": record_id, "material": name, "material_type": "pure_compound",
        "source_plant": "Plant species", "source_organ": "leaf",
        "original_url": "https://example.org/source", "source_locator": "Table 1",
        "endpoint": "remaining_growth", "endpoint_value": 0,
        "endpoint_unit": "%", "limitations": "One source isolate",
    } for record_id, name in zip(config["default_records"], ("A", "B", "C"), strict=True)]
    return evidence, config


def test_unknown_outcomes_and_historical_zero_are_distinct(inputs: tuple) -> None:
    """Never use a historical endpoint as a new measurement or new dose."""
    evidence, config = inputs
    original = copy.deepcopy((evidence, config))
    plan = build_plan(evidence, config)
    assert plan["candidates"][0]["evidence"]["endpoint_value"] == 0
    assert all(row["value"] is None and row["status"] == "not_tested" for row in plan["matrix"])
    assert all(row["dose_value"] is None for row in plan["layout"])
    assert all(value is None for fungus in plan["fungi"] for value in fungus["method"].values())
    assert (evidence, config) == original
    assert len(plan["matrix"]) == 15
    assert not plan["biological_execution_ready"]
    assert plan == build_plan(evidence, config)


def test_plate_overflow_keeps_controls_and_independent_runs(inputs: tuple) -> None:
    """Spilling to another plate must not drop controls or merge independent runs."""
    evidence, config = inputs
    config["design"]["dose_slots"] = 6
    plan = build_plan(evidence, config)
    plates = defaultdict(list)
    for row in plan["layout"]:
        plates[row["plate_id"]].append(row)
    assert len(plates) == 20
    for rows in plates.values():
        assert len(rows) <= 96
        assert len({r["well"] for r in rows}) == len(rows)
        assert len({r["independent_run"] for r in rows}) == 1
        counts = Counter(r["role"] for r in rows)
        assert counts["treatment"] == counts["material_only_blank"]
        for control in ("vehicle_growth", "medium_blank", "reference_antifungal"):
            assert counts[control] == 3


def test_duplicate_endpoints_cannot_become_independent_candidates(inputs: tuple) -> None:
    """A second endpoint from one material must not inflate the panel size."""
    evidence, config = inputs
    evidence.append(dict(evidence[0], record_id="duplicate-endpoint", endpoint="IC95"))
    with pytest.raises(ValueError, match="representative record"):
        build_plan(evidence, config, [evidence[0]["record_id"], "duplicate-endpoint"])


@pytest.mark.parametrize("records,fungi", [([], None), (["unknown"], None),
                                           (None, []), (None, ["unknown"])])
def test_invalid_selection_fails_closed(inputs: tuple, records: list, fungi: list) -> None:
    """A typo or empty panel must not silently produce a plausible default study."""
    with pytest.raises(ValueError):
        build_plan(*inputs, records, fungi)


def test_overcapacity_condition_is_rejected(inputs: tuple) -> None:
    """Reject a condition group that cannot fit with required blanks and controls."""
    evidence, config = inputs
    config["design"]["dose_slots"] = 20
    with pytest.raises(ValueError, match="capacity"):
        build_plan(evidence, config)


def test_export_escapes_evidence_and_clears_stale_simulation(inputs: tuple, tmp_path: Path) -> None:
    """Source text cannot escape the HTML data block or masquerade as a new simulation."""
    evidence, config = inputs
    evidence[0]["material"] = '</script><script>alert("source text")</script>'
    evidence[1]["material"] = '=HYPERLINK("https://example.org")'
    plan = build_plan(evidence, config)
    (tmp_path / "simulation_report.json").write_text('{"status":"passed"}')
    export_plan(plan, tmp_path)
    html = (tmp_path / "index.html").read_text()
    assert evidence[0]["material"] not in html
    data_text = html.split('<script id="plan-data" type="application/json">')[1].split('</script>')[0]
    assert json.loads(data_text)["plan"] == plan
    rows = list(csv.DictReader(io.StringIO((tmp_path / "study_matrix.csv").read_text())))
    assert rows[1]["material"].startswith("'=")
    assert rows[0]["value"] == ""
    assert json.loads((tmp_path / "simulation_report.json").read_text())["status"] == "not_run"
    tree = ast.parse((tmp_path / "opentrons_water_demo.py").read_text())
    destinations = next(ast.literal_eval(node.value) for node in tree.body
                        if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "DESTINATIONS"
                                for t in node.targets))
    assert len(destinations) == len(set(destinations)) == 81
    assert (tmp_path / "potato_brief.md").is_file()
