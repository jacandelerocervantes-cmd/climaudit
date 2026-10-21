"""Structural validation and normalization of H3 cell indexes (no native dependency).

An H3 cell index is a 64-bit integer written as 15 lowercase hex digits. Layout (high to low): reserved bit 63,
mode (4 bits, 1 = cell), reserved (3 bits), resolution (4 bits), base cell (7 bits), then 15 digits of 3 bits where
digits beyond the resolution are 7. This module checks that structure so two spellings of one cell cannot slip past
the spatial double-counting guard. It does not check that a base cell exists or that a cell lies on a polygon; use
the `geo` extra (h3 library) for geometry.
"""
from __future__ import annotations

import re

from .errors import ApiError

_HEX15 = re.compile(r"^[0-9a-f]{15}$")


def parse(cell: str) -> tuple[int, int]:
    """Return (index, resolution) for a normalized cell string, or raise ValueError."""
    if not _HEX15.match(cell):
        raise ValueError("not 15 lowercase hex digits")
    index = int(cell, 16)
    if (index >> 59) & 0xF != 1:
        raise ValueError("mode is not a cell")
    resolution = (index >> 52) & 0xF
    if resolution > 15:
        raise ValueError("resolution out of range")
    base_cell = (index >> 45) & 0x7F
    if base_cell > 121:
        raise ValueError("base cell out of range")
    for position in range(1, 16):
        digit = (index >> ((15 - position) * 3)) & 0x7
        if position <= resolution and digit == 7:
            raise ValueError("digit 7 inside the resolution")
        if position > resolution and digit != 7:
            raise ValueError("digits beyond the resolution must be 7")
    return index, resolution


def compose(resolution: int, base_cell: int, digits: list[int]) -> str:
    """Build a structurally valid cell string (used by tests and the fixture generator)."""
    if len(digits) != resolution or any(not 0 <= d <= 6 for d in digits):
        raise ValueError("need exactly `resolution` digits in 0..6")
    index = (1 << 59) | (resolution << 52) | (base_cell << 45)
    for position in range(1, 16):
        digit = digits[position - 1] if position <= resolution else 7
        index |= digit << ((15 - position) * 3)
    return format(index, "015x")


def normalize_cells(cells: list[str], allowed_resolutions: tuple[int, ...] = (9, 10), max_cells: int = 2000) -> list[str]:
    """Strip, lowercase, validate and de-duplicate; all cells must share one allowed resolution."""
    if not cells:
        raise ApiError("VALIDATION_FAILED", {"field": "cell_set", "rule": "required"})
    if len(cells) > max_cells:
        raise ApiError("VALIDATION_FAILED", {"field": "cell_set", "rule": "too_many_cells", "max": max_cells})
    normalized: set[str] = set()
    resolutions: set[int] = set()
    for raw in cells:
        cell = raw.strip().lower()
        try:
            _, resolution = parse(cell)
        except ValueError as exc:
            raise ApiError("VALIDATION_FAILED", {"field": "cell_set", "rule": "invalid_h3_cell", "reason": str(exc)}) from exc
        normalized.add(cell)
        resolutions.add(resolution)
    if len(resolutions) != 1:
        raise ApiError("VALIDATION_FAILED", {"field": "cell_set", "rule": "single_resolution_required", "found": sorted(resolutions)})
    (resolution,) = resolutions
    if resolution not in allowed_resolutions:
        raise ApiError("VALIDATION_FAILED", {"field": "cell_set", "rule": "resolution_not_allowed", "found": resolution, "allowed": list(allowed_resolutions)})
    return sorted(normalized)
