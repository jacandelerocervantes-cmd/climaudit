"""Builds the advisory checks from settings. Missing pieces degrade to "unavailable" findings, never to errors."""
from __future__ import annotations

from ..config import Settings
from .checks import ExternalChecks
from .geo import ExternalUnavailable
from .providers import OPEN_METEO_ARCHIVE, WORLDCOVER_BASE, OpenMeteoWeather, RegistryIndex, WorldCoverSampler


def build_external(settings: Settings) -> ExternalChecks | None:
    if not settings.external_checks:
        return None
    registry = None
    if settings.registry_index_path:
        try:
            registry = RegistryIndex.load(settings.registry_index_path)
        except ExternalUnavailable:
            registry = None  # reported per batch as EXTERNAL_CHECK_UNAVAILABLE
    return ExternalChecks(
        weather=OpenMeteoWeather(base_url=settings.open_meteo_url or OPEN_METEO_ARCHIVE),
        land_cover=WorldCoverSampler(settings.worldcover_url or WORLDCOVER_BASE),
        registry=registry,
    )
