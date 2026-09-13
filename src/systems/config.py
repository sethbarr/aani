"""Load and validate isolated exploratory-system configurations."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.common.io import read_json


class DirectionSemantics(BaseModel):
    """Meaning of directional labels for one behavioural system."""

    model_config = ConfigDict(extra="forbid")
    accept: str = Field(min_length=1)
    reject: str | None
    unknown: str = Field(min_length=1)


class ReferenceSource(BaseModel):
    """A source fixed for positive-control recall construction."""

    model_config = ConfigDict(extra="forbid")
    citation: str = Field(min_length=1)
    doi: str = Field(min_length=1)


class SystemConfig(BaseModel):
    """Prospective contract for one exploratory coevolved system."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    slug: Literal["propolis", "monarch", "attine_actino"]
    exploratory: Literal[True]
    positive_control: bool = False
    behaving_organism: str = Field(min_length=1)
    behaviour: str = Field(min_length=1)
    direction_semantics: DirectionSemantics
    chemical_target_class: str = Field(min_length=1)
    chemistry_backend: Literal["LOTUS", "none"]
    taxonomy_kingdom: str = Field(min_length=1)
    taxonomy_target: str = Field(min_length=1)
    assay_organisms: list[str]
    biological_assay_target: str | None = None
    assay_mismatch: str | None = None
    expected_outcome: str = Field(min_length=1)
    seed_query: str = Field(min_length=1)
    europe_pmc_query: str = Field(min_length=1)
    screening_terms: list[str] = Field(min_length=1)
    corpus_limit: int = Field(ge=1, le=20)
    extraction_job_limit: int = Field(ge=1, le=12)
    extraction_grounding: Literal["single_quote_v1"]
    run_chemistry: bool
    run_bioactivity: bool
    reference_sources: list[ReferenceSource] = Field(default_factory=list)
    time_limit_hours: int = Field(ge=1, le=4)

    @model_validator(mode="after")
    def validate_stage_scope(self) -> "SystemConfig":
        """Require stage settings consistent with the declared backend."""
        if self.chemistry_backend == "none" and (self.run_chemistry or self.run_bioactivity):
            raise ValueError("A system without chemistry cannot run chemistry or bioactivity")
        if self.run_bioactivity and not self.assay_organisms:
            raise ValueError("Bioactivity requires assay organisms")
        if self.positive_control and not self.reference_sources:
            raise ValueError("A positive control requires reference sources")
        return self


def load_system_config(path: Path) -> SystemConfig:
    """Read and validate a system config from its explicit path."""
    return SystemConfig.model_validate(read_json(path))


def system_paths(config: SystemConfig, root: Path = Path.cwd()) -> dict[str, Path]:
    """Return the only allowed artifact roots for one system."""
    interim = root / "data" / "interim" / "systems" / config.slug
    results = root / "results" / "systems" / config.slug
    return {"interim": interim, "results": results}
