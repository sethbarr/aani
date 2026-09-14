"""Render the chemical-distance summary as Markdown."""

from dataclasses import dataclass
from pathlib import Path

from src.chemical_distance.convention import DOMAIN_CONVENTION
from src.chemical_distance.neighbours import Distribution


@dataclass(frozen=True)
class GenusRow:
    """Per-genus nearest-neighbour statistics for unknown-activity compounds.

    Attributes:
        genus: Source genus.
        direction: Behavioural direction recorded for the genus.
        distribution: Nearest-neighbour distribution for its unknown compounds.
        scaffolds: Distinct Murcko scaffolds among its unknown compounds.
        shared_scaffolds: How many of those occur in the tested set.
    """

    genus: str
    direction: str
    distribution: Distribution
    scaffolds: int
    shared_scaffolds: int


@dataclass(frozen=True)
class ScaffoldOverlap:
    """Bemis-Murcko scaffold overlap between a query set and the tested set.

    Attributes:
        query_scaffolds: Distinct scaffolds among the query structures.
        shared_scaffolds: Distinct query scaffolds also in the tested set.
        covered_compounds: Query structures whose scaffold is in the tested set.
        acyclic_compounds: Query structures yielding no Murcko scaffold.
    """

    query_scaffolds: int
    shared_scaffolds: int
    covered_compounds: int
    acyclic_compounds: int


@dataclass(frozen=True)
class Report:
    """Everything the summary needs to render.

    Attributes:
        reference_size: Compounds in the tested reference set.
        reference_active: Tested compounds labelled active.
        reference_inactive: Tested compounds labelled inactive.
        reference_unknown: Tested compounds whose measurement yielded no label.
        reference_resolved: Tested compounds with a resolvable structure.
        classified_resolved: Classified compounds with a resolvable structure.
        reference_organisms: Fungal organisms present in the eligible assays.
        requested_organisms: Organisms the analysis brief asked for.
        missing_organisms: Requested organisms absent from the inventory.
        eligible_assays: Size of the eligible functional assay inventory.
        query_size: Unknown-activity compounds in the query set.
        query_resolved: Query compounds with a resolvable structure.
        query_unresolved: Query compounds without a resolvable structure.
        query_overlap: Query compounds already carrying an eligible measurement.
        query_low_complexity: Query compounds below the heavy-atom floor, whose
            similarity is dominated by having almost no fingerprint bits to set.
        low_complexity_floor: Heavy atom count below which that applies.
        unknown_vs_tested: Unknown-compound distribution against the tested set.
        unknown_never_tested: Distribution for unknown compounds that carry no
            eligible measurement at all.
        unknown_already_tested: Distribution for unknown compounds that carry an
            eligible measurement which yielded no usable label.
        classified_vs_tested: Classified-compound distribution, leave-one-out.
        unknown_vs_classified: Unknown-compound distribution against classified.
        classified_vs_classified: Classified distribution, leave-one-out.
        unknown_scaffolds: Scaffold overlap for the unknown compounds.
        classified_scaffolds: Scaffold overlap for the classified compounds.
        genus_rows: Per-genus statistics.
        verdict: One-sentence verdict on the coverage gap.
    """

    reference_size: int
    reference_active: int
    reference_inactive: int
    reference_unknown: int
    reference_resolved: int
    classified_resolved: int
    reference_organisms: tuple[str, ...]
    requested_organisms: tuple[str, ...]
    missing_organisms: tuple[str, ...]
    eligible_assays: int
    query_size: int
    query_resolved: int
    query_unresolved: int
    query_overlap: int
    query_low_complexity: int
    low_complexity_floor: int
    unknown_vs_tested: Distribution
    unknown_never_tested: Distribution
    unknown_already_tested: Distribution
    classified_vs_tested: Distribution
    unknown_vs_classified: Distribution
    classified_vs_classified: Distribution
    unknown_scaffolds: ScaffoldOverlap
    classified_scaffolds: ScaffoldOverlap
    genus_rows: tuple[GenusRow, ...]
    verdict: str


def percent(part: int, whole: int) -> str:
    """Format a count as a percentage of a whole.

    Args:
        part: Numerator.
        whole: Denominator.

    Returns:
        The percentage to one decimal place, or "n/a" when the whole is zero.
    """
    if whole == 0:
        return "n/a"
    return f"{100.0 * part / whole:.1f}%"


def distribution_row(name: str, distribution: Distribution) -> str:
    """Render one distribution as a Markdown table row.

    Args:
        name: Row label.
        distribution: The distribution to render.

    Returns:
        A pipe-delimited Markdown table row.
    """
    return (
        f"| {name} | {distribution.count} | {distribution.median:.3f} | "
        f"{distribution.first_quartile:.3f} | {distribution.third_quartile:.3f} | "
        f"{distribution.minimum:.3f} | {distribution.maximum:.3f} | "
        f"{distribution.below_convention} "
        f"({percent(distribution.below_convention, distribution.count)}) |"
    )


def render_distributions(report: Report) -> list[str]:
    """Render the nearest-neighbour distribution table.

    Args:
        report: The assembled report.

    Returns:
        Markdown lines.
    """
    return [
        "| Query set | n | Median | Q1 | Q3 | Min | Max | "
        f"Below {DOMAIN_CONVENTION} |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        distribution_row("Unknown activity vs tested set", report.unknown_vs_tested),
        distribution_row(
            "  of which never tested at all", report.unknown_never_tested
        ),
        distribution_row(
            "  of which tested but unclassifiable", report.unknown_already_tested
        ),
        distribution_row("Classified vs tested set (leave-one-out)", report.classified_vs_tested),
        distribution_row("Unknown activity vs classified set", report.unknown_vs_classified),
        distribution_row(
            "Classified vs classified (leave-one-out)", report.classified_vs_classified
        ),
    ]


def render_scaffolds(report: Report) -> list[str]:
    """Render the scaffold overlap section.

    Args:
        report: The assembled report.

    Returns:
        Markdown lines.
    """
    unknown = report.unknown_scaffolds
    classified = report.classified_scaffolds
    return [
        "| Query set | Distinct scaffolds | Also in tested set | "
        "Compounds on a shared scaffold | Compounds with no Murcko scaffold |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| Unknown activity | {unknown.query_scaffolds} | {unknown.shared_scaffolds} "
        f"({percent(unknown.shared_scaffolds, unknown.query_scaffolds)}) | "
        f"{unknown.covered_compounds} "
        f"({percent(unknown.covered_compounds, report.query_resolved)}) | "
        f"{unknown.acyclic_compounds} |",
        f"| Classified | {classified.query_scaffolds} | {classified.shared_scaffolds} "
        f"({percent(classified.shared_scaffolds, classified.query_scaffolds)}) | "
        f"{classified.covered_compounds} "
        f"({percent(classified.covered_compounds, report.classified_resolved)}) | "
        f"{classified.acyclic_compounds} |",
        "",
        "The classified row shares every scaffold with the tested set by construction,",
        "because those compounds are themselves members of it. The row is reported for",
        "completeness and carries no information about scaffold coverage.",
    ]


def render_genera(rows: tuple[GenusRow, ...]) -> list[str]:
    """Render the per-genus table.

    Args:
        rows: Per-genus statistics.

    Returns:
        Markdown lines.
    """
    lines = [
        "| Genus | Behavioural direction | n unknown | Median | Q1 | Q3 | "
        f"Below {DOMAIN_CONVENTION} | Scaffolds | Shared |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        distribution = row.distribution
        lines.append(
            f"| {row.genus} | {row.direction} | {distribution.count} | "
            f"{distribution.median:.3f} | {distribution.first_quartile:.3f} | "
            f"{distribution.third_quartile:.3f} | {distribution.below_convention} "
            f"({percent(distribution.below_convention, distribution.count)}) | "
            f"{row.scaffolds} | {row.shared_scaffolds} |"
        )
    return lines


def render(report: Report) -> str:
    """Render the complete summary.

    Args:
        report: The assembled report.

    Returns:
        The Markdown document.
    """
    missing = ", ".join(report.missing_organisms) if report.missing_organisms else "none"
    lines = [
        "# Chemical distance between untested plant structures and tested compounds",
        "",
        "**This analysis produces a distance measurement and a ranked test list only.**",
        "It contains no predicted activity label, no probability and no imputed value.",
        "Compounds of unknown activity remain of unknown activity. Nothing here is",
        "admissible to the enrichment analysis, and the feasibility-failure label is",
        "unchanged.",
        "",
        "## 1. Reference set: compounds that have been tested",
        "",
        "The reference set is every compound for which the bioactivity stage retrieved",
        "at least one measurement on an eligible functional assay against the target",
        "fungi, verified against the complete eligible assay inventory.",
        "",
        f"- Eligible functional assay inventory: {report.eligible_assays} assays",
        f"- Assay organisms present: {', '.join(report.reference_organisms)}",
        f"- Requested organisms: {', '.join(report.requested_organisms)}",
        f"- Requested but absent from the frozen inventory: {missing}",
        f"- Reference compounds: {report.reference_size}",
        f"- Active under the frozen 10 uM threshold: {report.reference_active} "
        f"({percent(report.reference_active, report.reference_size)})",
        f"- Inactive under the frozen 10 uM threshold: {report.reference_inactive} "
        f"({percent(report.reference_inactive, report.reference_size)})",
        f"- Tested but not classifiable, so still unknown: {report.reference_unknown} "
        f"({percent(report.reference_unknown, report.reference_size)})",
        f"- With a structure RDKit could resolve: {report.reference_resolved} "
        f"({percent(report.reference_resolved, report.reference_size)})",
        "",
        f"Classified compounds number {report.reference_active + report.reference_inactive}, "
        f"being {report.reference_active} active and {report.reference_inactive} inactive. "
        "The remainder were measured on an eligible assay whose value could not be read "
        "against the frozen threshold, overwhelmingly because the reported units are not "
        "convertible to a molar concentration.",
        "",
        "## 2. Query set: unknown-activity plant structures",
        "",
        f"- Unknown-activity compounds: {report.query_size}",
        f"- With a structure RDKit could resolve: {report.query_resolved} "
        f"({percent(report.query_resolved, report.query_size)})",
        f"- Without a resolvable structure, excluded from every distance: "
        f"{report.query_unresolved} ({percent(report.query_unresolved, report.query_size)})",
        f"- Already carrying an eligible measurement that yielded no usable label: "
        f"{report.query_overlap} ({percent(report.query_overlap, report.query_size)})",
        "",
        "Every compound is excluded from its own reference set, so no compound is its",
        "own nearest neighbour and the overlap above cannot inflate any similarity.",
        "",
        f"A further {report.query_low_complexity} query compounds "
        f"({percent(report.query_low_complexity, report.query_size)}) carry fewer than "
        f"{report.low_complexity_floor} heavy atoms. A structure that small sets almost no "
        "fingerprint bits, so it scores as maximally novel for want of substance rather "
        "than for want of a resembling tested compound, and the two single-atom records at "
        "the head of the ranked table are artefacts of exactly this. The table carries a "
        "heavy atom count so these can be discounted on sight.",
        "",
        "## 3. Nearest-neighbour similarity distributions",
        "",
        "Morgan fingerprints, radius 2, 2048 bits. Maximum Tanimoto similarity to any",
        "compound in the stated reference set.",
        "",
    ]
    lines.extend(render_distributions(report))
    lines.extend(
        [
            "",
            f"The {DOMAIN_CONVENTION} similarity threshold is a working convention for",
            "flagging a query compound as outside the applicability domain of a reference",
            "set. It is a convention in common use, not a law of chemistry, and nothing in",
            "this analysis depends on its exact value.",
            "",
            "## 4. Bemis-Murcko scaffold overlap",
            "",
        ]
    )
    lines.extend(render_scaffolds(report))
    lines.extend(
        [
            "",
            "## 5. Per-genus statistics for unknown-activity compounds",
            "",
            "A compound reported from several genera is counted once in each, so the",
            "genus counts sum to more than the query set.",
            "",
        ]
    )
    lines.extend(render_genera(report.genus_rows))
    lines.extend(
        [
            "",
            "## 6. Limitations that bound every number above",
            "",
            "**The reference set is the compounds retrieved during the bioactivity stage,",
            "not every compound ChEMBL holds for these assays.** The cached retrieval",
            f"filtered activities by plant compound, so although the {report.eligible_assays}",
            "eligible assays are a complete inventory, the compounds measured in them were",
            "never fetched and no structures for them exist offline. Every similarity here",
            f"is therefore a distance to {report.reference_size} compounds rather than to",
            "the true tested chemical space, and a fuller reference set would raise the",
            "similarities and shrink the share falling below the convention. The direction",
            "of the contrast would survive; the absolute values would not.",
            "",
            f"**{', '.join(report.missing_organisms) or 'No requested organism'} is absent",
            "from the frozen inventory.** The retrieval asked ChEMBL for three organisms,",
            "so nothing here speaks to that species.",
            "",
            "**Reference and query are drawn from the same corpus.** Every reference",
            "compound is also a plant structure from these genera, so this measures",
            "distance within the corpus, not distance to antifungal chemistry at large.",
            "",
            "## 7. Verdict",
            "",
            report.verdict,
            "",
        ]
    )
    return "\n".join(lines)


def write_summary(report: Report, path: Path) -> None:
    """Write the summary document.

    Args:
        report: The assembled report.
        path: Destination Markdown path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(report), encoding="utf-8")
