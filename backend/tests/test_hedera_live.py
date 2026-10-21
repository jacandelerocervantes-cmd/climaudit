"""Live Hedera TESTNET test. Skipped unless CP_LIVE_HEDERA=1 and the operator, topic and token variables are set.

It writes real testnet transactions (free testnet HBAR). Run it only with a testnet account you control:
    CP_LIVE_HEDERA=1 CP_HEDERA_OPERATOR_ID=... CP_HEDERA_OPERATOR_KEY=... CP_HCS_TOPIC_ID=... CP_HTS_TOKEN_ID=... pytest tests/test_hedera_live.py
Create the topic and token once with `python scripts/hedera_setup.py`.
"""
from __future__ import annotations

import os
import time
import uuid

import pytest

REQUIRED = ("CP_HEDERA_OPERATOR_ID", "CP_HEDERA_OPERATOR_KEY", "CP_HCS_TOPIC_ID", "CP_HTS_TOKEN_ID")
pytestmark = pytest.mark.skipif(
    os.environ.get("CP_LIVE_HEDERA") != "1" or not all(os.environ.get(k) for k in REQUIRED),
    reason="live Hedera testnet test: set CP_LIVE_HEDERA=1 and the CP_HEDERA_* / CP_HCS_* / CP_HTS_* variables",
)


def test_anchor_mint_and_burn_roundtrip_on_testnet():
    from climaudit.config import load_settings
    from climaudit.ledger.adapters import build_ledger
    from climaudit.ledger.port import SYNTHETIC_MARKER

    ledger = build_ledger(load_settings(), lambda: "t")
    assert ledger.mode == "direct"
    digest = uuid.uuid4().hex + uuid.uuid4().hex
    ref = ledger.anchor(digest, {"type": "correction", "batch_id": "live-test", "seq": 0})
    assert ref.sequence >= 1 and ref.tx_id
    for _ in range(10):  # the mirror node lags consensus by a few seconds
        if digest in ledger.published_hashes():
            break
        time.sleep(3)
    assert digest in ledger.published_hashes()
    op = uuid.uuid4().hex + uuid.uuid4().hex
    minted = ledger.mint(op, "live-test", 1, f"live {SYNTHETIC_MARKER}")
    assert minted.units == 1 and minted.tx_id
    burn = ledger.retire(uuid.uuid4().hex + uuid.uuid4().hex, minted.token_id, "treasury", 1, "live-test", "research")
    assert burn
