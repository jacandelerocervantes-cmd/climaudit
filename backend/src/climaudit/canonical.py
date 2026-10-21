"""Canonical JSON and SHA-256 hashing (BACKEND-SPEC.md section 11).

Subset of RFC 8785 used by the prototype: keys sorted by UTF-16 code units, no whitespace, UTF-8,
strings in NFC, integers only (fractions travel as decimal strings), no nulls, no floats.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

GENESIS_HASH = "0" * 64
MAX_SAFE_INT = 2**53 - 1  # RFC 8785 number serialization is exact only up to this magnitude


class CanonicalError(ValueError):
    pass


def _normalize(value: Any, path: str = "$") -> Any:
    if value is None:
        raise CanonicalError(f"null is not allowed at {path}; omit the key instead")
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise CanonicalError(f"float is not allowed at {path}; use an integer or a decimal string")
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INT:
            raise CanonicalError(f"integer beyond +-(2^53-1) at {path}; send it as a decimal string")
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, (list, tuple)):
        return [_normalize(v, f"{path}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise CanonicalError(f"non-string key at {path}")
            out[unicodedata.normalize("NFC", k)] = _normalize(v, f"{path}.{k}")
        return out
    raise CanonicalError(f"unsupported type {type(value).__name__} at {path}")


def _sort_keys(value: Any) -> Any:
    if isinstance(value, dict):
        ordered = sorted(value.items(), key=lambda kv: kv[0].encode("utf-16-be"))
        return {k: _sort_keys(v) for k, v in ordered}
    if isinstance(value, list):
        return [_sort_keys(v) for v in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    normalized = _sort_keys(_normalize(value))
    try:
        return json.dumps(normalized, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError as exc:  # lone surrogates cannot be written as UTF-8
        raise CanonicalError("string contains a lone surrogate") from exc


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_hex(canonical_bytes(value))
