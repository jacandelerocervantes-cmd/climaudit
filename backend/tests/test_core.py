"""Core tests: canonical JSON, hash chain vectors from BACKEND-SPEC.md section 11, decimals, config."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from climaudit.canonical import GENESIS_HASH, CanonicalError, canonical_bytes, canonical_hash
from climaudit.config import load_settings
from climaudit.decimals import C_TO_CO2, D, dstr, tonnes_to_kg_int
from climaudit.hashchain import make_event, verify_chain

# Literal vectors from BACKEND-SPEC.md section 11 (computed independently with a reference script).
V0_INPUT = (
    '{"batch_id":"b-001","payload_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
    '"prev_hash":"0000000000000000000000000000000000000000000000000000000000000000",'
    '"provenance":"synthetic","seq":0,"ts":"2026-10-16T12:00:00Z","type":"batch_submitted"}'
)
V0_HASH = "a16f9526c8b6e3f76cc295a7eb043dfbd3fbd64464e5b87e549afe5fa7fe27b4"
V1_HASH = "c496f195dcb6ad036eb6602521ced6c146c35c73280a9ed4f3eec17e51359768"
V2_HASH = "a5051c8aef6c526a9cf761d460133a9a0654dbe8a62b124140576dafb9a556a0"
PAYLOAD_HASH = "a" * 64


def test_vector_0_canonical_bytes_and_hash():
    event0 = make_event(0, "2026-10-16T12:00:00Z", "batch_submitted", "b-001", PAYLOAD_HASH, GENESIS_HASH, "synthetic")
    body = {k: v for k, v in event0.items() if k != "hash"}
    assert canonical_bytes(body).decode("utf-8") == V0_INPUT
    assert event0["hash"] == V0_HASH


def test_vector_1_chained_hash():
    event0 = make_event(0, "2026-10-16T12:00:00Z", "batch_submitted", "b-001", PAYLOAD_HASH, GENESIS_HASH, "synthetic")
    event1 = make_event(1, "2026-10-16T12:05:00Z", "report_issued", "b-001", PAYLOAD_HASH, event0["hash"], "synthetic")
    assert event1["prev_hash"] == V0_HASH
    assert event1["hash"] == V1_HASH


def test_vector_2_parcel_commitment():
    commitment = {
        "cell_set": sorted(["8928308280fffff", "8928308280bffff"]),
        "end": "2026-07-01T00:00:00Z",
        "methodology_id": "VM0044",
        "start": "2026-01-01T00:00:00Z",
    }
    assert canonical_hash(commitment) == V2_HASH


def test_key_order_does_not_change_hash():
    a = {"x": 1, "y": "z", "n": {"b": 2, "a": 1}}
    b = {"n": {"a": 1, "b": 2}, "y": "z", "x": 1}
    assert canonical_hash(a) == canonical_hash(b)


def test_nfc_normalization():
    composed = {"name": "Café"}
    decomposed = {"name": "Café"}
    assert canonical_hash(composed) == canonical_hash(decomposed)


@pytest.mark.parametrize("bad", [{"a": 1.5}, {"a": None}, {"a": {1, 2}}, {1: "x"}])
def test_rejects_floats_nulls_and_odd_types(bad):
    with pytest.raises(CanonicalError):
        canonical_bytes(bad)


def test_no_whitespace_and_utf8():
    assert canonical_bytes({"a": "é", "b": [1, 2]}) == b'{"a":"\xc3\xa9","b":[1,2]}'


def test_chain_verifies_and_detects_tampering():
    e0 = make_event(0, "2026-10-16T12:00:00Z", "batch_submitted", "b-1", PAYLOAD_HASH, GENESIS_HASH, "synthetic")
    e1 = make_event(1, "2026-10-16T12:01:00Z", "evidence_attached", "b-1", PAYLOAD_HASH, e0["hash"], "synthetic")
    e2 = make_event(2, "2026-10-16T12:02:00Z", "report_issued", "b-1", PAYLOAD_HASH, e1["hash"], "synthetic")
    assert verify_chain([e0, e1, e2]).ok
    tampered = dict(e1, payload_hash="b" * 64)
    result = verify_chain([e0, tampered, e2])
    assert not result.ok and result.first_broken_seq == 1
    result = verify_chain([e0, e2])
    assert not result.ok and result.first_broken_seq == 1


def test_event_rejects_unknown_type_and_provenance():
    with pytest.raises(ValueError):
        make_event(0, "t", "nope", "b", PAYLOAD_HASH, GENESIS_HASH, "synthetic")
    with pytest.raises(ValueError):
        make_event(0, "t", "correction", "b", PAYLOAD_HASH, GENESIS_HASH, "guess")


def test_decimals_reject_float_and_round_once():
    with pytest.raises(TypeError):
        D(0.1)
    assert D("0.1") + D("0.2") == D("0.3")
    assert dstr(Decimal("261.0000")) == "261"
    assert dstr(Decimal("0.50")) == "0.5"
    tonnes = Decimal("71.2") * C_TO_CO2  # 261.0666...
    assert tonnes_to_kg_int(tonnes, "central") == 261067
    assert tonnes_to_kg_int(tonnes, "low") == 261066
    assert tonnes_to_kg_int(tonnes, "high") == 261067


def test_config_has_no_machine_specific_defaults_and_parses_keys():
    settings = load_settings({})
    assert settings.ledger_mode == "fake"
    assert not settings.db_path.startswith(("/", "C:", "c:", "\\"))
    env = {"CP_API_KEYS": json.dumps({"k1": {"actor_id": "a1", "role": "owner"}}), "CP_LEDGER_MODE": "direct"}
    parsed = load_settings(env)
    assert parsed.api_keys["k1"].role == "owner" and parsed.ledger_mode == "direct"
    with pytest.raises(ValueError):
        load_settings({"CP_LEDGER_MODE": "bogus"})
    with pytest.raises(ValueError):
        load_settings({"CP_API_KEYS": json.dumps({"k": {"actor_id": "a", "role": "king"}})})
