"""Resolve attine microbial genera under an isolated GBIF rule."""

from math import isfinite
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict

from src.common.cache import CachedHTTP, OfflineCacheMiss
from src.common.io import read_json, write_jsonl
from src.taxonomy.gbif import CHECKLIST


class MicrobialTaxonomyConfig(BaseModel):
    """Fixed taxonomy policy for the attine microbial replay."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    system_slug: Literal["attine_actino"]
    scope: Literal["microbial"]
    query_kingdom_hint: Literal["Bacteria"]
    required_domain: Literal["Bacteria"]
    required_rank: Literal["genus"]
    required_match_type: Literal["EXACT"]
    minimum_confidence: Literal[90]
    checklist_key: Literal["7ddf754f-d193-4cc9-b351-99906754a03b"]


def load_microbial_taxonomy_config(path: Path) -> MicrobialTaxonomyConfig:
    """Load the attine-only microbial taxonomy policy.

    Args:
        path: JSON configuration path.

    Returns:
        Validated microbial taxonomy configuration.
    """
    return MicrobialTaxonomyConfig.model_validate(read_json(path))


def classification_by_rank(response: dict) -> dict[str, dict]:
    """Index valid GBIF classification rows by uppercase rank.

    Args:
        response: Decoded GBIF v2 match response.

    Returns:
        Classification records keyed by rank.
    """
    ranks: dict[str, dict] = {}
    for row in response.get("classification", []):
        if not isinstance(row, dict):
            continue
        rank = str(row.get("rank") or "").upper()
        if rank:
            ranks[rank] = row
    return ranks


def microbial_confidence(response: dict) -> float:
    """Read a finite GBIF confidence value or return a rejecting value.

    Args:
        response: Decoded GBIF v2 match response.

    Returns:
        Finite confidence, or -1 when the field is invalid.
    """
    diagnostics = response.get("diagnostics")
    raw = diagnostics.get("confidence", -1) if isinstance(diagnostics, dict) else -1
    try:
        confidence = float(raw)
    except (TypeError, ValueError):
        return -1
    return confidence if isfinite(confidence) else -1


def interpret_microbial_genus_match(
    response: dict, config: MicrobialTaxonomyConfig
) -> tuple[dict | None, str | None]:
    """Apply the attine-only exact genus and bacterial-domain gates.

    Args:
        response: Decoded GBIF v2 match response.
        config: Scoped microbial taxonomy policy.

    Returns:
        Resolved taxonomy fields and no reason, or no match and a reason.
    """
    diagnostics = response.get("diagnostics")
    match_type = diagnostics.get("matchType") if isinstance(diagnostics, dict) else None
    confidence = microbial_confidence(response)
    if match_type != config.required_match_type or confidence < config.minimum_confidence:
        return None, "inexact_or_low_confidence"

    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    accepted = (
        response.get("acceptedUsage")
        if isinstance(response.get("acceptedUsage"), dict)
        else {}
    )
    if str(usage.get("rank") or "").casefold() != config.required_rank:
        return None, "rank_mismatch"
    accepted_rank = str(accepted.get("rank") or "").casefold()
    if accepted_rank and accepted_rank != config.required_rank:
        return None, "rank_mismatch"

    ranks = classification_by_rank(response)
    domain = ranks.get("DOMAIN", {}).get("name")
    if str(domain).casefold() != config.required_domain.casefold():
        return None, "wrong_domain"

    usage_key = usage.get("key")
    is_synonym = response.get("synonym") is True or str(usage.get("status") or "").upper().endswith(
        "SYNONYM"
    )
    accepted_key = accepted.get("key")
    if accepted_key is None and not is_synonym:
        accepted_key = usage_key
    accepted_name = accepted.get("canonicalName") or accepted.get("name")
    if not accepted_name and not is_synonym and str(accepted_key) == str(usage_key):
        accepted_name = usage.get("canonicalName") or usage.get("name")
    genus = ranks.get("GENUS", {}).get("name")
    if accepted_rank == config.required_rank:
        genus = accepted.get("canonicalName") or accepted.get("name") or genus
    family = ranks.get("FAMILY", {}).get("name")
    if not genus or not family or usage_key is None or accepted_key is None or not accepted_name:
        return None, "incomplete_classification"

    return {
        "usage_key": str(usage_key),
        "accepted_usage_key": str(accepted_key),
        "accepted_name": accepted_name,
        "genus": genus,
        "family": family,
        "domain": domain,
        "kingdom": ranks.get("KINGDOM", {}).get("name"),
        "match_type": match_type,
        "checklist_key": CHECKLIST,
        "taxonomy_confidence": confidence,
        "taxonomy_rule": "attine_microbial_v1",
    }, None


def normalise_attine_microbes(
    observations: list[dict],
    cache: CachedHTTP,
    output: Path,
    config: MicrobialTaxonomyConfig,
) -> dict:
    """Resolve retained attine microbial records from a GBIF cache.

    Args:
        observations: Semantically retained attine extraction records.
        cache: HTTP cache opened in offline mode for replay.
        output: Separate microbial taxonomy artifact directory.
        config: Scoped microbial taxonomy policy.

    Returns:
        Replay counts and the cached request hashes used.
    """
    if not cache.offline:
        raise ValueError("Attine microbial taxonomy replay must run offline")
    if any(row.get("semantic_decision") != "include" for row in observations):
        raise ValueError("Taxonomy input must contain applied semantic-review inclusions")

    matched: list[dict] = []
    review: list[dict] = []
    memo: dict[tuple[str, str], tuple[dict | None, str | None, str | None]] = {}
    for observation in observations:
        name = observation.get("taxonomy_query_name", observation["target_name_as_written"])
        rank = observation.get("taxonomy_query_rank", observation["taxonomic_rank"])
        identity = (name, rank)
        if rank != config.required_rank:
            memo[identity] = (None, "rank_mismatch", None)
        elif identity not in memo:
            try:
                response, key = cache.get_json(
                    "https://api.gbif.org/v2/species/match",
                    {
                        "scientificName": name,
                        "taxonRank": rank.upper(),
                        "kingdom": config.query_kingdom_hint,
                        "checklistKey": config.checklist_key,
                    },
                )
                resolved, reason = interpret_microbial_genus_match(response, config)
                memo[identity] = (resolved, reason, key)
            except (httpx.HTTPError, OfflineCacheMiss) as error:
                memo[identity] = (None, str(error), None)
        resolved, reason, key = memo[identity]
        if resolved is None:
            review.append({**observation, "reason": reason, "taxonomy_request_hash": key})
        else:
            matched.append({**observation, **resolved, "taxonomy_request_hash": key})

    write_jsonl(output / "observations.jsonl", matched)
    write_jsonl(output / "review.jsonl", review)
    return {
        "status": "complete" if all(row[2] is not None for row in memo.values()) else "blocked",
        "offline": True,
        "external_requests": 0,
        "input_observations": len(observations),
        "matched_observations": len(matched),
        "review_observations": len(review),
        "unique_names": len(memo),
        "resolved_genera": sorted({row["genus"] for row in matched}),
        "resolved_taxa": len({row["accepted_usage_key"] for row in matched}),
        "taxonomy_request_hashes": sorted({row[2] for row in memo.values() if row[2]}),
        "rule": config.model_dump(),
    }
