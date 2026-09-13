"""Whitelist, preconditions, and verify rules for Control API v1."""

from .profiles import ProfileError, locator_path_for, spec as profile_spec

ACTION_NAMES = (
    "get_state",
    "restart_camera",
    "restart_worker",
    "reconnect_serial",
    "set_inference_profile",
    "set_locator_profile",
    "pause_inspection",
    "resume_inspection",
    "reload_config",
    "rollback_config",
)

SOURCES = ("human", "reflex", "reasoner")

SPECS = {
    "get_state": {"level": 1, "timeout_s": 1, "retry": 0, "implemented": True},
    "restart_camera": {"level": 2, "timeout_s": 8, "retry": 2, "implemented": True},
    "restart_worker": {"level": 2, "timeout_s": 30, "retry": 1, "implemented": True},
    "reconnect_serial": {"level": 2, "timeout_s": 3, "retry": 3, "implemented": True},
    "set_inference_profile": {"level": 2, "timeout_s": 90, "retry": 0, "implemented": True},
    "set_locator_profile": {"level": 2, "timeout_s": 90, "retry": 0, "implemented": True},
    "pause_inspection": {"level": 2, "timeout_s": 5, "retry": 0, "implemented": True},
    "resume_inspection": {"level": 2, "timeout_s": 30, "retry": 0, "implemented": True},
    "reload_config": {"level": 2, "timeout_s": 90, "retry": 0, "implemented": True},
    "rollback_config": {"level": 2, "timeout_s": 90, "retry": 0, "implemented": True},
}

SNAPSHOT_KEYS = ("schema_version", "system", "camera", "locator", "scratch_v5", "serial", "mission")


class ActionError(ValueError):
    pass


def parse_request(body):
    if not isinstance(body, dict):
        raise ActionError("请求必须是 JSON 对象")
    name = body.get("name")
    if name not in ACTION_NAMES:
        raise ActionError(f"未知动作：{name}")
    params = body.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ActionError("params 必须是对象")
    source = body.get("source")
    if source not in SOURCES:
        raise ActionError("source 必须是 human、reflex 或 reasoner")
    request_id = body.get("request_id")
    if not request_id or not isinstance(request_id, str):
        raise ActionError("缺少 request_id")
    return {"name": name, "params": params, "source": source, "request_id": request_id}


def accept(name, params, snapshot, extras=None):
    extras = extras or {}
    meta = SPECS.get(name)
    if meta is None:
        return False, f"未知动作：{name}"
    if not meta.get("implemented"):
        return False, f"动作 {name} 尚未实现"
    checker = _PRECONDITIONS.get(name)
    if checker is None:
        return True, None
    return checker(params, snapshot, extras)


def verify(name, params, before, after, extras=None):
    extras = extras or {}
    checker = _VERIFIERS.get(name)
    if checker is None:
        return False, f"动作 {name} 没有 verify"
    return checker(params, before, after, extras)


def _ok_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return False
    return all(key in snapshot for key in SNAPSHOT_KEYS)


def _pre_get_state(params, snapshot, extras):
    del params, extras
    return True, None


def _pre_restart_camera(params, snapshot, extras):
    del params, extras
    camera = snapshot.get("camera") or {}
    opened = bool(camera.get("opened"))
    age = camera.get("frame_age_ms")
    failures = int(camera.get("read_failures") or 0)
    stale = (not opened) or age is None or age > 1000 or failures > 8
    if not stale:
        return False, "摄像头未处于失败或 STALE，拒绝 restart_camera"
    return True, None


def _pre_restart_worker(params, snapshot, extras):
    del params
    errors = int((snapshot.get("scratch_v5") or {}).get("error_count") or 0)
    if errors >= 1 or extras.get("worker_failed"):
        return True, None
    return False, "worker 未异常，拒绝 restart_worker"


def _pre_reconnect_serial(params, snapshot, extras):
    del params
    if extras.get("serial_enabled") is False:
        return False, "当前任务未启用串口"
    serial = snapshot.get("serial") or {}
    if int(serial.get("consecutive_failures") or 0) >= 1 or not serial.get("connected"):
        return True, None
    return False, "串口已连接且无失败，拒绝 reconnect_serial"


def _pre_set_profile(params, snapshot, extras):
    del snapshot, extras
    name = params.get("profile")
    if not name:
        return False, "缺少 params.profile"
    try:
        profile = profile_spec(name)
    except ProfileError as exc:
        return False, str(exc)
    if not profile.get("implemented"):
        return False, f"档位 {name} 尚未实现"
    if name == "TRT_FAST":
        from .profiles import ENGINE_LOCATOR

        if not ENGINE_LOCATOR.is_file():
            return False, "找不到 model1.engine，无法进入 TRT_FAST"
    return True, None


def _pre_set_locator(params, snapshot, extras):
    del snapshot, extras
    name = params.get("profile")
    if not name:
        return False, "缺少 params.profile"
    try:
        locator_path_for(name)
    except ProfileError as exc:
        return False, str(exc)
    return True, None


def _pre_reload(params, snapshot, extras):
    del params, snapshot, extras
    return True, None


def _pre_rollback(params, snapshot, extras):
    del params, snapshot
    if extras.get("config_backup"):
        return True, None
    return False, "没有可回滚的配置快照"


def _pre_pause(params, snapshot, extras):
    del params, extras
    if not (snapshot.get("mission") or {}).get("inspection_active"):
        return False, "检测未在运行，拒绝 pause_inspection"
    return True, None


def _pre_resume(params, snapshot, extras):
    del params
    camera = snapshot.get("camera") or {}
    video = extras.get("video_mode")
    if video:
        return True, None
    if not camera.get("opened"):
        return False, "摄像头不可用，拒绝 resume_inspection"
    return True, None


def _ver_get_state(params, before, after, extras):
    del params, before, extras
    if _ok_snapshot(after):
        return True, None
    return False, "返回的 Snapshot 不完整"


def _ver_restart_camera(params, before, after, extras):
    del params, extras
    before_cam = before.get("camera") or {}
    after_cam = after.get("camera") or {}
    before_seq = int(before_cam.get("frame_seq") or 0)
    after_seq = int(after_cam.get("frame_seq") or 0)
    age = after_cam.get("frame_age_ms")
    if after_seq > before_seq and age is not None and age < 500:
        return True, None
    return False, "摄像头未恢复：frame_seq 未增加或画面过旧"


def _ver_restart_worker(params, before, after, extras):
    del params, before
    mission = after.get("mission") or {}
    if extras.get("worker_failed"):
        return False, "worker 仍异常"
    if mission.get("inspection_active"):
        return True, None
    return False, "worker 未在运行"


def _ver_reconnect_serial(params, before, after, extras):
    del params, before
    if extras.get("serial_open"):
        return True, None
    serial = after.get("serial") or {}
    if serial.get("connected"):
        return True, None
    return False, "串口未能打开"


def _ver_set_profile(params, before, after, extras):
    del extras
    wanted = params.get("profile")
    current = (after.get("mission") or {}).get("current_profile")
    if current != wanted:
        return False, f"档位仍为 {current}，期望 {wanted}"
    if wanted == "SAFE_STOP":
        if (after.get("mission") or {}).get("inspection_active"):
            return False, "SAFE_STOP 后检测仍在运行"
        return True, None
    previous = (before.get("mission") or {}).get("current_profile")
    if previous == "SAFE_STOP" and not (after.get("mission") or {}).get("inspection_active"):
        return False, "档位恢复后检测未运行"
    if wanted == "TRT_FAST" and (after.get("locator") or {}).get("backend") != "engine":
        return False, "TRT_FAST 后 locator 不是 engine"
    if wanted == "FULL" and previous == "TRT_FAST" and (after.get("locator") or {}).get("backend") != "pt":
        return False, "回 FULL 后 locator 不是 pt"
    return True, None


def _ver_set_locator(params, before, after, extras):
    del before
    wanted = params.get("profile")
    backend = (after.get("locator") or {}).get("backend")
    expected = {"pt_safe": "pt", "trt_fast": "engine"}.get(wanted)
    if expected is None:
        return False, f"未知定位档位：{wanted}"
    if backend != expected:
        return False, f"locator.backend={backend}，期望 {expected}"
    if extras.get("inspection_should_run") and not (after.get("locator") or {}).get("loaded"):
        return False, "locator 未加载"
    return True, None


def _ver_reload(params, before, after, extras):
    del params, before
    if extras.get("models_ok") is False:
        return False, "模型路径校验失败"
    current = (after.get("mission") or {}).get("current_profile")
    expected = extras.get("config_profile")
    if expected and current != expected:
        return False, f"档位仍为 {current}，期望 {expected}"
    return True, None


def _ver_rollback(params, before, after, extras):
    del params, before
    expected_profile = extras.get("backup_profile")
    expected_backend = extras.get("backup_backend")
    current = (after.get("mission") or {}).get("current_profile")
    backend = (after.get("locator") or {}).get("backend")
    if expected_profile and current != expected_profile:
        return False, f"回滚后档位为 {current}，期望 {expected_profile}"
    if expected_backend and backend != expected_backend:
        return False, f"回滚后 locator 为 {backend}，期望 {expected_backend}"
    return True, None


def _ver_pause(params, before, after, extras):
    del params, before, extras
    if (after.get("mission") or {}).get("inspection_active"):
        return False, "检测仍在运行"
    return True, None


def _ver_resume(params, before, after, extras):
    del params, before, extras
    if not (after.get("mission") or {}).get("inspection_active"):
        return False, "检测未恢复运行"
    return True, None


_PRECONDITIONS = {
    "get_state": _pre_get_state,
    "restart_camera": _pre_restart_camera,
    "restart_worker": _pre_restart_worker,
    "reconnect_serial": _pre_reconnect_serial,
    "set_inference_profile": _pre_set_profile,
    "set_locator_profile": _pre_set_locator,
    "pause_inspection": _pre_pause,
    "resume_inspection": _pre_resume,
    "reload_config": _pre_reload,
    "rollback_config": _pre_rollback,
}

_VERIFIERS = {
    "get_state": _ver_get_state,
    "restart_camera": _ver_restart_camera,
    "restart_worker": _ver_restart_worker,
    "reconnect_serial": _ver_reconnect_serial,
    "set_inference_profile": _ver_set_profile,
    "set_locator_profile": _ver_set_locator,
    "pause_inspection": _ver_pause,
    "resume_inspection": _ver_resume,
    "reload_config": _ver_reload,
    "rollback_config": _ver_rollback,
}
