"""Start the backend for local development of the web app and seed three synthetic batches.

Usage (from the backend folder, with the .venv active):
    python scripts/dev_stack.py [--port 8791] [--ledger fake|direct [--fresh-ledger]]

It generates random demo keys for the five personas, writes them to ../web/.env.local (git-ignored, server side only),
starts the API with the in-memory ledger and a temporary database, seeds a VERIFIED batch, an UNDER_REVIEW batch with a
report and a DRAFT batch, then keeps running. Stop it with Ctrl+C. Then run `npm run dev` in ../web.
With the default `--ledger fake` nothing touches Hedera or Guardian; `--ledger direct` publishes to the testnet account in
.env (use a fresh topic). All data is synthetic.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from climaudit.demo import ROLES, seed_demo


class Client:
    def __init__(self, base: str, keys: dict[str, str]):
        self.base, self.keys = base, keys

    def call(self, method: str, path: str, role: str, body: dict | None = None):
        headers = {"Authorization": f"Bearer {self.keys[role]}", "Content-Type": "application/json"}
        if method != "GET":
            headers["Idempotency-Key"] = uuid.uuid4().hex
        request = urllib.request.Request(self.base + path, method=method, headers=headers, data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"{method} {path} failed: HTTP {exc.code} {exc.read()[:300]!r}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--ledger", choices=["fake", "direct"], default="fake", help="direct publishes to the Hedera testnet account in backend/.env")
    parser.add_argument("--fresh-ledger", action="store_true", help="with --ledger direct: create a new testnet topic and token first, so the explorer shows only this run")
    args = parser.parse_args()
    if args.ledger == "direct":
        from make_snapshot import create_fresh_ledger_ids, load_dotenv  # same folder

        load_dotenv()
        if args.fresh_ledger:
            create_fresh_ledger_ids()
    web = Path(__file__).resolve().parents[2] / "web"
    keys = {role: secrets.token_hex(16) for role in ROLES}
    base = f"http://127.0.0.1:{args.port}"
    if web.is_dir():
        lines = [f"CP_API_URL={base}", *[f"CP_KEY_{role.upper()}={key}" for role, key in keys.items()]]
        (web / ".env.local").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {web / '.env.local'} (demo keys for the proxy; git-ignored)")
    workdir = tempfile.mkdtemp(prefix="climaudit-dev-")
    env = {
        **os.environ,
        "CP_API_KEYS": json.dumps({keys[r]: {"actor_id": actor, "role": r} for r, actor in ROLES.items()}),
        "CP_LEDGER_MODE": args.ledger, "CP_DB_PATH": str(Path(workdir) / "dev.db"), "CP_ENV": "prod", "CP_EXTERNAL_CHECKS": "0",
    }
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "climaudit.api.app:app_factory", "--factory", "--port", str(args.port), "--log-level", "warning"], env=env)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"{base}/health", timeout=2)
                break
            except OSError:
                if api.poll() is not None:
                    return 1
                time.sleep(1)
        client = Client(base, keys)
        seed_demo(lambda method, path, role, body=None: client.call(method, path, role, body))
        print(f"API ready at {base} with 3 synthetic batches (verified, under review, draft).")
        print("Now run `npm run dev` in the web folder and open http://localhost:3000. Press Ctrl+C here to stop the API.")
        api.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if api.poll() is None:
            api.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
