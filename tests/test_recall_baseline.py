"""Protect the baseline's denominators, stage separation and reference provenance."""

from copy import deepcopy
from pathlib import Path

from src.common.io import read_json
from src.evaluation.recall import build_baseline, make_reference, score_species, summarise_group


def baseline() -> dict:
    """Load the saved development panel and its original extraction."""
    audit = read_json(Path("data/interim/saverschek_audit/natural_audit.json"))
    return build_baseline(audit, read_json(Path(audit["source_path"])),
                          Path("data/interim/extraction_saverschek"))


def test_original_baseline_counts_and_scope() -> None:
    """Keep failed grounding separate from detection and exclude other experiments."""
    report = baseline()
    assert report["status"] == "complete"
    assert report["inventory"]["reconciled_with_original_artifacts"]
    assert report["inventory"]["natural_panel_candidates"] == 11
    assert report["inventory"]["outside_panel_candidates"] == 3
    primary = report["groups"]["PRIMARY"]
    assert primary["species_denominator"] == 6
    assert [s["species_count"] for s in primary["stages"].values()] == [6, 2, 2]
    context = report["groups"]["CONTEXT"]
    assert context["species_denominator"] == 5
    assert context["species_direction_pair_denominator"] == 10
    assert [s["species_direction_pair_count"] for s in context["stages"].values()] == [4, 1, 1]
    assert context["stages"]["detection"]["direction_coverage"] == {
        "both_directions_surfaced": 0, "collapsed_to_one": 4, "absent": 1, "unscorable": 0,
    }
    assert context["stages"]["correctness"]["direction_coverage"] == {
        "both_directions_surfaced": 0, "collapsed_to_one": 1, "absent": 4, "unscorable": 0,
    }


def test_quote_mention_does_not_emit_acceptance() -> None:
    """Count Hymenaea's structured rejection once despite acceptance in its quote."""
    report = baseline()
    hymenaea = next(r for r in report["species"] if r["species"] == "Hymenaea courbaril")
    assert len(hymenaea["candidate_ids"]) == 2
    assert hymenaea["proposed_directions"] == ["rejected"]
    assert hymenaea["correct_directions"] == ["rejected"]


def test_provenance_records_author_grouping_and_ignores_table_sign() -> None:
    """Expose Miconia's mixed provenance without deriving direction from its zero cells.

    Table 1 groups species under printed author headings, so a grouped label is an
    author-assigned category rather than an inference of ours. The denominators and
    the split are unchanged by that reclassification.
    """
    report = baseline()
    assert report["groups"]["PRIMARY"]["reference_provenance_species"] == {
        "author_prose": 2, "author_table_grouping": 4,
    }
    assert report["groups"]["CONTEXT"]["reference_provenance_species"] == {
        "author_prose": 4, "author_table_grouping": 1,
    }
    miconia = next(r for r in report["species"] if r["species"] == "Miconia argentea")
    assert miconia["reference_directions"] == ["accepted", "rejected"]
    assert [s["provenance_strength"] for s in miconia["reference_support"]] == [
        "author_prose", "author_table_grouping",
    ]
    assert miconia["provenance_strength"] == "author_table_grouping"
    assert not any(s["numerical_values_used_for_direction"] for s in miconia["reference_support"])


def test_miconia_context_basis_is_recorded() -> None:
    """The reference-set definition must state why Miconia is held in CONTEXT."""
    report = baseline()
    basis = report["miconia_context_basis"]
    assert "Immediate rejection" in basis or "immediate-rejection" in basis
    assert "CONTEXT" in basis
    assert "6 PRIMARY" in basis and "5 CONTEXT" in basis
    assert report["groups"]["PRIMARY"]["species_denominator"] == 6
    assert report["groups"]["CONTEXT"]["species_denominator"] == 5


def test_unscorable_reference_stays_in_denominator() -> None:
    """Retain a missing species with its reason instead of shrinking the panel."""
    audit = read_json(Path("data/interim/saverschek_audit/natural_audit.json"))
    damaged = deepcopy(audit)
    damaged["plants"] = [r for r in audit["plants"] if r["genus_as_written"] != "Trema"]
    rows = [score_species(r, []) for r in make_reference(damaged, read_json(Path(audit["source_path"])))]
    summary = summarise_group(rows, "PRIMARY")
    assert summary["species_denominator"] == 6
    assert summary["unscorable_species"] == ["Trema micrantha"]
    trema = next(r for r in rows if r["species"] == "Trema micrantha")
    assert trema["detection"] is None
    assert trema["blocked_reason"] == "reference_missing_or_disagrees_with_fixed_panel"


def test_wrong_surviving_direction_does_not_get_correctness_credit() -> None:
    """Keep a grounded direction error visible at the correctness stage."""
    reference = baseline()["species"][0]
    row = score_species(reference, [{
        "candidate_id": "test", "record": {"plant_name_as_written": reference["species"],
                                             "outcome": "accepted"},
        "grounding_status": "passed", "blocked_reason": None,
    }])
    assert row["detection"] and row["survival"]
    assert not row["correctness"]
    assert row["incorrect_surviving_directions"] == ["accepted"]
