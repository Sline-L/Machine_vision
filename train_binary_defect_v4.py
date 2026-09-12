from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import random
import shutil
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

from auto_optimize_defects_v3 import Sample, load_samples, make_groups


ROOT = Path(__file__).resolve().parent
WORK = ROOT / "dataset_defects" / "binary_defect_v4"
RUNS = ROOT / "runs" / "binary_defect_v4"
OUTPUT = ROOT / "outputs" / "binary_defect_v4"
SOURCE_IMAGES = ROOT / "dataset_defects" / "images" / "train"
SEED = 20260911
VIEWS = ("face", "oblique", "side")
FPR_CAPS = (0.10, 0.20, 0.30, 0.50)


@dataclass(frozen=True)
class Experiment:
    name: str
    family: str
    size: int
    defect_weight: float
    epochs: int
    seed: int = SEED


PILOTS = (
    Experiment("p_yolo_384_w1", "yolo", 384, 1.0, 30),
    Experiment("p_yolo_512_w2", "yolo", 512, 2.0, 30),
    Experiment("p_yolo_512_w4", "yolo", 512, 4.0, 30),
    Experiment("p_resnet18_384_w1", "resnet18", 384, 1.0, 30),
    Experiment("p_resnet18_384_w2", "resnet18", 384, 2.0, 30),
    Experiment("p_resnet18_512_w4", "resnet18", 512, 4.0, 30),
    Experiment("p_efficientnet_b0_384_w1", "efficientnet_b0", 384, 1.0, 30),
    Experiment("p_efficientnet_b0_384_w2", "efficientnet_b0", 384, 2.0, 30),
    Experiment("p_efficientnet_b0_512_w4", "efficientnet_b0", 512, 4.0, 30),
    Experiment("x_yolo_384_w1_s17", "yolo", 384, 1.0, 50, 17),
    Experiment("x_yolo_384_w1_s73", "yolo", 384, 1.0, 50, 73),
    Experiment("x_resnet18_384_w1_s17", "resnet18", 384, 1.0, 60, 17),
    Experiment("x_resnet18_384_w1_s73", "resnet18", 384, 1.0, 60, 73),
    Experiment("x_efficientnet_b0_384_w1_s17", "efficientnet_b0", 384, 1.0, 60, 17),
    Experiment("x_efficientnet_b0_384_w1_s73", "efficientnet_b0", 384, 1.0, 60, 73),
    Experiment("t_texture_resnet18_384_s17", "texture_resnet18", 384, 1.0, 80, 17),
    Experiment("t_texture_resnet18_384_s73", "texture_resnet18", 384, 1.0, 80, 73),
    Experiment("t_texture_resnet18_512_s109", "texture_resnet18", 512, 1.0, 80, 109),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the V4 high-recall binary gear defect classifier")
    parser.add_argument("--hours", type=float, default=6.0)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def binary_label(sample: Sample) -> int:
    return int(sample.category != "normal")


def build_split(samples: list[Sample]) -> tuple[dict[str, str], list[list[Sample]]]:
    groups = make_groups(samples)
    ratios = {"train": 0.70, "val": 0.15, "test": 0.15}
    strata = [(category, view) for category in ("normal", "scratch", "missing_tooth") for view in VIEWS]
    totals = Counter((sample.category, sample.view) for sample in samples)
    targets = {split: {key: totals[key] * ratio for key in strata} for split, ratio in ratios.items()}
    best_error, best = math.inf, None
    rng = random.Random(SEED)
    for _ in range(300):
        remaining = [group for group in groups if len(group) <= 20]
        rng.shuffle(remaining)
        selected: dict[str, list[list[Sample]]] = {"val": [], "test": []}
        for split in ("test", "val"):
            counts = Counter()
            target_total = round(len(samples) * ratios[split])
            while sum(counts.values()) < target_total - 2 and remaining:
                def cost(group: list[Sample]) -> float:
                    add = Counter((sample.category, sample.view) for sample in group)
                    after = sum(counts.values()) + len(group)
                    value = 3.0 * abs(after - target_total) / target_total
                    value += sum(abs(counts[key] + add[key] - targets[split][key]) / max(1.0, targets[split][key]) for key in strata)
                    if after > target_total + 3:
                        value += 10 * (after - target_total - 3)
                    return value + rng.random() * 1e-6
                chosen = min(remaining, key=cost)
                selected[split].append(chosen)
                counts.update((sample.category, sample.view) for sample in chosen)
                remaining.remove(chosen)
        assignments = {sample.stem: "train" for sample in samples}
        for split, split_groups in selected.items():
            for group in split_groups:
                for sample in group:
                    assignments[sample.stem] = split
        counts = {split: Counter((sample.category, sample.view) for sample in samples if assignments[sample.stem] == split) for split in ratios}
        error = sum(abs(counts[split][key] - targets[split][key]) for split in ratios for key in strata)
        error += 3 * sum(abs(sum(counts[split].values()) - len(samples) * ratios[split]) for split in ratios)
        if all(sum(counts[split].values()) > 0 and all(sum(counts[split][(category, view)] for view in VIEWS) > 0 for category in ("normal", "scratch", "missing_tooth")) for split in ratios) and error < best_error:
            best_error, best = error, assignments
    if best is None:
        raise RuntimeError("Could not create a stratified group split")
    return best, groups


def write_split(samples: list[Sample], assignments: dict[str, str], groups: list[list[Sample]]) -> dict[str, object]:
    WORK.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    group_ids = {sample.stem: index for index, group in enumerate(groups) for sample in group}
    rows = [{
        "stem": sample.stem,
        "binary_label": "defect" if binary_label(sample) else "normal",
        "source_category": sample.category,
        "view": sample.view,
        "split": assignments[sample.stem],
        "group": group_ids[sample.stem],
        "dhash": f"{sample.dhash:016x}",
    } for sample in samples]
    with (WORK / "split_manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    leaks = []
    for index, left in enumerate(samples):
        for right in samples[index + 1:]:
            if assignments[left.stem] != assignments[right.stem] and (left.dhash ^ right.dhash).bit_count() <= 2:
                leaks.append([left.stem, right.stem])
    report = {
        "images": len(rows),
        "unique_stems": len({row["stem"] for row in rows}),
        "counts": {split: dict(Counter(row["binary_label"] for row in rows if row["split"] == split)) for split in ("train", "val", "test")},
        "source_categories": {split: dict(Counter(row["source_category"] for row in rows if row["split"] == split)) for split in ("train", "val", "test")},
        "views": {split: dict(Counter(row["view"] for row in rows if row["split"] == split)) for split in ("train", "val", "test")},
        "groups": len(groups),
        "largest_group": max(map(len, groups)),
        "dhash_leaks_at_2": leaks,
    }
    (WORK / "preflight.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if report["images"] != 343 or report["unique_stems"] != 343 or leaks:
        raise RuntimeError(f"Preflight failed: {report}")
    return report


def materialize_yolo(samples: list[Sample], assignments: dict[str, str], experiment: Experiment) -> Path:
    target = WORK / "yolo" / experiment.name
    marker = target / "complete.flag"
    if marker.exists():
        return target
    for sample in samples:
        split = assignments[sample.stem]
        label = "defect" if binary_label(sample) else "normal"
        destination = target / split / label
        destination.mkdir(parents=True, exist_ok=True)
        copies = 1
        if split == "train" and binary_label(sample):
            copies = int(experiment.defect_weight)
        for index in range(copies):
            suffix = "" if index == 0 else f"_w{index}"
            shutil.copy2(sample.image, destination / f"{sample.stem}{suffix}.jpg")
    marker.write_text("complete\n", encoding="ascii")
    return target


def square_image(image: Image.Image, size: int) -> Image.Image:
    image = image.convert("RGB")
    scale = size / max(image.size)
    resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), (238, 238, 238))
    canvas.paste(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    return canvas


def clahe(image: Image.Image) -> Image.Image:
    array = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2LAB)
    array[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(array[:, :, 0])
    return Image.fromarray(cv2.cvtColor(array, cv2.COLOR_LAB2RGB))


def texture_image(image: Image.Image) -> Image.Image:
    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    edges = cv2.Laplacian(enhanced, cv2.CV_32F, ksize=3)
    edges = cv2.normalize(np.abs(edges), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return Image.fromarray(np.stack((gray, enhanced, edges), axis=2), "RGB")


class BinaryDataset(Dataset):
    def __init__(self, samples: list[Sample], size: int, augment: bool, representation: str = "rgb") -> None:
        self.samples, self.size, self.augment, self.representation = samples, size, augment, representation
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
                image = image.transpose(random.choice((Image.Transpose.FLIP_LEFT_RIGHT, Image.Transpose.FLIP_TOP_BOTTOM, Image.Transpose.ROTATE_90, Image.Transpose.ROTATE_270)))
            if random.random() < 0.65:
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
                table = np.array([((value / 255.0) ** gamma) * 255 for value in range(256)]).astype(np.uint8)
                image = Image.fromarray(table[np.asarray(image)])
        if self.representation == "texture":
            image = texture_image(image)
        image = square_image(image, self.size)
        return self.tensor(image), float(binary_label(sample))


def build_network(family: str) -> nn.Module:
    if family in {"resnet18", "texture_resnet18"}:
        network = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        network.fc = nn.Linear(network.fc.in_features, 1)
    elif family == "efficientnet_b0":
        network = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT)
        network.classifier[1] = nn.Linear(network.classifier[1].in_features, 1)
    else:
        raise ValueError(family)
    return network


def load_custom(path: Path) -> tuple[nn.Module, dict[str, object]]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    network = build_network(checkpoint["family"])
    network.load_state_dict(checkpoint["model"])
    return network.cuda().eval(), checkpoint


def train_custom(experiment: Experiment, train_samples: list[Sample], val_samples: list[Sample], workers: int, deadline: float) -> Path | None:
    run = RUNS / experiment.name
    best = run / "best.pt"
    if best.exists() and (run / "complete.flag").exists():
        return best
    if time.monotonic() >= deadline:
        return None
    run.mkdir(parents=True, exist_ok=True)
    random.seed(experiment.seed)
    np.random.seed(experiment.seed % (2**32 - 1))
    torch.manual_seed(experiment.seed)
    representation = "texture" if experiment.family == "texture_resnet18" else "rgb"
    train_data = BinaryDataset(train_samples, experiment.size, True, representation)
    val_data = BinaryDataset(val_samples, experiment.size, False, representation)
    strata = Counter((sample.category, sample.view) for sample in train_samples)
    sampler = WeightedRandomSampler([1.0 / strata[(sample.category, sample.view)] for sample in train_samples], len(train_samples), replacement=True)
    batch = 24 if experiment.size == 384 else 12
    train_loader = DataLoader(train_data, batch_size=batch, sampler=sampler, num_workers=workers, pin_memory=True, persistent_workers=workers > 0)
    val_loader = DataLoader(val_data, batch_size=batch, shuffle=False, num_workers=workers, pin_memory=True, persistent_workers=workers > 0)
    network = build_network(experiment.family).cuda()
    optimizer = torch.optim.AdamW(network.parameters(), lr=3e-4, weight_decay=5e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=experiment.epochs, eta_min=1e-6)
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([experiment.defect_weight], device="cuda"))
    scaler = torch.amp.GradScaler("cuda")
    best_score, stale, history = (-1.0, -1.0), 0, []
    for epoch in range(1, experiment.epochs + 1):
        if time.monotonic() >= deadline:
            break
        network.train()
        losses = []
        for images, labels in train_loader:
            images, labels = images.cuda(non_blocking=True), labels.cuda(non_blocking=True).unsqueeze(1)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.float16):
                logits = network(images)
                loss = criterion(logits, labels)
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite loss in {experiment.name}")
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach()))
        scheduler.step()
        network.eval()
        probabilities, labels = [], []
        with torch.no_grad():
            for images, target in val_loader:
                probabilities.extend(network(images.cuda(non_blocking=True)).sigmoid().cpu().flatten().tolist())
                labels.extend(target.int().tolist())
        metrics = choose_threshold(labels, probabilities, 0.30)
        score = (metrics["recall"], -metrics["fpr"])
        history.append({"epoch": epoch, "loss": float(np.mean(losses)), **metrics})
        print(f"{experiment.name} epoch={epoch} loss={np.mean(losses):.4f} recall={metrics['recall']:.3f} fpr={metrics['fpr']:.3f}")
        if score > best_score:
            best_score, stale = score, 0
            torch.save({"model": network.state_dict(), "family": experiment.family, "size": experiment.size, "defect_weight": experiment.defect_weight, "seed": experiment.seed}, best)
        else:
            stale += 1
        if stale >= (10 if experiment.epochs <= 30 else 16):
            break
    (run / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    (run / "complete.flag").write_text("complete\n", encoding="ascii")
    del network, train_loader, val_loader
    gc.collect()
    torch.cuda.empty_cache()
    return best if best.exists() else None


def train_yolo(experiment: Experiment, samples: list[Sample], assignments: dict[str, str], deadline: float, workers: int) -> Path | None:
    run = RUNS / experiment.name
    best = run / "weights" / "best.pt"
    if best.exists() and (run / "complete.flag").exists():
        return best
    if time.monotonic() >= deadline:
        return None
    data = materialize_yolo(samples, assignments, experiment)
    model = YOLO("yolo26n-cls.pt")
    batch = 32 if experiment.size == 384 else 16
    try:
        model.train(data=str(data), epochs=experiment.epochs, patience=10 if experiment.epochs <= 30 else 16,
                    imgsz=experiment.size, batch=batch, workers=workers, device=0, amp=True, cache="ram",
                    project=str(RUNS), name=experiment.name, exist_ok=True, optimizer="AdamW", lr0=7e-4,
                    weight_decay=5e-4, scale=0.0, degrees=3.0, translate=0.0, fliplr=0.5, flipud=0.5,
                    hsv_h=0.003, hsv_s=0.10, hsv_v=0.15, erasing=0.0, auto_augment=None,
                    seed=experiment.seed, deterministic=False, plots=True)
    except torch.OutOfMemoryError:
        torch.cuda.empty_cache()
        model = YOLO("yolo26n-cls.pt")
        model.train(data=str(data), epochs=experiment.epochs, patience=10, imgsz=experiment.size,
                    batch=max(4, batch // 2), workers=workers, device=0, amp=True, cache="ram",
                    project=str(RUNS), name=experiment.name, exist_ok=True, optimizer="AdamW",
                    scale=0.0, erasing=0.0, auto_augment=None, seed=experiment.seed, plots=True)
    (run / "complete.flag").write_text("complete\n", encoding="ascii")
    return best if best.exists() else None


def transformed_images(sample: Sample, size: int, mode: str, family: str = "rgb") -> list[np.ndarray]:
    with Image.open(sample.image) as opened:
        original = opened.convert("RGB")
    variants = [original]
    if mode == "tta_mean":
        variants += [original.transpose(Image.Transpose.FLIP_LEFT_RIGHT), original.transpose(Image.Transpose.FLIP_TOP_BOTTOM), clahe(original)]
    if family == "texture_resnet18":
        variants = [texture_image(image) for image in variants]
    return [np.asarray(square_image(image, size)) for image in variants]


def predict(weights: Path, experiment: Experiment, samples: list[Sample], tta: str) -> list[float]:
    output = []
    if experiment.family == "yolo":
        model = YOLO(weights)
        defect_index = next(index for index, name in model.names.items() if name == "defect")
        for sample in samples:
            results = model.predict(transformed_images(sample, experiment.size, tta, experiment.family), imgsz=experiment.size, batch=4, device=0, verbose=False)
            output.append(float(np.mean([result.probs.data[defect_index].item() for result in results])))
        del model
    else:
        network, _ = load_custom(weights)
        transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))])
        with torch.no_grad():
            for sample in samples:
                batch = torch.stack([transform(Image.fromarray(image)) for image in transformed_images(sample, experiment.size, tta, experiment.family)]).cuda()
                output.append(float(network(batch).sigmoid().mean()))
        del network
    gc.collect()
    torch.cuda.empty_cache()
    return output


def choose_threshold(labels: list[int], probabilities: list[float], fpr_cap: float) -> dict[str, float | int]:
    candidates = sorted(set([0.0, 1.0, *probabilities]))
    best = None
    for threshold in candidates:
        predicted = [value >= threshold for value in probabilities]
        tp = sum(actual == 1 and guess for actual, guess in zip(labels, predicted))
        fp = sum(actual == 0 and guess for actual, guess in zip(labels, predicted))
        tn = sum(actual == 0 and not guess for actual, guess in zip(labels, predicted))
        fn = sum(actual == 1 and not guess for actual, guess in zip(labels, predicted))
        recall, fpr = tp / max(1, tp + fn), fp / max(1, fp + tn)
        precision = tp / max(1, tp + fp)
        row = {"threshold": float(threshold), "recall": recall, "precision": precision,
               "f1": 2 * precision * recall / max(1e-9, precision + recall), "fpr": fpr,
               "specificity": 1 - fpr, "tp": tp, "fp": fp, "tn": tn, "fn": fn}
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
    roc_points = [(0.0, 0.0)]
    for index in order:
        if labels[index]:
            tp += 1
        else:
            fp += 1
        recall = tp / max(1, positives)
        precision = tp / max(1, tp + fp)
        auprc += (recall - previous_recall) * precision
        previous_recall = recall
        roc_points.append((fp / max(1, negatives), recall))
    auroc = sum((right[0] - left[0]) * (left[1] + right[1]) / 2 for left, right in zip(roc_points, roc_points[1:]))
    return auroc, auprc


def temperature_scale(labels: list[int], probabilities: list[float]) -> float:
    clipped = np.clip(np.asarray(probabilities), 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped))
    labels_array = np.asarray(labels)
    best = (math.inf, 1.0)
    for temperature in np.linspace(0.35, 4.0, 147):
        scaled = 1 / (1 + np.exp(-logits / temperature))
        nll = float(-np.mean(labels_array * np.log(scaled + 1e-9) + (1 - labels_array) * np.log(1 - scaled + 1e-9)))
        if nll < best[0]:
            best = nll, float(temperature)
    return best[1]


def apply_temperature(probabilities: list[float], temperature: float) -> list[float]:
    clipped = np.clip(np.asarray(probabilities), 1e-6, 1 - 1e-6)
    return (1 / (1 + np.exp(-np.log(clipped / (1 - clipped)) / temperature))).tolist()


def evaluate_probabilities(samples: list[Sample], probabilities: list[float], threshold: float) -> dict[str, object]:
    labels = [binary_label(sample) for sample in samples]
    metrics = choose_threshold(labels, probabilities, 1.0)
    predicted = [value >= threshold for value in probabilities]
    tp = sum(actual and guess for actual, guess in zip(labels, predicted))
    fp = sum(not actual and guess for actual, guess in zip(labels, predicted))
    tn = sum(not actual and not guess for actual, guess in zip(labels, predicted))
    fn = sum(actual and not guess for actual, guess in zip(labels, predicted))
    recall, precision, fpr = tp / max(1, tp + fn), tp / max(1, tp + fp), fp / max(1, fp + tn)
    overall = {"threshold": threshold, "recall": recall, "precision": precision,
               "f1": 2 * precision * recall / max(1e-9, precision + recall), "fpr": fpr,
               "specificity": 1 - fpr, "npv": tn / max(1, tn + fn), "tp": tp, "fp": fp, "tn": tn, "fn": fn,
               "auroc": binary_auc(labels, probabilities)[0], "auprc": binary_auc(labels, probabilities)[1]}
    groups = {}
    for key, predicate in {
        "scratch": lambda sample: sample.category == "scratch",
        "missing_tooth": lambda sample: sample.category == "missing_tooth",
        **{view: (lambda sample, view=view: sample.view == view and binary_label(sample)) for view in VIEWS},
    }.items():
        indexes = [index for index, sample in enumerate(samples) if predicate(sample)]
        groups[key] = {"count": len(indexes), "recall": sum(probabilities[index] >= threshold for index in indexes) / max(1, len(indexes))}
    return {"overall": overall, "subgroups": groups, "unused_unconstrained": metrics}


def save_confusion(metrics: dict[str, object], destination: Path) -> None:
    values = metrics["overall"]
    canvas = Image.new("RGB", (640, 520), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((30, 20), "Binary defect confusion matrix", fill="black")
    draw.text((215, 75), "Pred NORMAL", fill="black")
    draw.text((430, 75), "Pred DEFECT", fill="black")
    draw.text((30, 190), "True NORMAL", fill="black")
    draw.text((30, 370), "True DEFECT", fill="black")
    for x, y, value, color in ((210, 130, values["tn"], "#b8e6bf"), (420, 130, values["fp"], "#f4b8b8"), (210, 310, values["fn"], "#f4b8b8"), (420, 310, values["tp"], "#b8e6bf")):
        draw.rectangle((x, y, x + 170, y + 140), fill=color, outline="black", width=2)
        draw.text((x + 70, y + 55), str(value), fill="black")
    canvas.save(destination)


def main() -> None:
    args = parse_args()
    started = time.monotonic()
    deadline = started + args.hours * 3600
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    samples = load_samples()
    manifest = WORK / "split_manifest.csv"
    if manifest.exists():
        rows = list(csv.DictReader(manifest.open(encoding="utf-8")))
        assignments = {row["stem"]: row["split"] for row in rows}
        groups = make_groups(samples)
    else:
        assignments, groups = build_split(samples)
    preflight = write_split(samples, assignments, groups)
    train_samples = [sample for sample in samples if assignments[sample.stem] == "train"]
    val_samples = [sample for sample in samples if assignments[sample.stem] == "val"]
    test_samples = [sample for sample in samples if assignments[sample.stem] == "test"]
    leaderboard, artifacts = [], {}
    for experiment in PILOTS:
        print(f"\n=== {experiment.name} ===")
        try:
            weights = train_yolo(experiment, samples, assignments, deadline, args.workers) if experiment.family == "yolo" else train_custom(experiment, train_samples, val_samples, args.workers, deadline)
            if weights is None:
                break
            labels = [binary_label(sample) for sample in val_samples]
            best_variant = None
            for tta in ("none", "tta_mean"):
                raw = predict(weights, experiment, val_samples, tta)
                temperature = temperature_scale(labels, raw)
                probabilities = apply_temperature(raw, temperature)
                operating_points = {str(cap): choose_threshold(labels, probabilities, cap) for cap in FPR_CAPS}
                primary = operating_points["0.3"]
                auprc = binary_auc(labels, probabilities)[1]
                key = (primary["fpr"] <= 0.30, primary["recall"], -primary["fpr"], auprc)
                candidate = {"tta": tta, "temperature": temperature, "operating_points": operating_points, "auprc": auprc, "key": key}
                if best_variant is None or key > best_variant["key"]:
                    best_variant = candidate
            assert best_variant is not None
            row = {"name": experiment.name, "stage": "pilot", **asdict(experiment), "weights": str(weights), **{key: value for key, value in best_variant.items() if key != "key"}}
            leaderboard.append(row)
            artifacts[experiment.name] = (experiment, weights, best_variant)
        except Exception as error:
            leaderboard.append({"name": experiment.name, "stage": "pilot", "error": repr(error)})
            print(f"FAILED {experiment.name}: {error!r}")
    eligible = [row for row in leaderboard if "error" not in row]
    eligible.sort(key=lambda row: (row["operating_points"]["0.3"]["fpr"] <= 0.30, row["operating_points"]["0.3"]["recall"], -row["operating_points"]["0.3"]["fpr"], row["auprc"]), reverse=True)
    for rank, pilot in enumerate(eligible[:2], 1):
        source = artifacts[pilot["name"]][0]
        experiment = Experiment(f"xfull_{source.family}_{source.size}_w{int(source.defect_weight)}_s{source.seed}_r{rank}", source.family, source.size, source.defect_weight, 120, source.seed)
        print(f"\n=== {experiment.name} ===")
        weights = train_yolo(experiment, samples, assignments, deadline, args.workers) if experiment.family == "yolo" else train_custom(experiment, train_samples, val_samples, args.workers, deadline)
        if weights is None:
            continue
        labels = [binary_label(sample) for sample in val_samples]
        variants = []
        for tta in ("none", "tta_mean"):
            raw = predict(weights, experiment, val_samples, tta)
            temperature = temperature_scale(labels, raw)
            probabilities = apply_temperature(raw, temperature)
            points = {str(cap): choose_threshold(labels, probabilities, cap) for cap in FPR_CAPS}
            variants.append((points["0.3"]["fpr"] <= 0.30, points["0.3"]["recall"], -points["0.3"]["fpr"], binary_auc(labels, probabilities)[1], tta, temperature, points))
        chosen = max(variants)
        row = {"name": experiment.name, "stage": "full", **asdict(experiment), "weights": str(weights), "tta": chosen[4], "temperature": chosen[5], "operating_points": chosen[6], "auprc": chosen[3]}
        leaderboard.append(row)
    completed = [row for row in leaderboard if "error" not in row and "operating_points" in row]
    completed.sort(key=lambda row: (row["operating_points"]["0.3"]["fpr"] <= 0.30, row["operating_points"]["0.3"]["recall"], -row["operating_points"]["0.3"]["fpr"], row["auprc"]), reverse=True)
    if not completed:
        raise RuntimeError("No classifier completed")
    winner = completed[0]
    winner_experiment = Experiment(winner["name"], winner["family"], int(winner["size"]), float(winner["defect_weight"]), int(winner["epochs"]), int(winner["seed"]))
    final_dir = OUTPUT / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_weights = final_dir / "best.pt"
    shutil.copy2(winner["weights"], final_weights)
    config = {
        "model": {"family": winner["family"], "weights": str(final_weights), "imgsz": winner["size"]},
        "tta": winner["tta"], "temperature": winner["temperature"],
        "default_threshold": winner["operating_points"]["0.3"]["threshold"],
        "operating_points": winner["operating_points"],
        "decision": "REJECT when calibrated defect_probability >= threshold",
    }
    (OUTPUT / "inference_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (OUTPUT / "leaderboard.json").write_text(json.dumps(leaderboard, indent=2), encoding="utf-8")
    with (OUTPUT / "leaderboard.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("name", "stage", "family", "size", "defect_weight", "epochs", "recall", "fpr", "auprc", "tta", "error"))
        writer.writeheader()
        for row in leaderboard:
            point = row.get("operating_points", {}).get("0.3", {})
            writer.writerow({"name": row.get("name"), "stage": row.get("stage"), "family": row.get("family"), "size": row.get("size"), "defect_weight": row.get("defect_weight"), "epochs": row.get("epochs"), "recall": point.get("recall"), "fpr": point.get("fpr"), "auprc": row.get("auprc"), "tta": row.get("tta"), "error": row.get("error")})
    lock = OUTPUT / "test_evaluation_started.lock"
    complete = OUTPUT / "test_evaluation_complete.flag"
    if lock.exists() and not complete.exists():
        raise RuntimeError("An incomplete locked test evaluation already exists")
    lock.write_text("started\n", encoding="ascii")
    raw_test = predict(final_weights, winner_experiment, test_samples, winner["tta"])
    calibrated_test = apply_temperature(raw_test, float(winner["temperature"]))
    threshold = float(winner["operating_points"]["0.3"]["threshold"])
    test_metrics = evaluate_probabilities(test_samples, calibrated_test, threshold)
    predictions = []
    visual_dir = OUTPUT / "test_predictions"
    visual_dir.mkdir(parents=True, exist_ok=True)
    for sample, probability in zip(test_samples, calibrated_test):
        decision = "reject" if probability >= threshold else "pass"
        predictions.append({"stem": sample.stem, "truth": "defect" if binary_label(sample) else "normal", "source_category": sample.category, "view": sample.view, "defect_probability": probability, "decision": decision, "correct": int((probability >= threshold) == bool(binary_label(sample)))})
        with Image.open(sample.image) as opened:
            image = opened.convert("RGB")
        draw = ImageDraw.Draw(image)
        draw.text((8, 8), f"{decision.upper()} defect={probability:.3f} threshold={threshold:.3f}", fill=(255, 30, 30) if decision == "reject" else (0, 170, 40))
        image.save(visual_dir / f"{sample.stem}.jpg", quality=95)
    with (OUTPUT / "test_predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=predictions[0].keys())
        writer.writeheader()
        writer.writerows(predictions)
    save_confusion(test_metrics, OUTPUT / "confusion_matrix.png")
    report = {"gpu": torch.cuda.get_device_name(0), "elapsed_hours": (time.monotonic() - started) / 3600, "preflight": preflight, "winner": winner, "test": test_metrics, "target": {"recall": 0.95, "fpr_max": 0.30}, "target_met": test_metrics["overall"]["recall"] >= 0.95 and test_metrics["overall"]["fpr"] <= 0.30}
    (OUTPUT / "final_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    complete.write_text("complete\n", encoding="ascii")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
