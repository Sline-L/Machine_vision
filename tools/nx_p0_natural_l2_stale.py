#!/usr/bin/env python3
"""Natural L2 execute on LIVE isolated Replay CAMERA_STALE.

Does not use disable_l1. L1 is skipped only via existing Memory cooldown.
Does not overlay a healthy live camera as stale — freeze must be real.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edgemedic.adapter import adapt_snapshot
from edgemedic.client import ControlClient
from edgemedic.policy import Memory, classify_fault, decide
from edgemedic.runtime import EXECUTE_REPLAY, LoopState, make_client, run_once


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-url", required=True)
    parser.add_argument("--llm-url", default="http://127.0.0.1:8080")
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--wait-s", type=float, default=8.0)
    args = parser.parse_args(argv)
    if "8787" in args.control_url:
        raise SystemExit("refusing mutate against :8787")

    client = ControlClient(args.control_url, timeout=30.0)
    deadline = time.time() + args.wait_s
    snap = None
    fault = None
    while time.time() < deadline:
        snap = adapt_snapshot(client.get_state())
        fault = classify_fault(snap, Memory())
        if fault == "CAMERA_STALE":
            break
        time.sleep(0.5)
    evidence = {
        "protocol": "p0-natural-l2-stale-v1",
        "control_url": args.control_url,
        "live_fault": fault,
        "camera": (snap or {}).get("camera"),
        "disable_l1": False,
    }
    if fault != "CAMERA_STALE":
        evidence["result"] = "NOT_RUN"
        evidence["reason"] = "live snapshot never reached CAMERA_STALE (freeze inject missing or research inject off)"
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"result": evidence["result"], "reason": evidence["reason"]}, indent=2))
        return 2

    mem = Memory()
    mem.last_fire["CAMERA_STALE"] = mem.now()
    evidence["l1_on_cooldown"] = decide(snap, mem) is None
    evidence["l1_would_fire_without_cooldown"] = decide(snap, Memory()) is not None

    state = LoopState()
    state.memory = mem
    cycle = run_once(
        make_client(args.control_url, EXECUTE_REPLAY),
        state,
        llm_url=args.llm_url,
        execution_mode=EXECUTE_REPLAY,
        disable_l1=False,
        disable_memory=True,
        force_l2=False,
        l2_timeout=90.0,
    )
    evidence["cycle"] = cycle
    claims = {
        "route_is_l2": (cycle.get("route") or {}).get("selected") == "L2",
        "disable_l1_flag": (cycle.get("route") or {}).get("disable_l1"),
        "why_l2": (cycle.get("route") or {}).get("why_l2"),
        "l2_invoked": bool((cycle.get("l2") or {}).get("invoked")),
        "model": (cycle.get("l2") or {}).get("model"),
        "raw_preview": (cycle.get("l2") or {}).get("raw_preview"),
        "proposed": cycle.get("proposed_action"),
        "authority": cycle.get("authority_decision"),
        "actually_executed": bool(cycle.get("actually_executed")),
        "verify_level": cycle.get("verify_level"),
        "recovery_outcome": cycle.get("recovery_outcome"),
        "control_error": (cycle.get("control_result") or {}).get("error"),
    }
    evidence["claims"] = claims
    ok = (
        claims["route_is_l2"]
        and not claims["disable_l1_flag"]
        and claims["l2_invoked"]
        and claims["actually_executed"]
        and claims["recovery_outcome"] == "RECOVERED"
    )
    evidence["result"] = "PASS" if ok else "FAIL"
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": evidence["result"], "claims": claims}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
