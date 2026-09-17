#!/usr/bin/env python3
"""Midterm Agent observe-only demo.

Does not mutate GearPro. Does not POST Control actions. Does not call live Qwen
unless --live-l2 is explicitly requested (default: never).

Usage (from repo root):
  python tools/agent_midterm_demo.py
  python tools/agent_midterm_demo.py --scenario A_healthy
  python tools/agent_midterm_demo.py --scenario D_memory --memory on
  python tools/agent_midterm_demo.py --scenario D_memory --memory off
  python tools/agent_midterm_demo.py --show-frozen-abc
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
from edgemedic.readonly_client import ObserveOnlyViolation, ReadOnlyControlClient

SCENARIO_DIR = ROOT / "docs" / "midterm" / "scenarios"
FROZEN_DIR = ROOT / "docs" / "midterm" / "frozen"
OUT_DIR = ROOT / "docs" / "midterm" / "runs"


def _banner(title):
    line = "=" * 64
    print(f"\n{line}\n{title}\n{line}")


def _print_report(report):
    print(f"scenario:           {report.get('scenario')}")
    print(f"input_source:       {report.get('input_source')}")
    print(f"fault:              {report.get('fault')}")
    print(f"diagnosis:          {report.get('diagnosis')}")
    route = report.get("route") or {}
    print(f"route.selected:     {route.get('selected')}")
    print(f"route.L0/L1/MEM/L2: {route.get('L0')} / {route.get('L1')} / {route.get('MEM')} / {route.get('L2')}")
    action = report.get("proposed_action")
    if action:
        print(f"proposed_action:    {action.get('name')} {action.get('params')}  [{action.get('layer')}]")
    else:
        print("proposed_action:    (none)")
    print(f"execution_mode:     {report.get('execution_mode')}")
    print(f"actually_executed:  {report.get('actually_executed')}")
    print("ACTUAL EXECUTION DISABLED")
    print(f"recovery_claimed:   {report.get('recovery_claimed')}  (must stay false in observe-only)")
    l2 = report.get("l2") or {}
    print(f"l2.live:            {l2.get('invoked_live')}  historical={l2.get('used_historical')}")
    if l2.get("note"):
        print(f"l2.note:            {l2.get('note')}")
    view = report.get("system_view") or {}
    cam = view.get("camera") or {}
    mission = view.get("mission") or {}
    specs = view.get("specialists") or {}
    print(
        f"state: camera opened={cam.get('opened')} age_ms={cam.get('frame_age_ms')} "
        f"seq={cam.get('frame_seq')} | inspection_active={mission.get('inspection_active')} "
        f"| T={view.get('temperature_c')}C | scratch_ms={specs.get('scratch_latency_ms')} "
        f"missing_ms={specs.get('missing_latency_ms')}"
    )
    print(f"diagnose_ms:        {report.get('diagnose_ms')}")


def _load_scenario(name):
    path = SCENARIO_DIR / f"{name}.json"
    if not path.is_file():
        raise SystemExit(f"missing scenario file: {path}")
    return load_json(path)


def run_scenario(name, *, memory_mode="off", out_dir=None):
    client = ReadOnlyControlClient()
    if name == "D_memory":
        snap = _load_scenario("C_camera_stale")
        snap["scenario"] = f"D_memory_{memory_mode}"
        historical = None
        store = None
        enable_memory = memory_mode == "on"
        if enable_memory:
            # Copy frozen episode file to a temp path so the demo never writes the original.
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "episodes.json"
                shutil.copy2(FROZEN_DIR / "episodes_camera_stale.json", dest)
                store = EpisodeStore(dest)
                # Force L1 miss by cooling? L1 will catch CAMERA_STALE first.
                # For MEM demo we need L1 to miss: use a Memory that already fired CAMERA_STALE.
                from edgemedic.policy import Memory
                import time as _time

                mem = Memory()
                mem.last_fire["CAMERA_STALE"] = mem.now()
                report = diagnose(
                    snap,
                    store=store,
                    memory=mem,
                    enable_memory=True,
                    input_source="SYNTHETIC+FROZEN_EPISODE",
                    scenario=snap["scenario"],
                )
                # EpisodeStore may try to save; isolate by discarding temp dir after.
                client.bind_snapshot(snap)
                _assert_readonly(client)
                if out_dir:
                    write_report(Path(out_dir) / f"{snap['scenario']}.json", report)
                return report
        historical = load_json(FROZEN_DIR / "l2_camera_stale_historical.json")
        from edgemedic.policy import Memory

        mem = Memory()
        mem.last_fire["CAMERA_STALE"] = mem.now()
        report = diagnose(
            snap,
            store=None,
            memory=mem,
            enable_memory=False,
            historical_l2=historical,
            input_source="SYNTHETIC+FROZEN REPLAY",
            scenario=f"D_memory_off",
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


def _assert_readonly(client):
    try:
        client.post_action("restart_camera", {})
    except ObserveOnlyViolation:
        return
    raise RuntimeError("ReadOnlyControlClient failed to block post_action")


def show_frozen_abc():
    data = load_json(FROZEN_DIR / "demo_abc_historical.json")
    _banner("FROZEN REPLAY — Demo A/B/C (NOT a live recovery run)")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="EdgeMedic midterm observe-only Agent demo")
    parser.add_argument(
        "--scenario",
        choices=("A_healthy", "B_inspection_paused", "C_camera_stale", "D_memory", "all"),
        default="all",
    )
    parser.add_argument("--memory", choices=("on", "off"), default="on", help="for D_memory only")
    parser.add_argument("--show-frozen-abc", action="store_true")
    parser.add_argument("--json-out", type=Path, default=OUT_DIR)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    _banner("EdgeMedic Midterm Demo — OBSERVE ONLY")
    print("ACTUAL EXECUTION DISABLED")
    print("Control POST /api/action is structurally forbidden by ReadOnlyControlClient")
    print(f"repo: {ROOT}")

    if args.show_frozen_abc:
        show_frozen_abc()

    out_dir = args.json_out
    out_dir.mkdir(parents=True, exist_ok=True)

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
        report = run_scenario(name, memory_mode=mem or "off", out_dir=out_dir)
        reports.append(report)
        if not args.quiet:
            _print_report(report)

    if args.scenario == "all" or args.show_frozen_abc:
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
