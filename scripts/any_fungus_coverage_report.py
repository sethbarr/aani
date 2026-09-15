"""Aggregate the cached any-fungus tier classification into reports.

Offline only. Reads the completed retrieval under
data/interim/any_fungus_coverage and writes results/any_fungus_coverage. It
issues no request, recomputes no primary output and edits no frozen file.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from src.any_fungus_coverage.aggregate import (
    Measurement,
    build_measurements,
    summarise_tier,
    taxon_counts,
)
from src.any_fungus_coverage.inputs import Cache, load_cache
from src.any_fungus_coverage.report import (
    Population,
    build_population,
    convertibility_note,
    coverage_rows,
    endpoint_table,
    genus_line,
    summary_header,
    tier_four_section,
    tier_table,
    write_coverage_csv,
)
from src.any_fungus_coverage.tiers import (
    REPORT_ORDER,
    AssayTier,
    TierIndex,
    build_index,
    classify_assays,
    multi_tier_organisms,
)
from src.chemical_distance.datasets import load_genus_behaviour, load_structures

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/interim/any_fungus_coverage"
CHEMISTRY = ROOT / "data/processed/chemistry/occurrences.jsonl"
BEHAVIOUR = ROOT / "data/processed/behaviour/all_genera.csv"
OUTPUT = ROOT / "results/any_fungus_coverage"

REJECTED_GENERA = ("Desmopsis", "Hiraea", "Randia", "Sorocea", "Trema")


@dataclass
class GenusSets:
    """Genus populations derived from the frozen files.

    Attributes:
        genera_by_compound: Source genera by compound identifier.
        nine: Genera eligible for primary inference that carry chemistry.
        rejected: The five rejected genera named in the amendment.
    """

    genera_by_compound: dict[str, tuple[str, ...]]
    nine: tuple[str, ...]
    rejected: tuple[str, ...]


def build_genus_sets() -> GenusSets:
    """Derive genus populations from the frozen behaviour and chemistry files.

    Returns:
        The genus populations.
    """
    _, genera_by_compound = load_structures(CHEMISTRY)
    behaviour = load_genus_behaviour(BEHAVIOUR)
    with_chemistry = {genus for genera in genera_by_compound.values() for genus in genera}
    nine = tuple(
        sorted(
            genus
            for genus in with_chemistry
            if genus in behaviour and behaviour[genus].primary_eligible
        )
    )
    return GenusSets(genera_by_compound=genera_by_compound, nine=nine, rejected=REJECTED_GENERA)


def compounds_in(genera_by_compound: dict[str, tuple[str, ...]], genera: tuple[str, ...]) -> set[str]:
    """Select the compounds reported from any of a set of genera.

    Args:
        genera_by_compound: Source genera by compound identifier.
        genera: Genera to select.

    Returns:
        Compound identifiers reported from at least one of the genera.
    """
    wanted = set(genera)
    return {
        compound
        for compound, sources in genera_by_compound.items()
        if wanted.intersection(sources)
    }


def taxon_section(population: Population, tier: str, limit: int) -> list[str]:
    """Render the assay taxa contributing to one tier.

    Args:
        population: The population to render.
        tier: The tier to break down.
        limit: Maximum taxa to list.

    Returns:
        Markdown lines.
    """
    counts = taxon_counts(population.rows, tier)
    if not counts:
        return ["No assay taxon contributes to this tier."]
    lines = [
        "| Assay taxon | Measurements | Compounds |",
        "| --- | ---: | ---: |",
    ]
    for name, measurements, compounds in counts[:limit]:
        lines.append(f"| {name} | {measurements} | {compounds} |")
    if len(counts) > limit:
        lines.append(f"| {len(counts) - limit} further taxa | | |")
    return lines


def model_section(population: Population) -> list[str]:
    """Render the model-organism split inside T5.

    Args:
        population: The all-structures population.

    Returns:
        Markdown lines.
    """
    summary = summarise_tier(population.rows, "T5")
    named = {"Saccharomyces cerevisiae", "Neurospora crassa"}
    rows = [row for row in population.rows if row.tier == "T5"]
    lines = [
        "| Group | Compounds | Measurements |",
        "| --- | ---: | ---: |",
        f"| Declared model organisms | {summary.model_compounds} | "
        f"{summary.model_measurements} |",
        f"| All other T5 taxa | {summary.non_model_compounds} | "
        f"{summary.non_model_measurements} |",
    ]
    for name in sorted(named):
        selected = [row for row in rows if row.scientific_name == name]
        lines.append(
            f"| of which {name} | {len({row.compound_id for row in selected})} | "
            f"{len(selected)} |"
        )
    lines.extend(
        [
            "",
            "Residual tier membership does not establish that a taxon is non-pathogenic.",
            "Taxa outside the declared model set retain an unknown ecological role.",
        ]
    )
    return lines


def provenance_section(
    cache: Cache,
    assigned: dict[str, AssayTier],
    index: TierIndex,
    rows: list[Measurement],
) -> list[str]:
    """Render denominators, completeness and residual uncertainty.

    Args:
        cache: The loaded cache.
        assigned: Tier assignment by assay ChEMBL identifier.
        index: The resolved anchor index.
        rows: All measurement rows.

    Returns:
        Markdown lines.
    """
    matched = sum(1 for value in cache.compound_to_molecules.values() if value)
    unmatched = len(cache.compound_to_molecules) - matched
    without_taxon = sum(1 for assay in cache.assays.values() if assay.get("assay_tax_id") is None)
    unresolved = sum(
        1
        for assay in cache.assays.values()
        if assay.get("assay_tax_id") is not None
        and cache.taxonomy.get(f"id:{assay['assay_tax_id']}", {}).get("status") != "resolved"
    )
    lines = [
        f"- ChEMBL service: {cache.service.get('chembl_db_version')}, released "
        f"{cache.service.get('chembl_release_date')}",
        f"- Mapped structures in the denominator: {len(cache.compound_to_molecules)}",
        f"- Structures resolving to at least one ChEMBL molecule: {matched}",
        f"- Structures with no exact ChEMBL match, retained in the denominator: {unmatched}",
        f"- Activities retrieved: {len(cache.activities)}",
        f"- Assays retrieved: {len(cache.assays)}",
        f"- Assays carrying no assay organism taxon: {without_taxon}",
        f"- Assays whose taxon did not resolve: {unresolved}",
        f"- Assays assigned to at least one tier: {len(assigned)}",
        f"- Measurement rows after the compound and tier join: {len(rows)}",
        f"- Cached pages reporting an incomplete status: {len(cache.incomplete_pages)}",
    ]
    if index.unresolved:
        for group, names in sorted(index.unresolved.items()):
            lines.append(f"- Unresolved {group} anchors: {', '.join(names)}")
    return lines


def render(
    cache: Cache,
    index: TierIndex,
    assigned: dict[str, AssayTier],
    rows: list[Measurement],
    populations: list[Population],
    genus_sets: GenusSets,
) -> str:
    """Render the whole summary document.

    Args:
        cache: The loaded cache.
        index: The resolved anchor index.
        assigned: Tier assignment by assay ChEMBL identifier.
        rows: All measurement rows.
        populations: The three reporting populations, all structures first.
        genus_sets: The derived genus populations.

    Returns:
        The Markdown document.
    """
    everything = populations[0]
    summaries = {tier: summarise_tier(everything.rows, tier) for tier in REPORT_ORDER}
    multi = multi_tier_organisms(assigned)
    lines = summary_header(summaries)
    lines.extend(["## 1. T4, reported first", ""])
    lines.extend(tier_four_section(everything, cache, index.unresolved.get("T4", [])))
    lines.extend(
        [
            "",
            "## 2. Coverage by tier, all mapped structures",
            "",
            genus_line(everything) if everything.genera else
            f"Mapped structures in the denominator: {len(everything.compounds)}.",
            "",
        ]
    )
    lines.extend(tier_table(everything))
    lines.extend(["", "### Endpoint groups", ""])
    lines.extend(endpoint_table(everything))
    lines.extend(["", *convertibility_note(), ""])
    lines.extend(["### Model organisms inside T5", ""])
    lines.extend(model_section(everything))
    lines.extend(
        [
            "",
            "### Organisms carrying more than one tier",
            "",
            f"Assay taxa assigned to more than one tier: {len(multi)}. Their measurements "
            "are counted in each tier they carry.",
            "",
        ]
    )
    if multi:
        lines.extend(["| Assay taxon | Tiers |", "| --- | --- |"])
        for name in sorted(multi):
            lines.append(f"| {name} | {', '.join(multi[name])} |")
    oomycete = summaries["T3"].oomycete_measurements
    lines.extend(
        [
            "",
            f"Oomycete records inside T3: {summaries['T3'].oomycete_compounds} compounds, "
            f"{oomycete} measurements. Oomycetes are not true fungi and are excluded from "
            "any any-true-fungus union.",
            "",
        ]
    )
    for population in populations[1:]:
        lines.extend([f"## {population.title}", "", genus_line(population), ""])
        lines.extend(tier_table(population))
        lines.extend(["", "### Endpoint groups", ""])
        lines.extend(endpoint_table(population))
        lines.append("")
    lines.extend(["## 5. Assay taxa contributing to each tier, all structures", ""])
    for tier in REPORT_ORDER:
        lines.extend([f"### {tier}", ""])
        lines.extend(taxon_section(everything, tier, 15))
        lines.append("")
    lines.extend(["## 6. Provenance, denominators and residual uncertainty", ""])
    lines.extend(provenance_section(cache, assigned, index, rows))
    lines.extend(
        [
            "",
            "Absence of a ChEMBL record does not establish absence of published",
            "measurements. Extract-level assays and uncurated literature remain a separate",
            "gap this retrieval cannot see.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """Aggregate the cached classification and write both outputs."""
    cache = load_cache(CACHE)
    index = build_index(cache)
    assigned = classify_assays(cache, index)
    rows = build_measurements(cache, assigned)
    genus_sets = build_genus_sets()

    everything = set(cache.compound_to_molecules)
    nine = compounds_in(genus_sets.genera_by_compound, genus_sets.nine)
    rejected = compounds_in(genus_sets.genera_by_compound, genus_sets.rejected)
    populations = [
        build_population("all", "All mapped structures", (), everything, rows),
        build_population(
            "nine", "3. Coverage by tier, the nine genera with chemistry", genus_sets.nine, nine, rows
        ),
        build_population(
            "rejected",
            "4. Coverage by tier, the five rejected genera",
            genus_sets.rejected,
            rejected,
            rows,
        ),
    ]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "summary.md").write_text(
        render(cache, index, assigned, rows, populations, genus_sets), encoding="utf-8"
    )
    write_coverage_csv(
        coverage_rows(rows, genus_sets.genera_by_compound, nine, rejected),
        OUTPUT / "coverage.csv",
    )
    print(json.dumps({
        "measurement_rows": len(rows),
        "tiers": {tier: summarise_tier(rows, tier).measurements for tier in REPORT_ORDER},
        "nine_genera": len(genus_sets.nine),
        "rejected_genera": len(genus_sets.rejected),
    }, indent=2))


if __name__ == "__main__":
    main()
