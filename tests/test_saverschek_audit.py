"""Protect source-specific scientific decisions in the curated audit dataset."""

from pathlib import Path

from src.common.io import read_json, read_jsonl

AUDIT = Path("results/saverschek_audit")


def test_reversal_evidence_is_retained_and_excluded_from_primary() -> None:
    """Prevent missing acceptance from turning mixed taxa into rejecters."""
    genera = {r["genus"]: r for r in read_jsonl(AUDIT / "combined_genera.jsonl")}
    for genus in ["Hymenaea", "Inga", "Tetragastris", "Trichilia", "Miconia"]:
        assert genera[genus]["status"] == "conflict"
        assert genera[genus]["directions"] == ["accepted", "rejected"]
    primary = read_jsonl(AUDIT / "combined_genus_eligible_observations.jsonl")
    assert {r["genus"] for r in primary if r["outcome"] == "rejected"} == {
        "Desmopsis", "Hiraea", "Randia", "Sorocea"
    }
    assert not any(r["genus"] in {"Trema", "Stigmaphyllon", "Miconia"} for r in primary)


def test_table_sign_does_not_replace_author_direction() -> None:
    """Retain author rejection even when the provisional table index is positive."""
    rows = {r["cell_id"]: r for r in read_jsonl(AUDIT / "natural_contexts.jsonl")}
    for cell_id in ["SAVERSCHEK2010_individual_miconia_p_d1",
                    "SAVERSCHEK2010_individual_inga_p_d1",
                    "SAVERSCHEK2010_individual_trichilia_a_d2"]:
        row = rows[cell_id]
        assert row["outcome"] == "rejected"
        assert row["table_cell"]["summary_value_parsed_provisionally"] > 0
        assert not row["quantitative_measure_verified"]


def test_ambiguous_comparative_cells_remain_unknown() -> None:
    """Do not fill missing Figure 4 directions from rank or index signs."""
    rows = read_jsonl(AUDIT / "natural_contexts.jsonl")
    assert len(rows) == 110
    assert sum(r["outcome"] == "unclear" for r in rows) == 23
    spondias = [r for r in rows if r["genus_as_written"] == "Spondias"
                and r["experiment_id"] == "simultaneous_choice"]
    assert len(spondias) == 4 and all(r["outcome"] == "unclear" for r in spondias)


def test_recovered_figure_does_not_rewrite_model_input() -> None:
    """Keep the after-references caption traceable and model metrics unchanged."""
    tail = read_json(AUDIT / "figure7_recovered_tail.json")
    assert tail["blocks"][0]["block_id"] == "figure7_tail"
    assert tail["blocks"][0]["in_original_model_input"] is False
    summary = read_json(AUDIT / "summary.json")
    assert summary["extraction_metrics"]["candidate_records"] == 14
    assert len(read_jsonl(AUDIT / "extraction_candidate_audit.jsonl")) == 14
    assert summary["visual_numeric_cells_verified"] == 0
