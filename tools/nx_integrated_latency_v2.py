#!/usr/bin/env python3
"""ENGINEERING ONLY — integrated LATENCY_DEGRADED_V2 latency on NX.

NOT MISSION APPROVED. Not A3 effectiveness evidence.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import cv2
import numpy as np

BANNER = "ENGINEERING ONLY — NOT MISSION APPROVED — integrated latency probe"


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (p / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] * (1 - frac) + ordered[high] * frac


def load_crops(replay_root: Path, limit: int = 40):
    frames = sorted((replay_root / "frames").glob("*.jpg"))
    if not frames:
        raise SystemExit(f"no frames under {replay_root / 'frames'}")
    crops = []
    for path in frames[:limit]:
        image = cv2.imread(str(path))
        if image is None:
            continue
        # Replay pack frames are already gear crops for latency probes historically;
        # if full frame, use center square as ROI approximation for smoke only.
        h, w = image.shape[:2]
        side = min(h, w)
        y0 = (h - side) // 2
        x0 = (w - side) // 2
        crops.append(image[y0 : y0 + side, x0 : x0 + side])
    if len(crops) < 5:
        raise SystemExit(f"too few crops: {len(crops)}")
    return crops


def measure(runtime, crops, warmup=3):
    for crop in crops[:warmup]:
        runtime.predict(crop)
    samples = []
    for crop in crops:
        started = time.perf_counter()
        pred = runtime.predict(crop)
        total_ms = (time.perf_counter() - started) * 1000.0
        stage = (
            pred.classifier1_latency_ms
            + pred.classifier2_latency_ms
            + pred.detector_latency_ms
            + pred.fusion_latency_ms
        )
        samples.append(
            {
                "wall_ms": total_ms,
                "stage_sum_ms": stage,
                "cls1_ms": pred.classifier1_latency_ms,
                "cls2_ms": pred.classifier2_latency_ms,
                "det_ms": pred.detector_latency_ms,
                "score": pred.defect_score,
            }
        )
    walls = [s["wall_ms"] for s in samples]
    stages = [s["stage_sum_ms"] for s in samples]
    return {
        "n": len(samples),
        "wall_ms": {
            "mean": statistics.fmean(walls),
            "p50": percentile(walls, 50),
            "p95": percentile(walls, 95),
        },
        "stage_sum_ms": {
            "mean": statistics.fmean(stages),
            "p50": percentile(stages, 50),
            "p95": percentile(stages, 95),
        },
        "cls1_p95": percentile([s["cls1_ms"] for s in samples], 95),
        "cls2_p95": percentile([s["cls2_ms"] for s in samples], 95),
        "det_p95": percentile([s["det_ms"] for s in samples], 95),
        "finite_scores": all(np.isfinite(s["score"]) for s in samples),
    }


def gpu_snapshot():
    try:
        import subprocess

        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu,clocks.current.graphics,utilization.gpu,memory.used",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        ).strip()
        temp, clock, util, mem = [x.strip() for x in out.split(",")]
        return {
            "temp_c": float(temp),
            "gpu_clock_mhz": float(clock),
            "gpu_util_pct": float(util),
            "mem_used_mib": float(mem),
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def main():
    print(BANNER)
    root = Path(__file__).resolve().parents[1]
    replay = Path("/home/jetson/Projects/Machine_vision/tests/replay")
    crops = load_crops(replay, limit=40)

    from gp.scratch_v5 import ScratchV5Runtime
    from gp.capability_v2 import validate_frozen_artifacts, FULL_INFERENCE_CONFIG, V2_INFERENCE_CONFIG
    from gp.profiles import apply_to_config
    from gp.config import AppConfig

    frozen = validate_frozen_artifacts()
    # Production reject smoke
    try:
        apply_to_config(AppConfig(), "LATENCY_DEGRADED_V2", engineering_mode=False)
        production_rejected = False
    except Exception:
        production_rejected = True

    eng = AppConfig()
    apply_to_config(eng, "LATENCY_DEGRADED_V2", engineering_mode=True)
    apply_to_config(eng, "FULL", engineering_mode=True)

    before = gpu_snapshot()
    full_rt = ScratchV5Runtime(FULL_INFERENCE_CONFIG, warmup=True)
    full = measure(full_rt, crops)
    del full_rt

    v2_rt = ScratchV5Runtime(V2_INFERENCE_CONFIG, warmup=True)
    v2 = measure(v2_rt, crops)
    del v2_rt
    after = gpu_snapshot()

    report = {
        "mode": "ENGINEERING ONLY",
        "mission_approved": False,
        "a3_effectiveness": "NOT ESTABLISHED",
        "probe": "integrated_scratch_runtime_v2",
        "production_rejected": production_rejected,
        "frozen_config_hash": frozen["config_hash"],
        "n_crops": len(crops),
        "gpu_before": before,
        "gpu_after": after,
        "FULL": full,
        "LATENCY_DEGRADED_V2": v2,
        "relative_p95_wall": (
            None
            if not full["wall_ms"]["p95"]
            else v2["wall_ms"]["p95"] / full["wall_ms"]["p95"]
        ),
        "relative_p95_stage": (
            None
            if not full["stage_sum_ms"]["p95"]
            else v2["stage_sum_ms"]["p95"] / full["stage_sum_ms"]["p95"]
        ),
    }
    out = root / "results" / "latency_degraded_v2" / "integrated_latency_nx.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {out}")
    if not production_rejected or not full["finite_scores"] or not v2["finite_scores"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
