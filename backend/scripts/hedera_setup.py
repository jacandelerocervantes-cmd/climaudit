"""Create the HCS audit topic and the HTS credit token on Hedera TESTNET, once, and print the ids.

Usage (from the backend folder, with the `hedera` extra installed):
    CP_HEDERA_OPERATOR_ID=0.0.xxxx CP_HEDERA_OPERATOR_KEY=<private key> python scripts/hedera_setup.py
    python scripts/hedera_setup.py --dry-run        # prints what would be created, touches nothing, needs no credentials

The credentials are read from environment variables only; they are never printed or written anywhere. The script
prints the two ids to copy into your local `.env` as CP_HCS_TOPIC_ID and CP_HTS_TOKEN_ID. Running it creates two
testnet entities for the operator account (free testnet HBAR). It refuses to run against any network but testnet.

Token design: a fungible token with 3 decimals, so one token is one tonne of CO2e and one base unit is one kilogram
(BACKEND-SPEC.md Decision 2). Initial supply is 0; units are minted when a batch is issued. The operator account is
the treasury and holds the supply key.
"""
from __future__ import annotations

import argparse
import os
import sys

TOPIC_MEMO = "ClimAudit audit trail - SYNTHETIC_DEMO_DATA"
TOKEN_NAME = "ClimAudit Demo Credit"
TOKEN_SYMBOL = "CADEMO"
TOKEN_MEMO = "ClimAudit demo credit, 1 unit = 1 kg CO2e - SYNTHETIC_DEMO_DATA"
DECIMALS = 3


def parse_key(h, text: str):
    try:
        return h.PrivateKey.from_string_der(text)
    except Exception:  # noqa: BLE001 - fall back to raw hex and other encodings
        return h.PrivateKey.from_string(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    args = parser.parse_args()
    plan = [f"HCS topic, memo {TOPIC_MEMO!r}", f"HTS fungible token {TOKEN_NAME!r} ({TOKEN_SYMBOL}), {DECIMALS} decimals, initial supply 0, infinite supply"]
    print("Plan (Hedera testnet only):")
    for line in plan:
        print(" -", line)
    if args.dry_run:
        return 0

    operator_id, operator_key = os.environ.get("CP_HEDERA_OPERATOR_ID", ""), os.environ.get("CP_HEDERA_OPERATOR_KEY", "")
    if not operator_id or not operator_key:
        print("Set CP_HEDERA_OPERATOR_ID and CP_HEDERA_OPERATOR_KEY (testnet account) in the environment.", file=sys.stderr)
        return 2
    if os.environ.get("CP_HEDERA_NETWORK", "testnet") != "testnet":
        print("Only testnet is allowed.", file=sys.stderr)
        return 2
    try:
        import hiero_sdk_python as h  # noqa: PLC0415 (optional dependency)
    except ImportError:
        print('Install the SDK first:  pip install -e ".[hedera]"', file=sys.stderr)
        return 2

    client = h.Client.for_testnet()
    account = h.AccountId.from_string(operator_id)
    key = parse_key(h, operator_key)
    client.set_operator(account, key)

    topic_receipt = (
        h.TopicCreateTransaction(memo=TOPIC_MEMO, admin_key=key.public_key()).freeze_with(client).sign(key).execute(client, validate_status=True)
    )
    topic_id = str(topic_receipt.topic_id)

    token_receipt = (
        h.TokenCreateTransaction()
        .set_token_name(TOKEN_NAME)
        .set_token_symbol(TOKEN_SYMBOL)
        .set_decimals(DECIMALS)
        .set_initial_supply(0)
        .set_token_type(h.TokenType.FUNGIBLE_COMMON)
        .set_supply_type(h.SupplyType.INFINITE)
        .set_treasury_account_id(account)
        .set_admin_key(key.public_key())
        .set_supply_key(key.public_key())
        .set_memo(TOKEN_MEMO)
        .freeze_with(client)
        .sign(key)
        .execute(client, validate_status=True)
    )
    token_id = str(token_receipt.token_id)

    print("\nCreated on Hedera testnet. Put these two lines in your local .env (never commit it):")
    print(f"CP_HCS_TOPIC_ID={topic_id}")
    print(f"CP_HTS_TOKEN_ID={token_id}")
    print("CP_LEDGER_MODE=direct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
