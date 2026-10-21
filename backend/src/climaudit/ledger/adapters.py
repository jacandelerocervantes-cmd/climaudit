"""The factory that picks the ledger adapter from configuration, and the fail-closed placeholders.

- `fake`: in-memory ledger for tests and local demos.
- `direct`: `DirectHederaAdapter` over the Hiero SDK and the mirror node (ledger/hedera.py), testnet only. If its
  configuration is incomplete the factory returns an adapter that fails closed with LEDGER_UNAVAILABLE and names
  the missing variables.
- `guardian`: `GuardianAdapter` (ledger/guardian.py) anchors the audit trail through a published policy (verified live
  on Guardian 3.7.1); credit tokens go through the direct adapter. Incomplete configuration or an unexpected
  response fails closed.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, NoReturn

from ..config import Settings
from ..errors import ApiError
from .fake import FakeLedger
from .guardian import MIRROR_TESTNET, GuardianAdapter, GuardianConfig
from .hedera import DirectHederaAdapter, SdkGateway
from .port import LedgerPort, LedgerRef, MintResult


class _NotImplementedAdapter:
    mode = "unimplemented"
    needs: tuple[str, ...] = ()

    def __init__(self, settings: Settings):
        self.settings = settings

    def _fail(self) -> NoReturn:
        missing = [name for name in self.needs if not getattr(self.settings, name, None)]
        raise ApiError("LEDGER_UNAVAILABLE", {"adapter": self.mode, "reason": "adapter_not_implemented", "missing_config": missing})

    def anchor(self, event_hash: str, metadata: dict[str, Any]) -> LedgerRef:
        self._fail()

    def mint(self, op_key: str, batch_id: str, units: int, memo: str) -> MintResult:
        self._fail()

    def transfer(self, op_key: str, token_id: str, from_holder: str, to_holder: str, units: int) -> str:
        self._fail()

    def retire(self, op_key: str, token_id: str, holder: str, units: int, beneficiary_ref: str, reason_code: str) -> str:
        self._fail()

    def published_hashes(self) -> list[str]:
        self._fail()


class IncompleteDirectConfig(_NotImplementedAdapter):
    """Direct mode selected but not fully configured: every operation fails closed and lists what is missing."""

    mode = "direct"
    needs = ("hedera_operator_id", "hedera_operator_key", "hcs_topic_id", "hts_token_id")

    def _fail(self) -> NoReturn:
        missing = [name for name in self.needs if not getattr(self.settings, name, None)]
        raise ApiError("LEDGER_UNAVAILABLE", {"adapter": "direct", "reason": "incomplete_configuration", "missing_config": missing})


class IncompleteGuardianConfig(_NotImplementedAdapter):
    """Guardian mode selected but not fully configured: every operation fails closed and lists what is missing."""

    mode = "guardian"
    needs = ("guardian_url", "guardian_username", "guardian_password", "guardian_policy_id")

    def _fail(self) -> NoReturn:
        missing = [name for name in self.needs if not getattr(self.settings, name, None)]
        raise ApiError("LEDGER_UNAVAILABLE", {"adapter": "guardian", "reason": "incomplete_configuration", "missing_config": missing})


def build_ledger(settings: Settings, clock: Callable[[], str]) -> LedgerPort:
    if settings.ledger_mode == "fake":
        return FakeLedger(clock)
    if settings.ledger_mode == "direct":
        if not all([settings.hedera_operator_id, settings.hedera_operator_key, settings.hcs_topic_id, settings.hts_token_id]):
            return IncompleteDirectConfig(settings)
        gateway = SdkGateway(
            settings.hedera_operator_id,  # type: ignore[arg-type]
            settings.hedera_operator_key,  # type: ignore[arg-type]
            settings.hedera_supply_key,
            settings.hedera_network,
            settings.hedera_mirror_url,
        )
        return DirectHederaAdapter(gateway, settings.hcs_topic_id, settings.hts_token_id)  # type: ignore[arg-type]
    if not all([settings.guardian_url, settings.guardian_username, settings.guardian_password, settings.guardian_policy_id]):
        return IncompleteGuardianConfig(settings)
    tokens: LedgerPort | None = None
    if settings.hedera_operator_id and settings.hedera_operator_key and settings.hts_token_id:
        gateway = SdkGateway(settings.hedera_operator_id, settings.hedera_operator_key, settings.hedera_supply_key, settings.hedera_network, settings.hedera_mirror_url)
        tokens = DirectHederaAdapter(gateway, settings.hcs_topic_id or "unused", settings.hts_token_id)
    return GuardianAdapter(
        GuardianConfig(
            settings.guardian_url,  # type: ignore[arg-type]
            settings.guardian_username,  # type: ignore[arg-type]
            settings.guardian_password,  # type: ignore[arg-type]
            settings.guardian_policy_id,  # type: ignore[arg-type]
            settings.guardian_form_tag,
            settings.guardian_grid_tag,
            settings.hedera_mirror_url or MIRROR_TESTNET,
        ),
        tokens=tokens,
    )
