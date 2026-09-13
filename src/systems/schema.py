"""Single-quote extraction contract shared by exploratory systems."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SystemObservation(BaseModel):
    """One grounded behaviour or explicit organism-activity statement."""

    model_config = ConfigDict(extra="forbid")
    behaving_organism_as_written: str = Field(min_length=1)
    target_name_as_written: str = Field(min_length=1)
    taxonomic_rank: Literal["species", "genus", "family", "other"]
    direction: Literal["accept", "reject", "unknown"]
    evidence_type: Literal[
        "field_choice_assay",
        "lab_choice_assay",
        "observational",
        "pathogen_challenge",
        "compound_activity_assay",
        "review_secondary",
    ]
    quantitative_measure: str | None
    compound_name_as_written: str | None
    activity_target_as_written: str | None
    activity_outcome: Literal["suppresses", "does_not_suppress", "unknown"]
    source_id: str
    section: str
    block_id: str
    evidence_quote: str = Field(min_length=1)
    extraction_confidence: float = Field(ge=0, le=1)
    behavioural_choice: bool
    study_context: str = Field(min_length=1)
    original_source_id: str | None


class SystemExtraction(BaseModel):
    """Complete structured answer for supplied source blocks."""

    model_config = ConfigDict(extra="forbid")
    records: list[SystemObservation]
