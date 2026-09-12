from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw
from torchvision import transforms
from ultralytics import YOLO

from train_binary_defect_v4 import apply_temperature, clahe, load_custom, square_image, texture_image


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "outputs" / "binary_defect_v4" / "inference_config.json"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify cropped gear images as normal or defective")
    parser.add_argument("source", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "binary_defect_v4" / "inference")
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--device", default="0")
    return parser.parse_args()


def image_paths(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    return sorted(path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in EXTENSIONS)


def variants(path: Path, size: int, tta: str, family: str = "rgb") -> list[np.ndarray]:
    with Image.open(path) as opened:
        original = opened.convert("RGB")
    images = [original]
    if tta == "tta_mean":
        images += [original.transpose(Image.Transpose.FLIP_LEFT_RIGHT), original.transpose(Image.Transpose.FLIP_TOP_BOTTOM), clahe(original)]
    if family == "texture_resnet18":
        images = [texture_image(image) for image in images]
    return [np.asarray(square_image(image, size)) for image in images]


def rank_mean(values: list[list[float]]) -> list[float]:
    matrix = np.asarray(values)
    ranks = np.empty_like(matrix)
    for index, row in enumerate(matrix):
        order = np.argsort(row)
        ranks[index, order] = np.linspace(0.0, 1.0, len(row))
    return ranks.mean(axis=0).tolist()


def predict_model(model_config: dict[str, object], paths: list[Path], device: str) -> list[float]:
    family = str(model_config["family"])
    size = int(model_config["imgsz"])
    tta = str(model_config.get("tta", "none"))
    temperature = float(model_config.get("temperature", 1.0))
    yolo = YOLO(str(model_config["weights"])) if family == "yolo" else None
    network = None
    tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))])
    if family != "yolo":
        network, _ = load_custom(Path(str(model_config["weights"])))
    output = []
    for path in paths:
        arrays = variants(path, size, tta, family)
        if yolo is not None:
            defect_index = next(index for index, name in yolo.names.items() if name == "defect")
            results = yolo.predict(arrays, imgsz=size, batch=4, device=device, verbose=False)
            raw = float(np.mean([result.probs.data[defect_index].item() for result in results]))
        else:
            assert network is not None
            with torch.no_grad():
                batch = torch.stack([tensor(Image.fromarray(array)) for array in arrays]).cuda()
                raw = float(network(batch).sigmoid().mean())
        output.append(apply_temperature([raw], temperature)[0])
    return output


def main() -> None:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    paths = image_paths(args.source)
    if not paths:
        raise FileNotFoundError(f"No images found in {args.source}")
    args.output.mkdir(parents=True, exist_ok=True)
    threshold = float(args.threshold if args.threshold is not None else config["default_threshold"])
    models = config.get("models") or [{**config["model"], "tta": config["tta"], "temperature": config["temperature"]}]
    model_probabilities = [predict_model(model, paths, args.device) for model in models]
    fusion = config.get("fusion", "mean")
    matrix = np.asarray(model_probabilities)
    if fusion == "max":
        probabilities = matrix.max(axis=0).tolist()
    elif fusion == "rank_mean":
        probabilities = rank_mean(model_probabilities)
    else:
        probabilities = matrix.mean(axis=0).tolist()
    rows = []
    for path, probability in zip(paths, probabilities):
        decision = "reject" if probability >= threshold else "pass"
        with Image.open(path) as opened:
            plotted = opened.convert("RGB")
        draw = ImageDraw.Draw(plotted)
        draw.text((8, 8), f"{decision.upper()} defect={probability:.3f} threshold={threshold:.3f}", fill=(255, 30, 30) if decision == "reject" else (0, 170, 40))
        plotted.save(args.output / f"{path.stem}_prediction.jpg", quality=95)
        rows.append({"image": str(path), "decision": decision, "defect_probability": probability, "threshold": threshold})
    with (args.output / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"images": len(rows), "rejected": sum(row["decision"] == "reject" for row in rows), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
