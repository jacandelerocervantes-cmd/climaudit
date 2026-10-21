"""Geometry helpers: great-circle distance and H3 cell centers (needs the optional `geo` extra for cells)."""
from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0088  # IUGG mean Earth radius


class ExternalUnavailable(Exception):
    """A check cannot run (missing data, library or network). Carries a short machine-readable reason."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def _h3():
    try:
        import h3  # noqa: PLC0415 (optional dependency)
    except ImportError as exc:
        raise ExternalUnavailable("h3_not_installed") from exc
    return h3


def cell_center(cell: str) -> tuple[float, float]:
    h3 = _h3()
    try:
        return h3.cell_to_latlng(cell)
    except Exception as exc:  # noqa: BLE001 - invalid cells are a data problem, not a crash
        raise ExternalUnavailable("invalid_h3_cell") from exc


def cell_edge_km(cell: str) -> float:
    """Average edge length of the cell's resolution, used as the location uncertainty of a cell center."""
    h3 = _h3()
    return float(h3.average_hexagon_edge_length(h3.get_resolution(cell), unit="km"))
