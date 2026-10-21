"""SQLite persistence (system of record, BACKEND-SPEC.md section 1). Schema is Postgres-compatible in spirit:
plain tables with JSON text columns. One connection guarded by a lock; every write happens inside `transaction()`.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (project_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS facilities (facility_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS facility_year_evidence (item_id TEXT PRIMARY KEY, facility_id TEXT NOT NULL, year INTEGER NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS batches (
  batch_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, facility_id TEXT NOT NULL, state TEXT NOT NULL,
  dedup_key TEXT, period_start TEXT NOT NULL, period_end TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence (item_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (
  document_ref TEXT PRIMARY KEY, batch_id TEXT NOT NULL, sha256 TEXT NOT NULL, filename TEXT NOT NULL,
  media_type TEXT NOT NULL, size INTEGER NOT NULL, content BLOB NOT NULL, findings TEXT NOT NULL, visible_text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reports (report_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, created_at TEXT NOT NULL, evidence_hash TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events (seq INTEGER PRIMARY KEY, batch_id TEXT NOT NULL, hash TEXT NOT NULL, data TEXT NOT NULL, ledger_ref TEXT);
CREATE TABLE IF NOT EXISTS idempotency (
  actor_id TEXT NOT NULL, method TEXT NOT NULL, path TEXT NOT NULL, key TEXT NOT NULL,
  request_hash TEXT NOT NULL, status INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY (actor_id, method, path, key));
CREATE TABLE IF NOT EXISTS credits (credit_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL UNIQUE, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS balances (credit_id TEXT NOT NULL, holder TEXT NOT NULL, units INTEGER NOT NULL CHECK (units >= 0), PRIMARY KEY (credit_id, holder));
CREATE TABLE IF NOT EXISTS retirements (retirement_id TEXT PRIMARY KEY, credit_id TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger_ops (op_key TEXT PRIMARY KEY, batch_id TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS finding_overrides (batch_id TEXT NOT NULL, code TEXT NOT NULL, report_id TEXT NOT NULL, actor_id TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (batch_id, code));
"""


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            parent = Path(path).parent
            parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._depth = 0
        with self._lock:
            self._conn.executescript(SCHEMA)

    def lock(self):
        """Hold the process-wide lock across several transactions (used for multi-step ledger operations)."""
        return self._lock

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            outer = self._depth == 0
            if outer:
                self._conn.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield self._conn
            except BaseException:
                self._depth -= 1
                if outer:
                    self._conn.execute("ROLLBACK")
                raise
            else:
                self._depth -= 1
                if outer:
                    self._conn.execute("COMMIT")

    def checkpoint(self) -> None:
        """Commit what the open (outer) transaction has written so far and keep working in a fresh one.

        Used where a fact must survive a later failure of the same request, such as the intent to mint and the
        recorded mint result: if the request rolls back afterwards, these rows stay. No-op outside a transaction.
        """
        with self._lock:
            if self._depth == 0:
                return
            self._conn.execute("COMMIT")
            self._conn.execute("BEGIN IMMEDIATE")

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params))

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.transaction() as conn:
            conn.execute(sql, params)

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def loads(text: str) -> Any:
    return json.loads(text)
