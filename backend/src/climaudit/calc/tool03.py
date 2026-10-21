"""CDM TOOL03 v03.0: project or leakage CO2 from fossil fuel combustion (research/sources/cdm-tool03).

Eq. 1: PE_FC,j,y = sum_i FC_i,j,y * COEF_i,y
Eq. 2 (Option A, mass unit):    COEF = w_C * 44/12
Eq. 3 (Option A, volume unit):  COEF = w_C * rho * 44/12
Eq. 4 (Option B):               COEF = NCV * EF_CO2
Fuel properties (w_C, rho, NCV, EF_CO2) are inputs with provenance; the IPCC default tables were not read.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..decimals import C_TO_CO2


@dataclass(frozen=True)
class FuelUse:
    fuel: str
    quantity: Decimal  # mass or volume unit per year
    option: str  # "A" or "B"
    carbon_fraction: Decimal | None = None  # tC per mass unit (Option A)
    density: Decimal | None = None  # mass unit per volume unit (Option A, volume quantities)
    quantity_is_volume: bool = False
    ncv: Decimal | None = None  # GJ per mass or volume unit (Option B)
    ef_co2: Decimal | None = None  # tCO2 per GJ (Option B)


def co2_coefficient(use: FuelUse) -> Decimal:
    if use.option == "A":
        if use.carbon_fraction is None:
            raise ValueError("Option A needs carbon_fraction")
        if use.quantity_is_volume:
            if use.density is None:
                raise ValueError("Option A with a volume quantity needs density")
            return use.carbon_fraction * use.density * C_TO_CO2
        return use.carbon_fraction * C_TO_CO2
    if use.option == "B":
        if use.ncv is None or use.ef_co2 is None:
            raise ValueError("Option B needs ncv and ef_co2")
        return use.ncv * use.ef_co2
    raise ValueError(f"unknown option {use.option!r}")


def co2_from_fuels(uses: list[FuelUse]) -> Decimal:
    """Return tCO2 for the listed fuel uses (Eq. 1)."""
    total = Decimal(0)
    for use in uses:
        total += use.quantity * co2_coefficient(use)
    return total
