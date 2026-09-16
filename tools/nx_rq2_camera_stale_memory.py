#!/usr/bin/env python3
"""CAMERA_STALE live memory ON/OFF on NX. Controlled routing, not natural runtime.

Does not add a third fault family. Does not hand-write episodes.
L1 is disabled only in Phase B so memory vs L2 is observable.
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
from edgemedic.memory import MIN_REPEATED_SUCCESS, EpisodeStore
from edgemedic.policy import classify_fault
from edgemedic.runtime import LoopState, run_once

LLM = "http://127.0.0.1:8080"
CONTROL = "http://127.0.0.1:8787"
FREEZE = Path(os.getenv("GEARPRO_INJECT_FREEZE_CAMERA", "/tmp/gearpro-freeze-camera"))
OUT = ROOT / "results" / "rq2_camera_stale_memory"


def wait_fault(client, name, timeout_s=10.0):
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
            return last
        time.sleep(0.2)
    return last


def wait_healthy(client, timeout_s=12.0):
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        snap = client.get_state()
        last = {
            "fault": classify_fault(snap),
            "age_ms": (snap.get("camera") or {}).get("frame_age_ms"),
            "active": (snap.get("mission") or {}).get("inspection_active"),
            "seq": (snap.get("camera") or {}).get("frame_seq"),
        }
        age = last["age_ms"]
        if last["active"] and last["fault"] not in {"CAMERA_STALE", "INSPECTION_PAUSED"} and age is not None and age < 500:
            return last
        time.sleep(0.2)
    return last


def cycle_brief(cycle):
    proposed = cycle.get("proposed_action") or {}
    return {
        "fault": cycle.get("fault"),
        "route_chosen": cycle.get("route_chosen") or cycle.get("layer"),
        "disable_l1": cycle.get("disable_l1"),
        "memory_available": cycle.get("memory_available"),
        "memory_suggested": cycle.get("memory_suggested"),
        "memory_hit": (cycle.get("route_chosen") or cycle.get("layer")) == "MEM",
        "l2_invoked": bool(cycle.get("l2")),
        "l2_proposal": None if not cycle.get("l2") else {
            "name": ((cycle.get("l2") or {}).get("action") or {}).get("name") or proposed.get("name"),
            "params": ((cycle.get("l2") or {}).get("action") or {}).get("params") or proposed.get("params"),
        },
        "proposed_action": proposed,
        "control_accepted": cycle.get("control_accepted"),
        "control_error": cycle.get("control_error"),
        "actually_executed": cycle.get("actually_executed"),
        "verify_level": cycle.get("verify_level"),
        "recovery_outcome": cycle.get("recovery_outcome"),
        "e2e_latency_ms": (cycle.get("metrics") or {}).get("e2e_latency_ms"),
        "l2_latency_ms": (cycle.get("metrics") or {}).get("l2_latency_ms"),
        "metrics": cycle.get("metrics"),
    }


def induce_and_recover(client, store, llm_url=None, disable_l1=False, l2_timeout=20.0, force_layers=True):
    wait_healthy(client)
    try:
        FREEZE.write_text("freeze\n", encoding="utf-8")
        detected = wait_fault(client, "CAMERA_STALE", timeout_s=10.0)
        if not detected or detected.get("fault") != "CAMERA_STALE":
            return {"detected": detected, "error": "CAMERA_STALE not detected", "recover": None}
        cycle = run_once(
            client,
            state=LoopState(store),
            llm_url=llm_url,
            force_layers=force_layers,
            disable_l1=disable_l1,
            l2_timeout=l2_timeout,
        )
        return {"detected": detected, "recover": cycle_brief(cycle)}
    finally:
        try:
            FREEZE.unlink()
        except FileNotFoundError:
            pass
        wait_healthy(client)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    client = ControlClient(CONTROL, timeout=30.0)
    store = EpisodeStore(OUT / "episodes.json")
    payload = {
        "experiment": "rq2_camera_stale_live_memory",
        "controlled_routing": True,
        "natural_runtime_routing": False,
        "third_fault_family": False,
        "hand_written_episodes": False,
        "v3_untouched": True,
        "min_repeated_success": MIN_REPEATED_SUCCESS,
        "phase_a_accumulate": [],
        "suggest_after_accumulate": None,
        "phase_b_pair": None,
        "effectiveness_claimed": False,
    }
    for i in range(MIN_REPEATED_SUCCESS):
        row = induce_and_recover(client, store, llm_url=None, disable_l1=False)
        payload["phase_a_accumulate"].append(row)
        recovered = (row.get("recover") or {}).get("recovery_outcome") == "RECOVERED"
        if not recovered:
            payload["error"] = f"phase_a trial {i} not RECOVERED"
            break
        time.sleep(1.0)
    payload["suggest_after_accumulate"] = store.suggest("CAMERA_STALE")
    verified = [item for item in store.episodes if item.get("verified")]
    payload["verified_success_count"] = len(verified)

    if payload["suggest_after_accumulate"] is not None:
        on_row = induce_and_recover(
            client, store, llm_url=LLM, disable_l1=True, l2_timeout=20.0
        )
        empty = EpisodeStore(OUT / "episodes_memory_off.json")
        off_row = induce_and_recover(
            client, empty, llm_url=LLM, disable_l1=True, l2_timeout=45.0
        )
        on_r = on_row.get("recover") or {}
        off_r = off_row.get("recover") or {}
        payload["phase_b_pair"] = {
            "note": "disable_l1=True is a controlled routing experiment, not natural runtime routing.",
            "memory_on": on_r,
            "memory_off": off_r,
            "memory_on_detected": on_row.get("detected"),
            "memory_off_detected": off_row.get("detected"),
        }
        payload["mechanism_pattern"] = {
            "memory_on_route": on_r.get("route_chosen"),
            "memory_off_route": off_r.get("route_chosen"),
            "memory_on_l2_invoked": on_r.get("l2_invoked"),
            "memory_off_l2_invoked": off_r.get("l2_invoked"),
            "memory_on_recovered": on_r.get("recovery_outcome") == "RECOVERED",
            "memory_off_recovered": off_r.get("recovery_outcome") == "RECOVERED",
            "effectiveness_claimed": False,
        }
    (OUT / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("suggest_after_accumulate") else 2


if __name__ == "__main__":
    raise SystemExit(main())
