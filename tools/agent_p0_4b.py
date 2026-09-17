#!/usr/bin/env python3
"""P0 midterm demos A–F for dual-specialist + Qwen3-4B.

Default is observe-only. Use --execution-mode execute_replay only on an
isolated Replay Control instance you explicitly approve.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edgemedic.adapter import adapt_snapshot, specialist_view
from edgemedic.observe import load_json
from edgemedic.readonly_client import ObserveOnlyViolation, ReadOnlyControlClient
from edgemedic.runtime import EXECUTE_OBSERVE, EXECUTE_REPLAY, LoopState, make_client, run_once

SCENARIO_DIR = ROOT / "docs" / "midterm" / "scenarios"
OUT_DIR = ROOT / "docs" / "midterm" / "runs" / "p0"


def _banner(title):
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


def _print_cycle(cycle, title):
    _banner(title)
    print(json.dumps(cycle, ensure_ascii=False, indent=2))


def demo_a_live_state(control_url):
    client = ReadOnlyControlClient(base_url=control_url)
    snap = adapt_snapshot(client.get_state())
    view = specialist_view(snap)
    report = {
        "demo": "A",
        "title": "dual-specialist live snapshot",
        "input_source": "LIVE GET /api/state",
        "specialists": view,
        "schema_version": snap.get("schema_version"),
    }
    _print_cycle(report, "Demo A — live dual-specialist state")
    return report


def demo_b_diagnose(control_url):
    client = make_client(control_url, EXECUTE_OBSERVE)
    cycle = run_once(client, LoopState(), llm_url=None, execution_mode=EXECUTE_OBSERVE)
    cycle["demo"] = "B"
    _print_cycle(cycle, "Demo B — Agent diagnose (no LLM)")
    return cycle


def demo_c_4b(control_url, llm_url, synthetic=True):
    """Real 4B call. Uses synthetic UNKNOWN_SCRATCH so L1 cannot steal the route."""
    client = make_client(control_url, EXECUTE_OBSERVE)
    overlay = None
    if synthetic:
        overlay = load_json(SCENARIO_DIR / "L2_unknown_scratch.json")
    cycle = run_once(
        client,
        LoopState(),
        llm_url=llm_url,
        execution_mode=EXECUTE_OBSERVE,
        disable_l1=False,
        disable_memory=True,
        snapshot_overlay=overlay,
    )
    cycle["demo"] = "C"
    cycle["input_source"] = "SYNTHETIC L2_unknown_scratch" if synthetic else "LIVE GET"
    _print_cycle(cycle, "Demo C — Qwen3-4B live diagnose (observe-only)")
    return cycle


def demo_d_authority(control_url, llm_url):
    from edgemedic.authority import decide_execution

    client = make_client(control_url, EXECUTE_OBSERVE)
    overlay = load_json(SCENARIO_DIR / "L2_unknown_scratch.json")
    cycle = run_once(
        client,
        LoopState(),
        llm_url=llm_url,
        execution_mode=EXECUTE_OBSERVE,
        disable_memory=True,
        snapshot_overlay=overlay,
    )
    # Also show high-risk tool would be dry-run
    high = decide_execution({"name": "set_locator_profile", "params": {"profile": "trt_fast"}}, source="reasoner")
    cycle["demo"] = "D"
    cycle["high_risk_authority_example"] = high
    _print_cycle(cycle, "Demo D — Authority gate (4B proposal + high-risk example)")
    return cycle


def demo_e_replay_recovery(control_url, execution_mode):
    """INSPECTION_PAUSED → L1 resume. Requires execute_replay on isolated Control."""
    if execution_mode != EXECUTE_REPLAY:
        report = {
            "demo": "E",
            "skipped": True,
            "reason": "pass --execution-mode execute_replay on isolated Replay Control",
        }
        _print_cycle(report, "Demo E — skipped (observe-only)")
        return report
    client = make_client(control_url, EXECUTE_REPLAY)
    # Induce pause then recover
    pause = client.post_action("pause_inspection", {}, source="reflex", request_id="p0-demo-e-pause")
    cycle = run_once(
        client,
        LoopState(),
        llm_url=None,
        execution_mode=EXECUTE_REPLAY,
        disable_memory=True,
    )
    cycle["demo"] = "E"
    cycle["induced_pause"] = {
        "accepted": pause.get("accepted"),
        "executed": pause.get("executed"),
        "verify_level": pause.get("verify_level"),
    }
    _print_cycle(cycle, "Demo E — Replay L1 recovery (INSPECTION_PAUSED)")
    return cycle


def demo_f_verify(control_url, execution_mode):
    if execution_mode != EXECUTE_REPLAY:
        report = {"demo": "F", "skipped": True, "reason": "needs execute_replay after Demo E"}
        _print_cycle(report, "Demo F — skipped")
        return report
    client = make_client(control_url, EXECUTE_REPLAY)
    snap = specialist_view(adapt_snapshot(client.get_state()))
    report = {
        "demo": "F",
        "title": "post-recovery dual-specialist view",
        "specialists": snap,
        "note": "Verify levels appear on control_result of Demo E",
    }
    _print_cycle(report, "Demo F — dual-specialist Verify view")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="P0 4B midterm demos A–F")
    parser.add_argument("--demo", choices=("A", "B", "C", "D", "E", "F", "all"), default="all")
    parser.add_argument("--control-url", default="http://127.0.0.1:8787")
    parser.add_argument("--llm-url", default="http://127.0.0.1:8080")
    parser.add_argument("--execution-mode", choices=(EXECUTE_OBSERVE, EXECUTE_REPLAY), default=EXECUTE_OBSERVE)
    parser.add_argument("--json-out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    _banner("P0 EdgeMedic 4B demos")
    print(f"execution_mode={args.execution_mode}")
    print("ACTUAL EXECUTION DISABLED" if args.execution_mode == EXECUTE_OBSERVE else "EXECUTE_REPLAY ENABLED")

    # Safety: observe-only client must still block
    probe = ReadOnlyControlClient(base_url=args.control_url)
    try:
        probe.post_action("restart_camera", {})
        raise SystemExit("ReadOnlyControlClient failed to block POST")
    except ObserveOnlyViolation:
        print("ReadOnlyControlClient POST block: OK")

    args.json_out.mkdir(parents=True, exist_ok=True)
    reports = []
    mapping = {
        "A": lambda: demo_a_live_state(args.control_url),
        "B": lambda: demo_b_diagnose(args.control_url),
        "C": lambda: demo_c_4b(args.control_url, args.llm_url),
        "D": lambda: demo_d_authority(args.control_url, args.llm_url),
        "E": lambda: demo_e_replay_recovery(args.control_url, args.execution_mode),
        "F": lambda: demo_f_verify(args.control_url, args.execution_mode),
    }
    names = list(mapping) if args.demo == "all" else [args.demo]
    for name in names:
        report = mapping[name]()
        reports.append(report)
        path = args.json_out / f"demo_{name}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")

    _banner("Summary")
    for report in reports:
        demo = report.get("demo")
        if demo == "C":
            l2 = report.get("l2") or {}
            print(f"C: l2_invoked={l2.get('invoked')} protocol={l2.get('protocol_status')} executed={report.get('actually_executed')}")
        elif demo == "E":
            print(
                f"E: fault={report.get('fault')} route={((report.get('route') or {}).get('selected'))} "
                f"executed={report.get('actually_executed')} verify={report.get('verify_level')} outcome={report.get('recovery_outcome')}"
            )
        else:
            print(f"{demo}: keys={sorted(report.keys())[:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
