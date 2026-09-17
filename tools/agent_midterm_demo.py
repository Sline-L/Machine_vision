#!/usr/bin/env python3
"""Midterm Agent observe-only demo.

Does not mutate GearPro. Does not POST Control actions.
Live L2 is optional (--live-l2) and never executes proposals.

Usage:
  python tools/agent_midterm_demo.py --scenario all --show-frozen-abc
  python tools/agent_midterm_demo.py --scenario E_live --control-url http://127.0.0.1:8787
  python tools/agent_midterm_demo.py --scenario E_live --live-l2 --llm-url http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edgemedic.memory import EpisodeStore
from edgemedic.observe import diagnose, load_json, write_report
from edgemedic.policy import Memory
from edgemedic.readonly_client import ObserveOnlyViolation, ReadOnlyControlClient

SCENARIO_DIR = ROOT / "docs" / "midterm" / "scenarios"
FROZEN_DIR = ROOT / "docs" / "midterm" / "frozen"
OUT_DIR = ROOT / "docs" / "midterm" / "runs"


def _banner(title):
    line = "=" * 64
    print(f"\n{line}\n{title}\n{line}")


def _panel(title, lines):
    print(f"\n[{title}]")
    for line in lines:
        print(f"  {line}")


def _print_report(report):
    view = report.get("system_view") or {}
    cam = view.get("camera") or {}
    mission = view.get("mission") or {}
    specs = view.get("specialists") or {}
    route = report.get("route") or {}
    action = report.get("proposed_action")
    auth = report.get("authority_decision") or {}
    l2 = report.get("l2") or {}

    _panel(
        "1. System State",
        [
            f"input_source={report.get('input_source')}  scenario={report.get('scenario')}",
            f"camera opened={cam.get('opened')} seq={cam.get('frame_seq')} age_ms={cam.get('frame_age_ms')} health={cam.get('health')}",
            f"mission active={mission.get('inspection_active')} profile={view.get('profile')} T={view.get('temperature_c')}C",
            f"scratch health={specs.get('scratch_health')} latency_ms={specs.get('scratch_latency_ms')} loaded={specs.get('scratch_loaded')}",
            f"missing latency_ms={specs.get('missing_latency_ms')} loaded={specs.get('missing_loaded')}",
        ],
    )
    _panel(
        "2. Fault Diagnosis",
        [
            f"fault={report.get('fault')}",
            f"diagnosis={report.get('diagnosis')}",
            f"evidence={json.dumps(report.get('evidence') or {}, ensure_ascii=False)}",
        ],
    )
    selected = route.get("selected")
    marks = {
        "L0": "*" if selected in ("L0",) else " ",
        "L1": "*" if selected in ("L1", "L0") else " ",
        "MEM": "*" if selected == "MEM" else " ",
        "L2": "*" if selected == "L2" else " ",
    }
    _panel(
        "3. Decision Path (*=selected)",
        [
            f"L0[{marks['L0']}]={route.get('L0')}  L1[{marks['L1']}]={route.get('L1')}  "
            f"MEM[{marks['MEM']}]={route.get('MEM')}  L2[{marks['L2']}]={route.get('L2')}",
            f"selected={selected}",
        ],
    )
    _panel(
        "4. Action & Safety",
        [
            f"proposed={None if not action else action.get('name')} {None if not action else action.get('params')} layer={None if not action else action.get('layer')}",
            f"would_require_control_accept={auth.get('would_require_control_accept')}",
            f"execution_mode={report.get('execution_mode')}  actually_executed={report.get('actually_executed')}",
            "ACTUAL EXECUTION DISABLED",
            f"recovery_claimed={report.get('recovery_claimed')} (must stay false here)",
        ],
    )
    _panel(
        "5. Result / Log",
        [
            f"l2.live={l2.get('invoked_live')} historical={l2.get('used_historical')} note={l2.get('note')}",
            f"diagnose_ms={report.get('diagnose_ms')}  l2_meta={l2.get('meta')}",
        ],
    )


def _load_scenario(name):
    path = SCENARIO_DIR / f"{name}.json"
    if not path.is_file():
        raise SystemExit(f"missing scenario file: {path}")
    return load_json(path)


def _assert_readonly(client):
    try:
        client.post_action("restart_camera", {})
    except ObserveOnlyViolation:
        return
    raise RuntimeError("ReadOnlyControlClient failed to block post_action")


def _fetch_live_l2(llm_url, snapshot, overlay_paths, decode="grammar"):
    """Call NX EdgeMedic reasoner if available. Never posts Control actions."""
    saved_path = list(sys.path)
    saved_mods = {k: sys.modules[k] for k in list(sys.modules) if k == "edgemedic" or k.startswith("edgemedic.")}
    try:
        for key in list(saved_mods):
            del sys.modules[key]
        overlays = [p for p in (overlay_paths or []) if p]
        sys.path = overlays + [p for p in sys.path if p not in overlays and p != str(ROOT)]
        try:
            from edgemedic.reasoner import ReasonerError, complete_report  # type: ignore
        except ImportError as exc:
            return None, {"error": f"reasoner import failed: {exc}", "note": "LIVE L2 unavailable"}
        try:
            report = complete_report(
                llm_url,
                snapshot,
                extra_note="If camera is stale prefer restart_camera. If unsure abstain with tool null.",
                timeout=60.0,
                decode=decode,
            )
        except ReasonerError as exc:
            return None, {"error": str(exc), "note": "LIVE L2 failed"}
        action = report.get("action")
        meta = {
            "note": "LIVE INFERENCE (proposal only; not executed)",
            "latency_s": report.get("latency_s"),
            "tokens": report.get("tokens"),
            "decode": report.get("decode"),
            "protocol_status": report.get("protocol_status") or report.get("invalid_class"),
            "raw_preview": (report.get("raw") or "")[:240],
        }
        if not action:
            meta["note"] = "LIVE INFERENCE returned abstain/invalid; no executable proposal"
        return action, meta
    finally:
        sys.path[:] = saved_path
        for key in list(sys.modules):
            if key == "edgemedic" or key.startswith("edgemedic."):
                del sys.modules[key]
        sys.modules.update(saved_mods)


def run_scenario(
    name,
    *,
    memory_mode="off",
    out_dir=None,
    control_url=None,
    live_l2=False,
    llm_url=None,
    overlay_paths=None,
):
    client = ReadOnlyControlClient(base_url=control_url)
    overlay_paths = overlay_paths or []

    if name == "E_live":
        if not control_url:
            raise SystemExit("E_live requires --control-url")
        snap = client.get_state()
        _assert_readonly(client)
        live_prop = None
        live_meta = None
        # Pre-diagnose to see if L2 is needed, then optionally call LLM.
        pre = diagnose(snap, enable_memory=False, input_source="LIVE GET /api/state", scenario="E_live_pre")
        if live_l2 and pre.get("fault") and pre.get("proposed_action") is None:
            live_prop, live_meta = _fetch_live_l2(llm_url, snap, overlay_paths)
        elif live_l2:
            live_meta = {
                "note": "LIVE L2 skipped: no L2-needed fault (healthy or L1/MEM already proposed)",
                "pre_fault": pre.get("fault"),
                "pre_route": (pre.get("route") or {}).get("selected"),
            }
        report = diagnose(
            snap,
            enable_memory=False,
            live_l2_proposal=live_prop,
            live_l2_meta=live_meta,
            input_source="LIVE GET /api/state",
            scenario="E_live",
        )
        if out_dir:
            write_report(Path(out_dir) / "E_live.json", report)
        return report

    if name == "D_memory":
        snap = _load_scenario("C_camera_stale")
        enable_memory = memory_mode == "on"
        if enable_memory:
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "episodes.json"
                shutil.copy2(FROZEN_DIR / "episodes_camera_stale.json", dest)
                store = EpisodeStore(dest)
                mem = Memory()
                mem.last_fire["CAMERA_STALE"] = mem.now()
                report = diagnose(
                    snap,
                    store=store,
                    memory=mem,
                    enable_memory=True,
                    input_source="SYNTHETIC+FROZEN_EPISODE",
                    scenario="D_memory_on",
                )
                client.bind_snapshot(snap)
                _assert_readonly(client)
                if out_dir:
                    write_report(Path(out_dir) / "D_memory_on.json", report)
                return report
        historical = load_json(FROZEN_DIR / "l2_camera_stale_historical.json")
        mem = Memory()
        mem.last_fire["CAMERA_STALE"] = mem.now()
        report = diagnose(
            snap,
            store=None,
            memory=mem,
            enable_memory=False,
            historical_l2=historical,
            input_source="SYNTHETIC+FROZEN REPLAY",
            scenario="D_memory_off",
        )
        client.bind_snapshot(snap)
        _assert_readonly(client)
        if out_dir:
            write_report(Path(out_dir) / "D_memory_off.json", report)
        return report

    snap = _load_scenario(name)
    client.bind_snapshot(snap)
    report = diagnose(
        snap,
        enable_memory=False,
        input_source=snap.get("input_source") or "SYNTHETIC",
        scenario=snap.get("scenario") or name,
    )
    _assert_readonly(client)
    if out_dir:
        write_report(Path(out_dir) / f"{name}.json", report)
    return report


def show_frozen_abc():
    data = load_json(FROZEN_DIR / "demo_abc_historical.json")
    _banner("FROZEN REPLAY — Demo A/B/C (NOT a live recovery run)")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="EdgeMedic midterm observe-only Agent demo")
    parser.add_argument(
        "--scenario",
        choices=("A_healthy", "B_inspection_paused", "C_camera_stale", "D_memory", "E_live", "all"),
        default="all",
    )
    parser.add_argument("--memory", choices=("on", "off"), default="on", help="for D_memory only")
    parser.add_argument("--show-frozen-abc", action="store_true")
    parser.add_argument("--json-out", type=Path, default=OUT_DIR)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--control-url", default=None, help="e.g. http://127.0.0.1:8787 for E_live")
    parser.add_argument("--live-l2", action="store_true", help="optional LIVE L2 proposal (never executes)")
    parser.add_argument("--llm-url", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--overlay-path",
        action="append",
        default=[],
        help="path containing NX edgemedic reasoner (repeatable)",
    )
    args = parser.parse_args(argv)

    _banner("EdgeMedic Midterm Demo — OBSERVE ONLY")
    print("ACTUAL EXECUTION DISABLED")
    print("Control POST /api/action is structurally forbidden by ReadOnlyControlClient")
    print(f"repo: {ROOT}")

    if args.show_frozen_abc and args.scenario != "all":
        show_frozen_abc()

    out_dir = args.json_out
    out_dir.mkdir(parents=True, exist_ok=True)
    overlays = args.overlay_path or [
        "/home/jetson/Projects/edgemedic-live",
        str(ROOT.parent / "Machine_vision"),
    ]

    names = []
    if args.scenario == "all":
        names = [
            ("A_healthy", None),
            ("B_inspection_paused", None),
            ("C_camera_stale", None),
            ("D_memory", "on"),
            ("D_memory", "off"),
        ]
    elif args.scenario == "D_memory":
        names = [("D_memory", args.memory)]
    else:
        names = [(args.scenario, None)]

    reports = []
    for name, mem in names:
        label = name if mem is None else f"{name} memory={mem}"
        _banner(f"Scenario {label}")
        report = run_scenario(
            name,
            memory_mode=mem or "off",
            out_dir=out_dir,
            control_url=args.control_url,
            live_l2=args.live_l2,
            llm_url=args.llm_url,
            overlay_paths=overlays,
        )
        reports.append(report)
        if not args.quiet:
            _print_report(report)

    if args.scenario == "all":
        show_frozen_abc()

    _banner("Summary")
    for report in reports:
        action = report.get("proposed_action") or {}
        print(
            f"{report.get('scenario')}: fault={report.get('fault')} "
            f"route={((report.get('route') or {}).get('selected'))} "
            f"propose={action.get('name')} executed={report.get('actually_executed')}"
        )
    print(f"\nJSON reports written under: {out_dir}")
    print("Done. No recovery actions were executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
