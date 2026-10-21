"""Pre-ingestion document sanitizer (ARCHITECTURE.md 6.4).

Removes text a human reader cannot see before any model sees the document, and flags instruction-like text.

PDF text is hidden when, at the moment it is shown, any of these holds: near-white fill (gray/RGB >= 0.95, CMYK <= 0.05),
rendering mode 3 or 7, effective font size below 2 pt (font size x text matrix x CTM), zero horizontal scale,
transparent graphics state (/ca or /CA = 0), position outside the page, or a later white filled rectangle painted over
it. Form XObjects are traversed. Declared limits: text hidden behind images, clipping paths, non-white page
backgrounds, fonts whose text mapping hides the real characters, and optional-content layers are not detected. The
sanitizer reduces risk; it does not eliminate it.
"""
from __future__ import annotations

import hashlib
import io
import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from pypdf import PdfReader
from pypdf.generic import ContentStream, DictionaryObject

from ..errors import ApiError
from ..findings import Finding, make

MIN_VISIBLE_FONT_SIZE = 2.0
WHITE_LEVEL = 0.95
MAX_PAGES = 200
MAX_OPERATIONS = 300_000
MAX_FORM_DEPTH = 4
PAGE_MARGIN = 50.0
INVISIBLE_BENIGN_LIMIT = 16  # many ZWJ/ZWNJ/soft hyphens in one document is treated as a hiding technique

_BENIGN_INVISIBLE = {"﻿", "‌", "‍", "­", "\r"}
_HOMOGLYPHS = str.maketrans(
    {
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
        "і": "i", "ѕ": "s", "ј": "j", "һ": "h", "ԁ": "d", "ԛ": "q", "ο": "o",
        "α": "a", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ρ": "p", "υ": "u",
    }
)

_INSTRUCTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+|any\s+|every\w*\s+)?(the\s+)?(previous|prior|above|earlier|preceding)"),
    re.compile(r"ignore\s+everything\s+(above|before)"),
    re.compile(r"disregard\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier|rules|instructions)"),
    re.compile(r"system\s+(override|prompt|instruction)"),
    re.compile(r"you\s+are\s+now\b"),
    re.compile(r"\b(approve|certify)\s+(this|the)\s+(batch|credit|report|project)"),
    re.compile(r"\bmark\s+(this|the)\s+(batch|credit|report)\s+as\s+(verified|approved|valid)"),
    re.compile(r"\breport\s+h\s*[:/]?\s*c\s*[_-]?\s*(org)?\s+as\b"),
    re.compile(r"\bdo\s+not\s+(mention|flag)\s+(the\s+|this\s+|these\s+|any\s+)?(finding|issue|problem|error|moisture|value|h\s*[:/]\s*c)"),
    re.compile(r"\b(set|change)\s+the\s+(result|value|score)\s+to\b"),
]


@dataclass(frozen=True)
class HiddenSegment:
    page: int
    reason: str
    text: str


@dataclass
class SanitizedDocument:
    sha256: str
    pages: int
    visible_text: str
    hidden: list[HiddenSegment] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ text-level helpers
def fold(text: str) -> str:
    """Lowercase, NFKC-normalize, drop zero-width characters and fold common Cyrillic/Greek look-alikes."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return text.lower().translate(_HOMOGLYPHS)


def find_instructions(text: str) -> list[str]:
    folded = fold(text)
    found: list[str] = []
    for pattern in _INSTRUCTION_PATTERNS:
        for match in pattern.finditer(folded):
            start = max(match.start() - 20, 0)
            found.append(folded[start : match.end() + 40].replace("\n", " ").strip())
    return found


def _clean_invisible(text: str) -> tuple[str, int, int]:
    """Return (clean text, flagged invisible characters removed, benign invisible characters removed)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    flagged = benign = 0
    for ch in text:
        if ch in _BENIGN_INVISIBLE:
            benign += 1
            continue
        category = unicodedata.category(ch)
        if category in ("Cf", "Cs", "Co", "Cn") or (category == "Cc" and ch not in ("\n", "\t")):
            flagged += 1
            continue
        out.append(ch)
    return "".join(out), flagged, benign


def _invisible_segments(page: int, flagged: int, benign: int) -> list[HiddenSegment]:
    if flagged:
        return [HiddenSegment(page, "invisible_characters", f"{flagged} characters removed")]
    if benign > INVISIBLE_BENIGN_LIMIT:
        return [HiddenSegment(page, "invisible_characters", f"{benign} joiner/zero-width characters removed")]
    return []


def sanitize_text(text: str, raw: bytes | None = None) -> SanitizedDocument:
    cleaned, flagged, benign = _clean_invisible(text)
    doc = SanitizedDocument(
        sha256=hashlib.sha256(raw if raw is not None else text.encode("utf-8")).hexdigest(),
        pages=1,
        visible_text=cleaned,
        hidden=_invisible_segments(1, flagged, benign),
    )
    doc.instructions = find_instructions(cleaned)
    return doc


# ---------------------------------------------------------------------- PDF interpreter
Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _mul(m: Matrix, n: Matrix) -> Matrix:
    """Return m x n (apply m first, then n), PDF row-vector convention."""
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + b * c2, a * b2 + b * d2, c * a2 + d * c2, c * b2 + d * d2, e * a2 + f * c2 + e2, e * b2 + f * d2 + f2)


def _scale(m: Matrix) -> float:
    return math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))


def _is_white(operator: bytes, values: list[float]) -> bool | None:
    if operator == b"g" and len(values) == 1:
        return values[0] >= WHITE_LEVEL
    if operator == b"rg" and len(values) == 3:
        return all(v >= WHITE_LEVEL for v in values)
    if operator == b"k" and len(values) == 4:
        return all(v <= 1 - WHITE_LEVEL for v in values)
    if operator in (b"sc", b"scn"):
        if len(values) == 1:
            return values[0] >= WHITE_LEVEL
        if len(values) == 3:
            return all(v >= WHITE_LEVEL for v in values)
        if len(values) == 4:
            return all(v <= 1 - WHITE_LEVEL for v in values)
    return None


def _floats(operands: list[Any]) -> list[float]:
    out: list[float] = []
    for o in operands:
        try:
            out.append(float(o))
        except (TypeError, ValueError):
            continue
    return out


def _shown_text(operator: bytes, operands: list[Any]) -> str:
    def to_str(obj: Any) -> str:
        return obj.decode("latin-1") if isinstance(obj, bytes) else str(obj)

    if operator == b"Tj" and operands:
        return to_str(operands[0])
    if operator == b"TJ" and operands:
        return "".join(to_str(o) for o in operands[0] if not isinstance(o, (int, float)) and not hasattr(o, "__float__"))
    if operator in (b"'", b'"') and operands:
        return to_str(operands[-1])
    return ""


@dataclass
class _GState:
    ctm: Matrix = IDENTITY
    white: bool = False
    size: float = 12.0
    render_mode: int = 0
    h_scale: float = 100.0
    alpha_zero: bool = False


class _PageScan:
    def __init__(self, reader: PdfReader, page_no: int, width: float, height: float):
        self.reader = reader
        self.page_no = page_no
        self.width, self.height = width, height
        self.ops = 0
        self.texts: list[dict[str, Any]] = []  # {text, reason, x, y, order}
        self.white_rects: list[tuple[float, float, float, float, int]] = []
        self.order = 0

    def run(self, stream: ContentStream, resources: Any, state: _GState, depth: int) -> None:
        gs = state
        stack: list[_GState] = []
        tm: Matrix = IDENTITY
        tlm: Matrix = IDENTITY
        leading = 0.0
        pending_rect: tuple[float, float, float, float] | None = None
        res = resources.get_object() if resources is not None and hasattr(resources, "get_object") else resources
        for operands, operator in stream.operations:
            self.ops += 1
            if self.ops > MAX_OPERATIONS:
                raise ApiError("FILE_CORRUPT", {"reason": "too_many_operations"})
            values = _floats(operands)
            if operator == b"q":
                stack.append(_GState(gs.ctm, gs.white, gs.size, gs.render_mode, gs.h_scale, gs.alpha_zero))
            elif operator == b"Q":
                if stack:
                    gs = stack.pop()
            elif operator == b"cm" and len(values) == 6:
                gs.ctm = _mul(tuple(values), gs.ctm)  # type: ignore[arg-type]
            elif operator == b"BT":
                tm = tlm = IDENTITY
            elif operator == b"Tf" and len(operands) == 2:
                gs.size = abs(float(operands[1]))
            elif operator == b"Tr" and values:
                gs.render_mode = int(values[0])
            elif operator == b"Tz" and values:
                gs.h_scale = values[0]
            elif operator == b"TL" and values:
                leading = values[0]
            elif operator in (b"Td", b"TD") and len(values) == 2:
                if operator == b"TD":
                    leading = -values[1]
                tlm = _mul((1.0, 0.0, 0.0, 1.0, values[0], values[1]), tlm)
                tm = tlm
            elif operator == b"T*":
                tlm = _mul((1.0, 0.0, 0.0, 1.0, 0.0, -leading), tlm)
                tm = tlm
            elif operator == b"Tm" and len(values) == 6:
                tm = tlm = tuple(values)  # type: ignore[assignment]
            elif operator == b"gs" and operands and res is not None:
                states = res.get("/ExtGState") if hasattr(res, "get") else None
                entry = states.get_object().get(str(operands[0])) if states is not None else None
                if entry is not None:
                    entry = entry.get_object()
                    gs.alpha_zero = any(k in entry and float(entry[k]) == 0.0 for k in ("/ca", "/CA"))
            elif operator in (b"g", b"rg", b"k", b"sc", b"scn"):
                white = _is_white(operator, values)
                if white is not None:
                    gs.white = white
            elif operator == b"re" and len(values) == 4:
                pending_rect = (values[0], values[1], values[2], values[3])
            elif operator in (b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"):
                if pending_rect is not None and gs.white:
                    x, y, w, h = pending_rect
                    corners = [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
                    pts = [(a * gs.ctm[0] + b * gs.ctm[2] + gs.ctm[4], a * gs.ctm[1] + b * gs.ctm[3] + gs.ctm[5]) for a, b in corners]
                    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                    self.order += 1  # later than every text shown so far
                    self.white_rects.append((min(xs), min(ys), max(xs), max(ys), self.order))
                pending_rect = None
            elif operator == b"n":
                pending_rect = None
            elif operator == b"Do" and operands and depth < MAX_FORM_DEPTH and res is not None:
                self._form(res, str(operands[0]), gs, depth)
            else:
                text = _shown_text(operator, operands)
                if text:
                    if operator in (b"'", b'"'):
                        tlm = _mul((1.0, 0.0, 0.0, 1.0, 0.0, -leading), tlm)
                        tm = tlm
                    self._record(text, gs, tm)
                    tm = _mul((1.0, 0.0, 0.0, 1.0, max(len(text), 1) * gs.size * 0.5, 0.0), tm)

    def _form(self, res: Any, name: str, gs: _GState, depth: int) -> None:
        xobjects = res.get("/XObject") if hasattr(res, "get") else None
        if xobjects is None:
            return
        xobj = xobjects.get_object().get(name)
        if xobj is None:
            return
        xobj = xobj.get_object()
        if xobj.get("/Subtype") != "/Form":
            return
        matrix = tuple(float(v) for v in xobj.get("/Matrix", [1, 0, 0, 1, 0, 0]))
        inner = _GState(_mul(matrix, gs.ctm), gs.white, gs.size, gs.render_mode, gs.h_scale, gs.alpha_zero)  # type: ignore[arg-type]
        self.run(ContentStream(xobj, self.reader), xobj.get("/Resources", res), inner, depth + 1)

    def _record(self, text: str, gs: _GState, tm: Matrix) -> None:
        self.order += 1
        full = _mul(tm, gs.ctm)
        effective = gs.size * _scale(full)
        x, y = full[4], full[5]
        reason = None
        if gs.render_mode in (3, 7):
            reason = "invisible_render_mode"
        elif gs.alpha_zero:
            reason = "transparent_text"
        elif gs.h_scale == 0:
            reason = "zero_horizontal_scale"
        elif gs.white:
            reason = "white_text"
        elif effective < MIN_VISIBLE_FONT_SIZE:
            reason = "tiny_font"
        elif x < -PAGE_MARGIN or y < -PAGE_MARGIN or x > self.width + PAGE_MARGIN or y > self.height + PAGE_MARGIN:
            reason = "off_page"
        self.texts.append({"text": text, "reason": reason, "x": x, "y": y, "order": self.order})

    def results(self) -> tuple[list[str], list[HiddenSegment]]:
        visible: list[str] = []
        hidden: list[HiddenSegment] = []
        for item in self.texts:
            reason = item["reason"]
            if reason is None:
                for (x0, y0, x1, y1, order) in self.white_rects:
                    if order > item["order"] and x0 <= item["x"] <= x1 and y0 <= item["y"] <= y1:
                        reason = "covered_by_white_rectangle"
                        break
            if reason:
                hidden.append(HiddenSegment(self.page_no, reason, item["text"]))
            else:
                visible.append(item["text"])
        return visible, hidden


def sanitize_pdf(data: bytes, max_bytes: int | None = None) -> SanitizedDocument:
    if max_bytes is not None and len(data) > max_bytes:
        raise ApiError("FILE_CORRUPT", {"reason": "file_too_large", "max_bytes": max_bytes})
    try:
        return _sanitize_pdf(data)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001 - any parser failure on untrusted input is a corrupt file
        raise ApiError("FILE_CORRUPT", {"reason": "pdf_unreadable", "error": type(exc).__name__}) from exc


def _sanitize_pdf(data: bytes) -> SanitizedDocument:
    reader = PdfReader(io.BytesIO(data))
    page_count = len(reader.pages)
    if page_count > MAX_PAGES:
        raise ApiError("FILE_CORRUPT", {"reason": "too_many_pages", "max_pages": MAX_PAGES})
    doc = SanitizedDocument(sha256=hashlib.sha256(data).hexdigest(), pages=page_count, visible_text="")
    pages_text: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        contents = page.get_contents()
        box = page.mediabox
        scan = _PageScan(reader, index, float(box.width), float(box.height))
        if contents is not None:
            resources = page.get("/Resources")
            scan.run(ContentStream(contents, reader), resources, _GState(), 0)
        visible, hidden = scan.results()
        doc.hidden.extend(hidden)
        cleaned, flagged, benign = _clean_invisible("\n".join(visible))
        doc.hidden.extend(_invisible_segments(index, flagged, benign))
        pages_text.append(cleaned)
    doc.visible_text = "\n\n".join(pages_text)
    doc.instructions = find_instructions(doc.visible_text) + [s for h in doc.hidden for s in find_instructions(h.text)]
    return doc


def findings_for(doc: SanitizedDocument, document_ref: str) -> list[Finding]:
    findings: list[Finding] = []
    if doc.hidden:
        findings.append(
            make(
                "HIDDEN_TEXT_IN_DOCUMENT",
                document_ref=document_ref,
                segments=len(doc.hidden),
                reasons=sorted({h.reason for h in doc.hidden}),
                pages=sorted({h.page for h in doc.hidden}),
            )
        )
    if doc.instructions:
        findings.append(make("INSTRUCTION_IN_DOCUMENT", document_ref=document_ref, matches=len(doc.instructions)))
    return findings
