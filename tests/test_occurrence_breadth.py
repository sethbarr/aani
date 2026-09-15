"""Exploratory occurrence-breadth analysis: collapse, counting, permutation reproducibility."""

import gzip
from pathlib import Path

import numpy as np

from src.exploratory.occurrence_breadth.counting import collapse, count_breadth, first_block
from src.exploratory.occurrence_breadth.loading import (
    LOTUS_FIELDS,
    LotusRow,
    Structure,
    iter_lotus,
    lineage_rank,
    reference_key,
)
from src.exploratory.occurrence_breadth.reporting import format_p
from src.exploratory.occurrence_breadth.statistics import (
    MINIMUM_TESTED_PER_STRATUM,
    compare,
    permuted_differences,
    rank_biserial,
    reference_quartiles,
    stratified,
    within_stratum_permutation,
)

STRUCTURES = [
    Structure("AAAAAAAAAAAAAA-BBBBBBBBSA-N", "AAAAAAAAAAAAAA-BBBBBBBBSA-N", True, "active"),
    Structure("AAAAAAAAAAAAAA-CCCCCCCCSA-N", "AAAAAAAAAAAAAA-CCCCCCCCSA-N", False, "unknown"),
    Structure("DDDDDDDDDDDDDD-EEEEEEEESA-N", "DDDDDDDDDDDDDD-EEEEEEEESA-N", False, "unknown"),
    Structure("FFFFFFFFFFFFFF-GGGGGGGGSA-N", "FFFFFFFFFFFFFF-GGGGGGGGSA-N", True, "inactive"),
]


def row(inchikey: str, organism: str, genus: str, family: str, reference: str) -> LotusRow:
    """Build a fixture row."""
    return LotusRow(inchikey, organism, genus, family, reference)


def test_first_block_drops_stereo_and_charge_layers() -> None:
    """The connectivity block is the text before the first hyphen."""
    assert first_block("HVYWMOMLDIMFJA-DPAQBDIFSA-N") == "HVYWMOMLDIMFJA"


def test_collapse_merges_stereoisomers_and_inherits_tested() -> None:
    """Two stereoisomers become one connectivity unit that is tested if either is."""
    structure_units = collapse(STRUCTURES, "structure")
    connectivity_units = collapse(STRUCTURES, "connectivity")
    assert len(structure_units) == 4
    assert len(connectivity_units) == 3
    merged = connectivity_units[0]
    assert merged.key == "AAAAAAAAAAAAAA"
    assert merged.members == ("AAAAAAAAAAAAAA-BBBBBBBBSA-N", "AAAAAAAAAAAAAA-CCCCCCCCSA-N")
    assert merged.tested is True
    assert merged.labels == ("active", "unknown")
    assert sum(unit.tested for unit in structure_units) == 2
    assert sum(unit.tested for unit in connectivity_units) == 2


def test_count_breadth_on_small_fixture() -> None:
    """Distinct organisms, genera, families and references are counted at both levels."""
    rows = [
        row("AAAAAAAAAAAAAA-BBBBBBBBSA-N", "Ocimum basilicum", "Ocimum", "Lamiaceae", "doi:10.1/a"),
        row("AAAAAAAAAAAAAA-BBBBBBBBSA-N", "Ocimum basilicum", "Ocimum", "Lamiaceae", "doi:10.1/b"),
        row("AAAAAAAAAAAAAA-BBBBBBBBSA-N", "Vicia faba", "Vicia", "Fabaceae", "doi:10.1/a"),
        row("AAAAAAAAAAAAAA-ZZZZZZZZSA-N", "Inga edulis", "Inga", "Fabaceae", "pmid:1"),
        row("DDDDDDDDDDDDDD-EEEEEEEESA-N", "Miconia sp.", "", "", "doi:10.1/c"),
        row(
            "QQQQQQQQQQQQQQ-EEEEEEEESA-N", "Unrelated", "Unrelated", "Unrelatedaceae", "doi:10.1/d"
        ),
    ]
    full_keys = {structure.inchikey for structure in STRUCTURES}
    blocks = {first_block(key) for key in full_keys}
    by_key, by_block = count_breadth(rows, full_keys, blocks)
    assert by_key["AAAAAAAAAAAAAA-BBBBBBBBSA-N"].counts() == {
        "organisms": 2,
        "genera": 2,
        "families": 2,
        "references": 2,
        "lotus_rows": 3,
    }
    assert by_key["AAAAAAAAAAAAAA-CCCCCCCCSA-N"].counts()["lotus_rows"] == 0
    assert by_block["AAAAAAAAAAAAAA"].counts() == {
        "organisms": 3,
        "genera": 3,
        "families": 2,
        "references": 3,
        "lotus_rows": 4,
    }
    assert by_key["DDDDDDDDDDDDDD-EEEEEEEESA-N"].counts() == {
        "organisms": 1,
        "genera": 0,
        "families": 0,
        "references": 1,
        "lotus_rows": 1,
    }
    assert by_key["FFFFFFFFFFFFFF-GGGGGGGGSA-N"].counts()["lotus_rows"] == 0
    assert "QQQQQQQQQQQQQQ" not in by_block


def test_lineage_and_reference_parsing() -> None:
    """Ranks come from the aligned arrays; references prefer DOI, then PMCID, then PMID."""
    ranks = "unranked|kingdom|family|genus|species"
    taxa = "Biota|Plantae|Lamiaceae|Ocimum|Ocimum basilicum"
    assert lineage_rank(ranks, taxa, "genus") == "Ocimum"
    assert lineage_rank(ranks, taxa, "family") == "Lamiaceae"
    assert lineage_rank(ranks, taxa, "order") == ""
    assert lineage_rank("kingdom|genus", "Plantae", "genus") == ""
    assert reference_key("10.1/ABC", "NA", "NA", "doi", "x") == "doi:10.1/abc"
    assert reference_key("NA", "PMC9", "5", "pubmed", "x") == "pmcid:PMC9"
    assert reference_key("", "", "5", "pubmed", "x") == "pmid:5"
    assert reference_key("NA", "NA", "NA", "title", "Some book") == "title:Some book"


def test_permutation_is_reproducible_with_fixed_seed() -> None:
    """The same seed gives identical null draws and p-values; a different seed does not."""
    generator = np.random.default_rng(3)
    values = generator.poisson(4, size=200)
    first = permuted_differences(values, 20, 500, seed=1729)
    second = permuted_differences(values, 20, 500, seed=1729)
    other = permuted_differences(values, 20, 500, seed=1730)
    assert np.array_equal(first, second)
    assert not np.array_equal(first, other)
    tested = values[:20]
    untested = values[20:]
    a = compare("genera", tested, untested, 500, 1729)
    b = compare("genera", tested, untested, 500, 1729)
    assert a == b
    assert 0 < a.p_greater <= 1
    assert a.observed_difference == float(np.median(tested) - np.median(untested))


def test_rank_biserial_bounds_and_direction() -> None:
    """Complete separation gives +1 or -1; identical samples give 0."""
    assert rank_biserial(np.array([5, 6, 7]), np.array([1, 2, 3])) == 1.0
    assert rank_biserial(np.array([1, 2, 3]), np.array([5, 6, 7])) == -1.0
    assert rank_biserial(np.array([2, 2]), np.array([2, 2])) == 0.0


def test_stratification_reports_sparse_strata_instead_of_pooling() -> None:
    """Quartiles with too few tested units are marked skipped, not merged."""
    references = np.array([1] * 40 + [5] * 40 + [20] * 40 + [100] * 40)
    genera = references.copy()
    tested = np.zeros(160, dtype=bool)
    tested[120 : 120 + MINIMUM_TESTED_PER_STRATUM] = True
    tested[0:2] = True
    results = stratified("genera", genera, tested, references, 200, 1729)
    assert len(results) == 4
    assert results[0].n_tested == 2
    assert results[0].comparison is None
    assert "fewer than" in results[0].skipped_reason
    assert results[3].n_tested == MINIMUM_TESTED_PER_STRATUM
    assert results[3].comparison is not None
    assert results[3].comparison.n_untested == 40 - MINIMUM_TESTED_PER_STRATUM
    assert set(reference_quartiles(references)) == {0, 1, 2, 3}
    observed, p_greater, p_two = within_stratum_permutation(genera, tested, references, 200, 1729)
    assert observed == float(np.median(genera[tested]) - np.median(genera[~tested]))
    assert 0 < p_greater <= 1 and 0 < p_two <= 1


def test_p_value_formatting_shows_resolution_floor() -> None:
    """A p at the plus-one floor is reported as below the resolution, never as zero."""
    assert format_p(1 / 10001, 10000) == "< 0.0001"
    assert format_p(0.0234, 10000) == "0.0234"


def test_iter_lotus_tallies_rows_and_skips_malformed(tmp_path: Path) -> None:
    """The scan counter records every row and the malformed ones it skipped."""
    header = "\t".join(LOTUS_FIELDS)
    good = "\t".join(
        [
            "AAAAAAAAAAAAAA-BBBBBBBBSA-N",
            "Ocimum basilicum",
            "kingdom|family|genus",
            "Plantae|Lamiaceae|Ocimum",
            "doi",
            "10.1/x",
            "10.1/x",
            "NA",
            "NA",
        ]
    )
    bad = "only\ttwo"
    path = tmp_path / "lotus.tsv.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write("\n".join([header, good, bad, good]) + "\n")
    tally: dict[str, int] = {}
    rows = list(iter_lotus(path, tally))
    assert tally == {"scanned": 3, "malformed": 1}
    assert len(rows) == 2
    assert rows[0].genus == "Ocimum" and rows[0].family == "Lamiaceae"
    assert rows[0].reference == "doi:10.1/x"
