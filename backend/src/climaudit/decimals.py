"""Decimal arithmetic helpers: no binary floats anywhere in the calculation engine."""
from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, Decimal, getcontext, localcontext
from typing import Union

getcontext().prec = 28

Number = Union[str, int, Decimal]

C_TO_CO2 = Decimal(44) / Decimal(12)


def D(value: Number) -> Decimal:
    if isinstance(value, float):
        raise TypeError("float is not allowed; pass a string, int or Decimal")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def dstr(value: Decimal) -> str:
    """Plain decimal string without exponent, trailing zeros trimmed."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def tonnes_to_kg_int(tonnes: Decimal, mode: str) -> int:
    """Convert tonnes to whole kg once, at the end of a calculation.

    mode: "central" (half-even), "low" (floor), "high" (ceiling).
    """
    kg = tonnes * Decimal(1000)
    rounding = {"central": ROUND_HALF_EVEN, "low": ROUND_FLOOR, "high": ROUND_CEILING}[mode]
    with localcontext() as ctx:
        ctx.prec = 40
        return int(kg.to_integral_value(rounding=rounding))
