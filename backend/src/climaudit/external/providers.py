"""Data providers for the advisory checks: Open-Meteo weather, ESA WorldCover land cover, registry index.

Each provider is small and takes its transport as an argument so tests can script it. Network providers use the
standard library; the land cover sampler needs the optional `geo` extra (rasterio).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .geo import ExternalUnavailable

OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
WORLDCOVER_BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
USER_AGENT = "ClimAudit/0.1 (advisory cross-checks; hackathon prototype)"

# ESA WorldCover v200 class codes
WORLDCOVER_CLASSES = {
    10: "tree_cover", 20: "shrubland", 30: "grassland", 40: "cropland", 50: "built_up", 60: "bare_sparse",
    70: "snow_ice", 80: "permanent_water", 90: "herbaceous_wetland", 95: "mangroves", 100: "moss_lichen",
}

Fetch = Callable[[str], bytes]


def http_get(url: str, timeout: float = 15.0) -> bytes:
    if not url.startswith(("https://", "http://")):
        raise ExternalUnavailable("bad_url")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310 (scheme checked above)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.read()
    except urllib.error.HTTPError as exc:
        raise ExternalUnavailable(f"http_{exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ExternalUnavailable("network_unreachable") from exc


@dataclass(frozen=True)
class DailyWeather:
    date: str
    tmin_c: float | None
    tmax_c: float | None
    precipitation_mm: float | None


class WeatherProvider(Protocol):
    def daily(self, lat: float, lon: float, start: str, end: str) -> dict[str, DailyWeather]: ...


class OpenMeteoWeather:
    """Open-Meteo historical (ERA5 reanalysis) daily series. Free for non-commercial use, CC BY 4.0, no key."""

    def __init__(self, fetch: Fetch = http_get, base_url: str = OPEN_METEO_ARCHIVE):
        self._fetch, self._base = fetch, base_url

    def daily(self, lat: float, lon: float, start: str, end: str) -> dict[str, DailyWeather]:
        query = urllib.parse.urlencode({
            "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "start_date": start, "end_date": end,
            "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum", "timezone": "UTC",
        })
        try:
            data = json.loads(self._fetch(f"{self._base}?{query}").decode("utf-8"))
            daily = data["daily"]
            return {
                day: DailyWeather(day, daily["temperature_2m_min"][i], daily["temperature_2m_max"][i], daily["precipitation_sum"][i])
                for i, day in enumerate(daily["time"])
            }
        except ExternalUnavailable:
            raise
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise ExternalUnavailable("unexpected_weather_response") from exc


class LandCoverProvider(Protocol):
    def class_at(self, lat: float, lon: float) -> str | None: ...


def worldcover_tile_url(lat: float, lon: float, base: str = WORLDCOVER_BASE) -> str:
    """Tiles are 3x3 degrees named after their lower-left corner, e.g. ESA_WorldCover_10m_2021_v200_N51E003_Map.tif."""
    import math  # noqa: PLC0415

    tile_lat, tile_lon = math.floor(lat / 3) * 3, math.floor(lon / 3) * 3
    ns, ew = ("N" if tile_lat >= 0 else "S"), ("E" if tile_lon >= 0 else "W")
    return f"{base}/ESA_WorldCover_10m_2021_v200_{ns}{abs(tile_lat):02d}{ew}{abs(tile_lon):03d}_Map.tif"


class WorldCoverSampler:
    """Reads one pixel of the public ESA WorldCover v200 (2021) COG over HTTPS. Needs rasterio (`geo` extra)."""

    def __init__(self, base_url: str = WORLDCOVER_BASE):
        self._base = base_url

    def class_at(self, lat: float, lon: float) -> str | None:
        try:
            import rasterio  # noqa: PLC0415 (optional dependency)
        except ImportError as exc:
            raise ExternalUnavailable("rasterio_not_installed") from exc
        url = worldcover_tile_url(lat, lon, self._base)
        try:
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_TIMEOUT="20"):
                with rasterio.open(url) as src:
                    value = next(src.sample([(lon, lat)]))[0]
        except Exception as exc:  # noqa: BLE001 - network, missing tile (ocean) and GDAL errors are all "unavailable"
            raise ExternalUnavailable("worldcover_unreachable") from exc
        return WORLDCOVER_CLASSES.get(int(value))


@dataclass(frozen=True)
class RegistryProject:
    project_id: str
    name: str
    registry: str
    status: str
    type: str
    methodology: str
    country: str
    developer: str
    issued: int
    retired: int
    issued_by_vintage: dict[int, int]


class RegistryIndex:
    """Local index of the Berkeley Voluntary Registry Offsets Database built by scripts/build_registry_index.py."""

    def __init__(self, projects: dict[str, RegistryProject], meta: dict[str, Any]):
        self._projects, self.meta = projects, meta

    @classmethod
    def load(cls, path: str) -> "RegistryIndex":
        file = Path(path)
        if not file.is_file():
            raise ExternalUnavailable("registry_index_missing")
        try:
            raw = json.loads(file.read_text(encoding="utf-8"))
            projects = {
                p["project_id"].upper(): RegistryProject(
                    p["project_id"], p["name"], p["registry"], p["status"], p["type"], p["methodology"], p["country"], p["developer"],
                    int(p["issued"]), int(p["retired"]), {int(y): int(v) for y, v in p["issued_by_vintage"].items()},
                )
                for p in raw["projects"]
            }
            return cls(projects, raw["meta"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ExternalUnavailable("registry_index_invalid") from exc

    def get(self, project_id: str) -> RegistryProject | None:
        return self._projects.get(project_id.strip().upper())

    def __len__(self) -> int:
        return len(self._projects)
