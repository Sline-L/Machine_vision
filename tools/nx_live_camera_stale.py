#!/usr/bin/env python3
"""Second NX live family: freeze replay/camera capture thread, not snapshot fields.

research injector only
requires GEARPRO_RESEARCH_INJECT=1
does not mutate health state
not enabled by default

No new recovery verb. L1 still uses restart_camera.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path("/home/jetson/Projects/edgemedic-live")
sys.path.insert(0, str(ROOT))
sys.path.append("/home/jetson/Projects/Machine_vision")

from edgemedic.client import ControlClient
from edgemedic.memory import EpisodeStore
from edgemedic.policy import classify_fault
from edgemedic.runtime import LoopState, run_once

CONTROL = "http://127.0.0.1:8787"
FREEZE = Path(os.getenv("GEARPRO_INJECT_FREEZE_CAMERA", "/tmp/gearpro-freeze-camera"))
OUT = ROOT / "results" / "second_live_family"


def wait_fault(client, name, timeout_s=8.0):
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        snap = client.get_state()
        last = {
            "fault": classify_fault(snap),
            "age_ms": (snap.get("camera") or {}).get("frame_age_ms"),
            "opened": (snap.get("camera") or {}).get("opened"),
            "seq": (snap.get("camera") or {}).get("frame_seq"),
            "active": (snap.get("mission") or {}).get("inspection_active"),
        }
        if last["fault"] == name:
            return last, snap
        time.sleep(0.2)
    return last, client.get_state()


def brief(cycle):
    return {
        "fault": cycle.get("fault"),
        "route_chosen": cycle.get("route_chosen") or cycle.get("layer"),
        "l1_eligible": cycle.get("l1_eligible"),
        "cooldown_active": cycle.get("cooldown_active"),
        "proposed_action": cycle.get("proposed_action"),
        "actually_executed": cycle.get("actually_executed"),
        "control_accepted": cycle.get("control_accepted"),
        "control_error": cycle.get("control_error"),
        "verify_level": cycle.get("verify_level"),
        "recovery_outcome": cycle.get("recovery_outcome"),
        "metrics": cycle.get("metrics"),
        "l2_invoked": bool(cycle.get("l2")),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    client = ControlClient(CONTROL, timeout=30.0)
    before = client.get_state()
    payload = {
        "injector": "freeze_capture_thread",
        "new_recovery_verb": False,
        "health_state_written": False,
        "before": {
            "active": (before.get("mission") or {}).get("inspection_active"),
            "profile": (before.get("mission") or {}).get("current_profile"),
            "age_ms": (before.get("camera") or {}).get("frame_age_ms"),
            "seq": (before.get("camera") or {}).get("frame_seq"),
            "backend": (before.get("locator") or {}).get("backend"),
        },
        "detected": None,
        "recover": None,
        "after": None,
        "second_live_family": False,
    }
    try:
        FREEZE.write_text("freeze\n", encoding="utf-8")
        detected, _snap = wait_fault(client, "CAMERA_STALE", timeout_s=8.0)
        payload["detected"] = detected
        if not detected or detected.get("fault") != "CAMERA_STALE":
            payload["error"] = "CAMERA_STALE not detected via normal inspection"
        else:
            cycle = run_once(client, state=LoopState(EpisodeStore(OUT / "episodes.json")), llm_url=None, force_layers=True)
            payload["recover"] = brief(cycle)
            payload["second_live_family"] = (
                cycle.get("fault") == "CAMERA_STALE"
                and cycle.get("recovery_outcome") == "RECOVERED"
                and (cycle.get("proposed_action") or {}).get("name") == "restart_camera"
            )
    finally:
        try:
            FREEZE.unlink()
        except FileNotFoundError:
            pass
        after = client.get_state()
        payload["after"] = {
            "active": (after.get("mission") or {}).get("inspection_active"),
            "profile": (after.get("mission") or {}).get("current_profile"),
            "age_ms": (after.get("camera") or {}).get("frame_age_ms"),
            "seq": (after.get("camera") or {}).get("frame_seq"),
            "backend": (after.get("locator") or {}).get("backend"),
            "loaded": (after.get("locator") or {}).get("loaded"),
            "fault": classify_fault(after),
        }
    (OUT / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("second_live_family") else 2


if __name__ == "__main__":
    raise SystemExit(main())
