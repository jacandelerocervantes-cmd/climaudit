"""API error envelope (SCHEMA.md section 4). The server never sends user-facing sentences."""
from __future__ import annotations

from typing import Any

HTTP_STATUS = {
    "VALIDATION_FAILED": 422,
    "UNIT_INVALID": 422,
    "DATE_AMBIGUOUS": 422,
    "PERIOD_INVALID": 422,
    "FILE_UNSUPPORTED": 415,
    "FILE_CORRUPT": 422,
    "BATCH_NOT_FOUND": 404,
    "NOT_FOUND": 404,
    "BATCH_PERIOD_OVERLAP": 409,
    "STATE_TRANSITION_NOT_ALLOWED": 409,
    "IDEMPOTENCY_CONFLICT": 409,
    "IDEMPOTENCY_KEY_REQUIRED": 400,
    "ROLE_NOT_AUTHORIZED": 403,
    "AUTH_REQUIRED": 401,
    "FACTOR_SOURCE_MISSING": 422,
    "CALC_FAILED": 500,
    "REPORT_WITHHELD_UNGROUNDED": 422,
    "LLM_UNAVAILABLE": 503,
    "LEDGER_UNAVAILABLE": 503,
    "LEDGER_REJECTED": 502,
    "GUARDIAN_POLICY_REJECTED": 409,
    "INSUFFICIENT_BALANCE": 409,
    "RATE_LIMITED": 429,
    "INTERNAL_ERROR": 500,
}


class ApiError(Exception):
    def __init__(self, code: str, params: dict[str, Any] | None = None, status: int | None = None):
        super().__init__(code)
        self.code = code
        self.params = params or {}
        self.status = status or HTTP_STATUS.get(code, 400)

    def envelope(self, correlation_id: str) -> dict[str, Any]:
        return {"error": {"code": self.code, "params": self.params, "correlation_id": correlation_id}}
