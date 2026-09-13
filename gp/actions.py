"""Whitelist, preconditions, and verify rules for Control API v1."""

from .profiles import ProfileError, locator_path_for, spec as profile_spec
from .verify import assess as assess_verify
from .verify import config_verified

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
    "apply_settings",
    "use_camera",
    "use_video",
    "reset_stats",
)

HUMAN_ONLY = frozenset(("apply_settings", "use_camera", "use_video", "reset_stats"))

SOURCES = ("human", "reflex", "memory", "reasoner")
AGENT_SOURCES = ("reflex", "memory", "reasoner")
AUTHORITIES = ("human", "agent")
LKG_ACTIONS = frozenset(
    ("set_inference_profile", "set_locator_profile", "reload_config", "rollback_config", "apply_settings")
)

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
    "apply_settings": {"level": 2, "timeout_s": 90, "retry": 0, "implemented": True},
    "use_camera": {"level": 2, "timeout_s": 30, "retry": 0, "implemented": True},
    "use_video": {"level": 2, "timeout_s": 30, "retry": 0, "implemented": True},
    "reset_stats": {"level": 1, "timeout_s": 5, "retry": 0, "implemented": True},
}

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
    request_id = body.get("request_id")
    if not request_id or not isinstance(request_id, str):
        raise ActionError("缺少 request_id")
    return {
        "name": name,
        "params": params,
        "declared_source": body.get("source"),
        "request_id": request_id,
    }


def bind_source(declared, authority):
    """Authority is assigned by the server. HTTP callers cannot become human."""
    if authority not in AUTHORITIES:
        raise ActionError("authority 必须由服务器赋值")
    if authority == "human":
        return "human"
    if declared in AGENT_SOURCES:
        return declared
    return "reflex"


def accept(name, params, snapshot, extras=None, source=None):
    extras = extras or {}
    source = source or extras.get("source")
    meta = SPECS.get(name)
    if meta is None:
        return False, f"未知动作：{name}"
    if not meta.get("implemented"):
        return False, f"动作 {name} 尚未实现"
    if name in HUMAN_ONLY:
        if extras.get("authority") == "agent" or source != "human":
            return False, f"{name} 仅允许人工操作"
    checker = _PRECONDITIONS.get(name)
    if checker is None:
        return True, None
    return checker(params, snapshot, extras)


def verify(name, params, before, after, extras=None):
    extras = extras or {}
    level, reason = assess_verify(name, params, before, after, extras)
    if not config_verified(level):
        return False, reason
    return True, reason


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


def _pre_apply_settings(params, snapshot, extras):
    del snapshot, extras
    from .config import AppConfig

    try:
        AppConfig().update(params or {})
    except ValueError as exc:
        return False, str(exc)
    return True, None


def _pre_use_video(params, snapshot, extras):
    del snapshot, extras
    path = params.get("path")
    if not path:
        return False, "缺少 params.path"
    return True, None


def _pre_pause(params, snapshot, extras):
    del params
    if extras.get("source") == "human":
        return True, None
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
    "apply_settings": _pre_apply_settings,
    "use_video": _pre_use_video,
}
