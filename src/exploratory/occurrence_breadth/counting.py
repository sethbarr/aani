"""Collapse structures by InChIKey connectivity and count LOTUS occurrence breadth."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from src.exploratory.occurrence_breadth.loading import LotusRow, Structure

METRICS = ("organisms", "genera", "families", "references")


def first_block(inchikey: str) -> str:
    """Return the connectivity block of an InChIKey.

    Args:
        inchikey: A full standard InChIKey such as ``HVYWMOMLDIMFJA-DPAQBDIFSA-N``.

    Returns:
        The 14-character first block, which ignores stereochemistry and charge.
    """
    return inchikey.split("-")[0]


@dataclass(frozen=True)
class Unit:
    """One analysis unit at a chosen collapse level.

    Attributes:
        key: The full InChIKey (structure level) or its first block (connectivity level).
        members: Full InChIKeys collapsed into this unit.
        tested: True when any member is tested.
        labels: Sorted distinct labels of the members.
    """

    key: str
    members: tuple[str, ...]
    tested: bool
    labels: tuple[str, ...]


def collapse(structures: list[Structure], level: str) -> list[Unit]:
    """Group structures into analysis units.

    Args:
        structures: Distinct structures from the chemistry join.
        level: ``"structure"`` keeps every InChIKey; ``"connectivity"`` merges
            structures that share an InChIKey first block.

    Returns:
        Units in first-seen order. A connectivity unit is tested if any of its
        stereoisomers is tested.

    Raises:
        ValueError: On an unknown level.
    """
    if level not in {"structure", "connectivity"}:
        raise ValueError(f"Unknown collapse level: {level}")
    groups: dict[str, list[Structure]] = {}
    for structure in structures:
        key = structure.inchikey if level == "structure" else first_block(structure.inchikey)
        groups.setdefault(key, []).append(structure)
    units = []
    for key, members in groups.items():
        units.append(
            Unit(
                key=key,
                members=tuple(member.inchikey for member in members),
                tested=any(member.tested for member in members),
                labels=tuple(sorted({member.label for member in members})),
            )
        )
    return units


@dataclass
class Breadth:
    """Distinct entities observed for one key across the LOTUS export.

    Attributes:
        organisms: Distinct cleaned organism names.
        genera: Distinct genera from the aligned rank arrays.
        families: Distinct families from the aligned rank arrays.
        references: Distinct reference identifiers.
        rows: Export rows contributing to this key.
    """

    organisms: set[str] = field(default_factory=set)
    genera: set[str] = field(default_factory=set)
    families: set[str] = field(default_factory=set)
    references: set[str] = field(default_factory=set)
    rows: int = 0

    def add(self, row: LotusRow) -> None:
        """Record one export row."""
        self.rows += 1
        if row.organism:
            self.organisms.add(row.organism)
        if row.genus:
            self.genera.add(row.genus)
        if row.family:
            self.families.add(row.family)
        if row.reference:
            self.references.add(row.reference)

    def counts(self) -> dict[str, int]:
        """Return the distinct counts as plain integers."""
        return {
            "organisms": len(self.organisms),
            "genera": len(self.genera),
            "families": len(self.families),
            "references": len(self.references),
            "lotus_rows": self.rows,
        }


def count_breadth(
    rows: Iterable[LotusRow], full_keys: set[str], blocks: set[str]
) -> tuple[dict[str, Breadth], dict[str, Breadth]]:
    """Accumulate breadth per full InChIKey and per connectivity block in one pass.

    Args:
        rows: Every LOTUS export row.
        full_keys: Full InChIKeys of the structures under study.
        blocks: First blocks of those structures. A LOTUS row whose first block
            matches counts towards the block even when its full key is a
            stereoisomer absent from the chemistry join.

    Returns:
        Breadth keyed by full InChIKey, and breadth keyed by first block. Keys
        with no export row are present with zero counts.
    """
    by_key = {key: Breadth() for key in full_keys}
    by_block = {block: Breadth() for block in blocks}
    for row in rows:
        if not row.inchikey:
            continue
        block = first_block(row.inchikey)
        if block not in by_block:
            continue
        by_block[block].add(row)
        if row.inchikey in by_key:
            by_key[row.inchikey].add(row)
    return by_key, by_block
