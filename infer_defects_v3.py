from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from ultralytics import YOLO

from auto_optimize_defects_v3 import (
    CLASSES,
    GearClassificationDataset,
    Sample,
    combine_scores,
    contour_missing_score,
    infer_view,
    load_resnet,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "outputs" / "defect_search_v3" / "inference_config.json"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the V3 two-stage defect gate and localizers")
    parser.add_argument("source", type=Path, help="A cropped gear image or a directory of cropped gear images")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "defect_search_v3" / "inference")
    parser.add_argument("--device", default="0")
    return parser.parse_args()


def images_in(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    return sorted(path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in EXTENSIONS)


def anomaly_score(network: nn.Module, reference: dict[str, object], image: Image.Image) -> float:
    feature_model = nn.Sequential(*list(network.children())[:-1]).eval()
    transform = GearClassificationDataset([], augment=False).transform
    with torch.no_grad():
        feature = nn.functional.normalize(feature_model(transform(image).unsqueeze(0).cuda()).flatten(1), dim=1).cpu()
    bank = reference["embeddings"]
    raw = 1 - (feature @ bank.T).topk(min(5, bank.shape[0]), dim=1).values.mean(1)
    low, high = float(reference["low"]), float(reference["high"])
    return float(((raw - low) / max(1e-6, high - low)).clamp(0, 1))


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    paths = images_in(args.source)
    if not paths:
        raise FileNotFoundError(f"No images found in {args.source}")
    args.output.mkdir(parents=True, exist_ok=True)
    gate_config = config["gate"]
    yolo_classifier = YOLO(gate_config["yolo_classifier"])
    resnet = load_resnet(Path(gate_config["resnet_classifier"]))
    reference = torch.load(gate_config["anomaly_reference"], map_location="cpu", weights_only=False)
    localizers = {name: YOLO(values["weights"]) for name, values in config["localizers"].items()}
    rows = []
    for path in paths:
        with Image.open(path) as opened:
            image = opened.convert("RGB")
            width, height = image.size
        yolo_result = yolo_classifier.predict(str(path), imgsz=320, device=args.device, verbose=False)[0]
        yolo_values = [0.0] * len(CLASSES)
        for index, value in enumerate(yolo_result.probs.data.cpu().tolist()):
            yolo_values[CLASSES.index(yolo_classifier.names[index])] = float(value)
        transform = GearClassificationDataset([], augment=False).transform
        with torch.no_grad():
            resnet_values = resnet(transform(image).unsqueeze(0).cuda()).softmax(1)[0].cpu().tolist()
        anomaly = anomaly_score(resnet, reference, image)
        detector_values = [0.0, 0.0, 0.0]
        detections = {}
        for mode, model in localizers.items():
            settings = config["localizers"][mode]
            result = model.predict(str(path), imgsz=settings["imgsz"], conf=settings["confidence"], iou=settings["nms_iou"], device=args.device, verbose=False)[0]
            detections[mode] = result
            detector_values[CLASSES.index(mode)] = max(result.boxes.conf.cpu().tolist(), default=0.0)
        sample = Sample(path.stem, path, None, "normal", infer_view(width, height), width, height, (), 0)
        combined = combine_scores(
            [sample], {path.stem: yolo_values}, {path.stem: resnet_values},
            {path.stem: anomaly}, {path.stem: detector_values}, gate_config["strategy"],
        )[path.stem]
        thresholds = gate_config["thresholds"]
        predicted = [name for name in ("scratch", "missing_tooth") if combined[CLASSES.index(name)] >= thresholds[name]]
        plotted = image.copy()
        from PIL import ImageDraw
        draw = ImageDraw.Draw(plotted)
        colors = {"scratch": (255, 40, 40), "missing_tooth": (255, 170, 0)}
        for mode, result in detections.items():
            for box, confidence in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist()):
                draw.rectangle(tuple(box), outline=colors[mode], width=3)
                draw.text((box[0], max(18, box[1] - 12)), f"{mode}:{confidence:.2f}", fill=colors[mode])
        rejected = bool(predicted)
        draw.text((8, 8), f"{'REJECT' if rejected else 'PASS'} s={combined[1]:.2f} m={combined[2]:.2f}", fill=(255, 30, 30) if rejected else (0, 180, 60))
        plotted.save(args.output / f"{path.stem}_prediction.jpg", quality=95)
        rows.append({"image": str(path), "decision": "reject" if rejected else "pass", "predicted_defects": ";".join(predicted), "scratch_score": combined[1], "missing_tooth_score": combined[2], "anomaly_score": anomaly, "view": sample.view})
    with (args.output / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"images": len(rows), "rejected": sum(row["decision"] == "reject" for row in rows), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
