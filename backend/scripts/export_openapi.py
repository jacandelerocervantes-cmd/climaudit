"""Write the OpenAPI document of the API to a file, for generating the frontend types.

Usage (from the backend folder, with the .venv active):
    python scripts/export_openapi.py [output.json]      # default: ../web/openapi/climaudit.openapi.json

The live /openapi.json route is off unless CP_ENV=dev, so the document is built from the application object with an
in-memory store and the in-memory ledger; nothing is read from the environment and no network is used.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from climaudit.api.app import create_app
from climaudit.config import Settings
from climaudit.ledger.fake import FakeLedger
from climaudit.store import Store


def main() -> int:
    default = Path(__file__).resolve().parents[2] / "web" / "openapi" / "climaudit.openapi.json"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    store = Store(":memory:")
    app = create_app(Settings(), ledger=FakeLedger(lambda: "1970-01-01T00:00:00Z"), store=store)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    store.close()
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
