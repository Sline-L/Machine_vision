"""Incident records. Diagnosis is not exclusive to L2."""


def evidence_from(snapshot):
    camera = snapshot.get("camera") or {}
    locator = snapshot.get("locator") or {}
    v5 = snapshot.get("scratch_v5") or {}
    serial = snapshot.get("serial") or {}
    system = snapshot.get("system") or {}
    mission = snapshot.get("mission") or {}
    return {
        "frame_age_ms": camera.get("frame_age_ms"),
        "frame_seq": camera.get("frame_seq"),
        "camera_opened": camera.get("opened"),
        "locator_latency_ms": locator.get("latency_ms"),
        "locator_backend": locator.get("backend"),
        "scratch_latency_ms": v5.get("total_latency_ms"),
        "scratch_error_count": v5.get("error_count"),
        "serial_connected": serial.get("connected"),
        "serial_failures": serial.get("consecutive_failures"),
        "gpu_util": system.get("gpu_util"),
        "gpu_mem_mb": system.get("gpu_mem_mb"),
        "power_w": system.get("power_w"),
        "temperature_c": system.get("temperature_c"),
        "current_profile": mission.get("current_profile"),
        "utility": mission.get("utility"),
    }


def build_incident(fault, snapshot, action=None, layer=None, confidence=1.0):
    action = action or {}
    return {
        "fault": fault,
        "diagnosis": _diagnosis(fault),
        "evidence": evidence_from(snapshot),
        "confidence": confidence,
        "selected_action": action.get("name"),
        "params": action.get("params") or {},
        "decision_layer": layer or action.get("layer"),
    }


def _diagnosis(fault):
    mapping = {
        "THERMAL_STOP": "operational temperature policy threshold exceeded",
        "CAMERA_STALE": "camera stream is stale or closed",
        "INSPECTION_PAUSED": "inspection is paused while camera remains available",
        "WORKER_FAIL": "inspection worker error count increased",
        "SERIAL_FAIL": "serial port disconnected or send failed",
        "LOCATOR_OVERLOAD": "locator latency high while Scratch V5 is normal",
        "V5_OVERLOAD": "Scratch V5 latency high",
        "OVERLOAD_SPARSE": "inference overload",
    }
    if not fault:
        return "no fault"
    if fault.startswith("UNKNOWN_"):
        return "subsystem health collapsed without a named rule"
    return mapping.get(fault, fault)
