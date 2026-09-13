"""Recoverable software fault injectors. They must not damage the OS."""

INJECTORS = (
    "force_worker_exception",
    "force_serial_failure",
    "freeze_camera_state",
    "inject_invalid_config",
    "inject_locator_latency",
    "inject_v5_latency",
    "inject_gpu_pressure_state",
    "inject_no_gear_anomaly",
)


SNAPSHOT_PATCHES = {
    "force_worker_exception": {"scratch_v5": {"error_count": 3, "health": 0.0}},
    "force_serial_failure": {"serial": {"connected": False, "consecutive_failures": 2, "health": 0.0, "last_send_ok": False}},
    "freeze_camera_state": {"camera": {"frame_age_ms": 2000, "health": 0.0, "opened": True}},
    "inject_invalid_config": {"mission": {"current_profile": "CLASSIFY_ONLY"}},
    "inject_locator_latency": {"locator": {"latency_ms": 180, "health": 0.3}},
    "inject_v5_latency": {"scratch_v5": {"total_latency_ms": 240, "health": 0.3}},
    "inject_gpu_pressure_state": {"system": {"gpu_util": 92.0, "temperature_c": 72.0}},
    "inject_no_gear_anomaly": {"locator": {"gears_found": 0, "health": 0.4}, "mission": {"output_valid": False, "utility": 0.4}},
}


def patch_snapshot(snapshot, injector):
    if injector not in SNAPSHOT_PATCHES:
        raise ValueError(f"未知注入器：{injector}")
    patched = dict(snapshot)
    for key, value in SNAPSHOT_PATCHES[injector].items():
        if isinstance(value, dict) and isinstance(patched.get(key), dict):
            patched[key] = {**patched[key], **value}
        else:
            patched[key] = value
    return patched


def reset_snapshot(baseline):
    return dict(baseline)
