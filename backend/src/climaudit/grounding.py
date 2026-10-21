"""Report figure grounding (skill grounded-report-check): every number in the narrative must be in the evidence.

The check is language-neutral for digits: it extracts number tokens and compares them with the set of figures
the calculation produced. A narrative with an unknown number, a link, markup, a code fence or an
instruction-like phrase is withheld.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from .checks.sanitizer import find_instructions

_NUMBER = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")
_LINK = re.compile(r"https?://|www\.|\]\(|<[a-zA-Z/!?]")
_FENCE = re.compile(r"```")


@dataclass
class GroundingResult:
    passed: bool
    discrepancies: list[str] = field(default_factory=list)
    numbers_checked: int = 0


def extract_numbers(text: str) -> list[str]:
    return [m.group(0).replace(",", "") for m in _NUMBER.finditer(text)]


def _canon(token: str) -> str:
    try:
        d = Decimal(token)
    except InvalidOperation:
        return token
    text = format(d, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


_UNIT_TOKENS = re.compile(r"(?<![A-Za-z0-9])CO2e?(?![A-Za-z0-9])")  # chemical notation, not a figure


def check(narrative: str, allowed: set[str]) -> GroundingResult:
    allowed_canon = {_canon(a) for a in allowed}
    result = GroundingResult(passed=True)
    for token in extract_numbers(_UNIT_TOKENS.sub("CO_", narrative)):
        result.numbers_checked += 1
        if _canon(token) not in allowed_canon:
            result.passed = False
            result.discrepancies.append(f"number_not_in_evidence:{token}")
    if _LINK.search(narrative):
        result.passed = False
        result.discrepancies.append("contains_link_or_markup")
    if _FENCE.search(narrative):
        result.passed = False
        result.discrepancies.append("contains_code_fence")
    if find_instructions(narrative):
        result.passed = False
        result.discrepancies.append("contains_instruction_like_text")
    return result
