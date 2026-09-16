"""Internal Control/Verify snapshot. Not the public system-snapshot.v2 contract."""

CONTROL_VIEW_VERSION = "gearpro-control-view.v1"

DUAL_SPECIALIST_MISSION_DEFERRED = (
    "restart_camera",
    "restart_worker",
    "resume_inspection",
    "set_inference_profile",
    "set_locator_profile",
    "reload_config",
    "rollback_config",
    "apply_settings",
    "use_camera",
    "use_video",
)


def as_control_view(health):
    """Copy health into a Control-only view with v1-shaped scratch_v5.

    Public Web `/api/v2` health stays whatever `build_snapshot` emitted.
    Verify still only understands scratch_v5; dual-specialist mission is capped
    in ControlService, not by mutating the v2 schema.
    """
    view = dict(health or {})
    view["schema_version"] = CONTROL_VIEW_VERSION
    specialists = view.get("specialists") or {}
    if "scratch_v5" not in view or not view.get("scratch_v5"):
        view["scratch_v5"] = dict(specialists.get("scratch_v5") or {})
    view["control_view"] = {
        "dual_specialist_mission_verified": False,
        "missing_hole_independent_health": False,
        "note": "Missing Hole mission verify is deferred to Step 6.3",
    }
    return view


def cap_verify_level(name, params, level):
    """Scratch-only function/mission must not be reported as dual-specialist recovery."""
    params = params or {}
    if name == "set_inference_profile" and params.get("profile") == "SAFE_STOP":
        return level, None
    if name not in DUAL_SPECIALIST_MISSION_DEFERRED:
        return level, None
    if level in ("function", "mission"):
        return (
            "config",
            "双专项任务级验证留待 Step 6.3；当前不记 RECOVERED",
        )
    return level, None
