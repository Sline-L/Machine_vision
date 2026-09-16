"""Capability-aware reasoning input. Observation is not recovery authority."""

from __future__ import annotations

_PATTERN = {
    (True, True): "v2_positive_v3_1_positive",
    (True, False): "v2_positive_v3_1_negative",
    (False, True): "v2_negative_v3_1_positive",
    (False, False): "v2_negative_v3_1_negative",
}


def capabilities_of(snapshot):
    rows = snapshot.get("capabilities") if isinstance(snapshot, dict) else None
    return list(rows) if isinstance(rows, list) else []


def compact_capability(row):
    row = row or {}
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    source = str(row.get("source") or "")
    role = str(meta.get("role") or "")
    shadow = source == "v3_1" or role == "shadow"
    return {
        "name": row.get("capability"),
        "source": source,
        "status": row.get("status"),
        "decision": row.get("decision"),
        "confidence": row.get("confidence"),
        "authority": row.get("authority"),
        "drives_recovery": bool(row.get("drives_recovery")),
        "candidate_status": row.get("candidate_status"),
        "engineering_approved": row.get("candidate_status")
        in ("engineering_qualified", "production_bundle"),
        "mission_approved": bool(meta.get("mission_approved")),
        "holdout_validated": bool(meta.get("holdout_validated")),
        "shadow": shadow,
    }


def _primary_and_shadow(rows):
    primary = None
    shadow = None
    for row in rows:
        compact = compact_capability(row)
        if compact.get("source") == "v3_1" or compact.get("shadow"):
            if shadow is None or compact.get("source") == "v3_1":
                shadow = compact
            continue
        if primary is None:
            primary = compact
    if primary is None:
        for row in rows:
            compact = compact_capability(row)
            if not compact.get("shadow"):
                primary = compact
                break
    return primary, shadow


def capability_compare(snapshot):
    """Structured V2 / V3-1 relation. Diagnosis only; does not authorize actions."""
    rows = [compact_capability(item) for item in capabilities_of(snapshot)]
    primary, shadow = _primary_and_shadow(rows)
    primary_decision = None if primary is None else primary.get("decision")
    shadow_decision = None if shadow is None else shadow.get("decision")
    if primary is None or shadow is None or primary_decision is None or shadow_decision is None:
        relation = "incomplete"
        pattern = "incomplete"
        agreement = None
    else:
        agreement = bool(primary_decision) == bool(shadow_decision)
        relation = "agreement" if agreement else "disagreement"
        pattern = _PATTERN.get((bool(primary_decision), bool(shadow_decision)), "unknown")
    return {
        "agreement": agreement,
        "relation": relation,
        "pattern": pattern,
        "primary_source": None if primary is None else primary.get("source"),
        "shadow_source": None if shadow is None else shadow.get("source"),
        "primary_decision": primary_decision,
        "shadow_decision": shadow_decision,
        "shadow_drives_recovery": False if shadow is None else bool(shadow.get("drives_recovery")),
    }


def l1_reasons(snapshot, fault=None):
    reasons = []
    if fault:
        reasons.append("named_fault:" + str(fault))
    for node in ("camera", "locator", "scratch_v5", "serial"):
        health = (snapshot.get(node) or {}).get("health")
        if health is not None and float(health) <= 0.2:
            reasons.append("component_unhealthy:" + node)
    for row in [compact_capability(item) for item in capabilities_of(snapshot)]:
        if row.get("decision") is True and not row.get("shadow"):
            reasons.append("capability_signal:" + str(row.get("name") or "unknown"))
        if row.get("shadow") and row.get("decision") is True:
            reasons.append("shadow_signal:" + str(row.get("name") or "unknown"))
    compare = capability_compare(snapshot)
    if compare.get("relation") == "disagreement":
        reasons.append("capability_disagreement:" + str(compare.get("pattern")))
    if compare.get("shadow_drives_recovery") is False and compare.get("shadow_source"):
        reasons.append("shadow_no_recovery_authority")
    return reasons


def diagnosis_text(fault, snapshot):
    from .incident import _diagnosis

    base = _diagnosis(fault)
    reasons = l1_reasons(snapshot, fault)
    extra = []
    compare = capability_compare(snapshot)
    if compare.get("relation") == "disagreement":
        extra.append("capability disagreement " + str(compare.get("pattern")))
    elif compare.get("relation") == "agreement" and compare.get("pattern") != "incomplete":
        extra.append("capability agreement " + str(compare.get("pattern")))
    if "shadow_no_recovery_authority" in reasons:
        extra.append("v3_1 shadow observation only")
    if not extra:
        return base
    return base + "; " + "; ".join(extra)


def component_health(snapshot):
    out = {}
    for node in ("camera", "locator", "scratch_v5", "serial"):
        block = dict(snapshot.get(node) or {})
        out[node] = {
            "health": block.get("health"),
            "opened": block.get("opened"),
            "connected": block.get("connected"),
            "latency_ms": block.get("latency_ms") or block.get("total_latency_ms"),
            "error_count": block.get("error_count"),
            "frame_age_ms": block.get("frame_age_ms"),
            "consecutive_failures": block.get("consecutive_failures"),
        }
    return out


def reasoning_input(snapshot, fault=None, experience=None, recent_actions=None):
    """Compact L1/L2 contract. Drops detector implementation names."""
    from .incident import evidence_from

    snapshot = snapshot or {}
    compare = capability_compare(snapshot)
    system = dict(snapshot.get("system") or {})
    compact_system = {
        "temperature_c": system.get("temperature_c"),
        "gpu_util": system.get("gpu_util"),
        "gpu_mem_mb": system.get("gpu_mem_mb"),
        "power_w": system.get("power_w"),
    }
    caps = [compact_capability(item) for item in capabilities_of(snapshot)]
    return {
        "system": compact_system,
        "components": component_health(snapshot),
        "evidence": evidence_from(snapshot),
        "capabilities": caps,
        "capability_compare": compare,
        "active_faults": [] if not fault else [fault],
        "recent_actions": list(recent_actions or []),
        "l1_reasons": l1_reasons(snapshot, fault),
        "experience": list(experience or []),
        "authority_boundary": {
            "observed_capability_signal_is_not_recovery_authority": True,
            "v3_1_shadow_drives_recovery": False,
            "l2_may_use_shadow_for_diagnosis_only": True,
        },
    }


def retrieval_fingerprint(snapshot, fault=None):
    compare = capability_compare(snapshot)
    unhealthy = []
    for node in ("camera", "locator", "scratch_v5", "serial"):
        health = (snapshot.get(node) or {}).get("health")
        if health is not None and float(health) <= 0.2:
            unhealthy.append(node)
    return {
        "fault": fault,
        "unhealthy_components": unhealthy,
        "capability_pattern": compare.get("pattern"),
        "relation": compare.get("relation"),
    }


def shadow_cannot_authorize(snapshot):
    """Invariant helper: V3-1 never grants a recovery verb."""
    compare = capability_compare(snapshot)
    if compare.get("shadow_source") != "v3_1":
        return True
    return compare.get("shadow_drives_recovery") is False
