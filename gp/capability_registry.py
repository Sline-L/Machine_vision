"""Fail-closed capability registry (declarative).

A profile is switchable only when implemented AND mission_approved.
Rejected capabilities stay unavailable even if listed.
"""

from __future__ import annotations

import json
from pathlib import Path

from gp.config import PROJECT_ROOT

DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "docs" / "capabilities" / "registry.json"

_CACHE = None
_CACHE_PATH = None


class CapabilityError(ValueError):
    pass


def _load_path(path: Path | None = None) -> Path:
    return Path(path) if path is not None else DEFAULT_REGISTRY_PATH


def load_registry(path: Path | None = None, *, reload: bool = False) -> dict:
    global _CACHE, _CACHE_PATH
    reg_path = _load_path(path)
    if not reload and _CACHE is not None and _CACHE_PATH == reg_path:
        return _CACHE
    if not reg_path.is_file():
        # Fail closed: empty registry means nothing extra is approved.
        payload = {"schema_version": "capability-registry.v1", "fail_closed": True, "capabilities": []}
    else:
        payload = json.loads(reg_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("capabilities"), list):
        raise CapabilityError("capability registry must be an object with capabilities[]")
    _CACHE = payload
    _CACHE_PATH = reg_path
    return payload


def get_capability(profile_id: str, path: Path | None = None) -> dict | None:
    for row in load_registry(path).get("capabilities") or []:
        if isinstance(row, dict) and row.get("profile_id") == profile_id:
            return row
    return None


def is_runtime_available(profile_id: str, path: Path | None = None) -> bool:
    """Switchable only if explicitly implemented and Mission-approved."""
    row = get_capability(profile_id, path)
    if row is None:
        # Unknown to registry: fall back to legacy SPECS.implemented only via caller.
        return False
    if row.get("status") == "REJECTED":
        return False
    return bool(row.get("implemented")) and bool(row.get("mission_approved"))


def assert_switchable(
    profile_id: str,
    *,
    legacy_implemented: bool,
    path: Path | None = None,
    engineering_mode: bool = False,
) -> None:
    """Raise CapabilityError unless legacy + registry both allow the switch.

    engineering_mode skips mission_approved only for explicit harness use.
    REJECTED capabilities remain blocked even in engineering_mode.
    """
    if not legacy_implemented:
        raise CapabilityError(f"capability {profile_id} is not implemented")
    row = get_capability(profile_id, path)
    if row is None:
        # Profiles that predate registry and are legacy-implemented remain available
        # only when implemented flag is true (FULL/SPARSE/…).
        return
    if row.get("status") == "REJECTED":
        raise CapabilityError(f"capability {profile_id} is REJECTED and cannot be enabled")
    if not bool(row.get("implemented")):
        raise CapabilityError(f"capability {profile_id} registry.implemented is false")
    if engineering_mode:
        return
    if not bool(row.get("mission_approved")):
        raise CapabilityError(f"capability {profile_id} is not mission_approved")


def list_capabilities(path: Path | None = None) -> list[dict]:
    out = []
    for row in load_registry(path).get("capabilities") or []:
        if not isinstance(row, dict):
            continue
        pid = row.get("profile_id")
        available = is_runtime_available(pid, path) if pid else False
        # Legacy-only profiles without registry row are handled by list_profile_availability.
        out.append(
            {
                "profile_id": pid,
                "status": row.get("status"),
                "implemented": bool(row.get("implemented")),
                "mission_approved": bool(row.get("mission_approved")),
                "available": available,
                "formal_evaluation_status": row.get("formal_evaluation_status"),
            }
        )
    return out


def list_profile_availability(legacy_specs: dict, path: Path | None = None) -> list[dict]:
    """Merge SPECS with registry for operator/Agent visibility."""
    rows = {r["profile_id"]: r for r in list_capabilities(path) if r.get("profile_id")}
    out = []
    for name, spec in legacy_specs.items():
        reg = rows.get(name)
        legacy_ok = bool(spec.get("implemented"))
        if reg is None:
            available = legacy_ok
            status = "LEGACY_IMPLEMENTED" if legacy_ok else "UNIMPLEMENTED"
            mission_approved = legacy_ok
            implemented = legacy_ok
        else:
            implemented = bool(reg.get("implemented"))
            mission_approved = bool(reg.get("mission_approved"))
            available = legacy_ok and is_runtime_available(name, path)
            status = reg.get("status")
        out.append(
            {
                "profile_id": name,
                "status": status,
                "implemented": implemented,
                "mission_approved": mission_approved,
                "available": available,
            }
        )
    # Registry-only ids (e.g. classifier_only_v1) not in SPECS
    for name, reg in rows.items():
        if name in legacy_specs:
            continue
        out.append(
            {
                "profile_id": name,
                "status": reg.get("status"),
                "implemented": bool(reg.get("implemented")),
                "mission_approved": bool(reg.get("mission_approved")),
                "available": False,
            }
        )
    return out
