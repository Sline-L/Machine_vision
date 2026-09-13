"""Three-level verify: config, function, mission.

Config means the action stuck (do not rollback).
Function means one real infer/IO recovery succeeded (Repair Memory may learn).
Mission means a measured inspection window after that, not a fixed sleep.
"""

from math import ceil

LEVELS = ("none", "config", "function", "mission")

DEFAULT_WINDOW = {
    "min_cycles": 5,
    "output_valid_ratio": 0.8,
    "locator_p95_ms": 120.0,
    "v5_p95_ms": 200.0,
    "elapsed_p95_ms": 320.0,
    "camera_health_min": 0.5,
    "utility_min": 0.7,
}


def rank(level):
    try:
        return LEVELS.index(level)
    except ValueError:
        return 0


def config_verified(level):
    return rank(level) >= rank("config")


def recovery_success(level):
    return rank(level) >= rank("function")


def mission_success(level):
    return rank(level) >= rank("mission")


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    index = min(len(ordered) - 1, max(0, ceil(p / 100.0 * len(ordered)) - 1))
    return ordered[index]


def summarize_cycles(samples):
    samples = list(samples or [])
    n = len(samples)
    if n == 0:
        return {
            "n": 0,
            "output_valid_ratio": 0.0,
            "locator_p95_ms": None,
            "v5_p95_ms": None,
            "elapsed_p95_ms": None,
        }
    valid = [item for item in samples if item.get("valid")]
    locator = [item["locator_ms"] for item in valid if item.get("locator_ms") is not None]
    v5 = [item["v5_ms"] for item in valid if item.get("v5_ms") is not None]
    elapsed = [item["elapsed_ms"] for item in valid if item.get("elapsed_ms") is not None]
    return {
        "n": n,
        "output_valid_ratio": len(valid) / n,
        "locator_p95_ms": percentile(locator, 95),
        "v5_p95_ms": percentile(v5, 95),
        "elapsed_p95_ms": percentile(elapsed, 95),
    }


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
    return bool(extras.get("inspection_can_run"))


def mission_kind(name, params):
    if name in ("reconnect_serial", "pause_inspection"):
        return "alias"
    if name == "set_inference_profile" and params.get("profile") == "SAFE_STOP":
        return "alias"
    if name in (
        "set_inference_profile",
        "set_locator_profile",
        "restart_worker",
        "resume_inspection",
        "restart_camera",
        "reload_config",
        "rollback_config",
        "use_camera",
        "use_video",
    ):
        return "window"
    return None


def can_reach_mission(name, params, extras):
    extras = extras or {}
    if mission_kind(name, params) != "window":
        return False
    return bool(extras.get("inspection_can_run"))


def mission_spec(name, params, after):
    spec = dict(DEFAULT_WINDOW)
    profile = params.get("profile") or _mission(after).get("current_profile")
    if name == "set_inference_profile" and profile == "SPARSE":
        spec["utility_min"] = 0.85
        spec["v5_p95_ms"] = 220.0
    if name == "set_locator_profile" and params.get("profile") == "trt_fast":
        spec["locator_p95_ms"] = 80.0
    return spec


def evaluate_mission_window(name, params, after, extras):
    extras = extras or {}
    if extras.get("worker_failed") or extras.get("critical_incident"):
        return False, "窗口内出现新的 critical incident"
    if mission_kind(name, params) != "window":
        return False, None
    spec = mission_spec(name, params, after)
    stats = extras.get("window_stats") or {}
    n = int(stats.get("n") or 0)
    if n < int(spec["min_cycles"]):
        return False, f"窗口周期 {n} < {spec['min_cycles']}"
    ratio = float(stats.get("output_valid_ratio") or 0.0)
    if ratio < float(spec["output_valid_ratio"]):
        return False, f"output_valid_ratio {ratio:.2f} 低于 {spec['output_valid_ratio']}"
    loc_p95 = stats.get("locator_p95_ms")
    if loc_p95 is not None and loc_p95 > float(spec["locator_p95_ms"]):
        return False, f"locator p95 {loc_p95:.1f} ms 超过 {spec['locator_p95_ms']}"
    v5_p95 = stats.get("v5_p95_ms")
    if v5_p95 is not None and v5_p95 > float(spec["v5_p95_ms"]):
        return False, f"v5 p95 {v5_p95:.1f} ms 超过 {spec['v5_p95_ms']}"
    elapsed_p95 = stats.get("elapsed_p95_ms")
    if elapsed_p95 is not None and elapsed_p95 > float(spec["elapsed_p95_ms"]):
        return False, f"elapsed p95 {elapsed_p95:.1f} ms 超过 {spec['elapsed_p95_ms']}"
    cam = extras.get("camera_health")
    if cam is None:
        cam = _camera(after).get("health")
    if cam is not None and float(cam) < float(spec["camera_health_min"]):
        return False, "窗口内摄像头 health 过低"
    utility = _mission(after).get("utility")
    if utility is not None and float(utility) < float(spec["utility_min"]):
        return False, f"Mission Utility {utility} 低于 {spec['utility_min']}"
    if not _mission(after).get("inspection_active"):
        return False, "窗口结束时检测未在运行"
    return True, None


def _promote(name, params, after, extras, function_reason=None):
    kind = mission_kind(name, params)
    if kind == "alias":
        return "mission", None
    ok, why = evaluate_mission_window(name, params, after, extras)
    if ok:
        return "mission", None
    return "function", why or function_reason


def _ok_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return False
    keys = ("schema_version", "system", "camera", "locator", "scratch_v5", "serial", "mission")
    return all(key in snapshot for key in keys)


def assess_get_state(params, before, after, extras):
    del params, before, extras
    if _ok_snapshot(after):
        return "function", None
    return "none", "返回的 Snapshot 不完整"


def assess_restart_camera(params, before, after, extras):
    extras = extras or {}
    before_cam = _camera(before)
    after_cam = _camera(after)
    if not after_cam.get("opened"):
        return "none", "摄像头未打开"
    before_seq = int(before_cam.get("frame_seq") or 0)
    after_seq = int(after_cam.get("frame_seq") or 0)
    age = after_cam.get("frame_age_ms")
    if after_seq > before_seq and age is not None and age < 500:
        return _promote("restart_camera", params, after, extras)
    return "config", "摄像头已打开但画面尚未恢复"


def assess_restart_worker(params, before, after, extras):
    del before
    extras = extras or {}
    if extras.get("worker_failed"):
        return "none", "worker 仍异常"
    if _mission(after).get("inspection_active"):
        if infer_ok(after, extras):
            return _promote("restart_worker", params, after, extras)
        return "config", "worker 已运行但尚无成功 infer"
    return "none", "worker 未在运行"


def assess_reconnect_serial(params, before, after, extras):
    del params, before
    if extras.get("serial_open"):
        return "mission", None
    serial = after.get("serial") or {}
    if serial.get("connected"):
        return "mission", None
    return "none", "串口未能打开"


def assess_set_profile(params, before, after, extras):
    extras = extras or {}
    wanted = params.get("profile")
    current = _mission(after).get("current_profile")
    if current != wanted:
        return "none", f"档位仍为 {current}，期望 {wanted}"
    if wanted == "SAFE_STOP":
        if _mission(after).get("inspection_active"):
            return "none", "SAFE_STOP 后检测仍在运行"
        return "mission", None
    if wanted == "TRT_FAST" and _locator(after).get("backend") != "engine":
        return "none", "TRT_FAST 后 locator 不是 engine"
    previous = _mission(before).get("current_profile")
    if wanted == "FULL" and previous == "TRT_FAST" and _locator(after).get("backend") != "pt":
        return "none", "回 FULL 后 locator 不是 pt"
    if infer_ok(after, extras):
        return _promote("set_inference_profile", params, after, extras)
    return "config", "档位已切换，尚无成功 infer"


def assess_set_locator(params, before, after, extras):
    del before
    extras = extras or {}
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
        return _promote("set_locator_profile", params, after, extras)
    return "config", "定位权重已切换，尚无成功 infer"


def assess_reload(params, before, after, extras):
    del params, before
    extras = extras or {}
    if extras.get("models_ok") is False:
        return "none", "模型路径校验失败"
    current = _mission(after).get("current_profile")
    expected = extras.get("config_profile")
    if expected and current != expected:
        return "none", f"档位仍为 {current}，期望 {expected}"
    if infer_ok(after, extras):
        return _promote("reload_config", {}, after, extras)
    return "config", "配置已重载，尚无成功 infer"


def assess_rollback(params, before, after, extras):
    del params, before
    extras = extras or {}
    expected_profile = extras.get("backup_profile")
    expected_backend = extras.get("backup_backend")
    current = _mission(after).get("current_profile")
    backend = _locator(after).get("backend")
    if expected_profile and current != expected_profile:
        return "none", f"回滚后档位为 {current}，期望 {expected_profile}"
    if expected_backend and backend != expected_backend:
        return "none", f"回滚后 locator 为 {backend}，期望 {expected_backend}"
    if infer_ok(after, extras):
        return _promote("rollback_config", {}, after, extras)
    return "config", "配置已回滚，尚无成功 infer"


def assess_pause(params, before, after, extras):
    del params, before, extras
    if _mission(after).get("inspection_active"):
        return "none", "检测仍在运行"
    return "mission", None


def assess_resume(params, before, after, extras):
    del params, before
    extras = extras or {}
    if not _mission(after).get("inspection_active"):
        return "none", "检测未恢复运行"
    if infer_ok(after, extras):
        return _promote("resume_inspection", params, after, extras)
    return "config", "检测已恢复但尚无成功 infer"


def assess_apply_settings(params, before, after, extras):
    del before, after
    extras = extras or {}
    current = extras.get("settings") or {}
    for key, value in (params or {}).items():
        if key == "inference_profile":
            continue
        if current.get(key) != value:
            return "none", f"{key} 未生效"
    wanted_profile = (params or {}).get("inference_profile")
    if wanted_profile and extras.get("config_profile") != wanted_profile:
        return "none", f"档位仍为 {extras.get('config_profile')}，期望 {wanted_profile}"
    return "mission", None


def assess_use_camera(params, before, after, extras):
    del params, before
    extras = extras or {}
    if extras.get("video_mode"):
        return "none", "仍在视频模式"
    if infer_ok(after, extras):
        return _promote("use_camera", {}, after, extras)
    if _camera(after).get("opened"):
        return "config", "已切回相机"
    return "none", "相机未打开"


def assess_use_video(params, before, after, extras):
    del params, before, after
    extras = extras or {}
    if extras.get("video_mode"):
        return "mission", None
    return "none", "未进入视频模式"


def assess_reset_stats(params, before, after, extras):
    del params, before, after, extras
    return "mission", None


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
    "apply_settings": assess_apply_settings,
    "use_camera": assess_use_camera,
    "use_video": assess_use_video,
    "reset_stats": assess_reset_stats,
}


def assess(name, params, before, after, extras=None):
    extras = extras or {}
    checker = ASSESSORS.get(name)
    if checker is None:
        return "none", f"动作 {name} 没有 verify"
    return checker(params, before, after, extras)
