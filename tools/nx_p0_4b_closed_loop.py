#!/usr/bin/env python3
"""P0 closed-loop: real 4B → Authority → Control → Execute → Verify on isolated Replay.

Does NOT splice L1 recovery with a separate 4B diagnose case.
Uses disable_l1 so INSPECTION_PAUSED reaches L2; Authority must approve resume_inspection.

Usage (NX isolated Control :8788 only):
  PYTHONPATH=... python3 tools/nx_p0_4b_closed_loop.py \\
    --control-url http://127.0.0.1:8788 --llm-url http://127.0.0.1:8080 \\
    --execution-mode execute_replay --json-out docs/midterm/runs/p0/4b_closed_loop.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edgemedic.client import ControlClient
from edgemedic.runtime import EXECUTE_OBSERVE, EXECUTE_REPLAY, LoopState, make_client, run_once


def main(argv=None):
    parser = argparse.ArgumentParser(description="P0 4B closed-loop recovery on isolated Replay")
    parser.add_argument("--control-url", required=True)
    parser.add_argument("--llm-url", default="http://127.0.0.1:8080")
    parser.add_argument("--execution-mode", choices=(EXECUTE_OBSERVE, EXECUTE_REPLAY), default=EXECUTE_REPLAY)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args(argv)

    if "8787" in args.control_url and args.execution_mode == EXECUTE_REPLAY:
        raise SystemExit("refusing execute_replay against default production Control :8787")

    evidence = {
        "protocol": "p0-4b-closed-loop-v1",
        "control_url": args.control_url,
        "llm_url": args.llm_url,
        "execution_mode": args.execution_mode,
        "note": "Single case: pause → disable_l1 → L2(4B) → Authority → Control → Verify",
    }

    mutator = ControlClient(args.control_url, timeout=30.0)
    before = mutator.get_state()
    evidence["state_before_pause"] = {
        "schema_version": before.get("schema_version"),
        "inspection_active": (before.get("mission") or {}).get("inspection_active"),
        "scratch_loaded": ((before.get("specialists") or {}).get("scratch_v5") or before.get("scratch_v5") or {}).get("loaded"),
        "missing_loaded": ((before.get("specialists") or {}).get("missing_hole_v1") or {}).get("loaded"),
    }

    pause = mutator.post_action(
        "pause_inspection",
        {},
        source="reflex",
        request_id=f"p0-4b-pause-{uuid.uuid4().hex[:8]}",
    )
    evidence["induced_pause"] = {
        "accepted": pause.get("accepted"),
        "executed": pause.get("executed"),
        "verify_level": pause.get("verify_level"),
        "recovery_success": pause.get("recovery_success"),
        "error": pause.get("error"),
        "request_id": pause.get("request_id"),
    }
    if not pause.get("executed"):
        evidence["closed_loop"] = "ABORTED_PAUSE_FAILED"
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 2

    time.sleep(0.5)
    client = make_client(args.control_url, args.execution_mode)
    cycle = run_once(
        client,
        LoopState(),
        llm_url=args.llm_url,
        execution_mode=args.execution_mode,
        disable_l1=True,
        disable_memory=True,
        force_l2=False,
        l2_timeout=90.0,
    )
    evidence["agent_cycle"] = cycle
    evidence["claims"] = {
        "l2_invoked": bool((cycle.get("l2") or {}).get("invoked")),
        "route_is_l2": (cycle.get("route") or {}).get("selected") == "L2",
        "authority_would_execute": bool((cycle.get("authority_decision") or {}).get("would_execute")),
        "actually_executed": bool(cycle.get("actually_executed")),
        "verify_level": cycle.get("verify_level"),
        "recovery_outcome": cycle.get("recovery_outcome"),
        "proposed": cycle.get("proposed_action"),
        "l1_was_disabled": True,
        "not_l1_recovery": (cycle.get("route") or {}).get("selected") != "L1",
    }
    ok = (
        evidence["claims"]["l2_invoked"]
        and evidence["claims"]["route_is_l2"]
        and evidence["claims"]["not_l1_recovery"]
        and bool((cycle.get("authority_decision") or {}).get("would_execute") or (cycle.get("authority_decision") or {}).get("would_execute_if_armed"))
    )
    if args.execution_mode == EXECUTE_REPLAY:
        ok = ok and evidence["claims"]["actually_executed"] and evidence["claims"]["recovery_outcome"] == "RECOVERED"
        evidence["closed_loop"] = "PASS" if ok else "FAIL"
    else:
        evidence["closed_loop"] = "DIAGNOSE_ONLY_OBSERVE"
        evidence["note_observe"] = "Authority path exercised without Control mutate"

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"closed_loop": evidence["closed_loop"], "claims": evidence["claims"]}, ensure_ascii=False, indent=2))
    print(f"wrote {args.json_out}")
    return 0 if evidence["closed_loop"] in ("PASS", "DIAGNOSE_ONLY_OBSERVE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
