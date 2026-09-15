"""Healthy NX pretest: FULL V5 vs skip-detector (classifiers only).

Probe only — does NOT open CLASSIFY_ONLY, does NOT change Mission bars,
does NOT touch Control API / profiles.

Question answered:
  Does skipping P2 detector@960 materially cut per-inference v5_latency_ms?

Usage (on NX, PT locator + replay pack):

  .venv/bin/python -m edgemedic.latency_probe_skip_detector \\
    --replay-pack tests/replay \\
    --locator model/model1.pt \\
    --model2 model/model2/inference_config.json \\
    --out results/latency_probe_skip_detector
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import cv2
import numpy as np

from gp.config import PROJECT_ROOT, AppConfig
from gp.models import TwoStageInspector
from gp.replay import load_replay_pack
from gp.scratch_v5 import (
    ScratchV5Prediction,
    ScratchV5Runtime,
    apply_temperature,
    square_rgb_image,
)


def _percentile(values, pct):
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def _summary(values):
    values = [float(v) for v in values]
    if not values:
        return {"n": 0, "p50": None, "p95": None, "mean": None}
    return {
        "n": len(values),
        "p50": round(_percentile(values, 50), 3),
        "p95": round(_percentile(values, 95), 3),
        "mean": round(statistics.fmean(values), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def predict_classifiers_only(runtime: ScratchV5Runtime, crop) -> ScratchV5Prediction:
    """Same classifier path as FULL; skip detector; score = classifier mean."""
    if crop is None or not isinstance(crop, np.ndarray) or crop.size == 0:
        raise ValueError("empty crop")
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    classifier_scores = []
    classifier_times = []
    with runtime.torch.inference_mode():
        for item, model in runtime.classifiers:
            started = time.perf_counter()
            image = square_rgb_image(rgb, int(item["imgsz"]))
            tensor = runtime.tensor_transform(image).unsqueeze(0).to(runtime.device)
            raw = float(model(tensor).sigmoid()[0, 0].item())
            classifier_times.append((time.perf_counter() - started) * 1000)
            classifier_scores.append(apply_temperature(raw, item.get("temperature", 1.0)))
    started = time.perf_counter()
    classifier_score = (float(classifier_scores[0]) + float(classifier_scores[1])) / 2.0
    fusion_ms = (time.perf_counter() - started) * 1000
    return ScratchV5Prediction(
        classifier_score,
        classifier_score,
        0.0,
        None,
        classifier_times[0] if classifier_times else 0.0,
        classifier_times[1] if len(classifier_times) > 1 else 0.0,
        0.0,
        fusion_ms,
    )


def _v5_total_ms(pred: ScratchV5Prediction) -> float:
    return (
        float(pred.classifier1_latency_ms)
        + float(pred.classifier2_latency_ms)
        + float(pred.detector_latency_ms)
        + float(pred.fusion_latency_ms)
    )


def collect_crops(inspector: TwoStageInspector, frames, max_crops: int):
    crops = []
    for path in frames:
        frame = cv2.imread(str(path))
        if frame is None:
            continue
        located = inspector.locator.predict(
            source=frame,
            conf=inspector.config.locator_confidence,
            iou=inspector.config.locator_iou,
            verbose=False,
        )[0]
        if located.boxes is None or len(located.boxes) == 0:
            continue
        box = located.boxes.xyxy.detach().cpu().numpy()[0]
        coordinates = inspector._clip_box(box, frame.shape)
        crop, _ = inspector._crop_with_margin(frame, coordinates)
        if crop.size == 0:
            continue
        crops.append({"frame": path.name, "crop": crop.copy()})
        if len(crops) >= max_crops:
            break
    return crops


def run_mode(runtime, crops, mode: str, warmup: int):
    predict = runtime.predict if mode == "full" else (lambda c: predict_classifiers_only(runtime, c))
    for item in crops[:warmup]:
        predict(item["crop"])
    if runtime.device.type == "cuda":
        runtime.torch.cuda.synchronize()

    rows = []
    totals = []
    cls1 = []
    cls2 = []
    det = []
    for item in crops:
        if runtime.device.type == "cuda":
            runtime.torch.cuda.synchronize()
        wall0 = time.perf_counter()
        pred = predict(item["crop"])
        if runtime.device.type == "cuda":
            runtime.torch.cuda.synchronize()
        wall_ms = (time.perf_counter() - wall0) * 1000
        total = _v5_total_ms(pred)
        totals.append(total)
        cls1.append(pred.classifier1_latency_ms)
        cls2.append(pred.classifier2_latency_ms)
        det.append(pred.detector_latency_ms)
        rows.append(
            {
                "frame": item["frame"],
                "mode": mode,
                "v5_stage_sum_ms": round(total, 3),
                "v5_wall_ms": round(wall_ms, 3),
                "classifier1_ms": round(pred.classifier1_latency_ms, 3),
                "classifier2_ms": round(pred.classifier2_latency_ms, 3),
                "detector_ms": round(pred.detector_latency_ms, 3),
                "fusion_ms": round(pred.fusion_latency_ms, 3),
            }
        )
    return {
        "mode": mode,
        "v5_stage_sum_ms": _summary(totals),
        "v5_wall_ms": _summary([r["v5_wall_ms"] for r in rows]),
        "classifier1_ms": _summary(cls1),
        "classifier2_ms": _summary(cls2),
        "detector_ms": _summary(det),
        "samples": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-pack", type=Path, default=PROJECT_ROOT / "tests" / "replay")
    parser.add_argument("--locator", type=Path, default=PROJECT_ROOT / "model" / "model1.pt")
    parser.add_argument(
        "--model2",
        type=Path,
        default=PROJECT_ROOT / "model" / "model2" / "inference_config.json",
    )
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "results" / "latency_probe_skip_detector")
    parser.add_argument("--max-crops", type=int, default=40)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--order", choices=("full_first", "cls_first"), default="full_first")
    args = parser.parse_args(argv)

    pack = load_replay_pack(args.replay_pack)
    config = AppConfig(
        locator_model=Path(args.locator).resolve(),
        model2_config=Path(args.model2).resolve(),
        serial_enabled=False,
        inference_profile="FULL",
    )
    # Force PT locator path; do not use engine even if env points elsewhere.
    inspector = TwoStageInspector(config)
    runtime = inspector.model2

    crops = collect_crops(inspector, pack["paths"], args.max_crops)
    if len(crops) < 10:
        raise SystemExit(f"need ≥10 crops with detections, got {len(crops)}")

    modes = ("full", "classifiers_only") if args.order == "full_first" else ("classifiers_only", "full")
    results = {}
    for mode in modes:
        results[mode] = run_mode(runtime, crops, mode, args.warmup)

    full = results["full"]["v5_stage_sum_ms"]
    cls = results["classifiers_only"]["v5_stage_sum_ms"]
    delta_p95 = None
    ratio = None
    if full["p95"] is not None and cls["p95"] is not None:
        delta_p95 = round(full["p95"] - cls["p95"], 3)
        ratio = round(cls["p95"] / full["p95"], 4) if full["p95"] else None

    # Rough gate for "worth continuing" — advisory only, not Mission policy.
    worth = None
    if delta_p95 is not None and full["p95"]:
        worth = bool(delta_p95 >= 40.0 or (ratio is not None and ratio <= 0.75))

    payload = {
        "probe": "skip_detector_latency_v1",
        "claim": "latency_pretest_only",
        "classify_only_api_opened": False,
        "mission_semantics_changed": False,
        "locator": str(args.locator),
        "locator_backend": "pt",
        "model2": str(args.model2),
        "replay_pack": str(args.replay_pack),
        "replay_pack_id": pack["manifest"].get("replay_pack_id"),
        "n_crops": len(crops),
        "warmup": args.warmup,
        "order": args.order,
        "modes": {k: {kk: vv for kk, vv in v.items() if kk != "samples"} for k, v in results.items()},
        "delta_full_minus_cls_p95_ms": delta_p95,
        "cls_over_full_p95_ratio": ratio,
        "worth_continuing_classifier_only_route": worth,
        "samples": {
            "full": results["full"]["samples"],
            "classifiers_only": results["classifiers_only"]["samples"],
        },
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# Skip-detector latency pretest",
        "",
        f"- crops: {len(crops)}",
        f"- locator: `{args.locator}` (PT)",
        f"- FULL v5 stage-sum p50/p95: {full['p50']} / {full['p95']} ms",
        f"- classifiers-only p50/p95: {cls['p50']} / {cls['p95']} ms",
        f"- Δp95 (FULL−cls): {delta_p95} ms",
        f"- ratio cls/full p95: {ratio}",
        f"- worth_continuing (advisory): {worth}",
        "",
        "FULL detector p50/p95: "
        f"{results['full']['detector_ms']['p50']} / {results['full']['detector_ms']['p95']} ms",
        "",
        "Does **not** open CLASSIFY_ONLY or change Mission.",
    ]
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in payload if k != "samples"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
