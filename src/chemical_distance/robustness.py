"""Predeclared population and composition controls for retrieved assay coverage."""

from dataclasses import dataclass
from statistics import median

import numpy as np

from src.chemical_distance.datasets import PlantCompound
from src.chemical_distance.fingerprints import Structure
from src.chemical_distance.nullmodel import median_max_similarity

POPULATIONS = ("original", "size_filtered", "fingerprint_collapsed", "without_arabidopsis")
SCHEMES = ("unrestricted", "size", "genus", "joint")
SIZE_EDGES = (6, 11, 21, 31, 41, 61)
DRAWS = 2000
SEED = 20260914


@dataclass(frozen=True)
class Unit:
    """One equally weighted compound or fingerprint class.

    Attributes:
        structure: Deterministically selected fingerprint representative.
        members: All source compound identifiers in the unit.
        measured_members: Members with an eligible retrieved assay measurement.
        genera: Union of source genera across all members.
        heavy_atoms: Median heavy-atom count across members.
    """

    structure: Structure
    members: tuple[str, ...]
    measured_members: tuple[str, ...]
    genera: tuple[str, ...]
    heavy_atoms: float

    @property
    def measured(self) -> bool:
        """Return whether any member has an eligible retrieved measurement."""
        return bool(self.measured_members)


@dataclass(frozen=True)
class Stratum:
    """A fixed matching stratum and its required reference count.

    Attributes:
        key: Human-readable tuple of genus and size constraints.
        indices: Population indices eligible for selection.
        picks: Observed reference units in this stratum.
    """

    key: tuple[str, ...]
    indices: np.ndarray
    picks: int


def size_bin(heavy_atoms: float) -> int:
    """Assign a heavy-atom count to the predeclared half-open bin."""
    return sum(heavy_atoms >= edge for edge in SIZE_EDGES)


def compound_units(
    plants: list[PlantCompound], structures: dict[str, Structure], measured: set[str],
) -> list[Unit]:
    """Create resolved units without changing source labels or structure identifiers."""
    return [Unit(structures[item.compound_id], (item.compound_id,),
                 (item.compound_id,) if item.compound_id in measured else (),
                 tuple(sorted(set(item.genera))), float(structures[item.compound_id].heavy_atoms))
            for item in sorted(plants, key=compound_key) if item.compound_id in structures]


def compound_key(compound: PlantCompound) -> str:
    """Order source compounds independently of measurement status."""
    return compound.compound_id


def collapse_fingerprints(units: list[Unit]) -> list[Unit]:
    """Collapse exact fingerprints with union provenance and any-member reference flags."""
    groups: dict[str, list[Unit]] = {}
    for unit in units:
        groups.setdefault(unit.structure.fingerprint.ToBitString(), []).append(unit)
    collapsed = []
    for group in groups.values():
        ordered = sorted(group, key=unit_key)
        members = tuple(sorted(member for unit in ordered for member in unit.members))
        measured = tuple(sorted(member for unit in ordered for member in unit.measured_members))
        genera = tuple(sorted({genus for unit in ordered for genus in unit.genera}))
        collapsed.append(Unit(ordered[0].structure, members, measured, genera,
                              float(median(unit.heavy_atoms for unit in ordered))))
    return sorted(collapsed, key=unit_key)


def unit_key(unit: Unit) -> str:
    """Order units by their deterministic representative identifier."""
    return unit.structure.compound_id


def build_populations(units: list[Unit]) -> dict[str, list[Unit]]:
    """Construct all four declared populations before running any random draws."""
    filtered = [unit for unit in units if unit.heavy_atoms >= 6]
    collapsed = collapse_fingerprints(filtered)
    return dict(zip(POPULATIONS, (
        units, filtered, collapsed,
        [unit for unit in collapsed if "Arabidopsis" not in unit.genera],
    ), strict=True))


def stratum_key(unit: Unit, scheme: str) -> tuple[str, ...]:
    """Encode the exact declared matching conditions without resolving sparse strata."""
    if scheme not in SCHEMES:
        raise ValueError(f"unknown_matching_scheme:{scheme}")
    genus = unit.genera if scheme in {"genus", "joint"} else ()
    size = (f"size_bin={size_bin(unit.heavy_atoms)}",) if scheme in {"size", "joint"} else ()
    return genus + size


def build_strata(units: list[Unit], scheme: str) -> list[Stratum]:
    """Preserve observed reference counts in each size or genus-membership stratum."""
    groups: dict[tuple[str, ...], list[int]] = {}
    for index, unit in enumerate(units):
        groups.setdefault(stratum_key(unit, scheme), []).append(index)
    return [Stratum(key, np.array(indices, dtype=np.int64),
                    sum(units[index].measured for index in indices))
            for key, indices in sorted(groups.items())]


def sample_reference(strata: list[Stratum], generator: np.random.Generator) -> np.ndarray:
    """Sample each stratum without replacement, retaining every forced selection."""
    selections = []
    for stratum in strata:
        if stratum.picks == 0:
            continue
        if stratum.picks == len(stratum.indices):
            selections.append(stratum.indices)
        else:
            selections.append(generator.choice(stratum.indices, size=stratum.picks, replace=False))
    return np.sort(np.concatenate(selections)) if selections else np.array([], dtype=np.int64)


def complement_score(matrix: np.ndarray, references: np.ndarray) -> float:
    """Score exactly the units outside this reference selection, excluding self-matches."""
    available = np.ones(matrix.shape[0], dtype=bool)
    available[references] = False
    return median_max_similarity(matrix, np.flatnonzero(available), references)


def run_cell(
    matrix: np.ndarray, units: list[Unit], scheme: str, seed: int, draws: int = DRAWS,
) -> tuple[dict, list[float]]:
    """Execute a declared matching cell and expose null degeneracy and forced membership.

    Args:
        matrix: Pairwise similarity in the same order as units.
        units: Frozen population units with observed measurement flags.
        scheme: One of the four declared matching schemes.
        seed: Fixed cell-specific generator seed.
        draws: Number of random reference selections.

    Returns:
        Count-only results and every null statistic in draw order.
    """
    if matrix.shape != (len(units), len(units)) or draws < 1:
        raise ValueError("invalid_matrix_or_draw_count")
    references = np.array([i for i, unit in enumerate(units) if unit.measured], dtype=np.int64)
    strata = build_strata(units, scheme)
    forced = sum(s.picks for s in strata if s.picks == len(s.indices))
    result = {
        "scheme": scheme, "seed": seed, "planned_draws": draws,
        "population_units": len(units), "reference_units": len(references),
        "query_units": len(units) - len(references), "strata_count": len(strata),
        "forced_reference_units": forced, "exchangeable_reference_units": len(references) - forced,
        "strata": [{"key": list(s.key), "population": len(s.indices), "reference": s.picks}
                   for s in strata],
    }
    if not len(references) or len(references) == len(units):
        return {**result, "status": "unscorable", "reason": "empty_reference_or_complement",
                "completed_draws": 0}, []
    observed = complement_score(matrix, references)
    generator = np.random.default_rng(seed)
    values = []
    unique: set[bytes] = set()
    for _ in range(draws):
        sampled = sample_reference(strata, generator)
        unique.add(sampled.tobytes())
        values.append(complement_score(matrix, sampled))
    low, middle, high = np.percentile(values, [2.5, 50, 97.5])
    degenerate = len(unique) <= 1 or min(values) == max(values)
    result.update({
        "status": "complete", "reason": None, "completed_draws": draws,
        "observed": observed, "null_median": float(middle),
        "null_low": float(low), "null_high": float(high),
        "difference": observed - float(middle),
        "draws_at_or_below_observed": sum(value <= observed for value in values),
        "distinct_reference_sets": len(unique), "degenerate": degenerate,
        "below_null_low": observed < low,
    })
    result["below_null_low"] = bool(result["below_null_low"])
    return result, values


def interpretation(cells: list[dict]) -> str:
    """Apply the predeclared descriptive rule without selecting favorable cells."""
    complete = len(cells) == 16 and all(row["status"] == "complete" for row in cells)
    if not complete:
        return "The robustness comparison is incomplete; every unscorable cell remains reported."
    negatives = all(row["difference"] < 0 for row in cells)
    nondegenerate = all(not row["degenerate"] for row in cells)
    main = [row for row in cells if row["population"] in POPULATIONS[2:] and row["scheme"] == "joint"]
    if negatives and nondegenerate and len(main) == 2 and all(row["below_null_low"] for row in main):
        return ("Within-corpus separation is descriptively robust to the predeclared checks. "
                "The analysis does not establish the cause of uneven assay coverage.")
    return ("The within-corpus separation does not satisfy the predeclared robustness rule; "
            "the full grid shows its sensitivity to population and matching choices.")
