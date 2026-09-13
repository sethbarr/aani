"""Deduplicate grounded contexts and apply the frozen genus unanimity rule."""

from src.common.io import digest, normalise_space


def grounded_identity(row: dict) -> str:
    """Identify an observation independently of its extractor-assigned ID.

    Args:
        row: Grounded observation with taxonomic and experimental context.

    Returns:
        Hash of source, genus, direction, quote, ant and actual context. Distinct
        habitats, days, designs and ant species remain distinct observations.
    """
    fields = [
        "source_id", "genus", "outcome", "evidence_quote", "ant_species",
        "study_context", "experiment_id", "habitat", "test_day", "choice_design",
        "substrate_treatment", "rejection_timing", "evidence_type",
    ]
    identity = {key: normalise_space(str(row.get(key, ""))) for key in fields}
    return digest(identity)


def deduplicate(observations: list[dict]) -> tuple[list[dict], list[dict]]:
    """Keep one copy of each identical grounded context and retain duplicate IDs."""
    unique: dict[str, dict] = {}
    duplicate_rows = []
    for row in observations:
        key = grounded_identity(row)
        if key in unique:
            retained = unique[key]
            retained["merged_record_ids"].append(row["record_id"])
            duplicate_rows.append({
                "discarded_record_id": row["record_id"],
                "retained_record_id": retained["record_id"],
                "source_id": row["source_id"],
                "genus": row["genus"],
                "grounded_identity": key,
                "reason": "identical_grounded_observation_within_source_and_genus",
            })
        else:
            unique[key] = {
                **row, "grounded_identity": key, "merged_record_ids": [row["record_id"]],
            }
    return list(unique.values()), duplicate_rows


def eligibility_reason(row: dict) -> str | None:
    """Apply primary natural-substrate, directional and original-source eligibility."""
    if row.get("substrate_treatment") != "natural" or not row.get("behavioural_choice"):
        return "not_natural_substrate_choice"
    if row.get("evidence_type") == "review_secondary":
        return "secondary_evidence_requires_resolution"
    if row.get("outcome") not in {"accepted", "rejected"}:
        return "unclear_direction"
    if row.get("semantic_decision", "include") != "include":
        return "not_semantically_retained"
    if not row.get("genus") or not row.get("family"):
        return "missing_taxonomic_classification"
    return None


def summarize_genus(genus: str, rows: list[dict]) -> dict:
    """Count sources, ants and observations without claiming independent replicates."""
    directions = sorted({row["outcome"] for row in rows})
    families = sorted({row["family"] for row in rows})
    conflict = len(directions) != 1 or len(families) != 1
    outcome = "conflict" if conflict else directions[0]
    source_ids = sorted({row["source_id"] for row in rows})
    ant_species = sorted({row["ant_species"] for row in rows})
    accepted_names = sorted({row["accepted_name"] for row in rows})
    return {
        "genus": genus,
        "outcome": outcome,
        "status": outcome,
        "rejected": None if conflict else int(outcome == "rejected"),
        "family": families[0] if len(families) == 1 else None,
        "families": families,
        "directions": directions,
        "n_sources": len(source_ids),
        "n_ant_species": len(ant_species),
        "n_observations": len(rows),
        "n_accepted_species": len(accepted_names),
        "source_ids": source_ids,
        "source_urls": sorted({row["source_url"] for row in rows}),
        "ant_species": ant_species,
        "accepted_names": accepted_names,
        "behaviour_record_ids": sorted(row["record_id"] for row in rows),
        "observation_count_interpretation": "deduplicated_contexts_not_independent_replicates",
        "primary_eligible": not conflict,
        "conflict_reason": (
            "mixed_directions" if len(directions) > 1 else "inconsistent_family"
        ) if conflict else None,
    }


def aggregate(observations: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Separate unanimous genera, conflicting genera and ineligible observations."""
    groups: dict[str, list[dict]] = {}
    review = []
    for row in observations:
        reason = eligibility_reason(row)
        if reason:
            review.append({**row, "exclusion_reason": reason})
        else:
            groups.setdefault(row["genus"], []).append(row)
    genera, conflicts = [], []
    for genus, members in sorted(groups.items()):
        result = summarize_genus(genus, members)
        if result["primary_eligible"]:
            genera.append(result)
        else:
            conflicts.append(result)
    return genera, conflicts, review


def verify_miconia(observations: list[dict], conflicts: list[dict]) -> dict:
    """Verify both named species and opposite directions from the actual records."""
    members = [row for row in observations if row["genus"] == "Miconia"]
    tococa = [row for row in members if row["source_id"] == "PMC11543716"
              and row["plant_name_as_written"].casefold() == "tococa"
              and row["accepted_name"] == "Miconia microphysca"
              and row["outcome"] == "accepted"]
    rejected = [row for row in members if row["source_id"] == "SAVERSCHEK2010"
                and row["accepted_name"] == "Miconia argentea"
                and row["outcome"] == "rejected"]
    accepted = [row for row in members if row["source_id"] == "SAVERSCHEK2010"
                and row["accepted_name"] == "Miconia argentea"
                and row["outcome"] == "accepted"]
    conflict = next((row for row in conflicts if row["genus"] == "Miconia"), None)
    verified = bool(tococa and rejected and accepted and conflict)
    return {
        "verified": verified,
        "tococa_resolved_to_Miconia_microphysca_acceptance_ids": [
            row["record_id"] for row in tococa
        ],
        "Saverschek_Miconia_argentea_rejection_ids": [row["record_id"] for row in rejected],
        "Saverschek_Miconia_argentea_acceptance_ids": [row["record_id"] for row in accepted],
        "conflict_genus_present": conflict is not None,
        "primary_eligible": False if conflict else None,
    }
