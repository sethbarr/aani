"""Check the RDKit measurement layer of the chemical-distance analysis."""

import pytest

pytest.importorskip("rdkit", reason="RDKit is an optional chemistry dependency")

from src.chemical_distance.fingerprints import (  # noqa: E402
    MORGAN_BITS,
    MORGAN_RADIUS,
    Structure,
    build_structures,
    morgan_generator,
)
from src.chemical_distance.neighbours import (  # noqa: E402
    describe,
    nearest_neighbour,
    scaffold_overlap,
)


def structures_for(smiles: list[str]) -> list[Structure]:
    """Build structures for a list of SMILES using the frozen generator.

    Args:
        smiles: SMILES strings to parse.

    Returns:
        The resolved structures, in input order.
    """
    entries = [(f"C{index}", value) for index, value in enumerate(smiles)]
    resolved, _ = build_structures(entries, morgan_generator())
    return [resolved[key] for key, _ in entries if key in resolved]


def test_the_fingerprint_parameters_stay_frozen() -> None:
    """Morgan radius and bit count must not drift."""
    assert MORGAN_RADIUS == 2
    assert MORGAN_BITS == 2048


def test_unparseable_structures_are_reported_not_silently_dropped() -> None:
    """An unresolvable SMILES must surface in the unresolved list."""
    resolved, unresolved = build_structures(
        [("good", "c1ccccc1O"), ("bad", "not-a-smiles"), ("empty", "")], morgan_generator()
    )
    assert set(resolved) == {"good"}
    assert sorted(unresolved) == ["bad", "empty"]


def test_a_compound_is_never_its_own_nearest_neighbour() -> None:
    """Self-matches must be excluded so membership cannot inflate similarity."""
    built = structures_for(["CC(=O)Oc1ccccc1C(=O)O", "c1ccccc1O"])
    result = nearest_neighbour(built[0], built)
    assert result.neighbour_id != built[0].compound_id
    assert result.comparisons == len(built) - 1


def test_zero_similarity_names_no_neighbour() -> None:
    """A query sharing no bit with any reference names no nearest neighbour."""
    query = structures_for(["N"])[0]
    reference = structures_for(["c1ccccc1O"])
    result = nearest_neighbour(query, reference)
    assert result.similarity == 0.0
    assert result.neighbour_id == ""


def test_identical_structures_reach_unit_similarity() -> None:
    """Tanimoto similarity must reach one for a fingerprint-identical pair."""
    resolved, _ = build_structures(
        [("query", "c1ccccc1O"), ("other", "c1ccccc1O")], morgan_generator()
    )
    result = nearest_neighbour(resolved["query"], [resolved["other"]])
    assert result.similarity == pytest.approx(1.0)


def test_an_empty_reference_set_yields_no_neighbour() -> None:
    """A query with nothing to compare against must not raise."""
    query = structures_for(["c1ccccc1O"])[0]
    result = nearest_neighbour(query, [])
    assert result.comparisons == 0
    assert result.neighbour_id == ""


def test_describe_reports_counts_and_percentages_consistently() -> None:
    """The below-convention count and percentage must agree."""
    distribution = describe([0.1, 0.2, 0.5, 0.9])
    assert distribution.count == 4
    assert distribution.below_convention == 2
    assert distribution.below_convention_percent == pytest.approx(50.0)
    assert distribution.median == pytest.approx(0.35)


def test_describe_handles_an_empty_distribution() -> None:
    """An empty input must not raise and must report a zero count."""
    distribution = describe([])
    assert distribution.count == 0
    assert distribution.below_convention == 0


def test_scaffold_overlap_counts_shared_scaffolds() -> None:
    """Scaffold overlap must count shared scaffolds and acyclic queries."""
    queries = structures_for(["c1ccccc1O", "CCCC"])
    references = structures_for(["c1ccccc1C"])
    total, shared, covered, acyclic = scaffold_overlap(queries, references)
    assert total == 1
    assert shared == 1
    assert covered == 1
    assert acyclic == 1


def test_heavy_atom_count_is_recorded() -> None:
    """Heavy atom counts must be available to discount degenerate records."""
    built = structures_for(["N", "c1ccccc1O"])
    assert built[0].heavy_atoms == 1
    assert built[1].heavy_atoms == 7


def test_similarity_matrix_reproduces_rdkit_exactly() -> None:
    """The vectorised matrix must agree with RDKit's own Tanimoto."""
    from rdkit import DataStructs

    from src.chemical_distance.nullmodel import similarity_matrix

    built = structures_for(["c1ccccc1O", "CC(=O)Oc1ccccc1C(=O)O", "CCCCO", "c1ccncc1"])
    matrix = similarity_matrix(built)
    for row, structure in enumerate(built):
        expected = DataStructs.BulkTanimotoSimilarity(
            structure.fingerprint, [item.fingerprint for item in built]
        )
        for column, value in enumerate(expected):
            assert matrix[row][column] == pytest.approx(value, abs=1e-6)


def test_similarity_matrix_is_symmetric_with_a_unit_diagonal() -> None:
    """Self-similarity must be one and the matrix must be symmetric."""
    from src.chemical_distance.nullmodel import similarity_matrix

    matrix = similarity_matrix(structures_for(["c1ccccc1O", "CCCCO", "c1ccncc1"]))
    for row in range(matrix.shape[0]):
        assert matrix[row][row] == pytest.approx(1.0)
        for column in range(matrix.shape[0]):
            assert matrix[row][column] == pytest.approx(matrix[column][row])


def test_permutation_control_is_reproducible_and_excludes_members() -> None:
    """The control must be seed-reproducible and query only non-members."""
    import numpy as np

    from src.chemical_distance.nullmodel import permutation_null, similarity_matrix

    built = structures_for(
        ["c1ccccc1O", "CC(=O)Oc1ccccc1C(=O)O", "CCCCO", "c1ccncc1", "CCN", "c1ccc2ccccc2c1"]
    )
    matrix = similarity_matrix(built)
    references = np.array([0, 1])
    first = permutation_null(matrix, references, draws=32, seed=7)
    second = permutation_null(matrix, references, draws=32, seed=7)
    assert first == second
    assert first.draws == 32
    assert 0.0 < first.p_value <= 1.0
    assert first.observed <= 1.0


def test_permutation_p_value_is_never_zero() -> None:
    """The plus-one correction must keep the reported p above zero."""
    import numpy as np

    from src.chemical_distance.nullmodel import permutation_null, similarity_matrix

    built = structures_for(["c1ccccc1O", "CCCCO", "c1ccncc1", "CCN"])
    result = permutation_null(similarity_matrix(built), np.array([0]), draws=16, seed=3)
    assert result.p_value >= 1 / 17


def test_rarefaction_returns_one_point_per_requested_size() -> None:
    """Sizes above the reference set must be skipped, not raise."""
    import numpy as np

    from src.chemical_distance.nullmodel import rarefaction, similarity_matrix

    built = structures_for(["c1ccccc1O", "CC(=O)Oc1ccccc1C(=O)O", "CCCCO", "c1ccncc1"])
    points = rarefaction(
        similarity_matrix(built), np.array([0, 1]), sizes=(1, 2, 99), draws=4, seed=5
    )
    assert [point.size for point in points] == [1, 2]
    assert points[-1].draws == 1
