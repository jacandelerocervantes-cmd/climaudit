"""Domain models (SCHEMA.md section 2 and BACKEND-SPEC.md section 4)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .evidence import EvidenceItem

BATCH_STATES = (
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "NEEDS_INFO",
    "REJECTED",
    "VERIFIED",
    "BLOCKED",
    "ISSUED",
    "PARTIALLY_RETIRED",
    "RETIRED",
)
APPLICATION_TYPES = ("soil", "non_soil")
Provenance = Literal["measured", "modeled", "synthetic"]


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    owner_actor: str
    methodology_id: str = "VM0044"
    methodology_version: str = "1.2"
    profile_id: str = "VM0044@1.2"
    country: str = Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    provenance: Provenance = "synthetic"
    registry_project_id: str | None = Field(default=None, max_length=64)  # id of the project in an external registry, for cross-checks
    created_at: str


class Facility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facility_id: str
    project_id: str
    country: str = Field(min_length=2, max_length=2)
    process: Literal["pyrolysis", "gasification", "boiler"] = "pyrolysis"
    is_greenfield: bool = True
    pyrolysis_gas_combusted: bool = False
    heat_use_pct: str = "0"
    pollution_controls: bool = False
    temperature_measured: bool = False
    kiln_type: str | None = Field(default=None, max_length=128)
    declared_class: Literal["high", "low"] = "low"
    cell: str | None = Field(default=None, max_length=15)  # H3 cell of the facility, for the distance cross-check

    @field_validator("heat_use_pct")
    @classmethod
    def _heat_use_is_a_percentage(cls, value: str) -> str:
        try:
            d = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("heat_use_pct must be a decimal string") from exc
        if not d.is_finite() or d < 0 or d > 100:
            raise ValueError("heat_use_pct must be between 0 and 100")
        return value

    def meets_high_tech(self, min_heat_use_pct: Decimal) -> bool:
        return (
            self.pyrolysis_gas_combusted
            and Decimal(self.heat_use_pct) >= min_heat_use_pct
            and self.pollution_controls
            and self.temperature_measured
        )


class BatchRecord(BaseModel):
    """One batch = (facility, biochar type t, application type k, year y) with its parcel and period."""

    model_config = ConfigDict(extra="forbid")

    batch_id: str
    project_id: str
    facility_id: str
    year: int = Field(ge=2000, le=2100)
    biochar_type: str = Field(max_length=64)
    application_type: Literal["soil", "non_soil"] = "soil"
    profile_id: str = "VM0044@1.2"
    parcel_key: str | None = Field(default=None, max_length=128)
    cell_set: list[str] = Field(default_factory=list)
    product_batch_id: str | None = Field(default=None, max_length=128)
    period_start: str  # ISO date, inclusive; for submitted batches derived from the application dates
    period_end: str  # ISO date, exclusive
    claimed_kg_co2e: int = Field(default=0, ge=0)
    state: str = "DRAFT"
    created_at: str = ""
    updated_at: str = ""
