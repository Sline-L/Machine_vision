"""Paired structured/raw views of the same SystemSnapshot. No extra fault labels."""

from edgemedic.context import capabilities_of, capability_compare, component_health
from edgemedic.incident import evidence_from


def structured_view(snapshot):
    """Reshape measured fields. Does not inject classify_fault or L1 named_fault."""
    snapshot = snapshot or {}
    mission = dict(snapshot.get("mission") or {})
    evidence = dict(evidence_from(snapshot))
    evidence["inspection_active"] = mission.get("inspection_active")
    return {
        "system": {
            "temperature_c": (snapshot.get("system") or {}).get("temperature_c"),
            "gpu_util": (snapshot.get("system") or {}).get("gpu_util"),
            "gpu_mem_mb": (snapshot.get("system") or {}).get("gpu_mem_mb"),
            "power_w": (snapshot.get("system") or {}).get("power_w"),
        },
        "components": component_health(snapshot),
        "mission": mission,
        "evidence": evidence,
        "capabilities": capabilities_of(snapshot),
        "capability_compare": capability_compare(snapshot),
        "experience": [],
        "recent_actions": [],
    }
