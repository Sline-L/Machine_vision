"""SystemSnapshot builders. Fill only measured fields; leave GPU null if unknown."""

from datetime import datetime, timezone
from pathlib import Path

from .profiles import mission_utility


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def locator_backend(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".engine":
        return "engine"
    if suffix == ".pt":
        return "pt"
    return "none"


def camera_health(opened, frame_age_ms, read_failures):
    if not opened:
        return 0.0
    if frame_age_ms is None:
        return 0.2
    if frame_age_ms > 1000 or read_failures > 8:
        return 0.0
    if frame_age_ms > 200:
        return max(0.2, 1.0 - (frame_age_ms - 200) / 800)
    return 1.0 if read_failures == 0 else 0.7


def latency_health(latency_ms, good, bad):
    if latency_ms is None:
        return 0.0
    if latency_ms <= good:
        return 1.0
    if latency_ms >= bad:
        return 0.0
    return max(0.0, 1.0 - (latency_ms - good) / (bad - good))


def serial_health(connected, consecutive_failures, serial_required):
    if not serial_required:
        return 1.0
    if consecutive_failures >= 3:
        return 0.0
    if not connected or consecutive_failures:
        return 0.4
    return 1.0


def read_system_metrics():
    metrics = {
        "cpu_percent": 0.0,
        "ram_used_mb": 0.0,
        "ram_percent": 0.0,
        "gpu_util": None,
        "gpu_mem_mb": None,
        "temperature_c": None,
        "power_w": None,
    }
    try:
        import psutil
        vm = psutil.virtual_memory()
        metrics["cpu_percent"] = float(psutil.cpu_percent(interval=None))
        metrics["ram_used_mb"] = float(vm.used) / (1024 * 1024)
        metrics["ram_percent"] = float(vm.percent)
    except Exception:
        meminfo = Path("/proc/meminfo")
        if meminfo.is_file():
            values = {}
            for line in meminfo.read_text(encoding="utf-8").splitlines():
                parts = line.replace(":", " ").split()
                if len(parts) >= 2:
                    values[parts[0]] = float(parts[1])
            total = values.get("MemTotal", 0.0)
            available = values.get("MemAvailable", values.get("MemFree", 0.0))
            used = max(0.0, total - available)
            metrics["ram_used_mb"] = used / 1024.0
            if total:
                metrics["ram_percent"] = used / total * 100.0
    thermal = Path("/sys/class/thermal/thermal_zone0/temp")
    if thermal.is_file():
        try:
            metrics["temperature_c"] = float(thermal.read_text().strip()) / 1000.0
        except ValueError:
            pass
    return metrics


def build_snapshot(
    config,
    frame_store,
    camera_opened,
    camera_device,
    read_failures,
    actual_fps,
    serial,
    last_result=None,
    inspection_active=False,
    scratch_errors=0,
    schema_version="system-snapshot.v2",
    specialist_status=None,
    inspect_count=None,
    last_error_source="unknown",
):
    if schema_version not in {"system-snapshot.v1", "system-snapshot.v2"}:
        raise ValueError(f"不支持的快照版本：{schema_version}")
    packet = frame_store.read() if frame_store is not None else None
    sequence = 0 if packet is None else packet.sequence
    age_ms = None if packet is None else packet.age_ms
    backend = locator_backend(config.locator_model)
    locator_loaded = last_result is not None or inspection_active
    locator_ms = None if last_result is None else last_result.locator_latency_ms
    v5_total = None if last_result is None else last_result.scratch_latency_ms
    missing_total = None if last_result is None else last_result.missing_hole_latency_ms
    gears = 0 if last_result is None else len(last_result.observations)
    confs = [] if last_result is None else [item.location_confidence for item in last_result.observations]
    serial_required = bool(getattr(config, "serial_enabled", True))
    connected = bool(serial.is_open) if serial is not None else False
    failures = 0 if serial is None else serial.consecutive_failures
    last_ok = None if serial is None else serial.last_send_ok
    cam_h = camera_health(camera_opened, age_ms, read_failures)
    loc_h = 0.0 if not locator_loaded else latency_health(locator_ms, 40, 120)
    if locator_ms is None and locator_loaded:
        loc_h = 0.5
    v5_h = 0.0 if last_result is None else latency_health(v5_total, 80, 200)
    if last_result is None and inspection_active:
        v5_h = 0.5
    missing_h = 0.0 if last_result is None else latency_health(missing_total, 80, 200)
    if last_result is None and inspection_active:
        missing_h = 0.5
    ser_h = serial_health(connected, failures, serial_required)
    snapshot = {
        "schema_version": schema_version,
        "timestamp": utc_now(),
        "system": read_system_metrics(),
        "camera": {
            "device": camera_device,
            "opened": bool(camera_opened),
            "frame_seq": int(sequence),
            "actual_fps": float(actual_fps),
            "frame_age_ms": age_ms,
            "read_failures": int(read_failures),
            "health": round(cam_h, 4),
        },
        "locator": {
            "backend": backend,
            "loaded": bool(locator_loaded),
            "latency_ms": locator_ms,
            "gears_found": int(gears),
            "confidence_mean": None if not confs else round(sum(confs) / len(confs), 4),
            "health": round(loc_h, 4),
        },
        "serial": {
            "port": config.serial_port,
            "connected": connected,
            "last_send_ok": last_ok,
            "consecutive_failures": int(failures),
            "last_error": None if serial is None else serial.last_error,
            "health": round(ser_h, 4),
        },
        "mission": {
            "inspection_active": bool(inspection_active),
            "output_valid": last_result is not None,
            "inspection_rate_hz": None,
            "current_profile": getattr(config, "inference_profile", "FULL"),
            "inspection_count": None if inspect_count is None else int(inspect_count),
            "utility": mission_utility(
                getattr(config, "inference_profile", "FULL"),
                last_result is not None,
                (not serial_required) or last_ok is True,
            ),
        },
    }
    status = specialist_status or {}
    scratch = _specialist_block(
        "scratch_v5",
        last_result,
        v5_total,
        v5_h,
        status,
        last_error_source,
        scratch_errors,
        include_shared_error_count=True,
        latency_fields={
            "classifier1_latency_ms": None if last_result is None else last_result.classifier1_latency_ms,
            "classifier2_latency_ms": None if last_result is None else last_result.classifier2_latency_ms,
            "detector_latency_ms": None if last_result is None else last_result.detector_latency_ms,
            "fusion_latency_ms": None if last_result is None else last_result.fusion_latency_ms,
        },
    )
    if schema_version == "system-snapshot.v1":
        snapshot["scratch_v5"] = scratch
        return snapshot

    missing = _specialist_block(
        "missing_hole_v1",
        last_result,
        missing_total,
        missing_h,
        status,
        last_error_source,
        scratch_errors,
        include_shared_error_count=False,
        latency_fields={
            "classifier1_latency_ms": None if last_result is None else last_result.missing_hole_classifier1_latency_ms,
            "classifier2_latency_ms": None if last_result is None else last_result.missing_hole_classifier2_latency_ms,
            "detector_latency_ms": None if last_result is None else last_result.missing_hole_detector_latency_ms,
            "fusion_latency_ms": None if last_result is None else last_result.missing_hole_fusion_latency_ms,
        },
    )
    total = None if last_result is None else v5_total + missing_total
    snapshot["specialists"] = {"scratch_v5": scratch, "missing_hole_v1": missing}
    snapshot["inference"] = {
        "total_specialist_latency_ms": total,
        "health": round(min(v5_h, missing_h), 4),
        "error_count": int(scratch_errors),
        "error_attribution": "shared_worker" if last_error_source == "unknown" else last_error_source,
    }
    return snapshot


def _specialist_block(
    name,
    last_result,
    total_latency_ms,
    health,
    status,
    last_error_source,
    shared_worker_errors,
    include_shared_error_count,
    latency_fields,
):
    load = (status or {}).get(name, "unknown")
    if load == "loaded":
        loaded = True
    elif load == "failed":
        loaded = False
    else:
        loaded = None
    infer_ok = None if last_result is None else total_latency_ms is not None
    if loaded is False:
        infer_ok = False
    error_state = "unknown"
    independent_count = None
    if load == "failed":
        error_state = "load_failed"
        independent_count = 1
    elif last_error_source == name:
        error_state = "infer_failed"
        independent_count = 1
    elif loaded is True and last_result is not None:
        error_state = "none"
        independent_count = 0
    block = {
        "profile": "FULL",
        **latency_fields,
        "total_latency_ms": total_latency_ms,
        "detector_enabled": True,
        "classifiers_enabled": True,
        "health": round(health, 4),
        "loaded": loaded,
        "infer_ok": infer_ok,
        "last_valid_output": bool(last_result is not None and total_latency_ms is not None),
        "last_output_frame_seq": None if last_result is None else last_result.source_frame_seq,
        "error_state": error_state,
        "error_count": int(shared_worker_errors) if include_shared_error_count else independent_count,
    }
    return block
