"""Minimal dependency-free PDF writer used to build synthetic dossier documents (tests and fixtures).

It writes plain text lines with an explicit fill color, font size and rendering mode per run, which is exactly
what the sanitizer inspects. It is not a general PDF library.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Run:
    text: str
    size: int = 12
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)  # RGB fill, 0..1
    render_mode: int = 0  # 3 = invisible


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _page_stream(runs: list[Run]) -> bytes:
    lines: list[str] = []
    y = 780
    for run in runs:
        r, g, b = run.color
        lines.append(f"q {r:g} {g:g} {b:g} rg BT /F1 {run.size} Tf {run.render_mode} Tr 40 {y} Td ({_escape(run.text)}) Tj ET Q")
        y -= max(run.size + 6, 8)
    return "\n".join(lines).encode("latin-1")


def make_pdf(pages: list[list[Run]]) -> bytes:
    """Return the bytes of a valid PDF with one page per list of runs."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog_id = add(b"")  # placeholder, filled below
    pages_id = add(b"")
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []
    for runs in pages:
        stream = _page_stream(runs)
        content_id = add(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        page_id = add(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )
        page_ids.append(page_id)
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode()
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


def make_pdf_from_streams(page_streams: list[str], forms: dict[str, str] | None = None, alpha_zero_state: bool = False) -> bytes:
    """Build a PDF whose page content is given as raw content-stream text (for sanitizer technique tests).

    `forms` maps an XObject name to the content of a Form XObject the page can draw with `/Name Do`.
    `alpha_zero_state` defines an ExtGState named /GS0 with /ca 0 and /CA 0.
    """
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog_id = add(b"")
    pages_id = add(b"")
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    form_ids: dict[str, int] = {}
    for name, content in (forms or {}).items():
        raw = content.encode("latin-1")
        form_ids[name] = add(
            b"<< /Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /Font << /F1 "
            + f"{font_id} 0 R".encode()
            + b" >> >> /Length "
            + str(len(raw)).encode()
            + b" >>\nstream\n"
            + raw
            + b"\nendstream"
        )
    gs_id = add(b"<< /Type /ExtGState /ca 0 /CA 0 >>") if alpha_zero_state else None
    page_ids: list[int] = []
    for content in page_streams:
        raw = content.encode("latin-1")
        content_id = add(b"<< /Length " + str(len(raw)).encode() + b" >>\nstream\n" + raw + b"\nendstream")
        xobjects = "".join(f"/{name} {oid} 0 R " for name, oid in form_ids.items())
        resources = f"<< /Font << /F1 {font_id} 0 R >> /XObject << {xobjects}>> " + (f"/ExtGState << /GS0 {gs_id} 0 R >> " if gs_id else "") + ">>"
        page_ids.append(add(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] /Resources {resources} /Contents {content_id} 0 R >>".encode()))
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode()
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in page_ids)}] /Count {len(page_ids)} >>".encode()
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)
