"""Three-level verify: config, function, mission.

Config means the action stuck (do not rollback).
Function means one real infer/IO recovery succeeded (Repair Memory may learn).
Mission means a short healthy window after that (optional; not required for memory).
"""

LEVELS = ("none", "config", "function", "mission")


def rank(level):
    try:
        return LEVELS.index(level)
    except ValueError:
        return 0


def config_verified(level):
    return rank(level) >= rank("config")


def recovery_success(level):
    return rank(level) >= rank("function")


def _mission(after):
    return after.get("mission") or {}


def _locator(after):
    return after.get("locator") or {}


def _scratch(after):
    return after.get("scratch_v5") or {}


def _camera(after):
    return after.get("camera") or {}


def infer_ok(after, extras=None):
    extras = extras or {}
    if extras.get("worker_failed"):
        return False
    mission = _mission(after)
    if not mission.get("output_valid"):
        return False
    locator_ms = _locator(after).get("latency_ms")
    v5_ms = _scratch(after).get("total_latency_ms")
    if locator_ms is None and v5_ms is None:
        return False
    return True


def can_reach_function(extras):
    extras = extras or {}
    if extras.get("inspection_can_run"):
        return True
    return False


def _ok_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return False
    keys = ("schema_version", "system", "camera", "locator", "scratch_v5", "serial", "mission")
    return all(key in snapshot for key in keys)


def _maybe_mission(before, after, extras, base_level):
    if base_level != "function":
        return base_level
    if not extras.get("mission_window_ok"):
        before_u = (_mission(before) or {}).get("utility")
        after_u = (_mission(after) or {}).get("utility")
        before_loc = _locator(before).get("latency_ms")
        after_loc = _locator(after).get("latency_ms")
        improved = (
            after_u is not None
            and (before_u is None or after_u >= before_u)
            and after_loc is not None
            and (before_loc is None or after_loc <= before_loc)
            and infer_ok(after, extras)
            and (_mission(after).get("inspection_active"))
        )
        if not improved:
            return "function"
    return "mission"


def assess_get_state(params, before, after, extras):
    del params, before, extras
    if _ok_snapshot(after):
        return "function", None
    return "none", "返回的 Snapshot 不完整"


def assess_restart_camera(params, before, after, extras):
    del params, extras
    before_cam = _camera(before)
    after_cam = _camera(after)
    if not after_cam.get("opened"):
        return "none", "摄像头未打开"
    before_seq = int(before_cam.get("frame_seq") or 0)
    after_seq = int(after_cam.get("frame_seq") or 0)
    age = after_cam.get("frame_age_ms")
    if after_seq > before_seq and age is not None and age < 500:
        return "function", None
    return "config", "摄像头已打开但画面尚未恢复"


def assess_restart_worker(params, before, after, extras):
    del params, before
    if extras.get("worker_failed"):
        return "none", "worker 仍异常"
    if _mission(after).get("inspection_active"):
        if infer_ok(after, extras):
            return "function", None
        return "config", "worker 已运行但尚无成功 infer"
    return "none", "worker 未在运行"


def assess_reconnect_serial(params, before, after, extras):
    del params, before
    if extras.get("serial_open"):
        return "function", None
    serial = after.get("serial") or {}
    if serial.get("connected"):
        return "function", None
    return "none", "串口未能打开"


def assess_set_profile(params, before, after, extras):
    wanted = params.get("profile")
    current = _mission(after).get("current_profile")
    if current != wanted:
        return "none", f"档位仍为 {current}，期望 {wanted}"
    if wanted == "SAFE_STOP":
        if _mission(after).get("inspection_active"):
            return "none", "SAFE_STOP 后检测仍在运行"
        return "function", None
    if wanted == "TRT_FAST" and _locator(after).get("backend") != "engine":
        return "none", "TRT_FAST 后 locator 不是 engine"
    previous = _mission(before).get("current_profile")
    if wanted == "FULL" and previous == "TRT_FAST" and _locator(after).get("backend") != "pt":
        return "none", "回 FULL 后 locator 不是 pt"
    if infer_ok(after, extras):
        return _maybe_mission(before, after, extras, "function"), None
    return "config", "档位已切换，尚无成功 infer"


def assess_set_locator(params, before, after, extras):
    del before
    wanted = params.get("profile")
    backend = _locator(after).get("backend")
    expected = {"pt_safe": "pt", "trt_fast": "engine"}.get(wanted)
    if expected is None:
        return "none", f"未知定位档位：{wanted}"
    if backend != expected:
        return "none", f"locator.backend={backend}，期望 {expected}"
    loaded = bool(_locator(after).get("loaded"))
    if extras.get("inspection_can_run") and not loaded:
        return "none", "locator 未加载"
    if infer_ok(after, extras):
        return "function", None
    return "config", "定位权重已切换，尚无成功 infer"


def assess_reload(params, before, after, extras):
    del params, before
    if extras.get("models_ok") is False:
        return "none", "模型路径校验失败"
    current = _mission(after).get("current_profile")
    expected = extras.get("config_profile")
    if expected and current != expected:
        return "none", f"档位仍为 {current}，期望 {expected}"
    if infer_ok(after, extras):
        return "function", None
    return "config", "配置已重载，尚无成功 infer"


def assess_rollback(params, before, after, extras):
    del params, before
    expected_profile = extras.get("backup_profile")
    expected_backend = extras.get("backup_backend")
    current = _mission(after).get("current_profile")
    backend = _locator(after).get("backend")
    if expected_profile and current != expected_profile:
        return "none", f"回滚后档位为 {current}，期望 {expected_profile}"
    if expected_backend and backend != expected_backend:
        return "none", f"回滚后 locator 为 {backend}，期望 {expected_backend}"
    if infer_ok(after, extras):
        return "function", None
    return "config", "配置已回滚，尚无成功 infer"


def assess_pause(params, before, after, extras):
    del params, before, extras
    if _mission(after).get("inspection_active"):
        return "none", "检测仍在运行"
    return "function", None


def assess_resume(params, before, after, extras):
    del params, before
    if not _mission(after).get("inspection_active"):
        return "none", "检测未恢复运行"
    if infer_ok(after, extras):
        return "function", None
    return "config", "检测已恢复但尚无成功 infer"


ASSESSORS = {
    "get_state": assess_get_state,
    "restart_camera": assess_restart_camera,
    "restart_worker": assess_restart_worker,
    "reconnect_serial": assess_reconnect_serial,
    "set_inference_profile": assess_set_profile,
    "set_locator_profile": assess_set_locator,
    "pause_inspection": assess_pause,
    "resume_inspection": assess_resume,
    "reload_config": assess_reload,
    "rollback_config": assess_rollback,
}


def assess(name, params, before, after, extras=None):
    extras = extras or {}
    checker = ASSESSORS.get(name)
    if checker is None:
        return "none", f"动作 {name} 没有 verify"
    return checker(params, before, after, extras)
