"""Advisory public-data checks (distance, weather, land cover, registry) with scripted providers: no network."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from climaudit import dossiers as d
from climaudit.api.app import create_app
from climaudit.config import Settings
from climaudit.evidence import EvidenceItem
from climaudit.external.checks import ExternalChecks
from climaudit.external.geo import ExternalUnavailable, haversine_km
from climaudit.external.providers import DailyWeather, OpenMeteoWeather, RegistryIndex, RegistryProject, worldcover_tile_url
from climaudit.ledger.fake import FakeLedger
from climaudit.models import BatchRecord, Facility, Project
from climaudit.store import Store

from .conftest import KEYS, Client
from .test_api_flow import evidence_for, evidence_payload, submit

h3 = pytest.importorskip("h3")

FACILITY_CELL = h3.latlng_to_cell(19.40, -99.10, 9)  # near Mexico City
NEAR_CELL = h3.latlng_to_cell(19.41, -99.11, 9)  # about 1.5 km away
FAR_CELL = h3.latlng_to_cell(20.40, -99.10, 9)  # about 110 km away


def project(registry_id=None):
    return Project(project_id="p1", owner_actor="o", country="MX", registry_project_id=registry_id, created_at="t")


def facility(cell=FACILITY_CELL):
    return Facility(facility_id="f1", project_id="p1", country="MX", cell=cell)


def batch(cells, year=2026):
    return BatchRecord(batch_id="b1", project_id="p1", facility_id="f1", year=year, biochar_type="x", cell_set=list(cells), period_start="2026-01-01", period_end="2026-07-01")


def item(kind, value, group=None, unit=""):
    return EvidenceItem(item_id=f"{kind}-{group}-{value}", kind=kind, value=value, unit=unit, group=group)


def leg(group, km, kind="biochar"):
    return [item("transport_distance_km_return", km, group, "km"), item("transport_leg_kind", kind, group)]


class Weather:
    def __init__(self, days):
        self.days = days

    def daily(self, lat, lon, start, end):
        return {day: DailyWeather(day, *vals) for day, vals in self.days.items()}


class Cover:
    def __init__(self, cls):
        self.cls = cls

    def class_at(self, lat, lon):
        return self.cls


def codes(findings):
    """Finding codes without the unavailable-check notes of providers a test does not configure."""
    return [f.code for f in findings if f.code != "EXTERNAL_CHECK_UNAVAILABLE"]


def test_haversine_known_distance():
    # Paris to London is about 344 km
    assert 340 < haversine_km(48.8566, 2.3522, 51.5074, -0.1278) < 348


def test_declared_distance_shorter_than_the_geometry_allows_is_flagged():
    checks = ExternalChecks()
    far = checks.run(project(), facility(), batch([FAR_CELL]), leg("l1", "20"))
    assert codes(far) == ["TRANSPORT_DISTANCE_IMPLAUSIBLE"]  # 110 km one way needs more than 200 km return
    assert far[0].params["leg_id"] == "l1" and float(far[0].params["minimum_km_return"]) > 200
    ok = checks.run(project(), facility(), batch([FAR_CELL]), leg("l1", "260"))
    assert "TRANSPORT_DISTANCE_IMPLAUSIBLE" not in codes(ok)
    near = checks.run(project(), facility(), batch([NEAR_CELL]), leg("l1", "3"))
    assert "TRANSPORT_DISTANCE_IMPLAUSIBLE" not in codes(near)  # 1.5 km apart: a 3 km return trip is enough


def test_distance_check_needs_a_facility_location_and_ignores_biomass_legs():
    checks = ExternalChecks()
    missing = checks.run(project(), facility(cell=None), batch([FAR_CELL]), leg("l1", "20"))
    assert [(f.code, f.params["reason"]) for f in missing if f.params.get("check") == "distance"] == [("EXTERNAL_CHECK_UNAVAILABLE", "facility_location_missing")]
    assert codes(checks.run(project(), facility(), batch([FAR_CELL]), leg("l1", "20", kind="biomass"))) == []


def test_weather_flags_frozen_and_very_heavy_rain_days_only():
    days = {"2026-01-10": (-8.0, -1.0, 0.0), "2026-01-11": (5.0, 12.0, 80.0), "2026-01-12": (6.0, 14.0, 2.0)}
    checks = ExternalChecks(weather=Weather(days))
    items = [item("application_date", day) for day in days]
    found = checks.run(project(), facility(), batch([NEAR_CELL]), items)
    reasons = [(f.params["date"], f.params["reason"]) for f in found if f.code == "WEATHER_UNSUITABLE_FOR_APPLICATION"]
    assert reasons == [("2026-01-10", "frozen_ground_likely"), ("2026-01-11", "very_heavy_rain")]


def test_land_cover_mismatch_uses_the_declared_land_type():
    forest = ExternalChecks(land_cover=Cover("tree_cover"))
    found = forest.run(project(), facility(), batch([NEAR_CELL]), [item("land_type", "cropland")])
    assert codes(found) == ["LAND_COVER_MISMATCH"] and found[0].params["observed"] == "tree_cover"
    assert codes(forest.run(project(), facility(), batch([NEAR_CELL]), [item("land_type", "forest")])) == []
    water = ExternalChecks(land_cover=Cover("permanent_water")).run(project(), facility(), batch([NEAR_CELL]), [])
    assert codes(water) == ["LAND_COVER_MISMATCH"] and water[0].params["declared_land_type"] == "not_declared"
    assert codes(ExternalChecks(land_cover=Cover("tree_cover")).run(project(), facility(), batch([NEAR_CELL]), [])) == []


def registry():
    projects = {
        "VCS4679": RegistryProject("VCS4679", "Reignite", "VCS", "Registered", "Biochar", "VM0044 Methodology for Biochar", "India", "SRC", 115103, 19052, {2023: 39909, 2026: 10}),
        "CAR2048": RegistryProject("CAR2048", "Cleanup", "CAR", "Listed", "Biochar", "CAR Biochar Protocol", "United States", "3D", 0, 0, {}),
    }
    return RegistryIndex(projects, {"name": "Voluntary Registry Offsets Database", "version": "2026-08"})


def test_registry_found_methodology_mismatch_vintage_and_manual_link():
    checks = ExternalChecks(registry=registry())
    found = checks.run(project("vcs4679"), facility(), batch([NEAR_CELL], year=2026), [])
    assert codes(found) == ["REGISTRY_RECORD_FOUND", "REGISTRY_VINTAGE_ALREADY_ISSUED", "REGISTRY_MANUAL_CHECK"]
    assert next(f for f in found if f.code == "REGISTRY_VINTAGE_ALREADY_ISSUED").params["issued_credits"] == 10
    other = checks.run(project("CAR2048"), facility(), batch([NEAR_CELL]), [])
    assert "REGISTRY_METHODOLOGY_MISMATCH" in codes(other) and "REGISTRY_MANUAL_CHECK" not in codes(other)
    missing = checks.run(project("VCS9999999"), facility(), batch([NEAR_CELL]), [])
    assert "REGISTRY_PROJECT_NOT_FOUND" in codes(missing)


def test_unconfigured_or_failing_checks_degrade_to_info_findings_and_never_raise():
    class Broken:
        def daily(self, *a):
            raise ExternalUnavailable("network_unreachable")

    found = ExternalChecks(weather=Broken()).run(project("VCS4679"), facility(), batch([NEAR_CELL]), [item("application_date", "2026-01-10")])
    unavailable = {f.params["check"]: f.params["reason"] for f in found if f.code == "EXTERNAL_CHECK_UNAVAILABLE"}
    assert unavailable == {"weather": "network_unreachable", "land_cover": "land_cover_provider_not_configured", "registry": "registry_index_not_configured"}
    assert all(f.severity == "info" for f in found)


def test_open_meteo_parser_and_worldcover_tile_names():
    payload = {"daily": {"time": ["2026-01-10"], "temperature_2m_min": [1.0], "temperature_2m_max": [9.5], "precipitation_sum": [0.2]}}
    provider = OpenMeteoWeather(fetch=lambda url: json.dumps(payload).encode())
    assert provider.daily(19.4, -99.1, "2026-01-10", "2026-01-10")["2026-01-10"].tmax_c == 9.5
    with pytest.raises(ExternalUnavailable):
        OpenMeteoWeather(fetch=lambda url: b"{}").daily(0, 0, "2026-01-01", "2026-01-02")
    assert worldcover_tile_url(19.4, -99.1).endswith("ESA_WorldCover_10m_2021_v200_N18W102_Map.tif")
    assert worldcover_tile_url(-33.9, 151.2).endswith("_S36E150_Map.tif")


def test_registry_index_loader_rejects_missing_and_corrupt_files(tmp_path):
    with pytest.raises(ExternalUnavailable):
        RegistryIndex.load(str(tmp_path / "nope.json"))
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(ExternalUnavailable):
        RegistryIndex.load(str(bad))
    good = tmp_path / "ok.json"
    good.write_text(json.dumps({"meta": {"version": "x"}, "projects": [{"project_id": "VCS1", "name": "n", "registry": "VCS", "status": "s", "type": "t", "methodology": "m", "country": "c", "developer": "d", "issued": 5, "retired": 1, "issued_by_vintage": {"2024": 5}}]}))
    assert RegistryIndex.load(str(good)).get("vcs1").issued_by_vintage == {2024: 5}


def test_findings_reach_the_report_and_never_block_verification():
    store = Store(":memory:")
    external = ExternalChecks(weather=Weather({"2026-03-01": (-5.0, -2.0, 0.0)}), land_cover=Cover("tree_cover"), registry=registry())
    app = create_app(Settings(api_keys=dict(KEYS)), ledger=FakeLedger(lambda: "t"), store=store, external=external)
    client = Client(TestClient(app, raise_server_exceptions=False))
    project = client.ok("POST", "/projects", "owner", {"country": "MX", "registry_project_id": "VCS4679"})
    fac = client.ok("POST", f"/projects/{project['project_id']}/facilities", "owner", {"process": "pyrolysis", "pyrolysis_gas_combusted": True, "heat_use_pct": "80", "pollution_controls": True, "temperature_measured": True, "declared_class": "high", "cell": FACILITY_CELL})
    assert fac["cell"] == FACILITY_CELL
    client.ok("PUT", f"/facilities/{fac['facility_id']}/years/2026/evidence", "owner", evidence_payload(d.base_facility_year()))
    batch = client.ok("POST", "/batches", "owner", {"facility_id": fac["facility_id"], "year": 2026, "biochar_type": "agricultural_residue", "parcel_key": "P-EXT", "cell_set": [NEAR_CELL], "period_start": "2026-01-01", "period_end": "2026-07-01", "claimed_kg_co2e": 300000})
    client.ok("POST", f"/batches/{batch['batch_id']}/evidence", "owner", evidence_payload(evidence_for("2026-03-01")))
    submit(client, batch["batch_id"])
    report = client.ok("POST", f"/batches/{batch['batch_id']}/verification", "verifier")
    got = {f["code"] for f in report["findings"]}
    assert report["status"] == "complete" and {"WEATHER_UNSUITABLE_FOR_APPLICATION", "REGISTRY_RECORD_FOUND", "REGISTRY_MANUAL_CHECK"} <= got
    assert all(not f["blocks_calculation"] and not f["blocks_verified"] for f in report["findings"] if f["code"].startswith(("WEATHER", "REGISTRY", "EXTERNAL", "LAND", "TRANSPORT_DISTANCE_IMPLAUSIBLE")))
    store.close()


def test_bad_facility_cell_is_rejected_at_creation():
    app = create_app(Settings(api_keys=dict(KEYS)), ledger=FakeLedger(lambda: "t"), store=Store(":memory:"))
    client = Client(TestClient(app, raise_server_exceptions=False))
    project = client.ok("POST", "/projects", "owner", {"country": "MX"})
    r = client.call("POST", f"/projects/{project['project_id']}/facilities", "owner", {"process": "pyrolysis", "cell": "zzzzzzzzzzzzzzz"})
    assert r.status_code == 422 or r.status_code == 400
