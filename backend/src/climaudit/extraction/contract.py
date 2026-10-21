"""AI extraction contract (BACKEND-SPEC.md section 12).

The agent proposes evidence items from SANITIZED document text. This module is the deterministic checker, used both by
the client side and by the server (service.add_evidence): an item is accepted only if its quote appears verbatim in the
document text, is long enough to mean something, contains the value as a whole token, mentions a label that belongs to
the kind, and the kind is one the agent may extract. Accepted items are stored as `pending_confirmation` and never feed
a calculation until a human confirms them. The agent has no write access beyond proposing evidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from ..errors import ApiError

_WS = re.compile(r"\s+")
MIN_QUOTE_CHARS = 12

# Kinds an extraction agent may propose, each with labels of which at least one must appear in the quote.
KIND_KEYWORDS: dict[str, tuple[str, ...]] = {
    "h_corg_molar": ("h/corg", "h:corg", "h/c", "h:c", "hydrogen"),
    "organic_carbon_fraction": ("organic carbon", "corg", "total carbon", "carbon content", "carbon"),
    "dry_mass_biochar": ("dry", "mass", "weight", "tonnes", "tons"),
    "wet_mass_biochar": ("wet", "as received", "mass", "weight"),
    "moisture_pct": ("moisture", "water content"),
    "pyrolysis_temp_c": ("temperature", "pyrolysis", "°c", " c "),
    "production_date": ("produced", "production", "pyrolysed", "pyrolyzed"),
    "application_date": ("applied", "application", "incorporated", "spread"),
    "additive_pct": ("additive", "lime", "mineral", "ash"),
    "carbon_pct_dry": ("carbon",),
}


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _token_in(value: str, quote: str) -> bool:
    """The value must appear as a whole token (not as part of a longer number)."""
    return re.search(r"(?<![\w.])" + re.escape(value) + r"(?![\w]|\.\d)", quote) is not None


def quote_supports_value(document_text: str, kind: str, value: str, quote: str) -> str | None:
    """Return None if the quote supports the proposed item, otherwise the rejection reason."""
    if kind not in KIND_KEYWORDS:
        return "kind_not_allowed"
    q = _norm(quote)
    if len(q) < MIN_QUOTE_CHARS:
        return "quote_too_short"
    if q not in _norm(document_text):
        return "quote_not_in_document"
    if not _token_in(_norm(value), q):
        return "value_not_a_token_in_quote"
    lowered = " " + q.lower() + " "
    if not any(label in lowered for label in KIND_KEYWORDS[kind]):
        return "quote_lacks_label_for_kind"
    return None


@dataclass(frozen=True)
class Proposal:
    kind: str
    value: str
    unit: str
    document_ref: str
    page: int | None
    quote: str
    group: str | None = None


@dataclass(frozen=True)
class Rejection:
    proposal: Proposal
    reason: str


def check_proposals(document_text: str, proposals: list[Proposal]) -> tuple[list[Proposal], list[Rejection]]:
    """Return (accepted, rejected). Matching ignores whitespace differences only."""
    accepted: list[Proposal] = []
    rejected: list[Rejection] = []
    for p in proposals:
        reason = quote_supports_value(document_text, p.kind, p.value, p.quote)
        if reason:
            rejected.append(Rejection(p, reason))
        else:
            accepted.append(p)
    return accepted, rejected


def to_evidence_payload(accepted: list[Proposal]) -> list[dict[str, Any]]:
    """Body for POST /batches/{id}/evidence as the restricted `extractor` user."""
    return [
        {
            "kind": p.kind,
            "value": p.value,
            "unit": p.unit,
            "group": p.group,
            "document_ref": p.document_ref,
            "provenance": "synthetic",
            "span": {"page": p.page, "quote": p.quote},
        }
        for p in accepted
    ]


class Extractor(Protocol):
    def propose(self, document_ref: str, document_text: str) -> list[Proposal]:
        """Return candidate evidence items for one sanitized document."""


class StaticExtractor:
    """Deterministic extractor for tests: returns the proposals it was constructed with."""

    def __init__(self, proposals: list[Proposal]):
        self._proposals = proposals

    def propose(self, document_ref: str, document_text: str) -> list[Proposal]:
        return list(self._proposals)


def run_extraction(extractor: Extractor, document_ref: str, document_text: str) -> tuple[list[Proposal], list[Rejection]]:
    if not document_text.strip():
        raise ApiError("VALIDATION_FAILED", {"field": "document", "rule": "empty_visible_text"})
    return check_proposals(document_text, extractor.propose(document_ref, document_text))
