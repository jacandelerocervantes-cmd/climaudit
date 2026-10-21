"""Run every generated synthetic dossier through the verification pipeline and compare with expected.json.

Expected values were computed by scripts/build_fixtures.py with independent Decimal arithmetic. The test also
regenerates the fixtures into a temporary folder and checks they match the committed files (reproducibility).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from climaudit import dossiers as d
from climaudit.checks.sanitizer import findings_for, sanitize_pdf
from climaudit.evidence import EvidenceItem
from climaudit.models import BatchRecord, Facility
from climaudit.profiles import ProfileRegistry
from climaudit.verification import VerificationInput, verify

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND / "fixtures"
REG = ProfileRegistry()
CASES = sorted(p.parent for p in FIXTURES.glob("*/package.json"))


def load(case_dir: Path):
    pkg = json.loads((case_dir / "package.json").read_text(encoding="utf-8"))
    expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    return pkg, expected


def run_case(case_dir: Path):
    pkg, _ = load(case_dir)
    doc_findings = []
    for doc in pkg["documents"]:
        doc_findings += findings_for(sanitize_pdf((case_dir / doc["path"]).read_bytes()), doc["filename"])
    return verify(
        VerificationInput(
            profile=REG.get(pkg["profile_id"]),
            facility=Facility(**pkg["facility"]),
            batch=BatchRecord(**pkg["batch"]),
            evidence=d.normalized([EvidenceItem(**i) for i in pkg["evidence"]]),
            facility_year=d.normalized([EvidenceItem(**i) for i in pkg["facility_year"]]),
            project_country=pkg["project_country"],
            document_findings=doc_findings,
        )
    )


def test_fixture_set_is_present_and_complete():
    names = {c.name for c in CASES}
    required = {
        "happy_high_tech", "happy_low_tech_default_0.56", "wet_as_dry", "moisture_basis_missing", "hcorg_0.69", "hcorg_0.70", "hcorg_0.71",
        "transport_150_km", "transport_200_km", "transport_250_km", "application_after_one_year", "non_soil_low_tech",
        "mass_balance_log_mismatch", "mass_balance_freight_mismatch", "unverified_parameter", "hidden_text_injection",
        "benford_fabricated_series", "benford_natural_series",
    }
    assert required <= names, required - names


@pytest.mark.parametrize("case_dir", CASES, ids=[c.name for c in CASES])
def test_fixture_matches_expected(case_dir):
    pkg, expected = load(case_dir)
    assert pkg["provenance"] == "synthetic"
    report = run_case(case_dir)
    codes = {f["code"] for f in report["findings"]}
    assert report["status"] == expected["status"], (codes, report["status"])
    assert report["recommendation"] == expected["recommendation"], codes
    assert set(expected["findings_include"]) <= codes, codes
    assert not (set(expected["findings_exclude"]) & codes), codes
    if expected["kg_central"] is None:
        assert report["kg_co2e"] is None
    else:
        assert report["kg_co2e"]["central"] == expected["kg_central"]
        low, central, high = report["kg_co2e"]["low"], report["kg_co2e"]["central"], report["kg_co2e"]["high"]
        assert low <= central <= high
        assert report["issuable_kg"] <= max(low, 0) + 0 and report["issuable_kg"] <= pkg["batch"]["claimed_kg_co2e"]


def test_fixtures_regenerate_identically(tmp_path):
    sys.path.insert(0, str(BACKEND / "scripts"))
    try:
        import build_fixtures  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    build_fixtures.build(tmp_path)
    for case_dir in CASES:
        for name in ("package.json", "expected.json"):
            assert (tmp_path / case_dir.name / name).read_text(encoding="utf-8") == (case_dir / name).read_text(encoding="utf-8"), (case_dir.name, name)
        for doc in (case_dir / "docs").glob("*"):
            assert (tmp_path / case_dir.name / "docs" / doc.name).read_bytes() == doc.read_bytes()
