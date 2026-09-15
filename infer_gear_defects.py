from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from infer_scratch_v5 import fuse as fuse_scratch
from infer_scratch_v5 import predict_classifier as predict_scratch_classifier
from infer_scratch_v5 import predict_detector as predict_scratch_detector
from missing_hole_runtime import image_paths, predict_config


ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified high-recall scratch and missing-hole inference")
    parser.add_argument("source", type=Path)
    parser.add_argument("--scratch-config", type=Path, default=ROOT / "outputs" / "scratch_v5" / "inference_config.json")
    parser.add_argument("--missing-config", type=Path, default=ROOT / "outputs" / "missing_hole_v1" / "inference_config.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "gear_defect_inference")
    parser.add_argument("--device", default="0")
    parser.add_argument("--scratch-threshold", type=float)
    parser.add_argument("--missing-threshold", type=float)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = image_paths(args.source.resolve())
    if not paths:
        raise FileNotFoundError(f"No images found: {args.source}")
    scratch_config = json.loads(args.scratch_config.read_text(encoding="utf-8"))
    scratch_classifier_scores = {
        str(model["name"]): predict_scratch_classifier(model, paths, args.device)
        for model in scratch_config["classifiers"]
    }
    scratch_detector_scores, _ = predict_scratch_detector(scratch_config["detector"], paths, args.device)
    scratch_scores, _ = fuse_scratch(scratch_config, scratch_classifier_scores, scratch_detector_scores)
    missing_scores, _, _, missing_config = predict_config(args.missing_config.resolve(), paths, args.device, keep_boxes=False)
    scratch_threshold = float(scratch_config["default_threshold"] if args.scratch_threshold is None else args.scratch_threshold)
    missing_threshold = float(missing_config["default_threshold"] if args.missing_threshold is None else args.missing_threshold)
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for path, scratch, missing in zip(paths, scratch_scores, missing_scores):
        scratch_reject = scratch >= scratch_threshold
        missing_reject = missing >= missing_threshold
        rows.append({
            "image": str(path), "decision": "REJECT" if scratch_reject or missing_reject else "PASS",
            "scratch_probability": scratch, "scratch_threshold": scratch_threshold, "scratch_reject": scratch_reject,
            "missing_hole_probability": missing, "missing_hole_threshold": missing_threshold, "missing_hole_reject": missing_reject,
        })
    with (args.output / "predictions.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {"images": len(rows), "rejected": sum(row["decision"] == "REJECT" for row in rows), "passed": sum(row["decision"] == "PASS" for row in rows), "scratch_config": str(args.scratch_config.resolve()), "missing_config": str(args.missing_config.resolve()), "decision_rule": "REJECT when scratch OR missing_hole reaches its locked threshold"}
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
