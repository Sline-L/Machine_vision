#!/usr/bin/env python3
"""V3-1: extract EffNet+detector features on train/val ONLY.

EXPLORATION — NOT MISSION APPROVED.
Fresh holdout: DO NOT TOUCH.
test_scratch: DO NOT USE FOR TUNING.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np

EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
BANNER = "V3-1 FEATURE EXTRACT — train/val ONLY — NOT MISSION APPROVED — NO HOLDOUT"


def load_split(images: Path, annotations: Path):
    paths = sorted(p for p in images.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)
    labels = []
    for path in paths:
        xml_path = annotations / f"{path.stem}.xml"
        if not xml_path.is_file():
            labels.append(0)
            continue
        root = ET.parse(xml_path).getroot()
        labels.append(1 if root.findall("object") else 0)
    return paths, labels


def extract_one(runtime, image):
    """Return V2-topology component features (+ detector box stats)."""
    from gp.scratch_v5 import apply_temperature, fuse_single_classifier, square_rgb_image

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    item, model = runtime.classifiers[0]
    with runtime.torch.inference_mode():
        tensor = runtime.tensor_transform(square_rgb_image(rgb, int(item["imgsz"]))).unsqueeze(0).to(runtime.device)
        raw_cls = float(model(tensor).sigmoid()[0, 0].item())
    cls1 = apply_temperature(raw_cls, item.get("temperature", 1.0))

    detector = runtime.config["detector"]
    result = runtime.detector.predict(
        image,
        imgsz=int(detector["imgsz"]),
        conf=float(detector["conf_floor"]),
        iou=float(detector["iou"]),
        device=runtime.yolo_device,
        verbose=False,
    )[0]
    raw_confs = []
    if result.boxes is not None and len(result.boxes):
        raw_confs = [float(c) for c in result.boxes.conf.detach().cpu().numpy().tolist()]
    raw_det = max(raw_confs) if raw_confs else 0.0
    det = apply_temperature(raw_det, detector.get("temperature", 1.0))
    alpha = float(runtime.config["fusion"]["alpha"])
    fused, _ = fuse_single_classifier(cls1, det, alpha)
    n_boxes = len(raw_confs)
    top3 = sorted(raw_confs, reverse=True)[:3]
    while len(top3) < 3:
        top3.append(0.0)
    return {
        "raw_cls": raw_cls,
        "cls1": cls1,
        "raw_det": raw_det,
        "det": det,
        "fused_v2": fused,
        "n_boxes": n_boxes,
        "sum_conf": float(sum(raw_confs)),
        "mean_conf": float(sum(raw_confs) / n_boxes) if n_boxes else 0.0,
        "top1_conf": top3[0],
        "top2_conf": top3[1],
        "top3_conf": top3[2],
        "cls_minus_det": cls1 - det,
        "log1p_boxes": math.log1p(n_boxes),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-root", type=Path, required=True)
    parser.add_argument("--ann-root", type=Path, required=True)
    parser.add_argument("--splits", nargs="+", default=["train_scratch", "val_scratch"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    print(BANNER, flush=True)
    forbidden = {"test_scratch", "test", "holdout", "fresh"}
    for split in args.splits:
        if any(tok in split.lower() for tok in forbidden if tok != "val"):
            if "test" in split.lower() or "holdout" in split.lower() or "fresh" in split.lower():
                raise SystemExit(f"refusing split {split}: holdout/test forbidden")

    from gp.capability_v2 import V2_INFERENCE_CONFIG, validate_frozen_artifacts
    from gp.scratch_v5 import ScratchV5Runtime

    validate_frozen_artifacts()
    runtime = ScratchV5Runtime(V2_INFERENCE_CONFIG, device=args.device, warmup=True)
    thr = float(runtime.config["default_threshold"])
    args.out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = None
    rows_all = []
    for split in args.splits:
        images = args.images_root / split
        anns = args.ann_root / split
        paths, labels = load_split(images, anns)
        print(f"{split}: n={len(paths)} pos={sum(labels)}", flush=True)
        for path, label in zip(paths, labels):
            image = cv2.imread(str(path))
            if image is None:
                raise RuntimeError(f"read fail {path}")
            feat = extract_one(runtime, image)
            row = {
                "split": split,
                "image": path.name,
                "label": int(label),
                "v2_threshold": thr,
                "v2_reject": int(feat["fused_v2"] >= thr),
                **feat,
            }
            rows_all.append(row)
            if fieldnames is None:
                fieldnames = list(row.keys())

    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_all)

    meta = {
        "banner": BANNER,
        "n_rows": len(rows_all),
        "splits": args.splits,
        "v2_config": str(V2_INFERENCE_CONFIG),
        "v2_threshold": thr,
        "note": "train/val only; no test_scratch; no holdout",
    }
    args.out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {args.out} n={len(rows_all)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
