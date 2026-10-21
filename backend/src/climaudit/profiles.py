"""Methodology profile files (BACKEND-SPEC.md section 6). No methodology constant lives in code."""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from .config import BUILTIN_PROFILES_DIR
from .errors import ApiError


@dataclass(frozen=True)
class ParamRef:
    """A profile value that was used in a calculation, with its provenance in the source document."""

    name: str
    value: str
    verified: bool
    page: int | None = None
    profile_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"name": self.name, "value": self.value, "verified": self.verified, "profile_id": self.profile_id}
        if self.page is not None:
            out["page"] = self.page
        return out


class Profile:
    def __init__(self, data: dict[str, Any]):
        for key in ("profile_id", "methodology_id", "version", "permanence"):
            if key not in data:
                raise ValueError(f"profile is missing {key!r}")
        self.data = data
        self.profile_id: str = data["profile_id"]
        self.methodology_id: str = data["methodology_id"]
        self.version: str = data["version"]
        self.horizon_years: int = int(data.get("horizon_years", 100))
        self.alternative: bool = bool(data.get("alternative", False))
        self.label: str = data.get("label", data["profile_id"])
        self.permanence_mode: str = data["permanence"]["mode"]
        if self.permanence_mode not in ("temperature_table", "hcorg_linear"):
            raise ValueError(f"unknown permanence mode {self.permanence_mode!r}")

    # ------------------------------------------------------------------ helpers
    def _ref(self, name: str, entry: dict[str, Any], value: str | None = None) -> ParamRef:
        return ParamRef(
            name=name,
            value=value if value is not None else str(entry.get("value", "")),
            verified=bool(entry.get("verified", False)),
            page=entry.get("page"),
            profile_id=self.profile_id,
        )

    def rule(self, name: str) -> tuple[Decimal, ParamRef]:
        entry = self.data.get("rules", {}).get(name)
        if entry is None:
            raise ApiError("FACTOR_SOURCE_MISSING", {"parameter": name, "methodology": self.profile_id})
        return Decimal(entry["value"]), self._ref(f"rules.{name}", entry)

    def rule_entry(self, name: str) -> dict[str, Any]:
        entry = self.data.get("rules", {}).get(name)
        if entry is None:
            raise ApiError("FACTOR_SOURCE_MISSING", {"parameter": name, "methodology": self.profile_id})
        return entry

    def tolerance(self, name: str) -> tuple[Decimal, ParamRef]:
        entry = self.data.get("tolerances", {}).get(name)
        if entry is None:
            raise ApiError("FACTOR_SOURCE_MISSING", {"parameter": f"tolerances.{name}", "methodology": self.profile_id})
        return Decimal(entry["value"]), self._ref(f"tolerances.{name}", entry)

    def plausibility(self, name: str) -> tuple[Decimal, Decimal, ParamRef] | None:
        entry = self.data.get("plausibility", {}).get(name)
        if entry is None:
            return None
        return Decimal(entry["min"]), Decimal(entry["max"]), self._ref(f"plausibility.{name}", entry, f"{entry['min']}..{entry['max']}")

    def modeled_relative_uncertainty(self) -> tuple[Decimal, ParamRef]:
        entry = self.data.get("uncertainty", {}).get("modeled_relative_uncertainty")
        if entry is None:
            raise ApiError("FACTOR_SOURCE_MISSING", {"parameter": "uncertainty.modeled_relative_uncertainty", "methodology": self.profile_id})
        return Decimal(entry["value"]), self._ref("uncertainty.modeled_relative_uncertainty", entry)

    def limit(self, field: str, applies_to: str) -> dict[str, Any] | None:
        for entry in self.data.get("limits", []):
            if entry["field"] == field and entry.get("applies_to") in (applies_to, "any"):
                return entry
        return None

    def limit_ref(self, entry: dict[str, Any]) -> ParamRef:
        return self._ref(f"limits.{entry['field']}", entry)

    # ----------------------------------------------------------- permanence
    def permanence_from_temperature(self, temp_c: Decimal | None) -> tuple[Decimal, ParamRef]:
        """VM0044 Table 3 defaults by production temperature; the unknown default when temperature is absent."""
        if self.permanence_mode != "temperature_table":
            raise ApiError("CALC_FAILED", {"step": "permanence_mode_mismatch"})
        perm = self.data["permanence"]
        if temp_c is None:
            entry = perm["unknown_temperature_default"]
            return Decimal(entry["value"]), self._ref("permanence.unknown_temperature_default", entry)
        for row in perm["table"]:
            if "gt" in row and not temp_c > Decimal(row["gt"]):
                continue
            if "ge" in row and not temp_c >= Decimal(row["ge"]):
                continue
            if "le" in row and not temp_c <= Decimal(row["le"]):
                continue
            if "lt" in row and not temp_c < Decimal(row["lt"]):
                continue
            return Decimal(row["value"]), self._ref(f"permanence.{row['label']}", row)
        raise ApiError("FACTOR_SOURCE_MISSING", {"parameter": "permanence.temperature", "methodology": self.profile_id, "value": str(temp_c)})

    def permanence_from_hcorg(self, hcorg: Decimal, soil_temp_c: Decimal) -> tuple[Decimal, ParamRef]:
        """Woolf et al. (2021) linear regression, F_perm = c + m * H/Corg, capped at 1 when configured."""
        if self.permanence_mode != "hcorg_linear":
            raise ApiError("CALC_FAILED", {"step": "permanence_mode_mismatch"})
        perm = self.data["permanence"]
        for row in perm["rows"]:
            if int(row["horizon_years"]) == self.horizon_years and Decimal(row["soil_temp_c"]) == soil_temp_c:
                value = Decimal(row["c"]) + Decimal(row["m"]) * hcorg
                if perm.get("cap_at_one") and value > 1:
                    value = Decimal(1)
                if value < 0:
                    value = Decimal(0)
                return value, self._ref(f"permanence.hcorg_linear@{soil_temp_c}C", row, str(value))
        raise ApiError("FACTOR_SOURCE_MISSING", {"parameter": "permanence.soil_temp_c", "methodology": self.profile_id, "value": str(soil_temp_c)})

    # --------------------------------------------------------------- defaults
    def fc_default(self, feedstock_class: str, process: str) -> tuple[Decimal, ParamRef]:
        block = self.data.get("defaults", {}).get("organic_carbon_fraction_low_tech")
        if block is None:
            raise ApiError("FACTOR_SOURCE_MISSING", {"parameter": "organic_carbon_fraction_low_tech", "methodology": self.profile_id})
        try:
            raw = block["values"][feedstock_class][process]
        except KeyError as exc:
            raise ApiError("FACTOR_SOURCE_MISSING", {"parameter": f"fc.{feedstock_class}.{process}", "methodology": self.profile_id}) from exc
        return Decimal(raw), self._ref(f"defaults.fc.{feedstock_class}.{process}", block, raw)

    def default_value(self, name: str) -> tuple[Decimal, ParamRef]:
        entry = self.data.get("defaults", {}).get(name)
        if entry is None or "value" not in entry:
            raise ApiError("FACTOR_SOURCE_MISSING", {"parameter": f"defaults.{name}", "methodology": self.profile_id})
        return Decimal(entry["value"]), self._ref(f"defaults.{name}", entry)

    def tool_value(self, tool: str, *path: str) -> tuple[Decimal, ParamRef]:
        node: Any = self.data.get("tools", {}).get(tool)
        for part in path:
            if not isinstance(node, dict) or part not in node:
                raise ApiError("FACTOR_SOURCE_MISSING", {"parameter": f"tools.{tool}.{'.'.join(path)}", "methodology": self.profile_id})
            node = node[part]
        if not isinstance(node, dict) or "value" not in node:
            raise ApiError("FACTOR_SOURCE_MISSING", {"parameter": f"tools.{tool}.{'.'.join(path)}", "methodology": self.profile_id})
        return Decimal(node["value"]), self._ref(f"tools.{tool}.{'.'.join(path)}", node)


class ProfileRegistry:
    def __init__(self, extra_dir: str | None = None):
        self._profiles: dict[str, Profile] = {}
        self._raw: dict[str, dict[str, Any]] = {}
        self._load_dir(BUILTIN_PROFILES_DIR)
        if extra_dir:
            self._load_dir(Path(extra_dir))
        self._resolve_all()

    def _load_dir(self, directory: Path) -> None:
        if not directory.is_dir():
            return
        for path in sorted(directory.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            self._raw[data["profile_id"]] = data

    def _resolve_all(self) -> None:
        inheritable = ("limits", "defaults", "rules", "tools", "tolerances", "plausibility", "benford", "uncertainty")
        for profile_id, data in self._raw.items():
            merged = dict(data)
            parent_id = data.get("extends")
            if parent_id:
                parent = self._raw.get(parent_id)
                if parent is None:
                    raise ValueError(f"profile {profile_id!r} extends unknown profile {parent_id!r}")
                for key in inheritable:
                    if key not in data or data[key] in ({}, []):
                        merged[key] = parent.get(key, {} if key != "limits" else [])
            self._profiles[profile_id] = Profile(merged)

    def get(self, profile_id: str) -> Profile:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise ApiError("NOT_FOUND", {"resource": "profile", "id": profile_id}) from exc

    def ids(self) -> list[str]:
        return sorted(self._profiles)
