"""Deterministic L0 Guardian and L1 Reflex. Unknown faults are left for L2 later."""

import time
import uuid

THERMAL_STOP_C = 80.0  # operational policy threshold, not a hardware absolute limit
STALE_MS = 1000.0
SEQ_STUCK_S = 2.0
COOLDOWN_S = 10.0
LOCATOR_SLOW_MS = 120.0
V5_SLOW_MS = 200.0


class Memory:
    def __init__(self):
        self.last_seq = None
        self.seq_stuck_since = None
        self.last_error_count = 0
        self.last_fire = {}
        self.now = time.monotonic

    def cooled(self, rule):
        last = self.last_fire.get(rule)
        if last is None:
            return True
        return self.now() - last >= COOLDOWN_S

    def mark(self, rule):
        self.last_fire[rule] = self.now()


def _action(name, params, rule, layer):
    return {
        "name": name,
        "params": params,
        "source": "reflex",
        "request_id": f"{layer}-{rule}-{uuid.uuid4().hex[:8]}",
        "rule": rule,
        "layer": layer,
    }


def _profile(snapshot):
    return (snapshot.get("mission") or {}).get("current_profile") or "FULL"


def _inspection_paused(snapshot):
    """NX Demo A family: camera healthy but mission not running (not SAFE_STOP)."""
    mission = snapshot.get("mission") or {}
    if mission.get("inspection_active"):
        return False
    camera = snapshot.get("camera") or {}
    if not camera.get("opened"):
        return False
    age = camera.get("frame_age_ms")
    if age is not None and float(age) > STALE_MS:
        return False
    return True


def _camera_stale(snapshot, memory):
    camera = snapshot.get("camera") or {}
    if not camera.get("opened"):
        mission = snapshot.get("mission") or {}
        if mission.get("inspection_active"):
            return False
        return True
    age = camera.get("frame_age_ms")
    if age is not None and age > STALE_MS:
        return True
    seq = int(camera.get("frame_seq") or 0)
    now = memory.now()
    if memory.last_seq is None or seq != memory.last_seq:
        memory.last_seq = seq
        memory.seq_stuck_since = now
        return False
    if memory.seq_stuck_since is None:
        memory.seq_stuck_since = now
        return False
    return (now - memory.seq_stuck_since) >= SEQ_STUCK_S


def classify_fault(snapshot, memory=None):
    """Stable episode key. None means no fault for memory/L2."""
    memory = memory or Memory()
    profile = _profile(snapshot)
    temp = (snapshot.get("system") or {}).get("temperature_c")
    if temp is not None and float(temp) >= THERMAL_STOP_C and profile != "SAFE_STOP":
        return "THERMAL_STOP"
    if profile == "SAFE_STOP":
        return None
    if _inspection_paused(snapshot):
        return "INSPECTION_PAUSED"
    if _camera_stale(snapshot, memory):
        return "CAMERA_STALE"
    errors = int((snapshot.get("scratch_v5") or {}).get("error_count") or 0)
    if errors > memory.last_error_count:
        return "WORKER_FAIL"
    serial = snapshot.get("serial") or {}
    if int(serial.get("consecutive_failures") or 0) >= 1 or (
        not serial.get("connected") and serial.get("health") is not None and float(serial.get("health")) < 1.0
    ):
        return "SERIAL_FAIL"
    locator_ms = (snapshot.get("locator") or {}).get("latency_ms")
    v5_ms = (snapshot.get("scratch_v5") or {}).get("total_latency_ms")
    locator_slow = locator_ms is not None and locator_ms >= LOCATOR_SLOW_MS
    v5_slow = v5_ms is not None and v5_ms >= V5_SLOW_MS
    if _profile(snapshot) == "FULL" and v5_slow:
        return "V5_OVERLOAD"
    if _profile(snapshot) == "FULL" and locator_slow:
        return "LOCATOR_OVERLOAD"
    for node in ("camera", "locator", "scratch_v5", "serial"):
        health = (snapshot.get(node) or {}).get("health")
        if health is not None and float(health) <= 0.2:
            return "UNKNOWN_" + node.upper()
    return None


def is_anomaly(snapshot, memory=None):
    return classify_fault(snapshot, memory) is not None


def decide(snapshot, memory=None):
    """Return at most one Control API action, L0 before L1. No LLM."""
    memory = memory or Memory()
    profile = _profile(snapshot)
    system = snapshot.get("system") or {}
    temp = system.get("temperature_c")

    if temp is not None and float(temp) >= THERMAL_STOP_C and profile != "SAFE_STOP":
        if memory.cooled("THERMAL_STOP"):
            memory.mark("THERMAL_STOP")
            return _action("set_inference_profile", {"profile": "SAFE_STOP"}, "THERMAL_STOP", "L0")
        return None

    if profile == "SAFE_STOP":
        return None

    if _inspection_paused(snapshot) and memory.cooled("INSPECTION_PAUSED"):
        memory.mark("INSPECTION_PAUSED")
        return _action("resume_inspection", {}, "INSPECTION_PAUSED", "L1")

    if _camera_stale(snapshot, memory) and memory.cooled("CAMERA_STALE"):
        memory.mark("CAMERA_STALE")
        return _action("restart_camera", {}, "CAMERA_STALE", "L1")

    errors = int((snapshot.get("scratch_v5") or {}).get("error_count") or 0)
    if errors > memory.last_error_count:
        if memory.cooled("WORKER_FAIL"):
            memory.last_error_count = errors
            memory.mark("WORKER_FAIL")
            return _action("restart_worker", {}, "WORKER_FAIL", "L1")
        return None

    serial = snapshot.get("serial") or {}
    serial_fail = int(serial.get("consecutive_failures") or 0) >= 1 or (
        not serial.get("connected") and serial.get("health") is not None and float(serial.get("health")) < 1.0
    )
    if serial_fail and memory.cooled("SERIAL_FAIL"):
        memory.mark("SERIAL_FAIL")
        return _action("reconnect_serial", {}, "SERIAL_FAIL", "L1")

    v5_ms = (snapshot.get("scratch_v5") or {}).get("total_latency_ms")
    v5_slow = v5_ms is not None and v5_ms >= V5_SLOW_MS
    if v5_slow and profile == "FULL" and memory.cooled("V5_OVERLOAD"):
        memory.mark("V5_OVERLOAD")
        return _action("set_inference_profile", {"profile": "SPARSE"}, "V5_OVERLOAD", "L1")

    return None
