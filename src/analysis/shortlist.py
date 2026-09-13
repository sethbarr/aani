"""Exploratory, reference-relative structural novelty ranking."""

import numpy as np
import pandas as pd


def rank_candidates(
    genera: pd.DataFrame, occurrences: list[dict], labels: list[dict]
) -> tuple[pd.DataFrame, dict]:
    """Rank only when structures and a measured-active reference set are available."""
    if genera.empty:
        return pd.DataFrame(), {"status": "not_estimable", "reason": "no_genera"}
    try:
        from rdkit import Chem, DataStructs
        from rdkit.Chem import rdFingerprintGenerator
    except ImportError:
        return pd.DataFrame(), {
            "status": "not_estimable",
            "reason": "install_optional_rdkit_dependency",
        }
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    fingerprints = {}
    for row in occurrences:
        molecule = Chem.MolFromSmiles(row["canonical_smiles"])
        if molecule is not None and Chem.MolToInchiKey(molecule) == row["compound_id"]:
            fingerprints[row["compound_id"]] = generator.GetFingerprint(molecule)
    reference = [
        fingerprints[row["compound_id"]]
        for row in labels
        if row["label"] == "active" and row["compound_id"] in fingerprints
    ]
    if not reference:
        return pd.DataFrame(), {
            "status": "not_estimable",
            "reason": "no_valid_active_reference_structures",
        }
    candidate_rows = genera.loc[genera["rejected"] == 1].to_dict("records")
    excluded = [
        row["genus"]
        for row in candidate_rows
        if not all(compound in fingerprints for compound in row["compound_ids"])
    ]
    if excluded:
        return pd.DataFrame(), {
            "status": "not_estimable",
            "reason": "required_structures_unavailable",
            "excluded_missing_structures": excluded,
            "reference_structures": len(reference),
        }
    rows = []
    for row in candidate_rows:
        structures = row["compound_ids"]
        novelty = float(
            np.median(
                [
                    1 - max(DataStructs.BulkTanimotoSimilarity(fingerprints[compound], reference))
                    for compound in structures
                ]
            )
        )
        support = min(1.0, row["n_sources"] / 3)
        rows.append(
            {
                **row,
                "rejection_support": support,
                "reference_relative_novelty": novelty,
                "shortlist_score": support * novelty * (1 - row["assay_coverage"]),
            }
        )
    ranked = pd.DataFrame(rows)
    if not ranked.empty:
        ranked = ranked.sort_values(["shortlist_score", "genus"], ascending=[False, True])
    return ranked, {
        "status": "ok" if rows else "not_estimable",
        "ranked_genera": len(rows),
        "excluded_missing_structures": [],
        "reference_structures": len(reference),
    }
