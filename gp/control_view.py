"""Internal Control/Verify snapshot. Not the public system-snapshot.v2 contract."""

CONTROL_VIEW_VERSION = "gearpro-control-view.v1"

INSPECTION_RECOVERY_ACTIONS = frozenset(
    (
        "restart_camera",
        "restart_worker",
        "resume_inspection",
        "set_inference_profile",
        "set_locator_profile",
        "reload_config",
        "rollback_config",
        "use_camera",
        "use_video",
    )
)

# Cap still applies until extras prove dual-specialist evidence.
DUAL_SPECIALIST_MISSION_DEFERRED = tuple(INSPECTION_RECOVERY_ACTIONS) + ("apply_settings",)


def as_control_view(health):
    """Copy health into a Control-only view with v1-shaped specialist fields.

    Public Web `/api/v2` health stays whatever `build_snapshot` emitted.
    """
    view = dict(health or {})
    view["schema_version"] = CONTROL_VIEW_VERSION
    specialists = view.get("specialists") or {}
    if "scratch_v5" not in view or not view.get("scratch_v5"):
        view["scratch_v5"] = dict(specialists.get("scratch_v5") or {})
    if "missing_hole_v1" not in view or not view.get("missing_hole_v1"):
        view["missing_hole_v1"] = dict(specialists.get("missing_hole_v1") or {})
    dual = bool(
        view["scratch_v5"].get("loaded") is True
        and view["missing_hole_v1"].get("loaded") is True
        and view["scratch_v5"].get("last_valid_output")
        and view["missing_hole_v1"].get("last_valid_output")
    )
    view["control_view"] = {
        "dual_specialist_mission_verified": False,
        "missing_hole_independent_health": view["missing_hole_v1"].get("error_state") not in (None, "unknown"),
        "dual_output_present": dual,
        "note": "Control view is not system-snapshot.v2",
    }
    return view


def cap_verify_level(name, params, level, extras=None):
    """Keep recovery claims from outrunning dual-specialist evidence."""
    extras = extras or {}
    params = params or {}
    if name == "set_inference_profile" and params.get("profile") == "SAFE_STOP":
        return level, None
    if name in ("pause_inspection", "reconnect_serial", "reset_stats", "get_state"):
        return level, None
    if name == "apply_settings":
        if level in ("function", "mission"):
            return "config", "配置成功不等于任务恢复"
        return level, None
    if name not in INSPECTION_RECOVERY_ACTIONS:
        return level, None
    if extras.get("emergency_hold"):
        if level in ("function", "mission"):
            return "none", "紧急停机中断恢复"
        return level, None
    if extras.get("dual_specialist_evidence"):
        return level, None
    if level in ("function", "mission"):
        return (
            "config",
            "双专项证据不足，不记 RECOVERED",
        )
    return level, None


def inspection_recovery_success(name, params, level, extras=None):
    extras = extras or {}
    params = params or {}
    if name == "set_inference_profile" and params.get("profile") == "SAFE_STOP":
        return False
    if name not in INSPECTION_RECOVERY_ACTIONS:
        return False
    if level not in ("function", "mission"):
        return False
    return bool(extras.get("dual_specialist_evidence"))
