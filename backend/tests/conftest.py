"""Shared test fixtures: in-memory app with role keys, a deterministic clock and a fake ledger."""
from __future__ import annotations

import base64
import itertools
import uuid

import pytest
from fastapi.testclient import TestClient

from climaudit.api.app import create_app
from climaudit.config import ApiKey, Settings
from climaudit.ledger.fake import FakeLedger
from climaudit.store import Store

KEYS = {
    "k-owner": ApiKey("owner-1", "owner"),
    "k-owner2": ApiKey("owner-2", "owner"),
    "k-verifier": ApiKey("verifier-1", "verifier"),
    "k-registry": ApiKey("registry-1", "registry"),
    "k-holder": ApiKey("buyer-1", "holder"),
    "k-admin": ApiKey("admin-1", "admin"),
    "k-system": ApiKey("system-1", "system"),
    "k-extractor": ApiKey("extractor-1", "extractor"),
}


class Client:
    """Thin wrapper that adds the bearer key and a fresh idempotency key unless one is given."""

    def __init__(self, http: TestClient):
        self.http = http
        self.app = None

    def call(self, method: str, path: str, role: str | None, json=None, key: str | None = None, headers=None):
        hdrs = dict(headers or {})
        if role:
            hdrs["Authorization"] = f"Bearer k-{role}"
        if method in ("POST", "PUT") and key != "":
            hdrs["Idempotency-Key"] = key or uuid.uuid4().hex
        return self.http.request(method, path, json=json, headers=hdrs)

    def ok(self, method: str, path: str, role: str, json=None, status: int | None = None):
        r = self.call(method, path, role, json)
        assert r.status_code < 300, (method, path, r.status_code, r.text)
        if status is not None:
            assert r.status_code == status
        return r.json()


@pytest.fixture()
def env():
    counter = itertools.count()

    def clock() -> str:
        n = next(counter)
        return f"2026-10-16T{n // 3600 % 24:02d}:{n // 60 % 60:02d}:{n % 60:02d}Z"

    settings = Settings(api_keys=dict(KEYS))
    ledger = FakeLedger(clock)
    store = Store(":memory:")
    app = create_app(settings, ledger=ledger, store=store, clock=clock)
    client = Client(TestClient(app, raise_server_exceptions=False))
    client.app = app
    yield client, app.state.service, ledger, store
    store.close()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")
