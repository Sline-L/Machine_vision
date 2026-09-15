#!/usr/bin/env python3
"""ENGINEERING ONLY — preregistered V2 severity sweep S0–S3 on NX.

NOT MISSION APPROVED. NOT A3 EFFECTIVENESS.
Severities frozen before measurement — do not reverse-tune injector.
"""

from __future__ import annotations

import argparse
import csv
import faulthandler
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Reuse lean pilot helpers
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nx_v2_pressure_soak_pilot import (  # noqa: E402
    ADMISSION_P95_MS,
    HOLD_S,
    TIMEOUT_FIRST_INFER_S,
    TIMEOUT_MODEL_LOAD_S,
    TIMEOUT_TRANSITION_S,
    TIMEOUT_WARMUP_S,
    TIMEOUT_WINDOW_MARGIN_S,
    V5_SLOW_MS,
    StageRunner,
    bringup_profile,
    cool,
    load_crops,
    log,
    make_pressure,
    process_snapshot,
    gpu_snapshot,
    run_window,
)

BANNER = "ENGINEERING ONLY — SEVERITY SWEEP — NOT MISSION APPROVED — NOT A3"

# Frozen injector base (replicas vary only).
INJECTOR_BASE = {
    "kind": "bandwidth",
    "bytes_mb": 512,
    "buffers": 3,
    "streams": 4,
    "load_ms": 100,
    "idle_ms": 0,
}

# Pre-registered severities — DO NOT ALTER after seeing results.
SEVERITIES = (
    {"id": "S0", "label": "healthy", "replicas": 0},
    {"id": "S1", "label": "low", "replicas": 1},
    {"id": "S2", "label": "medium", "replicas": 2},
    {"id": "S3", "label": "qualified_severe", "replicas": 3},
)


class NullInjector:
    """S0: no pressure process."""

    def __init__(self):
        self.replicas = 0

    def config(self):
        return {**INJECTOR_BASE, "replicas": 0, "kind": "multi_bandwidth", "null": True}

    def hash(self):
        return "null_injector_s0"

    def start(self):
        return {"replicas": 0, "workers": [], "config": self.config(), "hash": self.hash()}

    def alive(self):
        return True

    def stop(self):
        return None


def make_injector(replicas: int):
    if replicas <= 0:
        return NullInjector()
    from edgemedic.multi_pressure import MultiGpuContention

    return MultiGpuContention(replicas=int(replicas), **INJECTOR_BASE)


def summarize_arm(summary: dict, injector) -> dict:
    return {
        "wall_p50": summary["wall_ms"]["p50"],
        "wall_p95": summary["wall_ms"]["p95"],
        "wall_max": summary["wall_ms"]["max"],
        "stage_p95": summary["stage_ms"]["p95"],
        "cls2_p95": summary["cls2_p95"],
        "gate190": summary["mission_latency_gate_190"],
        "sustained_overload": summary["sustained_overload"],
        "sustained_overload_onset": summary["sustained_overload_onset"],
        "valid_ratio": summary["valid_ratio"],
        "inspect_rate_hz": summary["inspect_rate_hz"],
        "n": summary["n"],
        "exceptions": summary["exceptions"],
        "identity": summary["identity"],
        "gpu": summary["gpu"],
        "process": summary["process"],
        "injector_alive": bool(injector.alive()) if injector is not None else None,
        "raw_label": summary["label"],
    }


def classify_envelope(cells: list) -> dict:
    """Pre-registered decision rule from v2-severity-sweep-plan.md."""
    # Aggregate by severity across repeats
    by_sev = {}
    for cell in cells:
        by_sev.setdefault(cell["severity_id"], []).append(cell)

    recovery_hits = []
    for sid, reps in by_sev.items():
        consistent = []
        for cell in reps:
            full = cell["FULL"]
            v2 = cell["LATENCY_DEGRADED_V2"]
            cls2_ok = float(v2.get("cls2_p95") or 0) <= 0.01
            hit = (
                full.get("gate190") is False
                and v2.get("gate190") is True
                and cls2_ok
                and bool(cell.get("injector_alive_both"))
            )
            consistent.append(hit)
        if sum(1 for h in consistent if h) >= 2:
            recovery_hits.append(sid)
        elif sum(1 for h in consistent if h) == 1 and len(consistent) == 1:
            # single-repeat severity: note but not enough for PRELIMINARY SUPPORTED under plan (≥2)
            recovery_hits.append(f"{sid}_single_repeat_only")

    true_hits = [h for h in recovery_hits if not str(h).endswith("_single_repeat_only")]
    if true_hits:
        return {
            "case": "A",
            "RECOVERY_ENVELOPE_FOUND": True,
            "envelope_severities": true_hits,
            "MODERATE_PRESSURE_MISSION_LATENCY_RECOVERY": "PRELIMINARY SUPPORTED",
            "SEVERE_PRESSURE_RECOVERY": "NOT SUPPORTED"
            if "S3" not in true_hits
            else "PRELIMINARY SUPPORTED",
            "note": "Do not generalize to all overload levels.",
        }

    # Characterize FULL fail / V2 fail pattern
    s1 = by_sev.get("S1") or []
    s2 = by_sev.get("S2") or []
    s3 = by_sev.get("S3") or []

    def _full_fail(cells_):
        return bool(cells_) and all(c["FULL"].get("gate190") is False for c in cells_)

    def _v2_fail(cells_):
        return bool(cells_) and all(c["LATENCY_DEGRADED_V2"].get("gate190") is False for c in cells_)

    def _full_pass(cells_):
        return bool(cells_) and all(c["FULL"].get("gate190") is True for c in cells_)

    if _full_pass(s1) and _full_fail(s2) and _v2_fail(s2) and _full_fail(s3) and _v2_fail(s3):
        return {
            "case": "B",
            "RECOVERY_ENVELOPE_FOUND": False,
            "V2": "LATENCY MITIGATION CAPABILITY",
            "MISSION_LATENCY_RECOVERY": "NOT SUPPORTED IN OBSERVED OPERATING REGION",
            "V3_RECOMMENDATION": "V3 RECOMMENDED",
        }

    # Case C: cannot stably trigger moderate FULL overload
    def _full_overload_stable(cells_):
        if len(cells_) < 1:
            return False
        return all(c["FULL"].get("sustained_overload") for c in cells_)

    moderate_trigger = any(_full_overload_stable(by_sev.get(s) or []) for s in ("S1", "S2"))
    if not moderate_trigger and _full_fail(s3) and _v2_fail(s3):
        return {
            "case": "C",
            "RECOVERY_ENVELOPE_FOUND": False,
            "NO_REPRODUCIBLE_MODERATE_RECOVERY_FAULT_REGION": True,
            "MISSION_LATENCY_RECOVERY": "NOT SUPPORTED UNDER CURRENT PREREGISTERED INJECTOR SWEEP",
            "note": "Do not retune injector post-hoc to manufacture recovery.",
            "V3_RECOMMENDATION": "V3 RECOMMENDED",
        }

    # Fallback: no FULL FAIL / V2 PASS band observed
    any_mitigation = False
    for cell in cells:
        fp = cell["FULL"].get("wall_p95")
        vp = cell["LATENCY_DEGRADED_V2"].get("wall_p95")
        if fp and vp and vp < fp * 0.95:
            any_mitigation = True

    return {
        "case": "B_or_mixed",
        "RECOVERY_ENVELOPE_FOUND": False,
        "V2": "LATENCY MITIGATION CAPABILITY" if any_mitigation else "INCONCLUSIVE",
        "MISSION_LATENCY_RECOVERY": "NOT SUPPORTED IN OBSERVED OPERATING REGION",
        "single_repeat_hints": [h for h in recovery_hits if str(h).endswith("_single_repeat_only")],
        "V3_RECOMMENDATION": "V3 RECOMMENDED" if not true_hits else "V3 NOT YET NECESSARY",
    }


def write_csv(path: Path, cells: list):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "severity",
                "replicas",
                "repeat",
                "profile",
                "wall_p95",
                "wall_p50",
                "gate190",
                "sustained_overload",
                "cls2_p95",
                "injector_alive",
                "temp_c",
            ]
        )
        for cell in cells:
            for profile in ("FULL", "LATENCY_DEGRADED_V2"):
                arm = cell[profile]
                w.writerow(
                    [
                        cell["severity_id"],
                        cell["replicas"],
                        cell["repeat"],
                        profile,
                        arm.get("wall_p95"),
                        arm.get("wall_p50"),
                        arm.get("gate190"),
                        arm.get("sustained_overload"),
                        arm.get("cls2_p95"),
                        arm.get("injector_alive"),
                        (arm.get("gpu") or {}).get("temp_c"),
                    ]
                )


def write_markdown(path: Path, report: dict):
    lines = [
        "# V2 severity sweep (NX) — ENGINEERING ONLY",
        "",
        "```text",
        "NOT MISSION APPROVED",
        "NOT A3 EFFECTIVENESS",
        "preregistered S0–S3; replicas-only knob",
        "```",
        "",
        "## Research question",
        "",
        "Exists natural operating envelope: `FULL p95 > 190` AND `V2 p95 < 190`?",
        "",
        f"**Answer:** `{report['verdict'].get('RECOVERY_ENVELOPE_FOUND')}`",
        "",
        f"Case: **{report['verdict'].get('case')}**",
        "",
        "```text",
        json.dumps(report["verdict"], indent=2),
        "```",
        "",
        "## Table",
        "",
        "| Severity | replicas | repeat | FULL p95 | FULL fault | FULL gate | V2 p95 | V2 gate | V2/FULL | injector |",
        "| --- | ---: | ---: | ---: | --- | --- | ---: | --- | ---: | --- |",
    ]
    for cell in report["cells"]:
        full = cell["FULL"]
        v2 = cell["LATENCY_DEGRADED_V2"]
        ratio = cell.get("ratio_v2_over_full")
        fault = "yes" if full.get("sustained_overload") else "no"
        # S2 note: do not auto-call qualified fault
        fault_label = fault
        if cell["severity_id"] == "S2" and full.get("sustained_overload"):
            fault_label = "yes (characterization; not auto-qualified)"
        elif cell["severity_id"] == "S2":
            fault_label = "no / incomplete hold"
        lines.append(
            "| {sid} | {rep} | {rpt} | {fp:.1f} | {fault} | {fg} | {vp:.1f} | {vg} | {ratio} | {alive} |".format(
                sid=cell["severity_id"],
                rep=cell["replicas"],
                rpt=cell["repeat"],
                fp=float(full["wall_p95"]),
                fault=fault_label,
                fg="PASS" if full.get("gate190") else "FAIL",
                vp=float(v2["wall_p95"]),
                vg="PASS" if v2.get("gate190") else "FAIL",
                ratio=f"{ratio:.3f}" if ratio is not None else "n/a",
                alive="yes" if cell.get("injector_alive_both") else "no",
            )
        )
    lines.extend(
        [
            "",
            "## Plot data",
            "",
            "CSV: `v2-severity-sweep-nx.csv` (x=replicas, y=wall_p95; Mission gate=190).",
            "",
            "Plotting: `tools/plot_v2_severity_sweep.py`.",
            "",
            "## Notes",
            "",
            "- S2 is a severity characterization point; prior ~1.995 s hold must not auto-qualify as fault.",
            "- Formal quality admission still blocked on fresh Scratch holdout.",
            "- A3 effectiveness = NOT ESTABLISHED.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    faulthandler.enable(all_threads=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, default=Path("/home/jetson/Projects/Machine_vision/tests/replay"))
    parser.add_argument("--window-s", type=float, default=45.0)
    parser.add_argument("--settle-s", type=float, default=5.0)
    parser.add_argument("--cool-s", type=float, default=40.0)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
        sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    log(BANNER)
    log(f"pid={os.getpid()} severities={[s['id'] for s in SEVERITIES]} repeats={args.repeats}")
    root = Path(__file__).resolve().parents[1]
    out_dir = args.out_dir or (root / "docs" / "capability-extraction" / "v3")
    out_dir.mkdir(parents=True, exist_ok=True)
    stages = StageRunner(timeout_dump_path=out_dir / "v2-severity-sweep-timeout-dump.json")
    crops = stages.run("load crops", 60.0, lambda: load_crops(args.replay))

    from gp.profiles import apply_to_config, ProfileError
    from gp.config import AppConfig

    def _prod():
        try:
            apply_to_config(AppConfig(), "LATENCY_DEGRADED_V2", engineering_mode=False)
            return False
        except ProfileError:
            return True

    production_rejected = stages.run("production reject", 30.0, _prod)
    if not production_rejected:
        raise SystemExit("production unexpectedly allowed V2")

    report = {
        "mode": "ENGINEERING ONLY",
        "banner": BANNER,
        "mission_approved": False,
        "a3_effectiveness": "NOT ESTABLISHED",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "preregistered_severities": list(SEVERITIES),
        "injector_base": INJECTOR_BASE,
        "admission_p95_ms": ADMISSION_P95_MS,
        "v5_slow_ms": V5_SLOW_MS,
        "hold_s": HOLD_S,
        "window_s": args.window_s,
        "repeats": args.repeats,
        "production_rejected": production_rejected,
        "cells": [],
        "stages": [],
        "verdict": {},
    }

    # Order: S0..S3 outer, repeats inner (or reverse repeats for thermal — keep simple)
    for sev in SEVERITIES:
        for rpt in range(1, max(1, int(args.repeats)) + 1):
            sid = sev["id"]
            replicas = int(sev["replicas"])
            log(f"=== {sid} replicas={replicas} repeat={rpt} ===")
            cell = {
                "severity_id": sid,
                "label": sev["label"],
                "replicas": replicas,
                "repeat": rpt,
                "order": ["FULL", "LATENCY_DEGRADED_V2"],
                "started_at": datetime.now(timezone.utc).isoformat(),
                "role": "severity characterization point"
                if sid != "S3"
                else "qualified severe anchor (characterization in-sweep)",
            }
            injector = make_injector(replicas)
            started = stages.run(
                f"{sid} injector start",
                60.0,
                injector.start,
            )
            cell["injector"] = {
                "start": started,
                "config": injector.config(),
                "hash": injector.hash(),
                "alive_at_start": injector.alive(),
            }
            if not injector.alive():
                cell["aborted"] = True
                cell["abort_reason"] = "injector not alive"
                report["cells"].append(cell)
                break
            cool(args.settle_s)

            # FULL
            full_rt, _ = bringup_profile(stages, "FULL", crops[0])
            full_sum = stages.run(
                f"{sid} FULL window",
                args.window_s + TIMEOUT_WINDOW_MARGIN_S,
                lambda: run_window(
                    full_rt, crops, args.window_s, f"{sid}_FULL_r{rpt}", injector=injector
                )[0],
                profile="FULL",
            )
            cell["FULL"] = summarize_arm(full_sum, injector)
            log(
                json.dumps(
                    {
                        "sev": sid,
                        "profile": "FULL",
                        "p95": cell["FULL"]["wall_p95"],
                        "gate": cell["FULL"]["gate190"],
                        "overload": cell["FULL"]["sustained_overload"],
                        "inj": cell["FULL"]["injector_alive"],
                    }
                )
            )
            del full_rt
            cool(5)

            # V2 under same pressure
            v2_rt, _ = bringup_profile(stages, "LATENCY_DEGRADED_V2", crops[0])
            v2_sum = stages.run(
                f"{sid} V2 window",
                args.window_s + TIMEOUT_WINDOW_MARGIN_S,
                lambda: run_window(
                    v2_rt, crops, args.window_s, f"{sid}_V2_r{rpt}", injector=injector
                )[0],
                profile="LATENCY_DEGRADED_V2",
            )
            cell["LATENCY_DEGRADED_V2"] = summarize_arm(v2_sum, injector)
            if float(cell["LATENCY_DEGRADED_V2"]["cls2_p95"] or 0) > 0.01:
                raise SystemExit(f"{sid}: V2 cls2 not zero")
            log(
                json.dumps(
                    {
                        "sev": sid,
                        "profile": "V2",
                        "p95": cell["LATENCY_DEGRADED_V2"]["wall_p95"],
                        "gate": cell["LATENCY_DEGRADED_V2"]["gate190"],
                        "cls2": cell["LATENCY_DEGRADED_V2"]["cls2_p95"],
                        "inj": cell["LATENCY_DEGRADED_V2"]["injector_alive"],
                    }
                )
            )
            del v2_rt

            fp = cell["FULL"]["wall_p95"]
            vp = cell["LATENCY_DEGRADED_V2"]["wall_p95"]
            cell["ratio_v2_over_full"] = None if not fp else vp / fp
            cell["delta_p95"] = None if fp is None or vp is None else vp - fp
            cell["injector_alive_both"] = bool(
                cell["FULL"]["injector_alive"] and cell["LATENCY_DEGRADED_V2"]["injector_alive"]
            )
            cell["envelope_hit"] = bool(
                cell["FULL"]["gate190"] is False
                and cell["LATENCY_DEGRADED_V2"]["gate190"] is True
                and cell["injector_alive_both"]
            )
            injector.stop()
            cell["injector_alive_after_stop"] = injector.alive()
            report["cells"].append(cell)
            cool(args.cool_s)

    report["stages"] = stages.stages
    report["verdict"] = classify_envelope(report["cells"])
    report["verdict"]["A3_EFFECTIVENESS"] = "NOT ESTABLISHED"
    report["verdict"]["FORMAL_QUALITY_ADMISSION"] = "BLOCKED ON FRESH SCRATCH-ONLY HOLDOUT"
    report["finished_at"] = datetime.now(timezone.utc).isoformat()

    json_path = out_dir / "v2-severity-sweep-nx.json"
    csv_path = out_dir / "v2-severity-sweep-nx.csv"
    md_path = out_dir / "v2-severity-sweep-nx.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    write_csv(csv_path, report["cells"])
    write_markdown(md_path, report)
    log(json.dumps(report["verdict"], indent=2))
    log(f"wrote {json_path}")
    log(f"wrote {csv_path}")
    log(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
