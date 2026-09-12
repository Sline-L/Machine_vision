from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw
from torchvision import transforms
from ultralytics import YOLO

from train_scratch_v5 import apply_temperature, clahe, load_custom, square_image


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "outputs" / "scratch_v5" / "inference_config.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "scratch_v5" / "inference"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Scratch V5 high-recall inference")
    parser.add_argument("source", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--device", default="0")
    parser.add_argument("--no-boxes", action="store_true", help="Do not draw auxiliary detector boxes")
    return parser.parse_args()


def image_paths(source: Path) -> list[Path]:
    if source.is_file() and source.suffix.lower() in EXTENSIONS:
        return [source]
    if source.is_dir():
        return sorted(path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in EXTENSIONS)
    return []


def variants(path: Path, size: int, tta: str) -> list[np.ndarray]:
    with Image.open(path) as opened:
        original = opened.convert("RGB")
    images = [original]
    if tta == "tta_mean":
        images += [
            original.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
            original.transpose(Image.Transpose.FLIP_TOP_BOTTOM),
            clahe(original),
        ]
    return [np.asarray(square_image(image, size)) for image in images]


def torch_device(device: str) -> str:
    if device.lower() == "cpu":
        return "cpu"
    return f"cuda:{device}" if device.isdigit() else device


def predict_classifier(config: dict[str, object], paths: list[Path], device: str) -> list[float]:
    family = str(config["family"])
    size = int(config["imgsz"])
    tta = str(config.get("tta", "none"))
    temperature = float(config.get("temperature", 1.0))
    output = []
    if family == "yolo_cls":
        model = YOLO(str(config["weights"]))
        defect_index = next(index for index, name in model.names.items() if name == "defect")
        for path in paths:
            results = model.predict(variants(path, size, tta), imgsz=size, batch=4, device=device, verbose=False)
            raw = float(np.mean([result.probs.data[defect_index].item() for result in results]))
            output.append(apply_temperature([raw], temperature)[0])
    else:
        network, _ = load_custom(Path(str(config["weights"])), torch_device(device))
        tensor = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ])
        with torch.no_grad():
            for path in paths:
                batch = torch.stack([tensor(Image.fromarray(array)) for array in variants(path, size, tta)]).to(torch_device(device))
                raw = float(network(batch).sigmoid().mean())
                output.append(apply_temperature([raw], temperature)[0])
    return output


def predict_detector(config: dict[str, object], paths: list[Path], device: str) -> tuple[list[float], list[list[tuple[float, float, float, float, float]]]]:
    model = YOLO(str(config["weights"]))
    size = int(config.get("imgsz", 960))
    confidence_floor = float(config.get("conf_floor", 0.001))
    iou = float(config.get("iou", 0.7))
    temperature = float(config.get("temperature", 1.0))
    scores = []
    all_boxes = []
    for path in paths:
        result = model.predict(str(path), imgsz=size, conf=confidence_floor, iou=iou, device=device, verbose=False)[0]
        boxes = []
        if result.boxes is not None and len(result.boxes):
            for coordinates, confidence in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist()):
                boxes.append((*map(float, coordinates), float(confidence)))
        all_boxes.append(boxes)
        raw = max((box[4] for box in boxes), default=0.0)
        scores.append(apply_temperature([raw], temperature)[0])
    return scores, all_boxes


def classifier_fusion(rule: dict[str, object], probabilities: dict[str, list[float]]) -> list[float]:
    kind = str(rule["type"])
    names = [str(name) for name in rule.get("models", [])]
    if kind == "classifier":
        return probabilities[names[0]]
    matrix = np.asarray([probabilities[name] for name in names])
    if kind == "classifier_mean":
        return matrix.mean(axis=0).tolist()
    if kind == "classifier_max":
        return matrix.max(axis=0).tolist()
    raise ValueError(f"Unknown classifier fusion: {kind}")


def fuse(config: dict[str, object], classifier_scores: dict[str, list[float]], detector_scores: list[float] | None) -> tuple[list[float], list[float]]:
    rule = config["fusion"]
    kind = str(rule["type"])
    if kind.startswith("classifier"):
        values = classifier_fusion(rule, classifier_scores)
        return values, values
    classifier_values = classifier_fusion(rule["classifier"], classifier_scores)
    if detector_scores is None:
        raise RuntimeError("Fusion config requires a detector")
    if kind == "weighted":
        alpha = float(rule["alpha"])
        fused = (alpha * np.asarray(classifier_values) + (1 - alpha) * np.asarray(detector_scores)).tolist()
    elif kind == "soft_or":
        fused = np.maximum(classifier_values, detector_scores).tolist()
    else:
        raise ValueError(f"Unknown fusion rule: {kind}")
    return fused, classifier_values


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    paths = image_paths(args.source)
    if not paths:
        raise FileNotFoundError(f"No supported images found in {args.source}")
    args.output.mkdir(parents=True, exist_ok=True)
    threshold = float(config["default_threshold"] if args.threshold is None else args.threshold)

    classifier_scores = {
        str(model["name"]): predict_classifier(model, paths, args.device)
        for model in config["classifiers"]
    }
    detector_scores = None
    detector_boxes: list[list[tuple[float, float, float, float, float]]] = [[] for _ in paths]
    if config.get("detector"):
        detector_scores, detector_boxes = predict_detector(config["detector"], paths, args.device)
    fused_scores, classifier_values = fuse(config, classifier_scores, detector_scores)

    rows = []
    for index, (path, probability) in enumerate(zip(paths, fused_scores)):
        decision = "REJECT" if probability >= threshold else "PASS"
        with Image.open(path) as opened:
            image = opened.convert("RGB")
        draw = ImageDraw.Draw(image)
        if not args.no_boxes and detector_boxes[index]:
            x1, y1, x2, y2, confidence = max(detector_boxes[index], key=lambda box: box[4])
            if confidence >= 0.05:
                draw.rectangle((x1, y1, x2, y2), outline=(255, 170, 0), width=2)
                draw.text((x1, max(0, y1 - 12)), f"{confidence:.2f}", fill=(255, 120, 0))
        draw.text((8, 8), f"{decision} scratch={probability:.3f} threshold={threshold:.3f}", fill=(255, 30, 30) if decision == "REJECT" else (0, 170, 40))
        destination = args.output / f"{path.stem}_prediction.jpg"
        image.save(destination, quality=95)
        rows.append({
            "image": str(path), "decision": decision, "scratch_probability": probability,
            "classifier_probability": classifier_values[index],
            "detector_probability": detector_scores[index] if detector_scores is not None else "",
            "threshold": threshold, "visualization": str(destination),
        })
    with (args.output / "predictions.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({
        "images": len(rows), "rejected": sum(row["decision"] == "REJECT" for row in rows),
        "threshold": threshold, "output": str(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
