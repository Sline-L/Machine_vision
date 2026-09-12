from __future__ import annotations

import json
import math
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw
from torchvision.ops import nms
from ultralytics import YOLO

from auto_optimize_defects import OFFICIAL, OUTPUT, ROOT, RUNS, WORK, Sample, load_samples, make_split


DATASET = WORK / "datasets" / "scratch_tiled_v1"
RUN_NAME = "f_scratch_tiled_640_seed42"
RUN_DIR = RUNS / RUN_NAME
REPORT_DIR = OUTPUT / "scratch_tiled"
FULL_WEIGHTS = OUTPUT / "final" / "scratch_best.pt"
THRESHOLDS = (0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40)


@dataclass
class Prediction:
    box: tuple[float, float, float, float]
    confidence: float


def clamp_crop(cx: float, cy: float, side: int, width: int, height: int) -> tuple[int, int, int, int]:
    side = min(side, width, height)
    left = max(0, min(width - side, round(cx - side / 2)))
    top = max(0, min(height - side, round(cy - side / 2)))
    return left, top, left + side, top + side


def labels_for_crop(sample: Sample, crop: tuple[int, int, int, int]) -> list[str]:
    left, top, right, bottom = crop
    crop_width, crop_height = right - left, bottom - top
    lines = []
    for name, xmin, ymin, xmax, ymax in sample.boxes:
        if name != "scratch":
            continue
        center_x, center_y = (xmin + xmax) / 2, (ymin + ymax) / 2
        if not (left <= center_x < right and top <= center_y < bottom):
            continue
        clipped = max(left, xmin), max(top, ymin), min(right, xmax), min(bottom, ymax)
        x1, y1, x2, y2 = clipped
        if x2 <= x1 or y2 <= y1:
            continue
        x = ((x1 + x2) / 2 - left) / crop_width
        y = ((y1 + y2) / 2 - top) / crop_height
        w, h = (x2 - x1) / crop_width, (y2 - y1) / crop_height
        lines.append(f"0 {x:.6f} {y:.6f} {w:.6f} {h:.6f}")
    return lines


def save_crop(sample: Sample, crop: tuple[int, int, int, int], split: str, name: str) -> None:
    image_dir, label_dir = DATASET / "images" / split, DATASET / "labels" / split
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(sample.image) as image:
        image.crop(crop).save(image_dir / f"{name}.jpg", quality=95)
    lines = labels_for_crop(sample, crop)
    (label_dir / f"{name}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="ascii")


def build_dataset(samples: list[Sample], assignments: dict[str, str]) -> Path:
    yaml_path = DATASET / "data.yaml"
    if yaml_path.exists():
        return yaml_path
    rng = random.Random(42)
    manifest = []
    for sample in samples:
        split = assignments[sample.stem]
        if split not in {"train", "val"}:
            continue
        scratches = [box for box in sample.boxes if box[0] == "scratch"]
        if scratches:
            repeats = 3 if split == "train" else 1
            for box_index, (_, xmin, ymin, xmax, ymax) in enumerate(scratches):
                box_side = max(xmax - xmin, ymax - ymin)
                for repeat in range(repeats):
                    scale = rng.uniform(3.2, 4.8) if split == "train" else 4.0
                    side = round(max(224, min(448, box_side * scale)))
                    jitter = 0.15 * side if split == "train" else 0
                    cx = (xmin + xmax) / 2 + rng.uniform(-jitter, jitter)
                    cy = (ymin + ymax) / 2 + rng.uniform(-jitter, jitter)
                    crop = clamp_crop(cx, cy, side, sample.width, sample.height)
                    name = f"{sample.stem}_p{box_index:02d}_{repeat}"
                    save_crop(sample, crop, split, name)
                    manifest.append({"name": name, "source": sample.stem, "split": split, "kind": "positive", "crop": crop})
        else:
            repeats = 2 if split == "train" else 1
            for repeat in range(repeats):
                side = min(384, sample.width, sample.height)
                cx = rng.uniform(side / 2, sample.width - side / 2) if sample.width > side else side / 2
                cy = rng.uniform(side / 2, sample.height - side / 2) if sample.height > side else side / 2
                crop = clamp_crop(cx, cy, side, sample.width, sample.height)
                name = f"{sample.stem}_n{repeat}"
                save_crop(sample, crop, split, name)
                manifest.append({"name": name, "source": sample.stem, "split": split, "kind": "hard_negative", "crop": crop})
    yaml_path.write_text(
        f"path: {DATASET.as_posix()}\ntrain: images/train\nval: images/val\nnames:\n  0: scratch\n",
        encoding="ascii",
    )
    (DATASET / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="ascii")
    return yaml_path


def train(data: Path) -> Path:
    best = RUN_DIR / "weights" / "best.pt"
    if best.exists() and (RUN_DIR / "complete.flag").exists():
        return best
    model = YOLO(OFFICIAL)
    model.train(
        data=str(data), epochs=80, patience=20, imgsz=640, batch=32, workers=4,
        device=0, amp=True, cache="ram", project=str(RUNS), name=RUN_NAME,
        exist_ok=False, optimizer="AdamW", lr0=0.0007, weight_decay=0.0005,
        mosaic=0.0, degrees=2.0, translate=0.03, scale=0.12, fliplr=0.5,
        flipud=0.5, hsv_h=0.005, hsv_s=0.12, hsv_v=0.10,
        seed=42, deterministic=False, plots=True,
    )
    (RUN_DIR / "complete.flag").write_text("completed\n", encoding="ascii")
    return best


def tile_positions(length: int, tile: int, overlap: float = 0.5) -> list[int]:
    if length <= tile:
        return [0]
    step = max(1, round(tile * (1 - overlap)))
    positions = list(range(0, length - tile + 1, step))
    if positions[-1] != length - tile:
        positions.append(length - tile)
    return positions


def collect_tiled(model: YOLO, sample: Sample) -> list[Prediction]:
    with Image.open(sample.image) as source:
        image = np.asarray(source.convert("RGB"))
    tile = min(384, sample.width, sample.height)
    entries = []
    for top in tile_positions(sample.height, tile):
        for left in tile_positions(sample.width, tile):
            entries.append((left, top, image[top:top + tile, left:left + tile]))
    results = model.predict([entry[2] for entry in entries], imgsz=640, conf=0.005, iou=0.7, max_det=100, batch=16, device=0, verbose=False)
    predictions = []
    for (left, top, _), result in zip(entries, results):
        for box, confidence in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist()):
            predictions.append(Prediction((box[0] + left, box[1] + top, box[2] + left, box[3] + top), confidence))
    return predictions


def collect_full(model: YOLO, sample: Sample) -> list[Prediction]:
    result = model.predict(str(sample.image), imgsz=960, conf=0.005, iou=0.7, max_det=100, device=0, verbose=False)[0]
    return [Prediction(tuple(box), confidence) for box, confidence in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist())]


def merge(predictions: list[Prediction], iou: float = 0.5) -> list[Prediction]:
    if not predictions:
        return []
    boxes = torch.tensor([item.box for item in predictions], dtype=torch.float32)
    scores = torch.tensor([item.confidence for item in predictions], dtype=torch.float32)
    return [predictions[index] for index in nms(boxes, scores, iou).tolist()]


def box_iou(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    x1, y1, x2, y2 = max(left[0], right[0]), max(left[1], right[1]), min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    return intersection / max(1e-9, left_area + right_area - intersection)


def score_samples(samples: list[Sample], predictions: dict[str, list[Prediction]], threshold: float) -> dict[str, object]:
    tp = fp = fn = 0
    per_image = []
    for sample in samples:
        ground_truth = [tuple(box[1:]) for box in sample.boxes if box[0] == "scratch"]
        detected = sorted((item for item in predictions[sample.stem] if item.confidence >= threshold), key=lambda item: item.confidence, reverse=True)
        unmatched = set(range(len(ground_truth)))
        image_tp = 0
        for prediction in detected:
            matches = [(box_iou(prediction.box, ground_truth[index]), index) for index in unmatched]
            best_iou, best_index = max(matches, default=(0.0, -1))
            if best_iou >= 0.5:
                unmatched.remove(best_index)
                image_tp += 1
            else:
                fp += 1
        tp += image_tp
        fn += len(unmatched)
        per_image.append({"stem": sample.stem, "tp": image_tp, "fp": len(detected) - image_tp, "fn": len(unmatched)})
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"threshold": threshold, "precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "per_image": per_image}


def pick_threshold(samples: list[Sample], predictions: dict[str, list[Prediction]]) -> dict[str, object]:
    results = [score_samples(samples, predictions, threshold) for threshold in THRESHOLDS]
    eligible = [item for item in results if item["precision"] >= 0.5]
    return max(eligible or results, key=lambda item: (item["recall"], item["f1"], item["precision"]))


def collect_for_split(samples: list[Sample], patch: YOLO, full: YOLO) -> tuple[dict[str, list[Prediction]], dict[str, list[Prediction]]]:
    tile_only, ensemble = {}, {}
    for index, sample in enumerate(samples, 1):
        tiled = merge(collect_tiled(patch, sample))
        tile_only[sample.stem] = tiled
        ensemble[sample.stem] = merge(tiled + collect_full(full, sample))
        print(f"inference {index}/{len(samples)}: {sample.stem}")
    return tile_only, ensemble


def render_examples(samples: list[Sample], predictions: dict[str, list[Prediction]], result: dict[str, object]) -> None:
    output = REPORT_DIR / "visuals"
    output.mkdir(parents=True, exist_ok=True)
    ranked = sorted(result["per_image"], key=lambda item: (item["fn"] + item["fp"], item["fn"], item["fp"]), reverse=True)
    chosen_stems = {item["stem"] for item in ranked[:16]}
    threshold = float(result["threshold"])
    for sample in samples:
        if sample.stem not in chosen_stems:
            continue
        with Image.open(sample.image) as source:
            image = source.convert("RGB")
        draw = ImageDraw.Draw(image)
        for name, x1, y1, x2, y2 in sample.boxes:
            if name == "scratch":
                draw.rectangle((x1, y1, x2, y2), outline=(0, 220, 80), width=3)
        for prediction in predictions[sample.stem]:
            if prediction.confidence >= threshold:
                draw.rectangle(prediction.box, outline=(255, 50, 50), width=3)
                draw.text((prediction.box[0], max(0, prediction.box[1] - 12)), f"{prediction.confidence:.2f}", fill=(255, 50, 50))
        image.save(output / f"{sample.stem}.jpg", quality=95)


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required")
    samples = load_samples()
    assignments = make_split(samples)
    data = build_dataset(samples, assignments)
    weights = train(data)
    patch_model, full_model = YOLO(weights), YOLO(FULL_WEIGHTS)
    val_samples = [sample for sample in samples if assignments[sample.stem] == "val"]
    val_tile, val_ensemble = collect_for_split(val_samples, patch_model, full_model)
    candidates = {"tile_only": pick_threshold(val_samples, val_tile), "tile_plus_full": pick_threshold(val_samples, val_ensemble)}
    selected_mode = max(candidates, key=lambda name: (candidates[name]["recall"], candidates[name]["f1"]))
    threshold = float(candidates[selected_mode]["threshold"])
    test_samples = [sample for sample in samples if assignments[sample.stem] == "test"]
    test_tile, test_ensemble = collect_for_split(test_samples, patch_model, full_model)
    test_predictions = test_tile if selected_mode == "tile_only" else test_ensemble
    test = score_samples(test_samples, test_predictions, threshold)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    final_weights = OUTPUT / "final" / "scratch_tiled_best.pt"
    shutil.copy2(weights, final_weights)
    report = {
        "weights": str(final_weights), "selection": selected_mode, "validation": candidates,
        "test": test, "inference": {"tile": 384, "overlap": 0.5, "nms_iou": 0.5, "confidence": threshold},
    }
    (REPORT_DIR / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    render_examples(test_samples, test_predictions, test)
    print(json.dumps({"selection": selected_mode, "validation": candidates, "test": {key: value for key, value in test.items() if key != "per_image"}}, indent=2))


if __name__ == "__main__":
    main()
