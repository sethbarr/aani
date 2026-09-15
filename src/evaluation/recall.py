"""Measure existing extraction against a fixed, source-audited development panel."""

from collections import Counter
from pathlib import Path

from src.common.io import digest, read_json, read_jsonl

AUTHOR_PROSE = "author_prose"
AUTHOR_TABLE_GROUPING = "author_table_grouping"
PROVENANCE_CLASSES = (AUTHOR_PROSE, AUTHOR_TABLE_GROUPING)

MICONIA_CONTEXT_BASIS = (
    "Miconia argentea is grouped under the printed immediate-rejection heading in Table 1 "
    "of the original, and was accepted in both habitats in the simultaneous-choice tests. "
    "It is held in CONTEXT on that basis, carrying both directions. Denominators are "
    "unchanged at 6 PRIMARY and 5 CONTEXT."
)

PANEL = {
    "Desmopsis panamensis": ("PRIMARY", ["rejected"]),
    "Hiraea grandifolia": ("PRIMARY", ["rejected"]),
    "Randia armata": ("PRIMARY", ["rejected"]),
    "Sorocea affinis": ("PRIMARY", ["rejected"]),
    "Trema micrantha": ("PRIMARY", ["rejected"]),
    "Spondias mombin": ("PRIMARY", ["accepted"]),
    "Hymenaea courbaril": ("CONTEXT", ["accepted", "rejected"]),
    "Inga goldmanii": ("CONTEXT", ["accepted", "rejected"]),
    "Tetragastris panamensis": ("CONTEXT", ["accepted", "rejected"]),
    "Trichilia tuberculata": ("CONTEXT", ["accepted", "rejected"]),
    "Miconia argentea": ("CONTEXT", ["accepted", "rejected"]),
}


def direction_support(name: str, direction: str) -> tuple[list[str], str]:
    """Select audited direction and corroborating anchors for a fixed pair.

    Args:
        name: Full name as written in the natural panel.
        direction: Fixed reference direction.

    Returns:
        Anchor identifiers and the rule connecting the named plant to the prose.
    """
    genus = name.split()[0]
    if genus in {"Desmopsis", "Spondias", "Hymenaea"}:
        return [f"individual_{genus.lower()}"], "explicit_named_prose"
    if genus in {"Inga", "Tetragastris", "Trichilia"}:
        return ["simultaneous_a_four"], "explicit_named_group_prose"
    if genus == "Miconia" and direction == "accepted":
        return ["simultaneous_miconia", "miconia_context_reversal"], "explicit_named_prose"
    if genus == "Miconia":
        return ["individual_spondias", "individual_group_directions"], "all_ten_except_spondias"
    return ["simultaneous_a_day2"], "all_nine_except_spondias_and_miconia"


def make_reference(audit: dict, source: dict) -> list[dict]:
    """Keep every panel species and record missing or inconsistent reference evidence."""
    plants = {row["plant_name_as_written"]: row for row in audit["plants"]}
    blocks = {row["block_id"]: row["text"] for row in source["blocks"]}
    result = []
    for name, (group, directions) in PANEL.items():
        plant = plants.get(name)
        reasons = []
        observed = sorted({row["outcome"] for row in audit["cells"]
                           if row["plant_name_as_written"] == name
                           and row["outcome"] in {"accepted", "rejected"}})
        if plant is None or observed != directions:
            reasons.append("reference_missing_or_disagrees_with_fixed_panel")
        support = []
        for direction in directions:
            anchor_ids, attribution = direction_support(name, direction)
            membership = attribution.startswith("all_")
            if membership and plant is not None:
                anchor_ids += ["table_immediate_group", "table_caption", plant["name_anchor_id"]]
            anchors = []
            for anchor_id in anchor_ids:
                anchor = audit["evidence_anchors"].get(anchor_id)
                if anchor is None or anchor["evidence_quote"] not in blocks.get(
                    anchor["block_id"], ""
                ):
                    reasons.append(f"reference_anchor_unverified:{anchor_id}")
                else:
                    anchors.append({"anchor_id": anchor_id, **anchor})
            support.append({
                "direction": direction,
                "provenance_strength": AUTHOR_TABLE_GROUPING if membership else AUTHOR_PROSE,
                "attribution": attribution,
                "table_membership_dependency": membership,
                "numerical_values_used_for_direction": False,
                "anchors": anchors,
            })
        result.append({
            "species": name, "group": group, "reference_directions": directions,
            "provenance_strength": AUTHOR_TABLE_GROUPING if any(
                s["provenance_strength"] == AUTHOR_TABLE_GROUPING for s in support
            ) else AUTHOR_PROSE,
            "table_membership_dependency": any(s["table_membership_dependency"] for s in support),
            "reference_support": support,
            "scorable": not reasons, "blocked_reason": ";".join(reasons) or None,
        })
    return result


def candidate_inventory(extraction: Path) -> tuple[list[dict], dict]:
    """Reconcile raw candidates against the original grounding pass/failure artifacts."""
    passed = {
        (row["input_hash"], row["record_id"]): row
        for row in read_jsonl(extraction / "observations.jsonl")
    }
    rejected = {
        (row["input_hash"], digest(row["candidate"])): row["reason"]
        for row in read_jsonl(extraction / "rejections.jsonl")
    }
    candidates = []
    seen = set()
    for path in sorted((extraction / "responses").glob("*.json")):
        response = read_json(path)
        for index, record in enumerate(response["output"]["records"]):
            key = (response["input_hash"], digest(record))
            seen.add(key)
            status = "passed" if key in passed else "failed" if key in rejected else "unscorable"
            candidates.append({
                "candidate_id": f"{response['input_hash']}:{index + 1}",
                "record_digest": key[1], "response_path": str(path),
                "input_hash": key[0], "record": record,
                "grounding_status": status,
                "grounding_failure_reason": rejected.get(key),
                "blocked_reason": "candidate_grounding_status_missing" if status == "unscorable" else None,
            })
    metrics = read_json(extraction / "metrics.json")
    reconciled = (
        len(candidates) == metrics["candidate_records"]
        and sum(c["grounding_status"] == "passed" for c in candidates) == metrics["validated_candidates"]
        and sum(c["grounding_status"] == "failed" for c in candidates) == metrics["rejected_candidates"]
        and seen == set(passed) | set(rejected)
    )
    return candidates, {
        "candidate_records": len(candidates),
        "grounding_passes": sum(c["grounding_status"] == "passed" for c in candidates),
        "grounding_failures": sum(c["grounding_status"] == "failed" for c in candidates),
        "reconciled_with_original_artifacts": reconciled,
        "blocked_reason": None if reconciled else "candidate_inventory_does_not_reconcile",
    }


def context_status(directions: list[str]) -> str:
    """Classify structured directional coverage for a two-direction species."""
    if set(directions) == {"accepted", "rejected"}:
        return "both_directions_surfaced"
    return "collapsed_to_one" if directions else "absent"


def score_species(reference: dict, candidates: list[dict]) -> dict:
    """Count structured labels without promoting words in quotes into extra records."""
    selected = [c for c in candidates if c["record"]["plant_name_as_written"] == reference["species"]]
    surviving = [c for c in selected if c["grounding_status"] == "passed"]
    proposed = sorted({c["record"]["outcome"] for c in selected
                       if c["record"]["outcome"] in {"accepted", "rejected"}})
    retained = sorted({c["record"]["outcome"] for c in surviving
                       if c["record"]["outcome"] in {"accepted", "rejected"}})
    correct = sorted(set(retained) & set(reference["reference_directions"]))
    reasons = [c["blocked_reason"] for c in selected if c["blocked_reason"]]
    if reference["blocked_reason"]:
        reasons.append(reference["blocked_reason"])
    scorable = not reasons
    return {
        **reference, "scorable": scorable, "blocked_reason": ";".join(reasons) or None,
        "candidate_ids": [c["candidate_id"] for c in selected],
        "surviving_candidate_ids": [c["candidate_id"] for c in surviving],
        "detection": bool(selected) if scorable else None,
        "survival": bool(surviving) if scorable else None,
        "correctness": bool(correct) if scorable else None,
        "proposed_directions": proposed, "surviving_directions": retained,
        "correct_directions": correct,
        "incorrect_surviving_directions": sorted(set(retained) - set(reference["reference_directions"])),
        "context_stages": {
            "detection": context_status(proposed) if scorable else "unscorable",
            "survival": context_status(retained) if scorable else "unscorable",
            "correctness": context_status(correct) if scorable else "unscorable",
        } if reference["group"] == "CONTEXT" else None,
    }


def summarise_group(rows: list[dict], group: str) -> dict:
    """Report fixed denominators and all unscorable species within one group."""
    selected = [row for row in rows if row["group"] == group]
    result = {
        "species_denominator": len(selected),
        "species_direction_pair_denominator": sum(len(r["reference_directions"]) for r in selected),
        "unscorable_species": [r["species"] for r in selected if not r["scorable"]],
        "reference_provenance_species": {
            strength: sum(r["provenance_strength"] == strength for r in selected)
            for strength in PROVENANCE_CLASSES
        },
        "table_membership_dependent_species": sum(r["table_membership_dependency"] for r in selected),
        "stages": {},
    }
    for stage, field in (("detection", "proposed_directions"),
                         ("survival", "surviving_directions"), ("correctness", "correct_directions")):
        known = [r for r in selected if r["scorable"]]
        count = sum(r[stage] for r in known)
        pairs = sum(len(set(r[field]) & set(r["reference_directions"])) for r in known)
        result["stages"][stage] = {"species_count": count, "species_direction_pair_count": pairs}
        if group == "CONTEXT":
            counts = Counter(r["context_stages"][stage] for r in selected)
            result["stages"][stage]["direction_coverage"] = {
                status: counts[status] for status in (
                    "both_directions_surfaced", "collapsed_to_one", "absent", "unscorable"
                )
            }
    return result


def build_baseline(audit: dict, source: dict, extraction: Path) -> dict:
    """Build the panel measurement using unchanged reference directions and extraction."""
    reference = make_reference(audit, source)
    candidates, inventory = candidate_inventory(extraction)
    if inventory["blocked_reason"]:
        for row in reference:
            row["scorable"] = False
            row["blocked_reason"] = inventory["blocked_reason"]
    rows = [score_species(row, candidates) for row in reference]
    scoped = [c for c in candidates if c["record"]["plant_name_as_written"] in PANEL]
    return {
        "schema_version": 1, "set_type": "DEVELOPMENT SET", "source_id": audit["source_id"],
        "status": "complete" if all(r["scorable"] for r in rows) else "partially_blocked",
        "blocked_reason": None if all(r["scorable"] for r in rows) else "unscorable_species_retained",
        "unit": "species-direction pair", "panel_species_denominator": 11,
        "sampling_scope": "One panel from one paper; it is not a sample from any population.",
        "name_matching": "Exact full names as written; taxonomy resolution does not gate this measurement.",
        "direction_scoring": "Only structured outcome fields count; a second direction mentioned in a quote does not count as an emitted pair.",
        "provenance_convention": "author_prose requires an explicitly named species or genus and direction; named groups qualify. author_table_grouping records a species placed under a printed author heading in Table 1 and is stronger provenance. Numerical signs never define a reference direction.",
        "miconia_context_basis": MICONIA_CONTEXT_BASIS,
        "inventory": {**inventory, "natural_panel_candidates": len(scoped),
                      "outside_panel_candidates": len(candidates) - len(scoped)},
        "groups": {group: summarise_group(rows, group) for group in ("PRIMARY", "CONTEXT")},
        "species": rows, "candidates": candidates,
    }
