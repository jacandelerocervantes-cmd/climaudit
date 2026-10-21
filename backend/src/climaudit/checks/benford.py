"""Benford's-law first-digit screen: a screening flag for manual review, never proof of fraud.

Valid only for series spanning several orders of magnitude, so a narrow-range series is reported as not
applicable instead of being flagged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

EXPECTED = {d: math.log10(1 + 1 / d) for d in range(1, 10)}  # reference probabilities, not hashed values


@dataclass(frozen=True)
class BenfordResult:
    applicable: bool
    reason: str
    n: int = 0
    chi2: float = 0.0
    mad: float = 0.0
    flagged: bool = False


def first_digit(value: Decimal) -> int | None:
    v = abs(value)
    if v == 0:
        return None
    exponent = v.adjusted()
    return int(v.scaleb(-exponent).to_integral_value(rounding="ROUND_FLOOR"))


def screen(values: list[Decimal], critical: Decimal, min_length: int, min_orders: int) -> BenfordResult:
    digits = [d for d in (first_digit(v) for v in values) if d is not None]
    n = len(digits)
    if n < min_length:
        return BenfordResult(False, "series_too_short", n)
    positives = [abs(v) for v in values if v != 0]
    if not positives:
        return BenfordResult(False, "no_positive_values", n)
    span = max(positives) / min(positives)
    if span < Decimal(10) ** min_orders:
        return BenfordResult(False, "narrow_range", n)
    counts = {d: 0 for d in range(1, 10)}
    for d in digits:
        counts[d] += 1
    chi2 = sum((counts[d] - n * EXPECTED[d]) ** 2 / (n * EXPECTED[d]) for d in range(1, 10))
    mad = sum(abs(counts[d] / n - EXPECTED[d]) for d in range(1, 10)) / 9
    return BenfordResult(True, "ok", n, chi2, mad, flagged=chi2 > float(critical))
