"""Read-only probe of a running Guardian: logs in and prints what the API exposes, never any credential or token.

Usage (from the backend folder, with the .venv active):
    python scripts/guardian_probe.py                 # list policies and their status
    python scripts/guardian_probe.py <policy_id>     # also show the policy's blocks and roles

Credentials come from CP_GUARDIAN_URL, CP_GUARDIAN_USERNAME and CP_GUARDIAN_PASSWORD, read from the environment or
from backend/.env (only those three names are read from the file). Nothing is written anywhere.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from climaudit.ledger.guardian import GuardianConfig, GuardianAdapter

WANTED = ("CP_GUARDIAN_URL", "CP_GUARDIAN_USERNAME", "CP_GUARDIAN_PASSWORD")


def load_env() -> dict[str, str]:
    values = {k: os.environ[k] for k in WANTED if os.environ.get(k)}
    path = Path(__file__).resolve().parent.parent / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            name = name.strip()
            if name in WANTED and name not in values and value.strip():
                values[name] = value.strip().strip('"').strip("'")
    return values


def walk(block: dict, depth: int = 0, out: list | None = None) -> list:
    out = [] if out is None else out
    out.append((depth, block.get("blockType"), block.get("tag"), block.get("permissions")))
    for child in block.get("children", []) or []:
        walk(child, depth + 1, out)
    return out


def main() -> int:
    env = load_env()
    missing = [k for k in WANTED if k not in env]
    if missing:
        print("Missing:", ", ".join(missing), file=sys.stderr)
        return 2
    adapter = GuardianAdapter(GuardianConfig(env["CP_GUARDIAN_URL"], env["CP_GUARDIAN_USERNAME"], env["CP_GUARDIAN_PASSWORD"], "-"))
    token = adapter._bearer()  # noqa: SLF001 (probe tool)
    print("login ok")
    me = adapter._call("GET", "/api/v1/profiles/" + env["CP_GUARDIAN_USERNAME"], None, token)  # noqa: SLF001
    print("profile:", {k: me.get(k) for k in ("username", "role", "confirmed", "failed") if isinstance(me, dict)})
    policies = adapter._call("GET", "/api/v1/policies?pageIndex=0&pageSize=50", None, token)  # noqa: SLF001
    items = policies if isinstance(policies, list) else policies.get("items", []) if isinstance(policies, dict) else []
    print(f"{len(items)} policies")
    for p in items:
        print(" -", p.get("id"), "|", p.get("name"), "|", p.get("status"), "| v", p.get("version"))
    if len(sys.argv) > 1:
        pid = sys.argv[1]
        policy = adapter._call("GET", f"/api/v1/policies/{pid}", None, token)  # noqa: SLF001
        print("roles:", policy.get("policyRoles"), "| topic:", policy.get("topicId"))
        for depth, kind, tag, perms in walk(policy.get("config", {})):
            if kind in ("requestVcDocumentBlock", "externalDataBlock", "mintDocumentBlock", "tokenActionBlock", "buttonBlock", "retirementDocumentBlock", "interfaceDocumentsSourceBlock"):
                print("  " * depth + f"{kind} tag={tag} roles={perms}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
