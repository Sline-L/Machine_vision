"""Three-level verify: config, function, mission.

config: target state written (profile/backend/settings). Not recovery.
function: the module completed one valid functional execution.
mission: a measured observation window still meets the task, not sleep(N).
recovery_success is true only for function and mission.
"""

from dataclasses import dataclass
from math import ceil

LEVELS = ("none", "config", "function", "mission")


@dataclass(frozen=True)
class MissionVerificationPolicy:
    window_seconds: float = 2.0
    min_cycles: int = 5
    min_valid_output_ratio: float = 0.80
    max_locator_p95_ms: float = 120.0
    max_v5_p95_ms: float = 200.0
    max_elapsed_p95_ms: float = 320.0
    min_mission_utility: float = 0.70
    min_health_score: float = 0.50
    reject_on_critical_incident: bool = True

    def as_dict(self):
        return {
            "window_seconds": self.window_seconds,
            "min_cycles": self.min_cycles,
            "output_valid_ratio": self.min_valid_output_ratio,
            "locator_p95_ms": self.max_locator_p95_ms,
            "v5_p95_ms": self.max_v5_p95_ms,
            "elapsed_p95_ms": self.max_elapsed_p95_ms,
            "camera_health_min": self.min_health_score,
            "utility_min": self.min_mission_utility,
            "reject_on_critical_incident": self.reject_on_critical_incident,
        }


DEFAULT_WINDOW = MissionVerificationPolicy().as_dict()


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


def latency_stats(values):
    values = [float(item) for item in values if item is not None]
    if not values:
        return {"mean": None, "p50": None, "p95": None, "max": None}
    return {
        "mean": round(sum(values) / len(values), 3),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "max": max(values),
    }


def summarize_cycles(samples):
    samples = list(samples or [])
    n = len(samples)
    valid = [item for item in samples if item.get("valid")]
    locator = latency_stats([item.get("locator_ms") for item in valid])
    v5 = latency_stats([item.get("v5_ms") for item in valid])
    missing = latency_stats([item.get("missing_ms") for item in valid])
    elapsed = latency_stats([item.get("elapsed_ms") for item in valid])
    return {
        "n": n,
        "output_valid_ratio": 0.0 if n == 0 else len(valid) / n,
        "locator": locator,
        "scratch_v5": v5,
        "missing_hole_v1": missing,
        "elapsed": elapsed,
        "locator_p95_ms": locator["p95"],
        "v5_p95_ms": v5["p95"],
        "missing_p95_ms": missing["p95"],
        "elapsed_p95_ms": elapsed["p95"],
        "locator_mean_ms": locator["mean"],
        "v5_mean_ms": v5["mean"],
        "elapsed_max_ms": elapsed["max"],
    }


def _mission(after):
    return after.get("mission") or {}


def _locator(after):
    return after.get("locator") or {}


def _scratch(after):
    return after.get("scratch_v5") or (after.get("specialists") or {}).get("scratch_v5") or {}


def _missing(after):
    return after.get("missing_hole_v1") or (after.get("specialists") or {}).get("missing_hole_v1") or {}


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


def specialist_loaded(block):
    loaded = block.get("loaded")
    if loaded is True:
        return True
    if loaded is False:
        return False
    return None


def dual_output_ok(after, extras=None):
    extras = extras or {}
    if extras.get("worker_failed") or extras.get("emergency_hold"):
        return False
    if extras.get("output_fresh") is False:
        return False
    scratch = _scratch(after)
    missing = _missing(after)
    if specialist_loaded(scratch) is False or specialist_loaded(missing) is False:
        return False
    if not scratch.get("last_valid_output") and scratch.get("total_latency_ms") is None:
        return False
    if not missing.get("last_valid_output") and missing.get("total_latency_ms") is None:
        return False
    if extras.get("dual_specialist_evidence"):
        return True
    if specialist_loaded(scratch) is True and specialist_loaded(missing) is True:
        if scratch.get("total_latency_ms") is None or missing.get("total_latency_ms") is None:
            return False
        if extras.get("output_fresh") is True:
            return True
        if extras.get("output_fresh") is None and infer_ok(after, extras):
            return False
    return False


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
    policy = MissionVerificationPolicy()
    profile = params.get("profile") or _mission(after).get("current_profile")
    if name == "set_inference_profile" and profile == "SPARSE":
        policy = MissionVerificationPolicy(
            window_seconds=10.0,
            min_cycles=8,
            min_valid_output_ratio=0.95,
            max_locator_p95_ms=120.0,
            max_v5_p95_ms=220.0,
            max_elapsed_p95_ms=320.0,
            min_mission_utility=0.85,
            min_health_score=0.5,
        )
    if name == "set_locator_profile" and params.get("profile") == "trt_fast":
        policy = MissionVerificationPolicy(max_locator_p95_ms=80.0)
    return policy.as_dict()


def evaluate_mission_window(name, params, after, extras):
    extras = extras or {}
    spec = mission_spec(name, params, after)
    if spec.get("reject_on_critical_incident") and (extras.get("worker_failed") or extras.get("critical_incident")):
        return False, "窗口内出现新的 critical incident"
    if mission_kind(name, params) != "window":
        return False, None
    elapsed_s = extras.get("window_elapsed_s")
    if elapsed_s is None:
        elapsed_s = 0.0
    if float(elapsed_s) < float(spec["window_seconds"]):
        return False, f"观察窗口 {elapsed_s:.2f}s < {spec['window_seconds']}s"
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
    missing_p95 = stats.get("missing_p95_ms")
    if missing_p95 is not None and missing_p95 > float(spec["v5_p95_ms"]):
        return False, f"missing hole p95 {missing_p95:.1f} ms 超过 {spec['v5_p95_ms']}"
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


def _promote_dual(name, params, after, extras, function_reason=None):
    extras = extras or {}
    if extras.get("emergency_hold"):
        return "none", "紧急停机中断恢复"
    if not dual_output_ok(after, extras):
        return "config", function_reason or "双专项尚未同时给出新输出"
    return _promote(name, params, after, extras, function_reason)


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
    if extras.get("emergency_hold"):
        return "none", "紧急停机中断恢复"
    before_cam = _camera(before)
    after_cam = _camera(after)
    if not after_cam.get("opened"):
        return "none", "摄像头未打开"
    before_seq = int(before_cam.get("frame_seq") or 0)
    after_seq = int(after_cam.get("frame_seq") or 0)
    age = after_cam.get("frame_age_ms")
    if after_seq > before_seq and age is not None and age < 500:
        return _promote_dual("restart_camera", params, after, extras, "摄像头已恢复，双专项输出待验证")
    return "config", "摄像头已打开但画面尚未恢复"


def assess_restart_worker(params, before, after, extras):
    del before
    extras = extras or {}
    if extras.get("emergency_hold"):
        return "none", "紧急停机中断恢复"
    if extras.get("worker_failed"):
        return "none", "worker 仍异常"
    scratch = _scratch(after)
    missing = _missing(after)
    if specialist_loaded(scratch) is False or specialist_loaded(missing) is False:
        return "none", "双专项未能全部加载"
    if _mission(after).get("inspection_active"):
        return _promote_dual("restart_worker", params, after, extras, "worker 已运行但尚无双专项新输出")
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
    if extras.get("emergency_hold"):
        return "none", "紧急停机中断恢复"
    if wanted == "TRT_FAST" and _locator(after).get("backend") != "engine":
        return "none", "TRT_FAST 后 locator 不是 engine"
    previous = _mission(before).get("current_profile")
    if wanted == "FULL" and previous == "TRT_FAST" and _locator(after).get("backend") != "pt":
        return "none", "回 FULL 后 locator 不是 pt"
    return _promote_dual("set_inference_profile", params, after, extras, "档位已切换，尚无双专项新输出")


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
    return _promote_dual("set_locator_profile", params, after, extras, "定位权重已切换，尚无双专项新输出")


def assess_reload(params, before, after, extras):
    del params, before
    extras = extras or {}
    if extras.get("models_ok") is False:
        return "none", "模型路径校验失败"
    current = _mission(after).get("current_profile")
    expected = extras.get("config_profile")
    if expected and current != expected:
        return "none", f"档位仍为 {current}，期望 {expected}"
    return _promote_dual("reload_config", {}, after, extras, "配置已重载，尚无双专项新输出")


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
    return _promote_dual("rollback_config", {}, after, extras, "配置已回滚，尚无双专项新输出")


def assess_pause(params, before, after, extras):
    del params, before, extras
    if _mission(after).get("inspection_active"):
        return "none", "检测仍在运行"
    return "mission", None


def assess_resume(params, before, after, extras):
    del params, before
    extras = extras or {}
    if extras.get("emergency_hold"):
        return "none", "紧急停机锁存或温度保护仍有效，拒绝 resume_inspection"
    if not _mission(after).get("inspection_active"):
        return "none", "检测未恢复运行"
    return _promote_dual("resume_inspection", params, after, extras, "检测已恢复但尚无双专项新输出")


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
    return "config", "配置已应用"


def assess_use_camera(params, before, after, extras):
    del params, before
    extras = extras or {}
    if extras.get("video_mode"):
        return "none", "仍在视频模式"
    if _camera(after).get("opened"):
        return _promote_dual("use_camera", {}, after, extras, "已切回相机")
    return "none", "相机未打开"


def assess_use_video(params, before, after, extras):
    del params, before, after
    extras = extras or {}
    if extras.get("video_mode"):
        if dual_output_ok(after, extras):
            return _promote("use_video", {}, after, extras)
        return "config", "已进入视频模式，双专项输出待验证"
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
