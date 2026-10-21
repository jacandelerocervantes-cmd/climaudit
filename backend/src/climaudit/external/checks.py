"""Advisory cross-checks (distance, weather, land cover, registry). Never blocks, never changes a number.

Each check returns findings for the human verifier. A check that cannot run (missing data, library or network)
reports `EXTERNAL_CHECK_UNAVAILABLE` and the others still run. Heuristic thresholds are named constants below and
are recorded in DECISIONS-LEDGER.md (D-172 to D-175); they are screening aids, not methodology rules.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from ..evidence import EvidenceItem, EvidenceView
from ..findings import Finding, make
from ..models import BatchRecord, Facility, Project
from .geo import ExternalUnavailable, cell_center, cell_edge_km, haversine_km
from .providers import LandCoverProvider, RegistryIndex, WeatherProvider

DISTANCE_SLACK = 0.99  # 1 % tolerance for the Earth radius and rounding of declared distances
FROZEN_TMAX_C = 0.0  # a day whose maximum air temperature stays below freezing: ground very likely frozen
HEAVY_RAIN_MM = 50.0  # daily precipitation at or above this is "very heavy" (the common R50mm climate index)
MAX_FINDINGS_PER_CHECK = 5
MAX_WEATHER_SPAN_DAYS = 366
MAX_CELLS_SAMPLED = 10
VERRA_REGISTRY_URL = "https://registry.verra.org/"

# Observed WorldCover classes that are plausible for a declared land type (soil application). "other" is never flagged.
PLAUSIBLE_COVER = {
    "cropland": {"cropland", "grassland", "shrubland", "bare_sparse"},
    "grassland": {"grassland", "cropland", "shrubland", "bare_sparse"},
    "forest": {"tree_cover", "shrubland", "mangroves"},
    "wetland": {"herbaceous_wetland", "mangroves", "permanent_water", "grassland"},
    "urban_soil": {"built_up", "grassland", "cropland", "tree_cover", "bare_sparse", "shrubland"},
}
IMPLAUSIBLE_WITHOUT_DECLARATION = {"permanent_water", "snow_ice"}


def _unavailable(check: str, reason: str) -> Finding:
    return make("EXTERNAL_CHECK_UNAVAILABLE", check=check, reason=reason)


class ExternalChecks:
    def __init__(self, weather: WeatherProvider | None = None, land_cover: LandCoverProvider | None = None, registry: RegistryIndex | None = None):
        self.weather, self.land_cover, self.registry = weather, land_cover, registry

    def run(self, project: Project, facility: Facility, batch: BatchRecord, items: list[EvidenceItem]) -> list[Finding]:
        view = EvidenceView(items)
        findings: list[Finding] = []
        for name, check in (
            ("distance", lambda: self._distance(facility, batch, view)),
            ("weather", lambda: self._weather(batch, view)),
            ("land_cover", lambda: self._land_cover(batch, view)),
            ("registry", lambda: self._registry(project, batch)),
        ):
            try:
                findings += check()
            except ExternalUnavailable as exc:
                findings.append(_unavailable(name, exc.reason))
            except Exception as exc:  # noqa: BLE001 - an advisory check must never break verification
                findings.append(_unavailable(name, f"unexpected_{type(exc).__name__}"))
        return findings

    # ------------------------------------------------------------------ distance
    def _distance(self, facility: Facility, batch: BatchRecord, view: EvidenceView) -> list[Finding]:
        """Road, rail or sea distance is never shorter than the great-circle distance, so a declared return trip
        shorter than twice the great-circle gap between the facility and the nearest parcel is impossible."""
        legs = [
            (leg_id, Decimal(g["transport_distance_km_return"].value))
            for leg_id, g in sorted(view.groups("transport_distance_km_return", "transport_leg_kind").items())
            if "transport_distance_km_return" in g and g.get("transport_leg_kind") is not None and g["transport_leg_kind"].value == "biochar"
        ]
        if not legs:
            return []
        if not facility.cell:
            raise ExternalUnavailable("facility_location_missing")
        if not batch.cell_set:
            raise ExternalUnavailable("application_location_missing")
        flat, flon = cell_center(facility.cell)
        f_edge = cell_edge_km(facility.cell)
        best: float | None = None
        for cell in batch.cell_set:
            lat, lon = cell_center(cell)
            gap = max(0.0, haversine_km(flat, flon, lat, lon) - f_edge - cell_edge_km(cell))
            best = gap if best is None else min(best, gap)
        minimum = 2 * (best or 0.0) * DISTANCE_SLACK
        out = []
        for leg_id, declared in legs:
            if float(declared) < minimum:
                out.append(make("TRANSPORT_DISTANCE_IMPLAUSIBLE", leg_id=leg_id, declared_km_return=format(declared, "f"), minimum_km_return=f"{minimum:.1f}"))
        return out

    # ------------------------------------------------------------------ weather
    def _weather(self, batch: BatchRecord, view: EvidenceView) -> list[Finding]:
        dates = sorted({i.value for i in view.all("application_date")})
        if not dates:
            return []
        if self.weather is None:
            raise ExternalUnavailable("weather_provider_not_configured")
        if not batch.cell_set:
            raise ExternalUnavailable("application_location_missing")
        start, end = dates[0], dates[-1]
        if (date.fromisoformat(end) - date.fromisoformat(start)) > timedelta(days=MAX_WEATHER_SPAN_DAYS):
            raise ExternalUnavailable("application_dates_span_too_long")
        lat, lon = cell_center(batch.cell_set[0])
        series = self.weather.daily(lat, lon, start, end)
        out: list[Finding] = []
        for day in dates:
            w = series.get(day)
            if w is None:
                continue
            if w.tmax_c is not None and w.tmax_c < FROZEN_TMAX_C:
                out.append(make("WEATHER_UNSUITABLE_FOR_APPLICATION", date=day, reason="frozen_ground_likely", tmax_c=f"{w.tmax_c:.1f}"))
            elif w.precipitation_mm is not None and w.precipitation_mm >= HEAVY_RAIN_MM:
                out.append(make("WEATHER_UNSUITABLE_FOR_APPLICATION", date=day, reason="very_heavy_rain", precipitation_mm=f"{w.precipitation_mm:.1f}"))
        return out[:MAX_FINDINGS_PER_CHECK]

    # ------------------------------------------------------------------ land cover
    def _land_cover(self, batch: BatchRecord, view: EvidenceView) -> list[Finding]:
        if batch.application_type != "soil":
            return []
        if not batch.cell_set:
            raise ExternalUnavailable("application_location_missing")
        if self.land_cover is None:
            raise ExternalUnavailable("land_cover_provider_not_configured")
        declared = view.text("land_type")
        if declared == "other":
            return []
        plausible = PLAUSIBLE_COVER.get(declared) if declared else None
        out: list[Finding] = []
        for cell in batch.cell_set[:MAX_CELLS_SAMPLED]:
            lat, lon = cell_center(cell)
            observed = self.land_cover.class_at(lat, lon)
            if observed is None:
                continue
            bad = observed not in plausible if plausible is not None else observed in IMPLAUSIBLE_WITHOUT_DECLARATION
            if bad:
                out.append(make("LAND_COVER_MISMATCH", cell=cell, observed=observed, declared_land_type=declared or "not_declared", dataset="ESA WorldCover v200 2021"))
        return out[:MAX_FINDINGS_PER_CHECK]

    # ------------------------------------------------------------------ registry
    def _registry(self, project: Project, batch: BatchRecord) -> list[Finding]:
        if not project.registry_project_id:
            raise ExternalUnavailable("registry_project_id_not_declared")
        if self.registry is None:
            raise ExternalUnavailable("registry_index_not_configured")
        found = self.registry.get(project.registry_project_id)
        source = {"dataset": str(self.registry.meta.get("name", "")), "version": str(self.registry.meta.get("version", ""))}
        if found is None:
            out = [make("REGISTRY_PROJECT_NOT_FOUND", registry_project_id=project.registry_project_id, **source)]
            if re.fullmatch(r"(?i)(vcs)?\d+", project.registry_project_id):
                out.append(make("REGISTRY_MANUAL_CHECK", registry="Verra", url=VERRA_REGISTRY_URL, registry_project_id=project.registry_project_id))
            return out
        out = [
            make(
                "REGISTRY_RECORD_FOUND", registry_project_id=found.project_id, registry=found.registry, status=found.status, type=found.type,
                registry_country=found.country, declared_country=project.country, issued=found.issued, retired=found.retired, **source,
            )
        ]
        if project.methodology_id.lower() not in found.methodology.lower():
            out.append(make("REGISTRY_METHODOLOGY_MISMATCH", registry_project_id=found.project_id, registry_methodology=found.methodology[:120], declared=project.methodology_id))
        already = found.issued_by_vintage.get(batch.year, 0)
        if already > 0:
            out.append(make("REGISTRY_VINTAGE_ALREADY_ISSUED", registry_project_id=found.project_id, vintage=batch.year, issued_credits=already, **source))
        if found.registry.lower().startswith(("verra", "vcs")):
            out.append(make("REGISTRY_MANUAL_CHECK", registry="Verra", url=VERRA_REGISTRY_URL, registry_project_id=found.project_id))
        return out
