"""Build the local registry index from the Berkeley Voluntary Registry Offsets Database (CC BY 4.0).

Usage (from the backend folder, with the `registry` extra: pip install -e ".[registry]"):
    python scripts/build_registry_index.py <Voluntary-Registry-Offsets-Database--vYYYY-MM.xlsx> data/registry_index.json

Download the workbook yourself from https://gspp.berkeley.edu/berkeley-carbon-trading-project/offsets-database and
keep it outside the repository. The index keeps only the PROJECTS sheet columns ClimAudit uses (id, name, registry,
status, type, methodology, country, developer, totals and credits issued per vintage year) plus the attribution
metadata. Then set CP_REGISTRY_INDEX_PATH to the output file and CP_EXTERNAL_CHECKS=1.

Citation required by the licence: Quartson, Haya, Bernard, Abayo, Rong, So and Elias, Voluntary Registry Offsets
Database, Berkeley Carbon Trading Project, University of California, Berkeley.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HEADER_ROW = 4
FIRST_VINTAGE_COL = 23  # column X ("1996"); the header cells from here on are years
MAX_COLS = 80


def to_int(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def text(value) -> str:
    return "" if value is None or str(value).strip() in ("None", "Not provided") else str(value).strip()


def build(xlsx: Path, out: Path) -> int:
    try:
        import openpyxl  # noqa: PLC0415 (optional dependency)
    except ImportError:
        print('Install the extra first:  pip install -e ".[registry]"', file=sys.stderr)
        return 2
    workbook = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    sheet = workbook["PROJECTS"]
    rows = sheet.iter_rows(min_row=HEADER_ROW, max_col=MAX_COLS, values_only=True)
    header = [("" if c is None else str(c).replace("\n", " ").strip()) for c in next(rows)]
    years = {i: int(h) for i, h in enumerate(header) if i >= FIRST_VINTAGE_COL and re.fullmatch(r"(19|20)\d\d", h)}
    projects = []
    for row in rows:
        if not row[0]:
            continue
        projects.append({
            "project_id": text(row[0]), "name": text(row[1]), "registry": text(row[2]), "status": text(row[4]), "type": text(row[6]),
            "methodology": text(row[8]), "country": text(row[11]), "developer": text(row[14]),
            "issued": to_int(row[15]), "retired": to_int(row[16]),
            "issued_by_vintage": {str(y): to_int(row[i]) for i, y in years.items() if to_int(row[i]) > 0},
        })
    version = re.search(r"v(\d{4}-\d{2})", xlsx.name)
    meta = {
        "name": "Voluntary Registry Offsets Database", "version": version.group(1) if version else "unknown",
        "license": "CC BY 4.0", "source": "https://gspp.berkeley.edu/berkeley-carbon-trading-project/offsets-database",
        "citation": "Quartson, Haya, Bernard, Abayo, Rong, So and Elias, Voluntary Registry Offsets Database, Berkeley Carbon Trading Project, UC Berkeley",
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "projects": len(projects),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": meta, "projects": projects}, separators=(",", ":")), encoding="utf-8", newline="\n")
    print(f"wrote {len(projects)} projects to {out}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    raise SystemExit(build(args.xlsx, args.out))
