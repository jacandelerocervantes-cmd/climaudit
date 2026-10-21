"""Runtime configuration read from environment variables only.

No path, secret or machine-specific value is hardcoded here. Relative paths resolve against the
process working directory; packaged data resolves against the installed package.
"""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
BUILTIN_PROFILES_DIR = PACKAGE_DIR / "profiles_data"

ROLES = ("owner", "verifier", "registry", "holder", "admin", "system", "extractor")
LEDGER_MODES = ("fake", "direct", "guardian")


@dataclass(frozen=True)
class ApiKey:
    actor_id: str
    role: str


@dataclass(frozen=True)
class Settings:
    env: str = "prod"  # `dev` serves /docs and /openapi.json; anything else does not
    db_path: str = "./data/climaudit.db"
    profiles_dir: str | None = None
    api_keys: dict[str, ApiKey] = field(default_factory=dict, repr=False)
    max_upload_bytes: int = 10 * 1024 * 1024
    max_documents_per_batch: int = 20
    force_synthetic: bool = True
    ledger_mode: str = "fake"
    hedera_network: str = "testnet"
    hedera_operator_id: str | None = None
    hedera_operator_key: str | None = field(default=None, repr=False)
    hedera_supply_key: str | None = field(default=None, repr=False)
    hedera_mirror_url: str | None = None
    hcs_topic_id: str | None = None
    hts_token_id: str | None = None
    guardian_url: str | None = None
    guardian_username: str | None = None
    guardian_password: str | None = field(default=None, repr=False)
    guardian_policy_id: str | None = None
    guardian_form_tag: str = "form"
    guardian_grid_tag: str = "grid"
    external_checks: bool = False
    registry_index_path: str | None = None
    open_meteo_url: str | None = None
    worldcover_url: str | None = None
    anthropic_api_key: str | None = field(default=None, repr=False)
    anthropic_model: str | None = None


def _parse_keys(raw: str | None) -> dict[str, ApiKey]:
    if not raw:
        return {}
    data = json.loads(raw)
    keys: dict[str, ApiKey] = {}
    for key, spec in data.items():
        role = spec["role"]
        if role not in ROLES:
            raise ValueError(f"unknown role in CP_API_KEYS: {role!r}")
        keys[key] = ApiKey(actor_id=spec["actor_id"], role=role)
    return keys


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from the process environment, or from an explicit mapping (used by tests)."""
    env = os.environ if environ is None else environ

    def get(name: str, default: str = "") -> str:
        return (env.get(name, default) or default).strip()

    def opt(name: str) -> str | None:
        value = get(name)
        return value or None

    mode = get("CP_LEDGER_MODE", "fake")
    if mode not in LEDGER_MODES:
        raise ValueError(f"CP_LEDGER_MODE must be one of {LEDGER_MODES}, got {mode!r}")
    return Settings(
        env=get("CP_ENV", "prod"),
        db_path=get("CP_DB_PATH", "./data/climaudit.db"),
        profiles_dir=opt("CP_PROFILES_DIR"),
        api_keys=_parse_keys(opt("CP_API_KEYS")),
        ledger_mode=mode,
        hedera_network=get("CP_HEDERA_NETWORK", "testnet"),
        hedera_operator_id=opt("CP_HEDERA_OPERATOR_ID"),
        hedera_operator_key=opt("CP_HEDERA_OPERATOR_KEY"),
        hedera_supply_key=opt("CP_HEDERA_SUPPLY_KEY"),
        hedera_mirror_url=opt("CP_HEDERA_MIRROR_URL"),
        hcs_topic_id=opt("CP_HCS_TOPIC_ID"),
        hts_token_id=opt("CP_HTS_TOKEN_ID"),
        guardian_url=opt("CP_GUARDIAN_URL"),
        guardian_username=opt("CP_GUARDIAN_USERNAME"),
        guardian_password=opt("CP_GUARDIAN_PASSWORD"),
        guardian_policy_id=opt("CP_GUARDIAN_POLICY_ID"),
        guardian_form_tag=get("CP_GUARDIAN_FORM_TAG", "form"),
        guardian_grid_tag=get("CP_GUARDIAN_GRID_TAG", "grid"),
        external_checks=get("CP_EXTERNAL_CHECKS", "0").lower() in ("1", "true", "yes"),
        registry_index_path=opt("CP_REGISTRY_INDEX_PATH"),
        open_meteo_url=opt("CP_OPEN_METEO_URL"),
        worldcover_url=opt("CP_WORLDCOVER_URL"),
        anthropic_api_key=opt("CP_ANTHROPIC_API_KEY"),
        anthropic_model=opt("CP_ANTHROPIC_MODEL"),
        max_upload_bytes=int(get("CP_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
        max_documents_per_batch=int(get("CP_MAX_DOCUMENTS_PER_BATCH", "20")),
        force_synthetic=get("CP_FORCE_SYNTHETIC", "1").lower() not in ("0", "false", "no"),
    )
