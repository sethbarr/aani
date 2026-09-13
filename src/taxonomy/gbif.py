"""Normalize plants with the current GBIF matcher and explicit dataset identity."""

from math import isfinite
from pathlib import Path

import httpx

from src.common.cache import CachedHTTP, OfflineCacheMiss
from src.common.io import write_jsonl

CHECKLIST = "7ddf754f-d193-4cc9-b351-99906754a03b"


def interpret_match(
    response: dict, expected_rank: str, threshold: int = 95, kingdom: str = "Plantae"
) -> tuple[dict | None, str | None]:
    """Accept exact matches in one configured kingdom with genus/family context.

    GBIF has returned both a flat v1-style payload and a nested v2 payload over
    the lifetime of the matcher. The request uses v2, but accepting the flat
    shape here makes cached imports and older manifests auditable rather than
    silently turning a format change into an empty taxonomy join.

    For accepted v2 matches, the name is in ``usage`` and ``acceptedUsage`` is
    absent. Synonym matches must supply the accepted identity; their matched
    name must never be attached to a different accepted key as a fallback.
    """
    diagnostics = (
        response.get("diagnostics") if isinstance(response.get("diagnostics"), dict) else {}
    )
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    accepted = (
        response.get("acceptedUsage") if isinstance(response.get("acceptedUsage"), dict) else {}
    )
    match_type = diagnostics.get("matchType") or response.get("matchType")
    raw_confidence = diagnostics.get("confidence", response.get("confidence", -1))
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        confidence = -1
    if match_type != "EXACT" or not isfinite(confidence) or confidence < threshold:
        return None, "inexact_or_low_confidence"
    if expected_rank not in {"species", "genus"}:
        return None, "rank_mismatch"
    usage_rank = str(usage.get("rank") or response.get("rank") or "").lower()
    if usage_rank != expected_rank:
        return None, "rank_mismatch"
    accepted_rank = str(accepted.get("rank") or response.get("acceptedRank") or "").lower()
    if accepted_rank and accepted_rank != expected_rank:
        return None, "rank_mismatch"
    ranks = {}
    for row in response.get("classification", []):
        if not isinstance(row, dict):
            continue
        rank = str(row.get("rank") or "").upper()
        if rank:
            ranks[rank] = row
    matched_kingdom = ranks.get("KINGDOM", {}).get("name") or response.get("kingdom")
    if str(matched_kingdom).casefold() != kingdom.casefold():
        return None, "not_plantae" if kingdom == "Plantae" else "wrong_kingdom"
    genus = ranks.get("GENUS", {}).get("name") or response.get("genus")
    if accepted_rank == "genus":
        genus = accepted.get("canonicalName") or accepted.get("name") or genus
    family = ranks.get("FAMILY", {}).get("name") or response.get("family")
    usage_key = usage.get("key") or response.get("usageKey")
    is_synonym = response.get("synonym") is True or str(
        usage.get("status") or response.get("status") or ""
    ).upper().endswith("SYNONYM")
    accepted_key = accepted.get("key") or response.get("acceptedUsageKey")
    if accepted_key is None and not is_synonym:
        accepted_key = usage_key
    accepted_name = accepted.get("canonicalName") or accepted.get("name")
    if not accepted_name and not is_synonym and str(accepted_key) == str(usage_key):
        accepted_name = (
            usage.get("canonicalName")
            or usage.get("name")
            or response.get("canonicalName")
            or response.get("scientificName")
        )
    if not genus or not family or accepted_key is None or usage_key is None or not accepted_name:
        return None, "incomplete_classification"
    return {
        "usage_key": str(usage_key),
        "accepted_usage_key": str(accepted_key),
        "accepted_name": accepted_name,
        "genus": genus,
        "family": family,
        "checklist_key": CHECKLIST,
        "taxonomy_confidence": confidence,
    }, None


def normalise(
    observations: list[dict],
    cache: CachedHTTP,
    output: Path,
    confidence: int = 95,
    kingdom: str = "Plantae",
    name_field: str = "plant_name_as_written",
    rank_field: str = "taxonomic_rank",
) -> dict:
    """Resolve unique names while retaining every observation's provenance."""
    matched, review = [], []
    memo = {}
    for observation in observations:
        identity = (
            observation.get("taxonomy_query_name", observation[name_field]),
            observation.get("taxonomy_query_rank", observation[rank_field]),
        )
        if identity not in memo:
            try:
                response, key = cache.get_json(
                    "https://api.gbif.org/v2/species/match",
                    {
                        "scientificName": identity[0],
                        "taxonRank": identity[1].upper(),
                        "kingdom": kingdom,
                        "checklistKey": CHECKLIST,
                    },
                )
                resolved, reason = interpret_match(response, identity[1], confidence, kingdom)
                memo[identity] = (resolved, reason, key)
            except (httpx.HTTPError, OfflineCacheMiss) as error:
                memo[identity] = (None, str(error), None)
        resolved, reason, key = memo[identity]
        if resolved:
            matched.append({**observation, **resolved, "taxonomy_request_hash": key})
        else:
            review.append({**observation, "reason": reason, "taxonomy_request_hash": key})
    write_jsonl(output / "observations.jsonl", matched)
    write_jsonl(output / "review.jsonl", review)
    return {
        "matched_observations": len(matched),
        "review_observations": len(review),
        "unique_names": len(memo),
    }
