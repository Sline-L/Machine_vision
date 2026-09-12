from __future__ import annotations

import argparse
import csv
import gc
import io
import json
import math
import os
import random
import shutil
import subprocess
import threading
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import models, transforms
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
WORK = ROOT / "dataset_defects" / "scratch_v5"
RUNS = ROOT / "runs" / "scratch_v5"
OUTPUT = ROOT / "outputs" / "scratch_v5"
OFFICIAL_DETECTOR = ROOT / "yolo26n.pt"
OFFICIAL_CLASSIFIER = ROOT / "yolo26n-cls.pt"
P2_YAML = ROOT / ".venv" / "Lib" / "site-packages" / "ultralytics" / "cfg" / "models" / "26" / "yolo26-p2.yaml"
FPR_CAPS = (0.10, 0.20, 0.30, 0.50)
PRIMARY_FPR_CAP = 0.20
SEED = 20260911


@dataclass(frozen=True)
class Sample:
    stem: str
    split: str
    label: int
    image: Path
    width: int
    height: int

    @property
    def view(self) -> str:
        ratio = max(self.width / self.height, self.height / self.width)
        return "side" if ratio >= 1.8 else "oblique" if ratio >= 1.25 else "face"


@dataclass(frozen=True)
class ClassifierExperiment:
    name: str
    family: str
    size: int
    defect_weight: float
    epochs: int
    seed: int = SEED


@dataclass(frozen=True)
class DetectorExperiment:
    name: str
    architecture: str
    epochs: int
    seed: int = SEED


CLASSIFIER_PILOTS = (
    ClassifierExperiment("p_resnet18_384_w1", "resnet18", 384, 1.0, 30),
    ClassifierExperiment("p_resnet18_512_w2", "resnet18", 512, 2.0, 30),
    ClassifierExperiment("p_efficientnet_b0_384_w1", "efficientnet_b0", 384, 1.0, 30),
    ClassifierExperiment("p_efficientnet_b0_512_w2", "efficientnet_b0", 512, 2.0, 30),
    ClassifierExperiment("p_yolo_cls_384_w1", "yolo_cls", 384, 1.0, 30),
    ClassifierExperiment("p_yolo_cls_512_w2", "yolo_cls", 512, 2.0, 30),
)
DETECTOR_PILOTS = (
    DetectorExperiment("p_detector_standard_960", "standard", 35),
    DetectorExperiment("p_detector_p2_960", "p2", 35),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the V5 high-recall scratch classifier/detector fusion")
    parser.add_argument("--hours", type=float, default=6.0)
    parser.add_argument("--workers", type=int, default=0, help="0 chooses min(8, cpu_count-2)")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--dry-run", action="store_true", help="Validate data and model construction without training")
    parser.add_argument(
        "--finalize-only",
        action="store_true",
        help="Reuse completed candidates, skip new full training, and rebuild fusion outputs",
    )
    return parser.parse_args()


def resolved_workers(requested: int) -> int:
    if requested > 0:
        return min(8, requested)
    return min(8, max(2, (os.cpu_count() or 4) - 2))


def load_samples() -> list[Sample]:
    manifest = WORK / "scratch_manifest.csv"
    if not manifest.is_file():
        raise FileNotFoundError(f"Run prepare_scratch_v5.py first: {manifest}")
    samples = []
    with manifest.open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["excluded_from_train"].lower() == "true":
                continue
            image = WORK / "images" / row["split"] / Path(row["image"]).name
            samples.append(Sample(
                stem=row["stem"],
                split=row["split"],
                label=int(row["label"] == "scratch"),
                image=image,
                width=int(row["width"]),
                height=int(row["height"]),
            ))
    counts = Counter((sample.split, sample.label) for sample in samples)
    expected = Counter({("train", 1): 119, ("train", 0): 245, ("val", 1): 43, ("val", 0): 107})
    if counts != expected or len(samples) != 514:
        raise RuntimeError(f"Unexpected V5 manifest counts: {counts}")
    return samples


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def square_image(image: Image.Image, size: int) -> Image.Image:
    image = image.convert("RGB")
    scale = size / max(image.size)
    resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), (238, 238, 238))
    canvas.paste(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    return canvas


def clahe(image: Image.Image) -> Image.Image:
    lab = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
    return Image.fromarray(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB))


def jpeg_compress(image: Image.Image, quality: int) -> Image.Image:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    with Image.open(buffer) as opened:
        return opened.convert("RGB")


class ScratchDataset(Dataset):
    def __init__(self, samples: list[Sample], size: int, augment: bool) -> None:
        self.samples = samples
        self.size = size
        self.augment = augment
        self.tensor = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ])

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, float]:
        sample = self.samples[index]
        with Image.open(sample.image) as opened:
            image = opened.convert("RGB")
        if self.augment:
            if random.random() < 0.75:
                image = image.transpose(random.choice((
                    Image.Transpose.FLIP_LEFT_RIGHT,
                    Image.Transpose.FLIP_TOP_BOTTOM,
                    Image.Transpose.ROTATE_90,
                    Image.Transpose.ROTATE_270,
                )))
            if random.random() < 0.70:
                image = ImageEnhance.Brightness(image).enhance(random.uniform(0.82, 1.18))
                image = ImageEnhance.Contrast(image).enhance(random.uniform(0.80, 1.22))
            if random.random() < 0.25:
                image = clahe(image)
            if random.random() < 0.15:
                image = image.filter(ImageFilter.GaussianBlur(random.uniform(0.1, 1.0)))
            if random.random() < 0.20:
                array = np.asarray(image).astype(np.float32)
                array += np.random.normal(0, random.uniform(1.0, 5.0), array.shape)
                image = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))
            if random.random() < 0.20:
                gamma = random.uniform(0.82, 1.18)
                table = np.array([((value / 255.0) ** gamma) * 255 for value in range(256)], dtype=np.uint8)
                image = Image.fromarray(table[np.asarray(image)])
            if random.random() < 0.15:
                image = jpeg_compress(image, random.randint(65, 92))
        return self.tensor(square_image(image, self.size)), float(sample.label)


def build_network(family: str) -> nn.Module:
    if family == "resnet18":
        network = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        network.fc = nn.Linear(network.fc.in_features, 1)
    elif family == "efficientnet_b0":
        network = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
        network.classifier[1] = nn.Linear(network.classifier[1].in_features, 1)
    else:
        raise ValueError(family)
    return network


def load_custom(path: Path, device: str = "cuda") -> tuple[nn.Module, dict[str, object]]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    network = build_network(str(checkpoint["family"]))
    network.load_state_dict(checkpoint["model"])
    return network.to(device).eval(), checkpoint


class FocalBCE(nn.Module):
    def __init__(self, positive_weight: float, gamma: float = 1.5) -> None:
        super().__init__()
        self.positive_weight = positive_weight
        self.gamma = gamma

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        probability = logits.sigmoid()
        pt = targets * probability + (1 - targets) * (1 - probability)
        weights = torch.where(targets > 0.5, self.positive_weight, 1.0)
        return (weights * (1 - pt).pow(self.gamma) * bce).mean()


def choose_threshold(labels: list[int], probabilities: list[float], fpr_cap: float) -> dict[str, float | int]:
    candidates = sorted({0.0, 1.0, *probabilities})
    best = None
    for threshold in candidates:
        guesses = [value >= threshold for value in probabilities]
        tp = sum(actual == 1 and guess for actual, guess in zip(labels, guesses))
        fp = sum(actual == 0 and guess for actual, guess in zip(labels, guesses))
        tn = sum(actual == 0 and not guess for actual, guess in zip(labels, guesses))
        fn = sum(actual == 1 and not guess for actual, guess in zip(labels, guesses))
        recall = tp / max(1, tp + fn)
        precision = tp / max(1, tp + fp)
        fpr = fp / max(1, fp + tn)
        row = {
            "threshold": float(threshold), "recall": recall, "precision": precision,
            "f1": 2 * precision * recall / max(1e-9, precision + recall), "fpr": fpr,
            "specificity": 1 - fpr, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        }
        key = (fpr <= fpr_cap, recall, -fpr, precision)
        if best is None or key > best[0]:
            best = (key, row)
    assert best is not None
    return best[1]


def binary_auc(labels: list[int], probabilities: list[float]) -> tuple[float, float]:
    order = sorted(range(len(labels)), key=lambda index: probabilities[index], reverse=True)
    positives = sum(labels)
    negatives = len(labels) - positives
    tp = fp = 0
    previous_recall = 0.0
    auprc = 0.0
    roc = [(0.0, 0.0)]
    for index in order:
        if labels[index]:
            tp += 1
        else:
            fp += 1
        recall = tp / max(1, positives)
        precision = tp / max(1, tp + fp)
        auprc += (recall - previous_recall) * precision
        previous_recall = recall
        roc.append((fp / max(1, negatives), recall))
    auroc = sum((right[0] - left[0]) * (left[1] + right[1]) / 2 for left, right in zip(roc, roc[1:]))
    return auroc, auprc


def temperature_scale(labels: list[int], probabilities: list[float]) -> float:
    clipped = np.clip(np.asarray(probabilities), 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped))
    actual = np.asarray(labels)
    best = (math.inf, 1.0)
    for temperature in np.linspace(0.35, 4.0, 147):
        scaled = 1 / (1 + np.exp(-logits / temperature))
        nll = float(-np.mean(actual * np.log(scaled + 1e-9) + (1 - actual) * np.log(1 - scaled + 1e-9)))
        if nll < best[0]:
            best = (nll, float(temperature))
    return best[1]


def apply_temperature(probabilities: list[float], temperature: float) -> list[float]:
    clipped = np.clip(np.asarray(probabilities), 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped))
    return (1 / (1 + np.exp(-logits / temperature))).tolist()


def undo_temperature(probability: float, temperature: float) -> float:
    clipped = float(np.clip(probability, 1e-6, 1 - 1e-6))
    calibrated_logit = math.log(clipped / (1 - clipped))
    return 1 / (1 + math.exp(-calibrated_logit * temperature))


def score_probabilities(samples: list[Sample], probabilities: list[float], threshold: float) -> dict[str, object]:
    labels = [sample.label for sample in samples]
    point = choose_threshold(labels, probabilities, 1.0)
    guesses = [value >= threshold for value in probabilities]
    tp = sum(actual == 1 and guess for actual, guess in zip(labels, guesses))
    fp = sum(actual == 0 and guess for actual, guess in zip(labels, guesses))
    tn = sum(actual == 0 and not guess for actual, guess in zip(labels, guesses))
    fn = sum(actual == 1 and not guess for actual, guess in zip(labels, guesses))
    recall = tp / max(1, tp + fn)
    precision = tp / max(1, tp + fp)
    fpr = fp / max(1, fp + tn)
    auroc, auprc = binary_auc(labels, probabilities)
    groups = {}
    for view in ("face", "oblique", "side"):
        indexes = [index for index, sample in enumerate(samples) if sample.label and sample.view == view]
        groups[view] = {"count": len(indexes), "recall": sum(probabilities[index] >= threshold for index in indexes) / max(1, len(indexes))}
    return {
        "overall": {
            "threshold": threshold, "recall": recall, "precision": precision,
            "f1": 2 * precision * recall / max(1e-9, precision + recall), "fpr": fpr,
            "specificity": 1 - fpr, "npv": tn / max(1, tn + fn),
            "tp": tp, "fp": fp, "tn": tn, "fn": fn, "auroc": auroc, "auprc": auprc,
        },
        "views": groups,
        "unused_unconstrained": point,
    }


def prediction_variants(path: Path, size: int, tta: str) -> list[np.ndarray]:
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


def predict_classifier(weights: Path, experiment: ClassifierExperiment, samples: list[Sample], tta: str) -> list[float]:
    output = []
    if experiment.family == "yolo_cls":
        model = YOLO(weights)
        defect_index = next(index for index, name in model.names.items() if name == "defect")
        for sample in samples:
            results = model.predict(prediction_variants(sample.image, experiment.size, tta), imgsz=experiment.size, batch=4, device=0, verbose=False)
            output.append(float(np.mean([result.probs.data[defect_index].item() for result in results])))
        del model
    else:
        network, _ = load_custom(weights)
        tensor = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ])
        with torch.no_grad():
            for sample in samples:
                batch = torch.stack([tensor(Image.fromarray(image)) for image in prediction_variants(sample.image, experiment.size, tta)]).cuda()
                output.append(float(network(batch).sigmoid().mean()))
        del network
    gc.collect()
    torch.cuda.empty_cache()
    return output


def train_custom(
    experiment: ClassifierExperiment,
    train_samples: list[Sample],
    val_samples: list[Sample],
    workers: int,
    deadline: float,
    hard_weights: dict[str, float] | None = None,
) -> Path | None:
    run = RUNS / experiment.name
    best = run / "best.pt"
    if best.is_file() and (run / "complete.flag").is_file():
        return best
    if time.monotonic() >= deadline:
        return None
    run.mkdir(parents=True, exist_ok=True)
    set_seed(experiment.seed)
    train_data = ScratchDataset(train_samples, experiment.size, True)
    val_data = ScratchDataset(val_samples, experiment.size, False)
    strata = Counter((sample.label, sample.view) for sample in train_samples)
    hard_weights = hard_weights or {}
    sample_weights = [(1.0 / strata[(sample.label, sample.view)]) * hard_weights.get(sample.stem, 1.0) for sample in train_samples]
    sampler = WeightedRandomSampler(sample_weights, len(train_samples), replacement=True)
    batch = 24 if experiment.size == 384 else 12
    train_loader = DataLoader(train_data, batch_size=batch, sampler=sampler, num_workers=workers, pin_memory=True, persistent_workers=workers > 0)
    val_loader = DataLoader(val_data, batch_size=batch, shuffle=False, num_workers=workers, pin_memory=True, persistent_workers=workers > 0)
    network = build_network(experiment.family).cuda()
    optimizer = torch.optim.AdamW(network.parameters(), lr=3e-4, weight_decay=5e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=experiment.epochs, eta_min=1e-6)
    criterion = FocalBCE(experiment.defect_weight)
    scaler = torch.amp.GradScaler("cuda")
    best_score = (-1.0, -1.0, -1.0)
    stale = 0
    history = []
    for epoch in range(1, experiment.epochs + 1):
        if time.monotonic() >= deadline:
            break
        network.train()
        losses = []
        for images, labels in train_loader:
            images = images.cuda(non_blocking=True)
            labels = labels.cuda(non_blocking=True).unsqueeze(1)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.float16):
                loss = criterion(network(images), labels)
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite loss in {experiment.name}")
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach()))
        scheduler.step()
        network.eval()
        probabilities = []
        labels = []
        with torch.no_grad():
            for images, target in val_loader:
                probabilities.extend(network(images.cuda(non_blocking=True)).sigmoid().cpu().flatten().tolist())
                labels.extend(target.int().tolist())
        point = choose_threshold(labels, probabilities, PRIMARY_FPR_CAP)
        score = (float(point["recall"]), -float(point["fpr"]), float(point["precision"]))
        history.append({"epoch": epoch, "loss": float(np.mean(losses)), **point})
        print(f"{experiment.name} epoch={epoch} loss={np.mean(losses):.4f} recall={point['recall']:.3f} fpr={point['fpr']:.3f}", flush=True)
        if score > best_score:
            best_score = score
            stale = 0
            torch.save({
                "model": network.state_dict(), "family": experiment.family, "size": experiment.size,
                "defect_weight": experiment.defect_weight, "seed": experiment.seed,
            }, best)
        else:
            stale += 1
        if stale >= (10 if experiment.epochs <= 35 else 18):
            break
    (run / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    (run / "complete.flag").write_text("complete\n", encoding="ascii")
    del network, train_loader, val_loader
    gc.collect()
    torch.cuda.empty_cache()
    return best if best.is_file() else None


def materialize_yolo_classification(experiment: ClassifierExperiment, samples: list[Sample], hard_weights: dict[str, float] | None = None) -> Path:
    target = WORK / "yolo_classification" / experiment.name
    marker = target / "complete.flag"
    if marker.is_file():
        return target
    hard_weights = hard_weights or {}
    for sample in samples:
        label = "defect" if sample.label else "normal"
        destination = target / sample.split / label
        destination.mkdir(parents=True, exist_ok=True)
        copies = 1
        if sample.split == "train":
            copies = max(copies, round(experiment.defect_weight) if sample.label else 1)
            copies = max(copies, round(hard_weights.get(sample.stem, 1.0)))
        for index in range(copies):
            suffix = "" if index == 0 else f"_copy{index}"
            shutil.copy2(sample.image, destination / f"{sample.stem}{suffix}{sample.image.suffix.lower()}")
    marker.write_text("complete\n", encoding="ascii")
    return target


def train_yolo_classifier(
    experiment: ClassifierExperiment,
    samples: list[Sample],
    workers: int,
    deadline: float,
    hard_weights: dict[str, float] | None = None,
) -> Path | None:
    run = RUNS / experiment.name
    best = run / "weights" / "best.pt"
    if best.is_file() and (run / "complete.flag").is_file():
        return best
    if time.monotonic() >= deadline:
        return None
    data = materialize_yolo_classification(experiment, samples, hard_weights)
    batch = 32 if experiment.size == 384 else 16
    for attempt in range(3):
        try:
            model = YOLO(OFFICIAL_CLASSIFIER)
            model.train(
                data=str(data), epochs=experiment.epochs, patience=10 if experiment.epochs <= 35 else 18,
                imgsz=experiment.size, batch=batch, workers=workers, device=0, amp=True, cache="ram",
                project=str(RUNS), name=experiment.name, exist_ok=True, optimizer="AdamW", lr0=7e-4,
                weight_decay=5e-4, scale=0.0, degrees=0.0, translate=0.0, fliplr=0.5, flipud=0.5,
                hsv_h=0.003, hsv_s=0.10, hsv_v=0.15, erasing=0.0, auto_augment=None,
                seed=experiment.seed, deterministic=False, plots=True,
            )
            break
        except torch.OutOfMemoryError:
            batch //= 2
            torch.cuda.empty_cache()
            if batch < 2 or attempt == 2:
                raise
    (run / "complete.flag").write_text("complete\n", encoding="ascii")
    return best if best.is_file() else None


def detector_model(architecture: str, weights: Path | None = None) -> YOLO:
    if weights is not None:
        return YOLO(weights)
    if architecture == "standard":
        return YOLO(OFFICIAL_DETECTOR)
    return YOLO(P2_YAML).load(OFFICIAL_DETECTOR)


def materialize_detector_dataset(name: str, samples: list[Sample], hard_weights: dict[str, float] | None = None) -> Path:
    target = WORK / "detectors" / name
    yaml_path = target / "data.yaml"
    if yaml_path.is_file():
        return yaml_path
    hard_weights = hard_weights or {}
    for sample in samples:
        source_label = WORK / "labels" / sample.split / f"{sample.stem}.txt"
        image_dir = target / "images" / sample.split
        label_dir = target / "labels" / sample.split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        copies = round(hard_weights.get(sample.stem, 1.0)) if sample.split == "train" else 1
        for index in range(max(1, copies)):
            suffix = "" if index == 0 else f"_hard{index}"
            shutil.copy2(sample.image, image_dir / f"{sample.stem}{suffix}{sample.image.suffix.lower()}")
            shutil.copy2(source_label, label_dir / f"{sample.stem}{suffix}.txt")
    yaml_path.write_text(
        f"path: {target.as_posix()}\ntrain: images/train\nval: images/val\nnames:\n  0: scratch\n",
        encoding="ascii",
    )
    return yaml_path


def train_detector(
    experiment: DetectorExperiment,
    samples: list[Sample],
    workers: int,
    deadline: float,
    hard_weights: dict[str, float] | None = None,
) -> Path | None:
    run = RUNS / experiment.name
    best = run / "weights" / "best.pt"
    if best.is_file() and (run / "complete.flag").is_file():
        return best
    if time.monotonic() >= deadline:
        return None
    data = materialize_detector_dataset(experiment.name, samples, hard_weights)
    batch = 12 if experiment.architecture == "standard" else 6
    detector_workers = min(workers, 4)
    for attempt in range(4):
        try:
            model = detector_model(experiment.architecture)
            model.train(
                data=str(data), epochs=experiment.epochs, patience=12 if experiment.epochs <= 35 else 20,
                imgsz=960, batch=batch, workers=detector_workers, device=0, amp=True, cache="ram",
                project=str(RUNS), name=experiment.name, exist_ok=True, optimizer="AdamW",
                lr0=8e-4, weight_decay=5e-4, mosaic=0.0, mixup=0.0, cutmix=0.0,
                degrees=0.0, translate=0.01, scale=0.05, fliplr=0.5, flipud=0.5,
                hsv_h=0.003, hsv_s=0.10, hsv_v=0.12, seed=experiment.seed,
                deterministic=False, plots=True,
            )
            break
        except torch.OutOfMemoryError:
            batch //= 2
            torch.cuda.empty_cache()
            if batch < 1 or attempt == 3:
                raise
    (run / "complete.flag").write_text("complete\n", encoding="ascii")
    return best if best.is_file() else None


def predict_detector(weights: Path, samples: list[Sample]) -> tuple[list[float], dict[str, list[tuple[float, float, float, float, float]]]]:
    model = YOLO(weights)
    probabilities = []
    boxes = {}
    for sample in samples:
        result = model.predict(str(sample.image), imgsz=960, conf=0.001, iou=0.7, device=0, verbose=False)[0]
        rows = []
        if result.boxes is not None and len(result.boxes):
            for coords, confidence in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist()):
                rows.append((*map(float, coords), float(confidence)))
        boxes[sample.stem] = rows
        probabilities.append(max((row[4] for row in rows), default=0.0))
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return probabilities, boxes


def read_ground_truth(sample: Sample) -> list[tuple[float, float, float, float]]:
    path = WORK / "labels" / sample.split / f"{sample.stem}.txt"
    output = []
    for line in path.read_text(encoding="ascii").splitlines():
        _, cx, cy, width, height = map(float, line.split())
        output.append(((cx - width / 2) * sample.width, (cy - height / 2) * sample.height, (cx + width / 2) * sample.width, (cy + height / 2) * sample.height))
    return output


def box_iou(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> float:
    ix1, iy1 = max(left[0], right[0]), max(left[1], right[1])
    ix2, iy2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    return intersection / max(1e-9, left_area + right_area - intersection)


def box_metrics(samples: list[Sample], predictions: dict[str, list[tuple[float, float, float, float, float]]], confidence: float, iou_threshold: float) -> dict[str, float | int]:
    tp = fp = fn = 0
    for sample in samples:
        actual = read_ground_truth(sample)
        predicted = [row[:4] for row in predictions[sample.stem] if row[4] >= confidence]
        matched = set()
        for box in predicted:
            candidates = [(box_iou(box, gt), index) for index, gt in enumerate(actual) if index not in matched]
            best = max(candidates, default=(0.0, -1))
            if best[0] >= iou_threshold:
                tp += 1
                matched.add(best[1])
            else:
                fp += 1
        fn += len(actual) - len(matched)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    return {"iou": iou_threshold, "precision": precision, "recall": recall, "f1": 2 * precision * recall / max(1e-9, precision + recall), "tp": tp, "fp": fp, "fn": fn}


def evaluate_classifier(
    experiment: ClassifierExperiment,
    weights: Path,
    samples: list[Sample],
) -> tuple[dict[str, object], list[float]]:
    labels = [sample.label for sample in samples]
    choices = []
    for tta in ("none", "tta_mean"):
        raw = predict_classifier(weights, experiment, samples, tta)
        temperature = temperature_scale(labels, raw)
        probabilities = apply_temperature(raw, temperature)
        points = {str(cap): choose_threshold(labels, probabilities, cap) for cap in FPR_CAPS}
        primary = points[str(PRIMARY_FPR_CAP)]
        auroc, auprc = binary_auc(labels, probabilities)
        key = (primary["fpr"] <= PRIMARY_FPR_CAP, primary["recall"], -primary["fpr"], auprc)
        choices.append((key, {"tta": tta, "temperature": temperature, "operating_points": points, "auroc": auroc, "auprc": auprc}, probabilities))
    _, result, probabilities = max(choices, key=lambda item: item[0])
    return result, probabilities


def hard_weights(samples: list[Sample], probabilities: list[float], threshold: float) -> dict[str, float]:
    output = {}
    for sample, probability in zip(samples, probabilities):
        if sample.label and probability < threshold:
            output[sample.stem] = 3.0
        elif not sample.label and probability >= threshold:
            output[sample.stem] = 2.0
    return output


def save_confusion(metrics: dict[str, object], destination: Path) -> None:
    values = metrics["overall"]
    canvas = Image.new("RGB", (640, 520), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((30, 20), "Scratch V5 confusion matrix", fill="black")
    draw.text((215, 75), "Pred NORMAL", fill="black")
    draw.text((430, 75), "Pred SCRATCH", fill="black")
    draw.text((30, 190), "True NORMAL", fill="black")
    draw.text((30, 370), "True SCRATCH", fill="black")
    for x, y, value, color in ((210, 130, values["tn"], "#b8e6bf"), (420, 130, values["fp"], "#f4b8b8"), (210, 310, values["fn"], "#f4b8b8"), (420, 310, values["tp"], "#b8e6bf")):
        draw.rectangle((x, y, x + 170, y + 140), fill=color, outline="black", width=2)
        draw.text((x + 70, y + 55), str(value), fill="black")
    canvas.save(destination)


class GpuMonitor:
    def __init__(self, destination: Path) -> None:
        self.destination = destination
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=5)

    def _run(self) -> None:
        first = not self.destination.exists()
        while not self.stop_event.is_set():
            try:
                result = subprocess.run([
                    "nvidia-smi", "--query-gpu=timestamp,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                    "--format=csv,noheader,nounits",
                ], capture_output=True, text=True, timeout=10, check=True)
                with self.destination.open("a", encoding="utf-8", newline="") as handle:
                    if first:
                        handle.write("timestamp,utilization_gpu_percent,memory_used_mb,memory_total_mb,temperature_c,power_w\n")
                        first = False
                    handle.write(result.stdout.strip() + "\n")
            except Exception:
                pass
            self.stop_event.wait(30)


def save_leaderboard(rows: list[dict[str, object]]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "leaderboard.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ("name", "kind", "stage", "family", "size", "recall", "precision", "fpr", "f1", "auroc", "auprc", "weights", "error")
    with (OUTPUT / "leaderboard.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            point = row.get("operating_points", {}).get(str(PRIMARY_FPR_CAP), {}) if isinstance(row.get("operating_points"), dict) else {}
            writer.writerow({
                "name": row.get("name"), "kind": row.get("kind"), "stage": row.get("stage"),
                "family": row.get("family") or row.get("architecture"), "size": row.get("size", 960 if row.get("kind") == "detector" else ""),
                "recall": point.get("recall"), "precision": point.get("precision"), "fpr": point.get("fpr"), "f1": point.get("f1"),
                "auroc": row.get("auroc"), "auprc": row.get("auprc"), "weights": row.get("weights"), "error": row.get("error"),
            })


def main() -> None:
    args = parse_args()
    os.chdir(ROOT)
    workers = resolved_workers(args.workers)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for V5 training")
    if not OFFICIAL_DETECTOR.is_file() or not OFFICIAL_CLASSIFIER.is_file() or not P2_YAML.is_file():
        raise FileNotFoundError("One or more official YOLO weights/model YAML files are missing")
    samples = load_samples()
    train_samples = [sample for sample in samples if sample.split == "train"]
    val_samples = [sample for sample in samples if sample.split == "val"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    runtime = {
        "gpu": torch.cuda.get_device_name(0), "cuda": torch.version.cuda, "torch": torch.__version__,
        "cpu_logical_cores": os.cpu_count(), "workers": workers, "amp": True,
        "train_images": len(train_samples), "val_images": len(val_samples),
    }
    (OUTPUT / "runtime.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    print(json.dumps(runtime, indent=2), flush=True)
    if args.dry_run:
        for family in ("resnet18", "efficientnet_b0"):
            network = build_network(family)
            del network
        detector_model("standard")
        detector_model("p2")
        print("V5 dry-run passed")
        return

    started = time.monotonic()
    deadline = started + args.hours * 3600
    monitor = GpuMonitor(OUTPUT / "gpu_monitor.csv")
    monitor.start()
    leaderboard: list[dict[str, object]] = []
    classifier_artifacts: list[tuple[ClassifierExperiment, Path, dict[str, object], list[float]]] = []
    detector_artifacts: list[tuple[DetectorExperiment, Path, dict[str, object], list[float], dict[str, list[tuple[float, float, float, float, float]]]]] = []
    try:
        for experiment in CLASSIFIER_PILOTS:
            if time.monotonic() >= deadline:
                break
            print(f"\n=== {experiment.name} ===", flush=True)
            try:
                weights = train_yolo_classifier(experiment, samples, workers, deadline) if experiment.family == "yolo_cls" else train_custom(experiment, train_samples, val_samples, workers, deadline)
                if weights is None:
                    break
                evaluation, probabilities = evaluate_classifier(experiment, weights, val_samples)
                row = {"name": experiment.name, "kind": "classifier", "stage": "pilot", **asdict(experiment), "weights": str(weights), **evaluation}
                leaderboard.append(row)
                classifier_artifacts.append((experiment, weights, evaluation, probabilities))
                save_leaderboard(leaderboard)
            except Exception as error:
                leaderboard.append({"name": experiment.name, "kind": "classifier", "stage": "pilot", "error": repr(error)})
                save_leaderboard(leaderboard)
                print(f"FAILED {experiment.name}: {error!r}", flush=True)

        for experiment in DETECTOR_PILOTS:
            if time.monotonic() >= deadline:
                break
            print(f"\n=== {experiment.name} ===", flush=True)
            try:
                weights = train_detector(experiment, samples, workers, deadline)
                if weights is None:
                    break
                probabilities, boxes = predict_detector(weights, val_samples)
                temperature = temperature_scale([sample.label for sample in val_samples], probabilities)
                calibrated = apply_temperature(probabilities, temperature)
                points = {str(cap): choose_threshold([sample.label for sample in val_samples], calibrated, cap) for cap in FPR_CAPS}
                threshold = float(points[str(PRIMARY_FPR_CAP)]["threshold"])
                raw_threshold = undo_temperature(threshold, temperature)
                auroc, auprc = binary_auc([sample.label for sample in val_samples], calibrated)
                evaluation = {
                    "temperature": temperature, "operating_points": points, "auroc": auroc, "auprc": auprc,
                    "box_iou_0.3": box_metrics(val_samples, boxes, raw_threshold, 0.3),
                    "box_iou_0.5": box_metrics(val_samples, boxes, raw_threshold, 0.5),
                }
                row = {"name": experiment.name, "kind": "detector", "stage": "pilot", **asdict(experiment), "weights": str(weights), **evaluation}
                leaderboard.append(row)
                detector_artifacts.append((experiment, weights, evaluation, calibrated, boxes))
                save_leaderboard(leaderboard)
            except Exception as error:
                leaderboard.append({"name": experiment.name, "kind": "detector", "stage": "pilot", "error": repr(error)})
                save_leaderboard(leaderboard)
                print(f"FAILED {experiment.name}: {error!r}", flush=True)

        if not classifier_artifacts:
            raise RuntimeError("No classifier experiment completed")
        rank_key = lambda item: (
            item[2]["operating_points"][str(PRIMARY_FPR_CAP)]["fpr"] <= PRIMARY_FPR_CAP,
            item[2]["operating_points"][str(PRIMARY_FPR_CAP)]["recall"],
            -item[2]["operating_points"][str(PRIMARY_FPR_CAP)]["fpr"],
            item[2]["auprc"],
        )
        classifier_artifacts.sort(key=rank_key, reverse=True)
        best_pilot = classifier_artifacts[0]
        train_probabilities = predict_classifier(best_pilot[1], best_pilot[0], train_samples, str(best_pilot[2]["tta"]))
        train_temperature = temperature_scale([sample.label for sample in train_samples], train_probabilities)
        train_calibrated = apply_temperature(train_probabilities, train_temperature)
        train_point = choose_threshold([sample.label for sample in train_samples], train_calibrated, PRIMARY_FPR_CAP)
        classifier_hard = hard_weights(train_samples, train_calibrated, float(train_point["threshold"]))
        (OUTPUT / "classifier_hard_cases.json").write_text(json.dumps(classifier_hard, indent=2), encoding="utf-8")

        full_classifiers = []
        seen_shapes = set()
        for rank, pilot in enumerate(classifier_artifacts, 1):
            shape = (pilot[0].family, pilot[0].size)
            if shape in seen_shapes:
                continue
            seen_shapes.add(shape)
            full_classifiers.append(ClassifierExperiment(
                f"f_{pilot[0].family}_{pilot[0].size}_w{int(pilot[0].defect_weight)}_s{args.seed}",
                pilot[0].family, pilot[0].size, pilot[0].defect_weight, 100, args.seed,
            ))
            if len(full_classifiers) == 2:
                break
        for experiment in full_classifiers:
            if time.monotonic() >= deadline:
                break
            print(f"\n=== {experiment.name} ===", flush=True)
            try:
                weights = train_yolo_classifier(experiment, samples, workers, deadline, classifier_hard) if experiment.family == "yolo_cls" else train_custom(experiment, train_samples, val_samples, workers, deadline, classifier_hard)
                if weights is None:
                    break
                evaluation, probabilities = evaluate_classifier(experiment, weights, val_samples)
                row = {"name": experiment.name, "kind": "classifier", "stage": "full", **asdict(experiment), "weights": str(weights), **evaluation}
                leaderboard.append(row)
                classifier_artifacts.append((experiment, weights, evaluation, probabilities))
                save_leaderboard(leaderboard)
            except Exception as error:
                leaderboard.append({"name": experiment.name, "kind": "classifier", "stage": "full", "error": repr(error)})
                save_leaderboard(leaderboard)
                print(f"FAILED {experiment.name}: {error!r}", flush=True)

        if detector_artifacts and time.monotonic() < deadline and not args.finalize_only:
            detector_artifacts.sort(key=rank_key, reverse=True)
            best_detector_pilot = detector_artifacts[0]
            train_detector_probabilities, _ = predict_detector(best_detector_pilot[1], train_samples)
            train_detector_temperature = temperature_scale([sample.label for sample in train_samples], train_detector_probabilities)
            train_detector_calibrated = apply_temperature(train_detector_probabilities, train_detector_temperature)
            detector_train_point = choose_threshold([sample.label for sample in train_samples], train_detector_calibrated, PRIMARY_FPR_CAP)
            detector_hard = hard_weights(train_samples, train_detector_calibrated, float(detector_train_point["threshold"]))
            (OUTPUT / "detector_hard_cases.json").write_text(json.dumps(detector_hard, indent=2), encoding="utf-8")
            full_detector = DetectorExperiment(f"f_detector_{best_detector_pilot[0].architecture}_960_s{args.seed}", best_detector_pilot[0].architecture, 100, args.seed)
            print(f"\n=== {full_detector.name} ===", flush=True)
            try:
                weights = train_detector(full_detector, samples, workers, deadline, detector_hard)
                if weights is not None:
                    probabilities, boxes = predict_detector(weights, val_samples)
                    temperature = temperature_scale([sample.label for sample in val_samples], probabilities)
                    calibrated = apply_temperature(probabilities, temperature)
                    points = {str(cap): choose_threshold([sample.label for sample in val_samples], calibrated, cap) for cap in FPR_CAPS}
                    auroc, auprc = binary_auc([sample.label for sample in val_samples], calibrated)
                    evaluation = {"temperature": temperature, "operating_points": points, "auroc": auroc, "auprc": auprc}
                    row = {"name": full_detector.name, "kind": "detector", "stage": "full", **asdict(full_detector), "weights": str(weights), **evaluation}
                    leaderboard.append(row)
                    detector_artifacts.append((full_detector, weights, evaluation, calibrated, boxes))
                    save_leaderboard(leaderboard)
            except Exception as error:
                leaderboard.append({"name": full_detector.name, "kind": "detector", "stage": "full", "error": repr(error)})
                save_leaderboard(leaderboard)
                print(f"FAILED {full_detector.name}: {error!r}", flush=True)

        classifier_artifacts.sort(key=rank_key, reverse=True)
        chosen_classifiers = classifier_artifacts[:2]
        labels = [sample.label for sample in val_samples]
        fusion_candidates: list[tuple[str, list[float], dict[str, object]]] = []
        for item in chosen_classifiers:
            fusion_candidates.append((item[0].name, item[3], {"type": "classifier", "models": [item[0].name]}))
        if len(chosen_classifiers) >= 2:
            matrix = np.asarray([item[3] for item in chosen_classifiers])
            fusion_candidates.append(("classifier_mean", matrix.mean(axis=0).tolist(), {"type": "classifier_mean", "models": [item[0].name for item in chosen_classifiers]}))
            fusion_candidates.append(("classifier_soft_or", matrix.max(axis=0).tolist(), {"type": "classifier_max", "models": [item[0].name for item in chosen_classifiers]}))
        best_detector = None
        if detector_artifacts:
            detector_artifacts.sort(key=rank_key, reverse=True)
            best_detector = detector_artifacts[0]
            classifier_sets = list(fusion_candidates)
            for classifier_name, classifier_scores, classifier_rule in classifier_sets:
                for alpha in (0.25, 0.50, 0.75):
                    combined = (alpha * np.asarray(classifier_scores) + (1 - alpha) * np.asarray(best_detector[3])).tolist()
                    fusion_candidates.append((f"weighted_{classifier_name}_a{alpha:.2f}", combined, {"type": "weighted", "alpha": alpha, "classifier": classifier_rule}))
                combined = np.maximum(classifier_scores, best_detector[3]).tolist()
                fusion_candidates.append((f"soft_or_{classifier_name}", combined, {"type": "soft_or", "classifier": classifier_rule}))

        fusion_rows = []
        for name, probabilities, rule in fusion_candidates:
            points = {str(cap): choose_threshold(labels, probabilities, cap) for cap in FPR_CAPS}
            auroc, auprc = binary_auc(labels, probabilities)
            primary = points[str(PRIMARY_FPR_CAP)]
            fusion_rows.append({"name": name, "probabilities": probabilities, "rule": rule, "operating_points": points, "auroc": auroc, "auprc": auprc, "key": (primary["fpr"] <= PRIMARY_FPR_CAP, primary["recall"], -primary["fpr"], auprc)})
        winner = max(fusion_rows, key=lambda row: row["key"])

        final = OUTPUT / "final"
        final.mkdir(parents=True, exist_ok=True)
        model_configs = []
        for index, item in enumerate(chosen_classifiers, 1):
            destination = final / f"classifier_{index}.pt"
            shutil.copy2(item[1], destination)
            model_configs.append({
                "name": item[0].name, "family": item[0].family, "weights": str(destination),
                "imgsz": item[0].size, "tta": item[2]["tta"], "temperature": item[2]["temperature"],
            })
        detector_config = None
        detector_boxes = {}
        if best_detector is not None:
            destination = final / "detector.pt"
            shutil.copy2(best_detector[1], destination)
            detector_config = {"name": best_detector[0].name, "weights": str(destination), "imgsz": 960, "temperature": best_detector[2]["temperature"], "conf_floor": 0.001, "iou": 0.7}
            detector_boxes = best_detector[4]
        config = {
            "version": "scratch_v5", "classes": {"0": "normal", "1": "scratch"},
            "classifiers": model_configs, "detector": detector_config,
            "fusion": winner["rule"], "default_threshold": winner["operating_points"][str(PRIMARY_FPR_CAP)]["threshold"],
            "operating_points": winner["operating_points"],
            "decision": "REJECT when fused scratch probability >= threshold",
        }
        (OUTPUT / "inference_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

        threshold = float(config["default_threshold"])
        metrics = score_probabilities(val_samples, winner["probabilities"], threshold)
        save_confusion(metrics, OUTPUT / "confusion_matrix.png")
        visual_dir = OUTPUT / "val_predictions"
        visual_dir.mkdir(parents=True, exist_ok=True)
        prediction_rows = []
        for sample, probability in zip(val_samples, winner["probabilities"]):
            decision = "REJECT" if probability >= threshold else "PASS"
            with Image.open(sample.image) as opened:
                image = opened.convert("RGB")
            draw = ImageDraw.Draw(image)
            sample_boxes = detector_boxes.get(sample.stem, []) if detector_config else []
            if sample_boxes:
                x1, y1, x2, y2, confidence = max(sample_boxes, key=lambda box: box[4])
                if confidence >= 0.05:
                    draw.rectangle((x1, y1, x2, y2), outline=(255, 170, 0), width=2)
            draw.text((8, 8), f"{decision} scratch={probability:.3f} threshold={threshold:.3f}", fill=(255, 30, 30) if decision == "REJECT" else (0, 170, 40))
            image.save(visual_dir / f"{sample.stem}.jpg", quality=95)
            prediction_rows.append({
                "stem": sample.stem, "truth": "scratch" if sample.label else "normal", "view": sample.view,
                "scratch_probability": probability, "threshold": threshold, "decision": decision,
                "correct": int((probability >= threshold) == bool(sample.label)),
            })
        with (OUTPUT / "val_predictions.csv").open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=prediction_rows[0].keys())
            writer.writeheader()
            writer.writerows(prediction_rows)

        hard_review = sorted(
            prediction_rows,
            key=lambda row: (row["correct"], abs(float(row["scratch_probability"]) - threshold)),
        )[:60]
        with (OUTPUT / "review_list.csv").open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=prediction_rows[0].keys())
            writer.writeheader()
            writer.writerows(hard_review)

        report = {
            "runtime": runtime, "elapsed_hours": (time.monotonic() - started) / 3600,
            "data": json.loads((WORK / "preflight_report.json").read_text(encoding="utf-8")),
            "selection_split": "val", "strict_blind_test": False,
            "winner": {key: value for key, value in winner.items() if key not in {"probabilities", "key"}},
            "validation": metrics, "target": {"scratch_recall": 0.95, "normal_fpr_max": PRIMARY_FPR_CAP},
            "target_met": metrics["overall"]["recall"] >= 0.95 and metrics["overall"]["fpr"] <= PRIMARY_FPR_CAP,
        }
        (OUTPUT / "final_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        summary = [
            "# Scratch V5 训练结果", "",
            f"- 最佳方案：`{winner['name']}`",
            f"- Recall：`{metrics['overall']['recall']:.3f}`",
            f"- Precision：`{metrics['overall']['precision']:.3f}`",
            f"- F1：`{metrics['overall']['f1']:.3f}`",
            f"- 正常误报率：`{metrics['overall']['fpr']:.3f}`",
            f"- AUROC：`{metrics['overall']['auroc']:.3f}`",
            f"- AUPRC：`{metrics['overall']['auprc']:.3f}`",
            f"- 是否达到 Recall >= 0.95 且 FPR <= 0.20：`{'是' if report['target_met'] else '否'}`",
            "", "本结果使用 val 同时选择模型与阈值，不是严格独立测试结果。",
        ]
        (OUTPUT / "README.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
        save_leaderboard(leaderboard)
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    finally:
        monitor.stop()


if __name__ == "__main__":
    main()
