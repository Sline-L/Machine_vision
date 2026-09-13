"""Load and score EdgeMedicBench cases. No live LLM."""

from pathlib import Path
import json

from edgemedic.policy import Memory, classify_fault, decide
from edgemedic.reasoner import parse_tool_json

CASES_DIR = Path(__file__).resolve().parent / "cases"


def default_snapshot():
    return {
        "schema_version": "system-snapshot.v1",
        "system": {
            "cpu_percent": 20.0,
            "ram_used_mb": 1024.0,
            "ram_percent": 30.0,
            "gpu_util": None,
            "gpu_mem_mb": None,
            "temperature_c": 55.0,
            "power_w": None,
        },
        "camera": {
            "device": "/dev/video0",
            "opened": True,
            "frame_seq": 40,
            "actual_fps": 20.0,
            "frame_age_ms": 40,
            "read_failures": 0,
            "health": 1.0,
        },
        "locator": {
            "backend": "pt",
            "loaded": True,
            "latency_ms": 18.0,
            "gears_found": 1,
            "confidence_mean": 0.9,
            "health": 1.0,
        },
        "scratch_v5": {
            "profile": "FULL",
            "total_latency_ms": 50.0,
            "error_count": 0,
            "health": 1.0,
            "detector_enabled": True,
            "classifiers_enabled": True,
        },
        "serial": {
            "port": "/dev/ttyHS1",
            "connected": True,
            "last_send_ok": True,
            "consecutive_failures": 0,
            "health": 1.0,
        },
        "mission": {
            "inspection_active": True,
            "output_valid": True,
            "current_profile": "FULL",
            "utility": 1.0,
        },
    }


def merge_state(overrides):
    snapshot = default_snapshot()
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(snapshot.get(key), dict):
            snapshot[key] = {**snapshot[key], **value}
        else:
            snapshot[key] = value
    return snapshot


def load_cases(directory=CASES_DIR):
    cases = []
    for path in sorted(Path(directory).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["_path"] = str(path)
        cases.append(payload)
    return cases


def _matches(action, spec):
    if spec is None:
        return action is None
    if action is None:
        return False
    if spec.get("tool") and action.get("name") != spec.get("tool"):
        return False
    if spec.get("name") and action.get("name") != spec.get("name"):
        return False
    params = spec.get("params")
    if params:
        actual = action.get("params") or {}
        for key, value in params.items():
            if actual.get(key) != value:
                return False
    return True


def score_case(case, memory=None):
    snapshot = merge_state(case.get("state"))
    memory = memory or Memory()
    fault = classify_fault(snapshot, memory)
    action = decide(snapshot, memory)
    expected_fault = case.get("fault")
    fault_ok = expected_fault is None or fault == expected_fault
    layer = case.get("expected_layer")
    layer_ok = True
    if layer == "L1":
        layer_ok = action is not None and action.get("layer") == "L1"
    elif layer == "none":
        layer_ok = action is None

    acceptable = case.get("acceptable_actions") or []
    abstain_allowed = bool(case.get("abstain_allowed"))
    l1_ok = True
    if acceptable and layer == "L1":
        l1_ok = any(_matches(action, spec) for spec in acceptable)
    elif layer == "none":
        l1_ok = action is None

    llm_text = case.get("llm_output")
    parsed = parse_tool_json(llm_text) if llm_text is not None else None
    l2_ok = True
    if llm_text is not None:
        if parsed is None:
            l2_ok = abstain_allowed or case.get("expect_l2") == "abstain"
        elif case.get("expect_l2") == "abstain":
            l2_ok = False
        elif acceptable:
            l2_ok = any(_matches(parsed, spec) for spec in acceptable)
        forbidden = case.get("forbidden_actions") or []
        if any(_matches(parsed, spec) for spec in forbidden):
            l2_ok = False

    ok = fault_ok and layer_ok and l1_ok and l2_ok
    return {
        "ok": ok,
        "fault": fault,
        "l1": None if action is None else {"name": action.get("name"), "params": action.get("params"), "layer": action.get("layer")},
        "l2": parsed,
        "fault_ok": fault_ok,
        "l1_ok": l1_ok and layer_ok,
        "l2_ok": l2_ok,
    }
