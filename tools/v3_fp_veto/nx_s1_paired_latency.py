#!/usr/bin/env python3
"""NX S1 paired integrated latency: V2 vs V3-1 (veto on/off).

ENGINEERING ONLY — not accuracy validation.
Fresh holdout untouched. Registry unchanged.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from nx_v2_pressure_soak_pilot import (  # noqa: E402
    ADMISSION_P95_MS,
    StageRunner,
    cool,
    gpu_snapshot,
    load_crops,
    log,
    process_snapshot,
    _pct,
)
from v3_fp_veto.frozen_inference import backbone_features, load_veto  # noqa: E402

BANNER = "V3-1 NX S1 PAIRED LATENCY — ENGINEERING ONLY — NOT VALIDATED"
S1_REPLICAS = 1
INJECTOR_BASE = {
    "kind": "bandwidth",
    "bytes_mb": 512,
    "buffers": 3,
    "streams": 4,
    "load_ms": 100,
    "idle_ms": 0,
}
EXTRA_BUDGET_MS = 12.0


def make_s1():
    from edgemedic.multi_pressure import MultiGpuContention

    return MultiGpuContention(replicas=S1_REPLICAS, **INJECTOR_BASE)


def run_arm(runtime, crops, duration_s, mode, veto_proba=None, veto_thr=None, v2_thr=None):
    samples = []
    t0 = time.monotonic()
    deadline = t0 + float(duration_s)
    idx = 0
    while time.monotonic() < deadline:
        crop = crops[idx % len(crops)]
        idx += 1
        started = time.perf_counter()
        if mode == "V2":
            pred = runtime.predict(crop)
            wall = (time.perf_counter() - started) * 1000.0
            score = float(pred.defect_score)
            reject = score >= float(v2_thr)
        elif mode == "V3_1":
            feat = backbone_features(runtime, crop)
            p = float(veto_proba(feat))
            wall = (time.perf_counter() - started) * 1000.0
            score = p
            reject = p >= float(veto_thr)
        else:
            raise ValueError(mode)
        samples.append({"wall_ms": wall, "score": score, "reject": int(reject)})
    walls = [s["wall_ms"] for s in samples]
    return {
        "mode": mode,
        "n": len(samples),
        "duration_s": round(time.monotonic() - t0, 3),
        "wall_ms": {
            "p50": _pct(walls, 50),
            "p95": _pct(walls, 95),
            "p99": _pct(walls, 99),
            "mean": float(np.mean(walls)) if walls else None,
            "max": max(walls) if walls else None,
        },
        "reject_rate": None if not samples else sum(s["reject"] for s in samples) / len(samples),
        "process": process_snapshot(),
        "gpu": gpu_snapshot(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, default=Path("/home/jetson/Projects/Machine_vision/tests/replay"))
    parser.add_argument("--window-s", type=float, default=45.0)
    parser.add_argument("--settle-s", type=float, default=5.0)
    parser.add_argument("--warmup-s", type=float, default=8.0)
    parser.add_argument(
        "--veto",
        type=Path,
        default=Path("docs/capability-extraction/v3/v3-1-fp-veto/primary_veto_model.json"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/capability-extraction/v3/v3-1-engineering-freeze/nx_s1_paired_latency.json"),
    )
    args = parser.parse_args()

    try:
        import sys

        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    log(BANNER)
    root = Path(__file__).resolve().parents[2]
    veto_path = args.veto if args.veto.is_absolute() else root / args.veto
    out_path = args.out if args.out.is_absolute() else root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    stages = StageRunner(timeout_dump_path=out_path.with_suffix(".timeout.json"))
    crops = stages.run("load crops", 60.0, lambda: load_crops(args.replay))
    veto_payload, veto_proba, veto_thr, _ = load_veto(veto_path)

    from gp.capability_v2 import V2_INFERENCE_CONFIG, validate_frozen_artifacts, load_frozen
    from gp.scratch_v5 import ScratchV5Runtime

    validate_frozen_artifacts()
    frozen = load_frozen()
    v2_thr = float(frozen["threshold"])

    log("[START] load V2 runtime")
    runtime = ScratchV5Runtime(V2_INFERENCE_CONFIG, warmup=True)
    log("[PASS] load V2 runtime")

    # Warmup both paths
    log("[START] warmup")
    t_w = time.monotonic()
    while time.monotonic() - t_w < args.warmup_s:
        crop = crops[0]
        _ = runtime.predict(crop)
        feat = backbone_features(runtime, crop)
        _ = veto_proba(feat)
    log("[PASS] warmup")

    pressure = make_s1()
    inj = pressure.start()
    log(f"[PASS] S1 injector replicas=1 alive={pressure.alive()} hash={pressure.hash()}")
    cool(args.settle_s)

    # Counterbalance: V2 then V3-1, then V3-1 then V2
    order = ["V2", "V3_1", "V3_1", "V2"]
    arms = []
    for i, mode in enumerate(order, start=1):
        log(f"=== arm {i}/{len(order)} mode={mode} ===")
        summary = run_arm(
            runtime,
            crops,
            args.window_s,
            mode,
            veto_proba=veto_proba,
            veto_thr=veto_thr,
            v2_thr=v2_thr,
        )
        summary["repeat_index"] = i
        summary["injector_alive"] = pressure.alive()
        arms.append(summary)
        log(json.dumps({"mode": mode, "p95": summary["wall_ms"]["p95"], "p50": summary["wall_ms"]["p50"]}))
        cool(3)

    pressure.stop()

    v2_p95s = [a["wall_ms"]["p95"] for a in arms if a["mode"] == "V2"]
    v31_p95s = [a["wall_ms"]["p95"] for a in arms if a["mode"] == "V3_1"]
    v2_p95 = float(np.mean(v2_p95s))
    v31_p95 = float(np.mean(v31_p95s))
    delta = v31_p95 - v2_p95
    gate_ok = v31_p95 < ADMISSION_P95_MS
    budget_ok = delta <= EXTRA_BUDGET_MS
    # Also require not catastrophically worse than noise: soft note if delta > 2ms
    passed = gate_ok and budget_ok and all(a.get("injector_alive") for a in arms)

    report = {
        "banner": BANNER,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "fresh_holdout": "UNTOUCHED",
        "registry": "UNCHANGED",
        "s1": {"replicas": S1_REPLICAS, "injector": INJECTOR_BASE, "start": inj},
        "veto": {
            "artifact": str(veto_path),
            "mode": veto_payload["mode"],
            "threshold": veto_thr,
            "type": veto_payload["type"],
        },
        "v2_threshold": v2_thr,
        "window_s": args.window_s,
        "order": order,
        "arms": arms,
        "summary": {
            "V2_p50_mean": float(np.mean([a["wall_ms"]["p50"] for a in arms if a["mode"] == "V2"])),
            "V2_p95_mean": v2_p95,
            "V2_p99_mean": float(np.mean([a["wall_ms"]["p99"] for a in arms if a["mode"] == "V2"])),
            "V3_1_p50_mean": float(np.mean([a["wall_ms"]["p50"] for a in arms if a["mode"] == "V3_1"])),
            "V3_1_p95_mean": v31_p95,
            "V3_1_p99_mean": float(np.mean([a["wall_ms"]["p99"] for a in arms if a["mode"] == "V3_1"])),
            "delta_p95": delta,
            "gate_190": gate_ok,
            "extra_budget_12ms": budget_ok,
            "PASS": passed,
        },
        "verdict": {
            "result": "PASS" if passed else "FAIL",
            "status_if_pass": "V3-1 ENGINEERING-QUALIFIED CANDIDATE",
            "not": ["VALIDATED", "production-ready", "mission_approved"],
            "note": (
                "Accuracy not re-evaluated here. Microbench ≠ integrated proof; "
                "this paired S1 is the integrated proof for latency only."
            ),
        },
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path = out_path.with_suffix(".md")
    md_path.write_text(
        "\n".join(
            [
                "# V3-1 NX S1 paired latency",
                "",
                "```text",
                BANNER,
                f"result: {report['verdict']['result']}",
                "```",
                "",
                "| arm | p50 | p95 | p99 |",
                "| --- | ---: | ---: | ---: |",
                f"| V2 mean | {report['summary']['V2_p50_mean']:.2f} | {report['summary']['V2_p95_mean']:.2f} | {report['summary']['V2_p99_mean']:.2f} |",
                f"| V3-1 mean | {report['summary']['V3_1_p50_mean']:.2f} | {report['summary']['V3_1_p95_mean']:.2f} | {report['summary']['V3_1_p99_mean']:.2f} |",
                f"| **delta_p95** | — | **{delta:.3f}** | — |",
                "",
                f"- gate p95 < 190: `{gate_ok}`",
                f"- delta_p95 ≤ 12 ms: `{budget_ok}`",
                f"- PASS: `{passed}`",
                "",
                "If PASS → suggest `V3-1 ENGINEERING-QUALIFIED CANDIDATE` (not validated).",
                "",
            ]
        ),
        encoding="utf-8",
    )
    log(json.dumps(report["summary"], indent=2))
    log(json.dumps(report["verdict"], indent=2))
    log(f"wrote {out_path}")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
