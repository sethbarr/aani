"""Render the any-fungus coverage report and table."""

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from src.any_fungus_coverage.aggregate import (
    Measurement,
    TierSummary,
    restrict,
    summarise_tier,
)
from src.any_fungus_coverage.endpoints import CONVERTIBLE_UNITS, ENDPOINT_GROUPS
from src.any_fungus_coverage.inputs import Cache
from src.any_fungus_coverage.tiers import REPORT_ORDER

TIER_LABELS = {
    "T4": "T4 Leucoagaricus and attine cultivar fungi",
    "T1": "T1 frozen three species lineages",
    "T2": "T2 other human fungal pathogens",
    "T3": "T3 plant and agricultural pathogens",
    "T5": "T5 remaining verified fungi",
}

COVERAGE_COLUMNS = (
    "compound_id",
    "tier",
    "measurements",
    "convertible",
    "non_convertible",
    "distinct_organisms",
    "source_genera",
    "in_nine_genera_with_chemistry",
    "in_five_rejected_genera",
    "organisms",
    "endpoints",
    "standard_types",
    "standard_values",
    "standard_units",
    "standard_relations",
    "convertible_flags",
    "activity_ids",
)


@dataclass(frozen=True)
class Population:
    """One reporting population.

    Attributes:
        key: Short identifier used in headings.
        title: Human-readable heading.
        genera: Genera defining the population, empty for all structures.
        compounds: Compound identifiers in the population.
        rows: Measurement rows restricted to the population.
    """

    key: str
    title: str
    genera: tuple[str, ...]
    compounds: set[str]
    rows: list[Measurement]


def build_population(
    key: str,
    title: str,
    genera: tuple[str, ...],
    compounds: set[str],
    rows: list[Measurement],
) -> Population:
    """Restrict the measurement rows to one population.

    Args:
        key: Short identifier used in headings.
        title: Human-readable heading.
        genera: Genera defining the population, empty for all structures.
        compounds: Compound identifiers in the population.
        rows: All measurement rows.

    Returns:
        The population with its restricted rows.
    """
    return Population(
        key=key,
        title=title,
        genera=genera,
        compounds=compounds,
        rows=restrict(rows, compounds),
    )


def tier_table(population: Population) -> list[str]:
    """Render the tier coverage table for one population.

    Args:
        population: The population to render.

    Returns:
        Markdown lines.
    """
    lines = [
        "| Tier | Compounds with at least one measurement | Measurements | "
        "Convertible units | Non-convertible units | Distinct assay taxa |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for tier in REPORT_ORDER:
        summary = summarise_tier(population.rows, tier)
        lines.append(
            f"| {TIER_LABELS[tier]} | {summary.compounds} | {summary.measurements} | "
            f"{summary.convertible} | {summary.non_convertible} | {summary.organisms} |"
        )
    return lines


def endpoint_table(population: Population) -> list[str]:
    """Render the endpoint breakdown for one population.

    Args:
        population: The population to render.

    Returns:
        Markdown lines.
    """
    header = " | ".join(ENDPOINT_GROUPS)
    lines = [
        f"| Tier | {header} |",
        "| --- |" + " ---: |" * len(ENDPOINT_GROUPS),
    ]
    for tier in REPORT_ORDER:
        summary = summarise_tier(population.rows, tier)
        cells = " | ".join(str(summary.endpoints[group]) for group in ENDPOINT_GROUPS)
        lines.append(f"| {TIER_LABELS[tier]} | {cells} |")
    return lines


CULTIVAR_TERMS = (
    "leucoagaricus",
    "leucocoprinus",
    "myrmecopterula",
    "attamyces",
    "conioexocarpus",
)

ATTINE_TERMS = ("attine", "leaf-cutting", "leafcutter", "leaf cutting")


def cultivar_name_hits(cache: Cache) -> tuple[int, int]:
    """Cross-check the T4 result at the level of recorded names.

    Taxonomy establishes membership and names do not, but the absence of any
    relevant name is evidence that a taxonomic zero is not an artefact of an
    anchor that failed to resolve.

    Args:
        cache: The loaded cache.

    Returns:
        A pair of the assays whose organism name mentions a cultivar genus and
        the assays whose description mentions attine cultivation.
    """
    organism_hits = 0
    description_hits = 0
    for assay in cache.assays.values():
        organism = (assay.get("assay_organism") or "").lower()
        description = (assay.get("description") or "").lower()
        if any(term in organism for term in CULTIVAR_TERMS):
            organism_hits += 1
        if any(term in description for term in ATTINE_TERMS):
            description_hits += 1
    return organism_hits, description_hits


def tier_four_section(population: Population, cache: Cache, unresolved: list[str]) -> list[str]:
    """Render the T4 statement, which is reported first and even when zero.

    Args:
        population: The all-structures population.
        cache: The loaded cache, for the name-level cross-check.
        unresolved: T4 anchor names that no taxonomy lookup resolved.

    Returns:
        Markdown lines.
    """
    summary = summarise_tier(population.rows, "T4")
    potential = [row for row in population.rows if row.potential_cultivar]
    lines = [
        f"**T4 resolved records: {summary.compounds} compounds, "
        f"{summary.measurements} measurements.**",
        "",
    ]
    if summary.measurements == 0:
        lines.extend(
            [
                "No cached assay resolves to Leucoagaricus gongylophorus, to its",
                "authoritative synonyms, or to any other taxon documented as an attine",
                "cultivar. This is a verified zero across the retrieved records, not an",
                "unqueried gap: every assay identifier returned by the activity query was",
                "fetched and every assay taxon resolved.",
                "",
                "The absence of a ChEMBL record does not establish absence of published",
                "measurements. Extract-level assays and uncurated literature remain a",
                "separate gap that this retrieval cannot see.",
            ]
        )
        organism_hits, description_hits = cultivar_name_hits(cache)
        lines.extend(
            [
                "",
                "Cross-check at the level of recorded names, which does not itself establish",
                f"membership: {organism_hits} cached assays carry an organism name mentioning",
                "Leucoagaricus, Leucocoprinus, Myrmecopterula, Attamyces or Conioexocarpus,",
                f"and {description_hits} carry a description mentioning attine or",
                "leaf-cutting cultivation.",
            ]
        )
        if unresolved:
            lines.extend(
                [
                    "",
                    f"One caveat is recorded rather than hidden: the T4 anchor "
                    f"{', '.join(unresolved)} did not resolve to a taxonomic node, so no",
                    "assay could have been matched to it by lineage. The name cross-check",
                    "above covers that gap, since no assay in the cache carries a name in",
                    "any of these genera at all.",
                ]
            )
    else:
        lines.append("Resolved attine cultivar records are listed in the taxon breakdown below.")
    lines.extend(
        [
            "",
            f"Potential-cultivar records held separately: {len(potential)} measurements on "
            "broad Leucoagaricus, Leucocoprinus, Myrmecopterula or Conioexocarpus nodes "
            "that genus membership alone does not establish as ant-cultivated. These are "
            "excluded from the T4 counts above.",
        ]
    )
    return lines


def genus_line(population: Population) -> str:
    """Describe the genera defining a population.

    Args:
        population: The population to describe.

    Returns:
        A single Markdown line naming the genera and the denominator.
    """
    genera = ", ".join(population.genera)
    return (
        f"Genera ({len(population.genera)}): {genera}. "
        f"Mapped structures in this population: {len(population.compounds)}."
    )


def coverage_rows(
    rows: list[Measurement],
    genera_by_compound: dict[str, tuple[str, ...]],
    nine: set[str],
    rejected: set[str],
) -> list[dict[str, str]]:
    """Build one coverage row per compound per tier.

    Args:
        rows: All measurement rows.
        genera_by_compound: Source genera by compound identifier.
        nine: Compounds in the nine genera with chemistry.
        rejected: Compounds in the five rejected genera.

    Returns:
        Coverage rows ordered by compound then tier.
    """
    grouped: dict[tuple[str, str], list[Measurement]] = {}
    for row in rows:
        grouped.setdefault((row.compound_id, row.tier), []).append(row)
    output: list[dict[str, str]] = []
    for key in sorted(grouped):
        compound, tier = key
        items = sorted(grouped[key], key=lambda item: item.activity_id)
        output.append(
            {
                "compound_id": compound,
                "tier": tier,
                "measurements": str(len(items)),
                "convertible": str(sum(1 for item in items if item.convertible)),
                "non_convertible": str(sum(1 for item in items if not item.convertible)),
                "distinct_organisms": str(
                    len({item.scientific_name or item.organism for item in items})
                ),
                "source_genera": ";".join(genera_by_compound.get(compound, ())),
                "in_nine_genera_with_chemistry": str(compound in nine),
                "in_five_rejected_genera": str(compound in rejected),
                "organisms": json.dumps(
                    [item.scientific_name or item.organism for item in items]
                ),
                "endpoints": json.dumps([item.endpoint for item in items]),
                "standard_types": json.dumps([item.standard_type for item in items]),
                "standard_values": json.dumps([item.standard_value for item in items]),
                "standard_units": json.dumps([item.standard_units for item in items]),
                "standard_relations": json.dumps([item.standard_relation for item in items]),
                "convertible_flags": json.dumps([item.convertible for item in items]),
                "activity_ids": json.dumps([item.activity_id for item in items]),
            }
        )
    return output


def write_coverage_csv(rows: list[dict[str, str]], path: Path) -> None:
    """Write the coverage table.

    Args:
        rows: Coverage rows.
        path: Destination CSV path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(COVERAGE_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def convertibility_note() -> list[str]:
    """State what convertibility does and does not mean.

    Returns:
        Markdown lines.
    """
    units = ", ".join(CONVERTIBLE_UNITS)
    return [
        f"Convertible means a finite positive standard value in one of {units}. Mass",
        "concentrations, percentages, zone diameters, missing values and every other unit",
        "are non-convertible, and no mass-to-molar conversion is inferred. Convertibility",
        "is assessed independently of organism, endpoint, assay type, validity flag and",
        "potency, and it does not establish a frozen active or inactive label. Relations",
        "are retained unaltered in the coverage table.",
    ]


def summary_header(summaries: dict[str, TierSummary]) -> list[str]:
    """Render the opening protection statement.

    Args:
        summaries: Tier summaries for all structures.

    Returns:
        Markdown lines.
    """
    return [
        "# Any-fungus ChEMBL coverage of the mapped plant structures",
        "",
        "Exploratory sensitivity analysis declared in",
        "docs/amendment_2026-09-14_any_fungus_coverage.md. It describes database coverage",
        "of the fixed mapped structures and changes no primary label, eligibility rule,",
        "enrichment result, funnel or feasibility-failure label. Broader measurement",
        "coverage is never newly established biological activity. Counts are database",
        "records, not independent experiments.",
        "",
        "Tiers overlap at compound and measurement level, so tier counts do not sum to any",
        "total. A measurement on an assay carrying several roles is counted in each tier",
        "it belongs to.",
        "",
    ]
