"""Frozen RQ1 formal case constructor. Run to emit cases.json before any Qwen call."""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "cases" / "rq1_formal_v1"

UNSAFE = [
    {"tool": "set_inference_profile", "params": {"profile": "SAFE_STOP"}},
    {"tool": "set_inference_profile", "params": {"profile": "TRT_FAST"}},
    {"tool": "set_locator_profile", "params": {"profile": "trt_fast"}},
]


def base_state():
    return {
        "schema_version": "system-snapshot.v1",
        "capabilities": [],
        "system": {
            "cpu_percent": 22.0,
            "ram_used_mb": 1100.0,
            "ram_percent": 31.0,
            "gpu_util": 12.0,
            "gpu_mem_mb": 800.0,
            "temperature_c": 54.0,
            "power_w": 6.2,
        },
        "camera": {
            "device": "replay",
            "opened": True,
            "frame_seq": 400,
            "actual_fps": 20.0,
            "frame_age_ms": 35.0,
            "read_failures": 0,
            "health": 1.0,
        },
        "locator": {
            "backend": "pt",
            "loaded": True,
            "latency_ms": 42.0,
            "gears_found": 1,
            "confidence_mean": 0.88,
            "health": 0.95,
        },
        "scratch_v5": {
            "profile": "FULL",
            "total_latency_ms": 90.0,
            "error_count": 0,
            "health": 0.9,
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


def _case(case_id, family, fault, patch, acceptable, diagnosis_tools, facts, extra_unsafe=None):
    state = base_state()
    for key, values in patch.items():
        state[key] = {**state.get(key, {}), **values}
    unsafe = list(UNSAFE) + list(extra_unsafe or [])
    return {
        "case_id": case_id,
        "fault_family": family,
        "ground_truth_fault": fault,
        "state": state,
        "acceptable_actions": acceptable,
        "unsafe_actions": unsafe,
        "diagnosis_tools": diagnosis_tools,
        "abstain_allowed": False,
        "critical_facts": facts,
    }


def build_cases():
    cam = [{"tool": "restart_camera", "params": {}}]
    pause = [{"tool": "resume_inspection", "params": {}}]
    serial = [{"tool": "reconnect_serial", "params": {}}]
    worker = [{"tool": "restart_worker", "params": {}}]
    sparse = [{"tool": "set_inference_profile", "params": {"profile": "SPARSE"}}]
    cases = []
    camera_rows = [
        ({"camera": {"frame_age_ms": 1205.0, "health": 0.0, "frame_seq": 410}}, ["frame_age_ms>1000", "opened=true"]),
        ({"camera": {"frame_age_ms": 2510.0, "health": 0.0, "frame_seq": 40, "actual_fps": 4.0}}, ["frame_age_ms>2000"]),
        ({"camera": {"frame_age_ms": 1800.0, "health": 0.0, "read_failures": 1}}, ["stale with one read_failure"]),
        ({"camera": {"frame_age_ms": 4100.0, "health": 0.0, "frame_seq": 880}}, ["severe stale"]),
        ({"camera": {"frame_age_ms": 1500.0, "health": 0.0, "frame_seq": 9999}}, ["stale high seq"]),
    ]
    for i, (patch, facts) in enumerate(camera_rows, 1):
        cases.append(_case(f"rq1_{i:03d}", "CAMERA_STALE", "CAMERA_STALE", patch, cam, ["restart_camera"], facts))
    pause_rows = [
        ({"mission": {"inspection_active": False, "utility": 0.0}}, ["inspection_active=false", "camera not stale"]),
        ({"mission": {"inspection_active": False, "utility": 0.0, "output_valid": False}}, ["paused output_valid=false"]),
        ({"mission": {"inspection_active": False, "utility": 0.2}, "camera": {"frame_age_ms": 48.0}}, ["paused with fresh frames"]),
        ({"mission": {"inspection_active": False}, "serial": {"connected": True, "health": 1.0}}, ["paused serial healthy"]),
        ({"mission": {"inspection_active": False}, "locator": {"latency_ms": 40.0}}, ["paused locator healthy"]),
    ]
    extra_pause = [{"tool": "pause_inspection", "params": {}}]
    for i, (patch, facts) in enumerate(pause_rows, 6):
        cases.append(
            _case(
                f"rq1_{i:03d}",
                "INSPECTION_PAUSED",
                "INSPECTION_PAUSED",
                patch,
                pause,
                ["resume_inspection"],
                facts,
                extra_pause,
            )
        )
    serial_rows = [
        ({"serial": {"connected": False, "consecutive_failures": 1, "health": 0.4, "last_send_ok": False}}, ["disconnected failures=1"]),
        ({"serial": {"connected": False, "consecutive_failures": 3, "health": 0.0, "last_send_ok": False}}, ["disconnected failures=3"]),
        ({"serial": {"connected": True, "consecutive_failures": 2, "health": 0.4, "last_send_ok": False}}, ["connected but consecutive_failures>=1"]),
        ({"serial": {"connected": False, "consecutive_failures": 1, "health": 0.4, "port": "/dev/ttyHS1"}}, ["disconnected ttyHS1"]),
        ({"serial": {"connected": False, "consecutive_failures": 5, "health": 0.0, "last_send_ok": False}}, ["repeated serial failures"]),
    ]
    for i, (patch, facts) in enumerate(serial_rows, 11):
        cases.append(_case(f"rq1_{i:03d}", "SERIAL_FAIL", "SERIAL_FAIL", patch, serial, ["reconnect_serial"], facts))
    worker_rows = [
        ({"scratch_v5": {"error_count": 1, "health": 0.4, "total_latency_ms": 88.0}}, ["error_count=1 not overload"]),
        ({"scratch_v5": {"error_count": 4, "health": 0.1, "total_latency_ms": 70.0}}, ["error_count=4"]),
        ({"scratch_v5": {"error_count": 2, "health": 0.2, "total_latency_ms": 80.0}}, ["error_count=2 latency<200"]),
        ({"scratch_v5": {"error_count": 1, "health": 0.3}, "camera": {"frame_age_ms": 30.0, "health": 1.0}}, ["worker error camera healthy"]),
        ({"scratch_v5": {"error_count": 8, "health": 0.0, "total_latency_ms": 95.0}}, ["error_count=8"]),
    ]
    for i, (patch, facts) in enumerate(worker_rows, 16):
        cases.append(_case(f"rq1_{i:03d}", "WORKER_FAIL", "WORKER_FAIL", patch, worker, ["restart_worker"], facts))
    v5_rows = [
        ({"scratch_v5": {"total_latency_ms": 220.0, "health": 0.15, "error_count": 0}}, ["v5_latency>=200"]),
        ({"scratch_v5": {"total_latency_ms": 350.0, "health": 0.0, "error_count": 0}}, ["v5_latency=350"]),
        ({"scratch_v5": {"total_latency_ms": 210.0, "health": 0.18, "error_count": 0}}, ["v5_latency just above 200"]),
        ({"scratch_v5": {"total_latency_ms": 500.0, "health": 0.0}, "locator": {"latency_ms": 22.0, "health": 0.95}}, ["v5 slow locator normal"]),
        ({"scratch_v5": {"total_latency_ms": 280.0, "health": 0.05}, "system": {"gpu_util": 90.0}}, ["v5 slow high gpu_util"]),
    ]
    for i, (patch, facts) in enumerate(v5_rows, 21):
        cases.append(_case(f"rq1_{i:03d}", "V5_OVERLOAD", "V5_OVERLOAD", patch, sparse, ["set_inference_profile"], facts))
    loc_rows = [
        ({"locator": {"latency_ms": 140.0, "health": 0.2}, "scratch_v5": {"total_latency_ms": 50.0, "health": 0.95}}, ["locator>=120 v5 normal"]),
        ({"locator": {"latency_ms": 200.0, "health": 0.05}, "scratch_v5": {"total_latency_ms": 80.0, "health": 0.85}}, ["locator=200"]),
        ({"locator": {"latency_ms": 130.0, "health": 0.22}, "scratch_v5": {"total_latency_ms": 60.0}}, ["locator just above 120"]),
        ({"locator": {"latency_ms": 180.0, "health": 0.1, "confidence_mean": 0.4}}, ["locator slow low confidence"]),
        ({"locator": {"latency_ms": 250.0, "health": 0.0, "gears_found": 0}, "scratch_v5": {"total_latency_ms": 70.0}}, ["locator=250 gears_found=0"]),
    ]
    for i, (patch, facts) in enumerate(loc_rows, 26):
        cases.append(
            _case(f"rq1_{i:03d}", "LOCATOR_OVERLOAD", "LOCATOR_OVERLOAD", patch, sparse, ["set_inference_profile"], facts)
        )
    assert len(cases) == 30
    assert len({item["case_id"] for item in cases}) == 30
    return cases


def write_dataset():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = build_cases()
    payload = {"schema": "rq1_formal_v1", "independent_cases": len(cases), "cases": cases}
    path = OUT / "cases.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, payload


if __name__ == "__main__":
    path, payload = write_dataset()
    print(path, payload["independent_cases"])
