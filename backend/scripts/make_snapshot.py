"""Record a real run of the whole lifecycle and write the snapshot that the public, read-only web app replays.

Usage (from the backend folder, with the .venv active):
    python scripts/make_snapshot.py                       # Hedera testnet: needs the CP_HEDERA_* variables, see README
    python scripts/make_snapshot.py --ledger fake         # in-memory ledger, for trying the replay without a network

With `--ledger direct` it first creates a FRESH audit topic and credit token on testnet (so the recorded ledger check
compares one clean topic with one clean chain), runs the synthetic lifecycle through the real API rules, waits for the
public mirror node to catch up, and records the answer of every read route the web app uses, for every persona. The
result is written to ../web/snapshot/snapshot.json. Nothing in it is a secret: ids, hashes and synthetic data only.
Credentials are read from the environment or from backend/.env and are never printed or written.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def load_dotenv() -> None:
    path = BACKEND / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        name, _, value = line.strip().partition("=")
        if name and not name.startswith("#") and value.strip() and name.strip() not in os.environ:
            os.environ[name.strip()] = value.strip().strip('"').strip("'")


def create_fresh_ledger_ids() -> None:
    """Run hedera_setup.py (creates one topic and one token on testnet) and keep only the two ids it prints."""
    result = subprocess.run([sys.executable, str(BACKEND / "scripts" / "hedera_setup.py")], capture_output=True, text=True, env=os.environ.copy(), check=False)
    topic = re.search(r"^CP_HCS_TOPIC_ID=(\S+)$", result.stdout, re.M)
    token = re.search(r"^CP_HTS_TOKEN_ID=(\S+)$", result.stdout, re.M)
    if result.returncode != 0 or not topic or not token:
        raise SystemExit(f"could not create the testnet topic and token (exit {result.returncode}); check the CP_HEDERA_* variables")
    os.environ["CP_HCS_TOPIC_ID"], os.environ["CP_HTS_TOKEN_ID"] = topic.group(1), token.group(1)
    print(f"fresh testnet topic {topic.group(1)} and token {token.group(1)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ledger", choices=("direct", "fake"), default="direct")
    parser.add_argument("--out", type=Path, default=BACKEND.parent / "web" / "snapshot" / "snapshot.json")
    parser.add_argument("--reuse-ids", action="store_true", help="use CP_HCS_TOPIC_ID and CP_HTS_TOKEN_ID as they are instead of creating new ones")
    args = parser.parse_args()

    load_dotenv()
    if args.ledger == "direct" and not args.reuse_ids:
        create_fresh_ledger_ids()
    os.environ["CP_LEDGER_MODE"] = args.ledger

    from fastapi.testclient import TestClient  # noqa: PLC0415

    from climaudit.api.app import create_app  # noqa: PLC0415
    from climaudit.config import ApiKey, Settings, load_settings  # noqa: PLC0415
    from climaudit.demo import ROLES, seed_demo  # noqa: PLC0415
    from climaudit.ledger.adapters import build_ledger  # noqa: PLC0415
    from climaudit.store import Store  # noqa: PLC0415

    def now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    env = load_settings()
    keys = {secrets.token_hex(12): ApiKey(actor, role) for role, actor in ROLES.items()}
    key_of = {k.role: name for name, k in keys.items()}
    ledger = build_ledger(env, now)
    app = create_app(Settings(api_keys=keys, ledger_mode=env.ledger_mode, hedera_network=env.hedera_network), ledger=ledger, store=Store(":memory:"), clock=now)
    http = TestClient(app, raise_server_exceptions=False)

    def call(method: str, path: str, role: str, body: dict | None = None):
        headers = {"Authorization": f"Bearer {key_of[role]}"}
        if method != "GET":
            headers["Idempotency-Key"] = secrets.token_hex(12)
        response = http.request(method, path, json=body, headers=headers)
        if response.status_code >= 300:
            raise SystemExit(f"{method} {path} as {role} failed: HTTP {response.status_code} {response.text[:300]}")
        return response.json()

    print(f"recording the lifecycle on the {ledger.mode} ledger ...")
    ids = seed_demo(call, lifecycle=True)

    def read(path: str, role: str) -> dict:
        response = http.get("/" + path, headers={"Authorization": f"Bearer {key_of[role]}"})
        try:
            body = response.json()
        except ValueError:
            body = None
        return {"status": response.status_code, "body": body}

    verdict = read("audit/verify", "verifier")
    for _ in range(30 if ledger.mode != "fake" else 1):  # the public mirror node lags consensus by a few seconds
        if verdict["status"] == 200 and verdict["body"]["ledger_matches"]:
            break
        time.sleep(3)
        verdict = read("audit/verify", "verifier")
    if verdict["status"] != 200 or not verdict["body"]["chain_ok"] or not verdict["body"]["ledger_matches"]:
        raise SystemExit(f"the recorded run does not verify against the ledger: {verdict}")

    batch_ids = list(ids.values())
    documents = {b: read(f"batches/{b}/documents", "owner")["body"] for b in batch_ids}
    static = ["me", "config", "catalog", "profiles", "profiles/VM0044@1.2", "projects", "batches", "credits", "audit/verify"]
    per_batch = [f"batches/{b}{suffix}" for b in batch_ids for suffix in ("", "/report", "/documents", "/findings")] + [f"audit/{b}" for b in batch_ids]
    texts = [f"documents/{doc['document_ref']}/text" for docs in documents.values() for doc in docs]
    recorded = {role: {path: read(path, role) for path in [*static, *per_batch, *texts]} for role in ROLES}

    events = read(f"audit/{batch_ids[0]}", "owner")["body"]
    credits = read("credits", "verifier")["body"]
    meta = {
        "generated_at": now(),
        "ledger_mode": ledger.mode,
        "network": env.hedera_network if ledger.mode != "fake" else None,
        "topic_id": next((e["ledger_ref"]["topic_id"] for e in events if e.get("ledger_ref")), None),
        "token_id": credits[0]["token_id"] if credits else None,
        "batches": ids,
        "verify": verdict["body"],
        "note": "Synthetic demonstration data (SYNTHETIC_DEMO_DATA). Nothing here is a real credit.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"meta": meta, "roles": recorded}, sort_keys=True, separators=(",", ":")), encoding="utf-8", newline="\n")
    print(f"wrote {args.out} ({args.out.stat().st_size // 1024} KB): {len(batch_ids)} batches, {sum(len(v) for v in recorded.values())} recorded answers")
    print(f"ledger check: chain intact {verdict['body']['chain_ok']}, matches ledger {verdict['body']['ledger_matches']}, events {verdict['body']['event_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
