from __future__ import annotations

import gc
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torchvision import transforms
from ultralytics import YOLO

from train_scratch_v5 import apply_temperature, build_network, square_image


def resolve_config_paths(config: dict[str, object], config_path: Path) -> dict[str, object]:
    """Resolve model paths relative to the inference config file."""
    for model in config.get("models", []):
        weight = Path(str(model["weights"]))
        if not weight.is_absolute():
            weight = config_path.parent / weight
        model["weights"] = str(weight.resolve())
    return config


def image_paths(source: Path) -> list[Path]:
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
    if source.is_file():
        return [source]
    return sorted(path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in extensions)


def tta_images(path: Path, size: int, tta: str) -> list[np.ndarray]:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    images = [image]
    if tta == "flip":
        images += [image.transpose(Image.Transpose.FLIP_LEFT_RIGHT), image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)]
    elif tta == "rot90":
        images += [image.transpose(Image.Transpose.ROTATE_90), image.transpose(Image.Transpose.ROTATE_270)]
    return [np.asarray(square_image(item, size)) for item in images]


def predict_model(model_config: dict[str, object], paths: list[Path], device: str = "0", keep_boxes: bool = False) -> tuple[list[float], list[list[dict[str, object]]]]:
    kind = str(model_config["kind"])
    family = str(model_config["family"])
    size = int(model_config["imgsz"])
    temperature = float(model_config.get("temperature", 1.0))
    probabilities: list[float] = []
    all_boxes: list[list[dict[str, object]]] = [[] for _ in paths]
    if kind == "detector":
        model = YOLO(str(model_config["weights"]))
        for index, path in enumerate(paths):
            result = model.predict(str(path), imgsz=size, conf=0.001, iou=0.7, device=device, verbose=False)[0]
            probability = 0.0
            if result.boxes is not None and len(result.boxes):
                probability = float(result.boxes.conf.max().item())
                if keep_boxes:
                    all_boxes[index] = [
                        {"xyxy": coordinates, "confidence": float(confidence), "class_id": int(class_id)}
                        for coordinates, confidence, class_id in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist())
                    ]
            probabilities.append(probability)
        del model
    elif family == "yolo_cls":
        model = YOLO(str(model_config["weights"]))
        defect_index = next(index for index, name in model.names.items() if name in {"missing_hole", "defect", "any_defect"})
        for path in paths:
            results = model.predict(tta_images(path, size, str(model_config.get("tta", "none"))), imgsz=size, batch=4, device=device, verbose=False)
            probabilities.append(float(np.mean([result.probs.data[defect_index].item() for result in results])))
        del model
    else:
        checkpoint = torch.load(str(model_config["weights"]), map_location="cpu", weights_only=False)
        network = build_network(family, pretrained=False)
        network.load_state_dict(checkpoint["model"])
        torch_device = "cuda:0" if str(device) != "cpu" and torch.cuda.is_available() else "cpu"
        network.to(torch_device).eval()
        tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))])
        with torch.no_grad():
            for path in paths:
                batch = torch.stack([tensor(Image.fromarray(array)) for array in tta_images(path, size, str(model_config.get("tta", "none")))]).to(torch_device)
                probabilities.append(float(network(batch).sigmoid().mean()))
        del network
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return apply_temperature(probabilities, temperature), all_boxes


def apply_rule(rule: dict[str, object], scores: dict[str, list[float]]) -> list[float]:
    kind = str(rule["type"])
    if kind in {"classifier", "detector"}:
        return list(scores[str(rule["models"][0])])
    if kind in {"classifier_mean", "classifier_max"}:
        matrix = np.asarray([scores[str(name)] for name in rule["models"]])
        return (matrix.mean(axis=0) if kind == "classifier_mean" else matrix.max(axis=0)).tolist()
    classifier = np.asarray(apply_rule(rule["classifier"], scores))
    detector = np.asarray(scores[str(rule["detector"])])
    if kind == "weighted":
        alpha = float(rule["alpha"])
        return (alpha * classifier + (1 - alpha) * detector).tolist()
    if kind == "soft_or":
        return np.maximum(classifier, detector).tolist()
    raise ValueError(f"Unknown fusion rule: {kind}")


def predict_config(config_path: Path, paths: list[Path], device: str = "0", keep_boxes: bool = False) -> tuple[list[float], dict[str, list[float]], list[list[dict[str, object]]], dict[str, object]]:
    config_path = config_path.expanduser().resolve()
    config = resolve_config_paths(json.loads(config_path.read_text(encoding="utf-8")), config_path)
    scores: dict[str, list[float]] = {}
    detector_boxes: list[list[dict[str, object]]] = [[] for _ in paths]
    for model_config in config["models"]:
        probabilities, boxes = predict_model(model_config, paths, device, keep_boxes)
        scores[str(model_config["name"])] = probabilities
        if model_config["kind"] == "detector":
            detector_boxes = boxes
    return apply_rule(config["fusion"], scores), scores, detector_boxes, config
