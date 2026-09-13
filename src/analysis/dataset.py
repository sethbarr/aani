"""Build genus and compound tables without turning missing data into negatives."""

import json

import pandas as pd

from src.behaviour.aggregation import deduplicate


def aggregate_behaviour(
    observations: list[dict], evidence: set[str] | None = None, delayed_only: bool = False
) -> tuple[list[dict], list[dict]]:
    """Assign a genus direction only when eligible source observations agree."""
    eligible, review = [], []
    for row in observations:
        reason = None
        if row.get("semantic_decision", "include") != "include":
            reason = "not_semantically_retained"
        elif not row.get("genus") or not row.get("family"):
            reason = "missing_taxonomic_classification"
        elif row["substrate_treatment"] != "natural" or not row["behavioural_choice"]:
            reason = "not_natural_substrate_choice"
        elif row["evidence_type"] == "review_secondary":
            reason = "secondary_evidence_requires_deduplication"
        elif evidence is not None and row["evidence_type"] not in evidence:
            reason = "outside_evidence_sensitivity"
        elif row["outcome"] not in {"accepted", "rejected"}:
            reason = "unclear_direction"
        elif delayed_only and row["outcome"] == "rejected" and row["rejection_timing"] != "delayed":
            reason = "not_delayed_rejection"
        if reason:
            review.append({**row, "exclusion_reason": reason})
        else:
            eligible.append(row)
    if not eligible:
        return [], review
    unique, duplicates = deduplicate(eligible)
    review.extend({**row, "exclusion_reason": row["reason"]} for row in duplicates)
    frame = pd.DataFrame(unique)
    originals = {row["grounded_identity"]: row for row in unique}
    genera = []
    for genus, group in frame.groupby("genus", sort=True):
        if group["outcome"].nunique() != 1 or group["family"].nunique() != 1:
            review.extend(
                {
                    **originals[identity],
                    "exclusion_reason": "conflicting_genus_direction_or_family",
                }
                for identity in group["grounded_identity"]
            )
            continue
        genera.append(
            {
                "genus": genus,
                "family": group["family"].iloc[0],
                "rejected": int(group["outcome"].iloc[0] == "rejected"),
                "n_sources": group["source_id"].nunique(),
                "n_ant_species": group["ant_species"].nunique() if "ant_species" in group else 0,
                "n_observations": len(group),
                "source_ids": sorted(group["source_id"].unique().tolist()),
                "source_urls": sorted(group["source_url"].unique().tolist()),
                "behaviour_record_ids": sorted(group["record_id"].unique().tolist()),
                "accepted_names": sorted(group["accepted_name"].unique().tolist()),
            }
        )
    return genera, review


def build_dataset(
    observations: list[dict],
    occurrences: list[dict],
    labels: list[dict],
    evidence: set[str] | None = None,
    delayed_only: bool = False,
    exclude_discordant: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Join directional genera to deduplicated structures and measured labels.

    Args:
        observations: Taxonomically resolved behavioural observations.
        occurrences: Validated occurrence records.
        labels: One assay classification per compound.
        evidence: Optional allowed evidence types.
        delayed_only: Restrict rejected observations to delayed rejection.
        exclude_discordant: Treat discordant assay labels as unknown.

    Returns:
        Genus summary, classified genus–compound model rows and review records.
    """
    genera, review = aggregate_behaviour(observations, evidence, delayed_only)
    label_map = {row["compound_id"]: row for row in labels}
    if len(label_map) != len(labels):
        raise ValueError("Activity labels must be unique by compound_id")
    summaries, model_rows = [], []
    for genus in genera:
        matching = [row for row in occurrences if row["genus"] == genus["genus"]]
        if not matching:
            review.append({**genus, "exclusion_reason": "no_chemistry"})
            continue
        frame = pd.DataFrame(matching)
        distinct = frame.drop_duplicates("occurrence_id")
        structures = sorted(frame["compound_id"].unique().tolist())
        species_matches = (frame["aggregation_level"] == "species") & frame[
            "plant_name"
        ].isin(genus["accepted_names"])
        species_match_by_occurrence = species_matches.groupby(frame["occurrence_id"]).any()
        covariates = {
            "phytochemistry_records": len(distinct),
            "species_match_fraction": float(species_match_by_occurrence.mean()),
        }
        classified, active_count = [], 0
        for compound in structures:
            label = label_map.get(compound, {"label": "unknown"})
            if label["label"] not in {"active", "inactive", "unknown"}:
                raise ValueError(f"Unrecognised activity label for {compound}")
            if label.get("retrieval_status") == "failed":
                continue
            if label["label"] == "unknown" or (exclude_discordant and label.get("discordant")):
                continue
            active = int(label["label"] == "active")
            active_count += active
            classified.append(compound)
            model_rows.append(
                {
                    "genus": genus["genus"],
                    "family": genus["family"],
                    "compound_id": compound,
                    "rejected": genus["rejected"],
                    "active": active,
                    **covariates,
                }
            )
        if not classified:
            review.append(
                {
                    **genus,
                    **covariates,
                    "n_compounds": len(structures),
                    "exclusion_reason": "no_classified_compounds",
                }
            )
            continue
        summaries.append(
            {
                **genus,
                **covariates,
                "n_compounds": len(structures),
                "n_classified": len(classified),
                "n_active": active_count,
                "n_unknown": len(structures) - len(classified),
                "hit_fraction": active_count / len(classified) if classified else None,
                "assay_coverage": len(classified) / len(structures),
                "documented_active_fraction": active_count / len(structures),
                "compound_ids": structures,
                "occurrence_references": sorted(frame["reference_url"].unique().tolist()),
            }
        )
    return pd.DataFrame(summaries), pd.DataFrame(model_rows), review


def csv_ready(frame: pd.DataFrame) -> pd.DataFrame:
    """Encode list-valued provenance columns as portable JSON strings."""
    result = frame.copy()
    for column in result.columns:
        result[column] = result[column].map(encode_cell)
    return result


def encode_cell(value: object) -> object:
    """Serialize nested provenance while leaving scalar values unchanged."""
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
