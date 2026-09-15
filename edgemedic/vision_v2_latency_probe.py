"""NX latency probe for vision v2 paths (effnet + detector).

Extends skip-detector probe with single-classifier + detector timing.
Does NOT open runtime profiles.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from edgemedic.latency_probe_skip_detector import (
    _summary,
    _v5_total_ms,
    collect_crops,
    predict_classifiers_only,
    run_mode,
)
from gp.config import PROJECT_ROOT, AppConfig
from gp.models import TwoStageInspector
from gp.replay import load_replay_pack
from gp.scratch_v5 import ScratchV5Runtime, apply_temperature, square_rgb_image


def predict_effnet_detector(runtime: ScratchV5Runtime, crop, alpha: float = 0.25):
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    with runtime.torch.inference_mode():
        item, model = runtime.classifiers[0]
        started = time.perf_counter()
        image = square_rgb_image(rgb, int(item["imgsz"]))
        tensor = runtime.tensor_transform(image).unsqueeze(0).to(runtime.device)
        cls_score = apply_temperature(float(model(tensor).sigmoid()[0, 0].item()), item.get("temperature", 1.0))
        cls1_ms = (time.perf_counter() - started) * 1000
        detector_cfg = runtime.config["detector"]
        started = time.perf_counter()
        result = runtime.detector.predict(
            crop,
            imgsz=int(detector_cfg["imgsz"]),
            conf=float(detector_cfg["conf_floor"]),
            iou=float(detector_cfg["iou"]),
            device=runtime.yolo_device,
            verbose=False,
        )[0]
        det_ms = (time.perf_counter() - started) * 1000
        raw_detector = 0.0
        if result.boxes is not None and len(result.boxes):
            raw_detector = float(result.boxes.conf.detach().cpu().numpy().max())
        det_score = apply_temperature(raw_detector, detector_cfg.get("temperature", 1.0))
        fused = alpha * cls_score + (1.0 - alpha) * det_score
    from gp.scratch_v5 import ScratchV5Prediction

    return ScratchV5Prediction(
        fused,
        cls_score,
        det_score,
        None,
        cls1_ms,
        0.0,
        det_ms,
        0.0,
    )


def run_custom_mode(runtime, crops, warmup, predict_fn, mode_name):
    for item in crops[:warmup]:
        predict_fn(item["crop"])
    if runtime.device.type == "cuda":
        runtime.torch.cuda.synchronize()
    totals = []
    for item in crops:
        if runtime.device.type == "cuda":
            runtime.torch.cuda.synchronize()
        pred = predict_fn(item["crop"])
        totals.append(_v5_total_ms(pred))
    return {"mode": mode_name, "v5_stage_sum_ms": _summary(totals)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vision v2 latency probe")
    parser.add_argument("--replay-pack", type=Path, default=PROJECT_ROOT / "tests" / "replay")
    parser.add_argument("--locator", type=Path, default=PROJECT_ROOT / "model" / "model1.pt")
    parser.add_argument("--model2", type=Path, default=PROJECT_ROOT / "model" / "model2" / "inference_config.json")
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--max-crops", type=int, default=34)
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "results" / "lightweight_capability_v2" / "latency")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    pack = load_replay_pack(args.replay_pack)
    config = AppConfig(
        locator_model=Path(args.locator).resolve(),
        model2_config=Path(args.model2).resolve(),
        serial_enabled=False,
        inference_profile="FULL",
    )
    inspector = TwoStageInspector(config)
    runtime = inspector.model2
    crops = collect_crops(inspector, pack["paths"], args.max_crops)
    if not crops:
        raise SystemExit("no crops from replay pack")

    full = run_mode(runtime, crops, "full", args.warmup)
    cls_only = run_mode(runtime, crops, "classifiers_only", args.warmup)
    effnet_det = run_custom_mode(
        runtime,
        crops,
        args.warmup,
        lambda c: predict_effnet_detector(runtime, c, 0.25),
        "effnet_det_a0.25",
    )
    full_p95 = full["v5_stage_sum_ms"]["p95"]
    effnet_det["relative_p95"] = None if not full_p95 else round(effnet_det["v5_stage_sum_ms"]["p95"] / full_p95, 3)
    payload = {
        "probe": "vision_v2_latency_v1",
        "claim": "latency_characterization_only",
        "n_crops": len(crops),
        "modes": {"full": full, "classifiers_only": cls_only, "effnet_det_a0.25": effnet_det},
    }
    (args.out / "vision_v2_latency_summary.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "effnet_det_p95": effnet_det["v5_stage_sum_ms"]["p95"], "full_p95": full_p95}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
