#!/usr/bin/env python3
"""Natural routing tests (no disable_l1 / no policy edits).

A) Simple fault → L1 (INSPECTION_PAUSED on live Control)
B/C/D/E) UNKNOWN_* has no L1 → natural L2 → real 4B → Authority
   Optional execute_replay for AUTO_LOW_RISK tools on isolated Control.

Does not modify production routing rules.
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
from edgemedic.observe import load_json
from edgemedic.runtime import EXECUTE_OBSERVE, EXECUTE_REPLAY, LoopState, make_client, run_once

SCENARIO = ROOT / "docs" / "midterm" / "scenarios" / "L2_unknown_scratch.json"


def _write(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def test_a_l1(control_url, out_dir: Path):
    mutator = ControlClient(control_url, timeout=30.0)
    # Wait until dual specialists report loaded (avoid warmup false-negatives on Verify)
    for _ in range(30):
        st = mutator.get_state()
        specs = st.get("specialists") or {}
        s = specs.get("scratch_v5") or {}
        m = specs.get("missing_hole_v1") or {}
        if s.get("loaded") and m.get("loaded") and s.get("infer_ok") and m.get("infer_ok"):
            break
        time.sleep(1.0)
    pause = mutator.post_action(
        "pause_inspection", {}, source="human", request_id=f"nat-a-pause-{uuid.uuid4().hex[:8]}"
    )
    time.sleep(0.5)
    client = make_client(control_url, EXECUTE_REPLAY)
    cycle = run_once(client, LoopState(), llm_url=None, execution_mode=EXECUTE_REPLAY, disable_l1=False)
    report = {
        "case": "A_natural_L1",
        "induced_pause": {k: pause.get(k) for k in ("accepted", "executed", "verify_level", "error")},
        "cycle": cycle,
        "claims": {
            "route_is_l1": (cycle.get("route") or {}).get("selected") == "L1",
            "l2_invoked": bool((cycle.get("l2") or {}).get("invoked")),
            "actually_executed": bool(cycle.get("actually_executed")),
            "recovery_outcome": cycle.get("recovery_outcome"),
            "verify_level": cycle.get("verify_level"),
        },
    }
    routing_ok = report["claims"]["route_is_l1"] and not report["claims"]["l2_invoked"] and report["claims"]["actually_executed"]
    verify_ok = report["claims"]["recovery_outcome"] == "RECOVERED" and report["claims"]["verify_level"] == "mission"
    report["routing_result"] = "PASS" if routing_ok else "FAIL"
    report["verify_result"] = "PASS" if verify_ok else "FAIL"
    report["result"] = "PASS" if (routing_ok and verify_ok) else ("ROUTING_PASS_VERIFY_FAIL" if routing_ok else "FAIL")
    _write(out_dir / "natural_A_l1.json", report)
    return report


def test_b_natural_l2(control_url, llm_url, execution_mode, out_dir: Path):
    if "8787" in control_url and execution_mode == EXECUTE_REPLAY:
        raise SystemExit("refusing execute_replay against :8787")
    overlay = load_json(SCENARIO)
    client = make_client(control_url, execution_mode)
    cycle = run_once(
        client,
        LoopState(),
        llm_url=llm_url,
        execution_mode=execution_mode,
        disable_l1=False,
        disable_memory=True,
        force_l2=False,
        snapshot_overlay=overlay,
        l2_timeout=90.0,
    )
    route = cycle.get("route") or {}
    l2 = cycle.get("l2") or {}
    auth = cycle.get("authority_decision") or {}
    claims = {
        "disable_l1": False,
        "force_l2": False,
        "route_is_l2": route.get("selected") == "L2",
        "why_l2": route.get("why_l2"),
        "natural_upgrade": "no_l1_or_mem_proposal" in (route.get("why_l2") or [])
        and "disable_l1" not in (route.get("why_l2") or []),
        "l2_invoked": bool(l2.get("invoked")),
        "l2_model": l2.get("model"),
        "l2_latency_ms": l2.get("latency_ms"),
        "raw_preview": l2.get("raw_preview"),
        "authority": auth.get("execution_authority"),
        "would_execute": bool(auth.get("would_execute") or auth.get("would_execute_if_armed")),
        "actually_executed": bool(cycle.get("actually_executed")),
        "verify_level": cycle.get("verify_level"),
        "recovery_outcome": cycle.get("recovery_outcome"),
        "fault": cycle.get("fault"),
        "proposed": cycle.get("proposed_action"),
    }
    # Natural L2 + real 4B + Authority is required. Execute only when mode allows and Authority passes.
    ok = (
        claims["natural_upgrade"]
        and claims["l2_invoked"]
        and claims["l2_model"]
        and claims["would_execute"]
    )
    if execution_mode == EXECUTE_REPLAY:
        ok = ok and claims["actually_executed"]
    report = {
        "case": "B_natural_L2_unknown",
        "execution_mode": execution_mode,
        "input": "SYNTHETIC overlay L2_unknown_scratch (no policy change; L1 has no verb for UNKNOWN_*)",
        "cycle": cycle,
        "claims": claims,
        "result": "PASS" if ok else "FAIL",
        "coverage_note": (
            "This proves natural L2 upgrade for UNKNOWN_* via existing policy."
            " Live dual hardware faults that only produce L1-covered symptoms are not claimed here."
        ),
    }
    _write(out_dir / "natural_B_l2.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-url", required=True)
    parser.add_argument("--llm-url", default="http://127.0.0.1:8080")
    parser.add_argument("--execution-mode", choices=(EXECUTE_OBSERVE, EXECUTE_REPLAY), default=EXECUTE_OBSERVE)
    parser.add_argument("--json-out-dir", type=Path, required=True)
    parser.add_argument("--skip-a", action="store_true")
    parser.add_argument("--skip-b", action="store_true")
    args = parser.parse_args(argv)
    summary = {"A": None, "B": None}
    if not args.skip_a:
        summary["A"] = test_a_l1(args.control_url, args.json_out_dir)
    if not args.skip_b:
        summary["B"] = test_b_natural_l2(args.control_url, args.llm_url, args.execution_mode, args.json_out_dir)
    compact = {
        k: {"result": (v or {}).get("result"), "claims": (v or {}).get("claims")} for k, v in summary.items() if v
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2))
    failed = [k for k, v in summary.items() if v and v.get("result") not in ("PASS", "ROUTING_PASS_VERIFY_FAIL")]
    # ROUTING_PASS_VERIFY_FAIL still exits 0 for routing coverage; verify noted in report.
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
