#!/usr/bin/env python3
"""Fixed final demo. Three scenes only. Not a new experiment.

Requires GearPro with GEARPRO_RESEARCH_INJECT=1 for Demo B/C.
Demo C reads the frozen RQ2 episode store; it does not accumulate new science n.
"""

from __future__ import annotations

import json
import os
import shutil
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
LLM = "http://127.0.0.1:8080"
FREEZE = Path(os.getenv("GEARPRO_INJECT_FREEZE_CAMERA", "/tmp/gearpro-freeze-camera"))
FROZEN_EPISODES = ROOT / "results" / "rq2_camera_stale_memory" / "episodes.json"
OUT = ROOT / "results" / "final_demo"


def say(title, body):
    print("\n" + "=" * 60)
    print(title)
    print("-" * 60)
    print(body)
    print("=" * 60, flush=True)


def brief_state(snap):
    mission = snap.get("mission") or {}
    camera = snap.get("camera") or {}
    loc = snap.get("locator") or {}
    return {
        "fault": classify_fault(snap),
        "active": mission.get("inspection_active"),
        "profile": mission.get("current_profile"),
        "age_ms": camera.get("frame_age_ms"),
        "seq": camera.get("frame_seq"),
        "backend": loc.get("backend"),
    }


def cycle_brief(cycle):
    return {
        "fault": cycle.get("fault"),
        "route": cycle.get("route_chosen") or cycle.get("layer"),
        "action": cycle.get("proposed_action"),
        "l2_invoked": bool(cycle.get("l2")),
        "accepted": cycle.get("control_accepted"),
        "verify": cycle.get("verify_level"),
        "outcome": cycle.get("recovery_outcome"),
        "e2e_ms": (cycle.get("metrics") or {}).get("e2e_latency_ms"),
        "l2_ms": (cycle.get("metrics") or {}).get("l2_latency_ms"),
    }


def wait_fault(client, name, timeout_s=10.0):
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        last = brief_state(client.get_state())
        if last["fault"] == name:
            return last
        time.sleep(0.2)
    return last


def wait_running(client, timeout_s=12.0):
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        last = brief_state(client.get_state())
        age = last.get("age_ms")
        if last.get("active") and last.get("fault") != "CAMERA_STALE" and age is not None and age < 500:
            return last
        time.sleep(0.2)
    return last


def demo_a(client):
    say(
        "DEMO A — INSPECTION_PAUSED",
        "pause → detect → resume_inspection → mission verify",
    )
    wait_running(client)
    pause = client.post_action("pause_inspection", source="reflex", request_id="demo-a-pause", timeout=15.0)
    detected = wait_fault(client, "INSPECTION_PAUSED", timeout_s=6.0)
    cycle = run_once(client, state=LoopState(EpisodeStore(OUT / "demo_a_episodes.json")), llm_url=None, force_layers=True)
    after = brief_state(client.get_state())
    return {
        "pause_accepted": pause.get("accepted"),
        "detected": detected,
        "recover": cycle_brief(cycle),
        "after": after,
    }


def demo_b(client):
    say(
        "DEMO B — CAMERA_STALE (replay capture pipeline)",
        "freeze publish → frame_age grows → restart_camera → frames resume\n"
        "Not a physical /dev/video* unplug.",
    )
    wait_running(client)
    try:
        FREEZE.write_text("demo-b\n", encoding="utf-8")
        detected = wait_fault(client, "CAMERA_STALE", timeout_s=10.0)
        cycle = run_once(client, state=LoopState(EpisodeStore(OUT / "demo_b_episodes.json")), llm_url=None, force_layers=True)
    finally:
        try:
            FREEZE.unlink()
        except FileNotFoundError:
            pass
    after = wait_running(client)
    return {"detected": detected, "recover": cycle_brief(cycle), "after": after}


def demo_c(client):
    say(
        "DEMO C — CAMERA_STALE memory ON vs OFF",
        "Frozen RQ2 episodes. Controlled routing (L1 off).\n"
        "Do not read this as a new success-rate experiment.",
    )
    if not FROZEN_EPISODES.is_file():
        return {"error": f"missing frozen store {FROZEN_EPISODES}"}
    dest = OUT / "demo_c_memory_on.json"
    shutil.copyfile(FROZEN_EPISODES, dest)
    on_store = EpisodeStore(dest)
    off_store = EpisodeStore(OUT / "demo_c_memory_off.json")

    def one(store, label):
        wait_running(client)
        try:
            FREEZE.write_text("demo-c\n", encoding="utf-8")
            detected = wait_fault(client, "CAMERA_STALE", timeout_s=10.0)
            cycle = run_once(
                client,
                state=LoopState(store),
                llm_url=LLM,
                force_layers=True,
                disable_l1=True,
                l2_timeout=45.0,
            )
        finally:
            try:
                FREEZE.unlink()
            except FileNotFoundError:
                pass
        wait_running(client)
        return {"label": label, "detected": detected, "recover": cycle_brief(cycle)}

    return {"memory_on": one(on_store, "memory_on"), "memory_off": one(off_store, "memory_off")}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    client = ControlClient(CONTROL, timeout=30.0)
    say(
        "FEATURE DEVELOPMENT FREEZE — FINAL DEMO",
        "Unreliable 4B model inside a bounded runtime.\n"
        "V3-1 = shadow observation, drives_recovery=false.",
    )
    payload = {
        "demo_a": demo_a(client),
        "demo_b": demo_b(client),
        "demo_c": demo_c(client),
        "after": brief_state(client.get_state()),
    }
    (OUT / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
