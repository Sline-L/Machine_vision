from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import random
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageDraw
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import models, transforms
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "dataset_defects"
WORK = SOURCE / "auto_search_v3"
RUNS = ROOT / "runs" / "defect_search_v3"
OUTPUT = ROOT / "outputs" / "defect_search_v3"
OFFICIAL = ROOT / "yolo26n.pt"
V2_EVAL = ROOT / "outputs" / "defect_search_v2" / "final_evaluation.json"
CLASSES = ("normal", "scratch", "missing_tooth")
DEFECTS = ("scratch", "missing_tooth")
IMAGE_SIZE = 960
CONF_GRID = (0.01, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
GATE_GRID = tuple(value / 20 for value in range(1, 20))


@dataclass(frozen=True)
class Sample:
    stem: str
    image: Path
    xml: Path | None
    category: str
    view: str
    width: int
    height: int
    boxes: tuple[tuple[str, float, float, float, float], ...]
    dhash: int


@dataclass(frozen=True)
class DetectorExperiment:
    name: str
    mode: str
    architecture: str
    representation: str
    epochs: int
    seed: int = 42


def parse_xml(path: Path) -> tuple[int, int, tuple[tuple[str, float, float, float, float], ...]]:
    root = ET.parse(path).getroot()
    size = root.find("size")
    if size is None:
        raise ValueError(f"Missing size in {path}")
    width, height = int(size.findtext("width", "0")), int(size.findtext("height", "0"))
    boxes = []
    for obj in root.findall("object"):
        name = obj.findtext("name", "").strip()
        box = obj.find("bndbox")
        if name not in DEFECTS or box is None:
            raise ValueError(f"Invalid object in {path}")
        coords = tuple(float(box.findtext(key, "0")) for key in ("xmin", "ymin", "xmax", "ymax"))
        if not (0 <= coords[0] < coords[2] <= width and 0 <= coords[1] < coords[3] <= height):
            raise ValueError(f"Invalid box in {path}: {coords}")
        boxes.append((name, *coords))
    return width, height, tuple(boxes)


def dhash(path: Path) -> int:
    with Image.open(path) as image:
        gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = np.asarray(gray)
    value = 0
    for bit in (pixels[:, :-1] > pixels[:, 1:]).reshape(-1):
        value = (value << 1) | int(bit)
    return value


def infer_view(width: int, height: int) -> str:
    ratio = max(width / height, height / width)
    return "side" if ratio >= 1.8 else "oblique" if ratio >= 1.25 else "face"


def load_samples() -> list[Sample]:
    samples = []
    for index in range(1, 344):
        stem = f"train_{index:03d}"
        image = SOURCE / "images" / "train" / f"{stem}.jpg"
        xml = SOURCE / "annotations" / "train" / f"{stem}.xml"
        if not image.is_file():
            raise FileNotFoundError(image)
        if xml.is_file():
            width, height, boxes = parse_xml(xml)
            names = {box[0] for box in boxes}
            if len(names) != 1:
                raise ValueError(f"Expected one defect class in {xml}: {names}")
            category, xml_path = next(iter(names)), xml
        else:
            with Image.open(image) as opened:
                width, height = opened.size
            boxes, category, xml_path = (), "normal", None
        samples.append(Sample(stem, image, xml_path, category, infer_view(width, height), width, height, boxes, dhash(image)))
    counts = Counter(sample.category for sample in samples)
    if counts != Counter(normal=132, scratch=79, missing_tooth=132):
        raise ValueError(f"Unexpected source counts: {counts}")
    return samples


def gray_signature(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    image = cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)
    image -= image.mean()
    norm = np.linalg.norm(image)
    return image.reshape(-1) / max(float(norm), 1e-6)


def make_groups(samples: list[Sample]) -> list[list[Sample]]:
    parent = list(range(len(samples)))
    component_size = [1] * len(samples)

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: int, right: int, cap: int | None = None) -> None:
        left, right = find(left), find(right)
        if left != right and (cap is None or component_size[left] + component_size[right] <= cap):
            parent[right] = left
            component_size[left] += component_size[right]

    signatures = [gray_signature(sample.image) for sample in samples]
    for left in range(len(samples)):
        for right in range(left + 1, len(samples)):
            distance = (samples[left].dhash ^ samples[right].dhash).bit_count()
            if distance <= 2:
                union(left, right)
    for left in range(len(samples)):
        for right in range(left + 1, min(len(samples), left + 4)):
            distance = (samples[left].dhash ^ samples[right].dhash).bit_count()
            if distance <= 2:
                continue
            ratio_left = samples[left].width / samples[left].height
            ratio_right = samples[right].width / samples[right].height
            ratio_delta = abs(ratio_left - ratio_right) / max(ratio_left, ratio_right)
            correlation = float(signatures[left] @ signatures[right])
            if ratio_delta <= 0.15 and distance <= 8 and correlation >= 0.92:
                union(left, right, cap=12)
    groups: dict[int, list[Sample]] = {}
    for index, sample in enumerate(samples):
        groups.setdefault(find(index), []).append(sample)
    return list(groups.values())


def make_split(samples: list[Sample]) -> tuple[dict[str, str], list[list[Sample]]]:
    groups = make_groups(samples)
    splits = ("train", "val", "test")
    ratios = {"train": 0.70, "val": 0.15, "test": 0.15}
    strata = [(category, view) for category in CLASSES for view in ("face", "oblique", "side")]
    totals = Counter((sample.category, sample.view) for sample in samples)
    targets = {split: {key: totals[key] * ratios[split] for key in strata} for split in splits}
    best_error, best = math.inf, None
    rng = random.Random(42)
    for _ in range(150):
        remaining = [group for group in groups if len(group) <= 20]
        rng.shuffle(remaining)
        selected: dict[str, list[list[Sample]]] = {"test": [], "val": []}
        for split in ("test", "val"):
            counts = Counter()
            target_total = round(len(samples) * ratios[split])
            while sum(counts.values()) < target_total - 2 and remaining:
                def candidate_cost(group: list[Sample]) -> float:
                    additions = Counter((sample.category, sample.view) for sample in group)
                    after_total = sum(counts.values()) + len(group)
                    value = 3.0 * abs(after_total - target_total) / target_total
                    value += sum(abs(counts[key] + additions[key] - targets[split][key]) / max(1.0, targets[split][key]) for key in strata)
                    if after_total > target_total + 3:
                        value += 10 * (after_total - target_total - 3)
                    return value + rng.random() * 1e-5
                chosen = min(remaining, key=candidate_cost)
                selected[split].append(chosen)
                counts.update((sample.category, sample.view) for sample in chosen)
                remaining.remove(chosen)
        assignments = {sample.stem: "train" for sample in samples}
        for split in ("test", "val"):
            for group in selected[split]:
                for sample in group:
                    assignments[sample.stem] = split
        counts = {split: Counter((sample.category, sample.view) for sample in samples if assignments[sample.stem] == split) for split in splits}
        error = sum(abs(counts[split][key] - targets[split][key]) for split in splits for key in strata)
        error += 3 * sum(abs(sum(counts[split].values()) - len(samples) * ratios[split]) for split in splits)
        if error < best_error:
            best_error, best = error, assignments
    if best is None:
        raise RuntimeError("Could not create split")
    return best, groups


def write_split(samples: list[Sample], assignments: dict[str, str], groups: list[list[Sample]]) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    group_ids = {sample.stem: index for index, group in enumerate(groups) for sample in group}
    rows = [
        {"stem": sample.stem, "category": sample.category, "view": sample.view, "split": assignments[sample.stem], "group": group_ids[sample.stem], "dhash": f"{sample.dhash:016x}"}
        for sample in samples
    ]
    (WORK / "split_manifest.json").write_text(json.dumps(rows, indent=2), encoding="ascii")
    with (WORK / "split_manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    leaks = []
    for left, sample in enumerate(samples):
        for other in samples[left + 1:]:
            if assignments[sample.stem] != assignments[other.stem] and (sample.dhash ^ other.dhash).bit_count() <= 2:
                leaks.append((sample.stem, other.stem))
    report = {
        "counts": {split: dict(Counter(sample.category for sample in samples if assignments[sample.stem] == split)) for split in ("train", "val", "test")},
        "views": {split: dict(Counter(sample.view for sample in samples if assignments[sample.stem] == split)) for split in ("train", "val", "test")},
        "groups": len(groups), "largest_group": max(map(len, groups)), "dhash_leaks_at_2": leaks,
    }
    (WORK / "preflight.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if leaks:
        raise RuntimeError(f"Cross-split near duplicates remain: {leaks[:5]}")


def write_review_queue(samples: list[Sample], assignments: dict[str, str]) -> None:
    scores = Counter()
    reasons: dict[str, set[str]] = {}
    if V2_EVAL.exists():
        previous = json.loads(V2_EVAL.read_text(encoding="utf-8"))
        for mode in DEFECTS:
            for row in previous.get(mode, {}).get("per_image", []):
                stem = row["stem"]
                if assignments.get(stem) == "test":
                    continue
                difficulty = 3 * int(row["fn"]) + 2 * int(row["fp"])
                if difficulty:
                    scores[stem] += difficulty
                    reasons.setdefault(stem, set()).add(f"v2_{mode}_fn{row['fn']}_fp{row['fp']}")
    for sample in samples:
        if assignments[sample.stem] == "test":
            continue
        if sample.category == "scratch" and (len(sample.boxes) >= 4 or any((box[3] - box[1]) / max(1, box[4] - box[2]) > 4 for box in sample.boxes)):
            scores[sample.stem] += 2
            reasons.setdefault(sample.stem, set()).add("complex_scratch_boxes")
        if sample.category == "missing_tooth" and sample.view == "side":
            scores[sample.stem] += 1
            reasons.setdefault(sample.stem, set()).add("side_view_missing_tooth")
    selected = [stem for stem, _ in scores.most_common(50)]
    rows = []
    preview_dir = OUTPUT / "review_queue"
    preview_dir.mkdir(parents=True, exist_ok=True)
    by_stem = {sample.stem: sample for sample in samples}
    for stem in selected:
        sample = by_stem[stem]
        with Image.open(sample.image) as source:
            image = source.convert("RGB")
        draw = ImageDraw.Draw(image)
        for name, x1, y1, x2, y2 in sample.boxes:
            draw.rectangle((x1, y1, x2, y2), outline=(0, 255, 80), width=3)
            draw.text((x1, max(0, y1 - 12)), name, fill=(0, 255, 80))
        preview = preview_dir / f"{stem}.jpg"
        image.save(preview, quality=95)
        rows.append({"stem": stem, "split": assignments[stem], "category": sample.category, "view": sample.view, "score": scores[stem], "reasons": ";".join(sorted(reasons[stem])), "preview": str(preview)})
    with (OUTPUT / "review_queue.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def yolo_line(box: tuple[str, float, float, float, float], sample: Sample, class_ids: dict[str, int]) -> str:
    name, x1, y1, x2, y2 = box
    return f"{class_ids[name]} {(x1+x2)/(2*sample.width):.6f} {(y1+y2)/(2*sample.height):.6f} {(x2-x1)/sample.width:.6f} {(y2-y1)/sample.height:.6f}"


def transform_image(source: Path, destination: Path, representation: str) -> None:
    image = cv2.imread(str(source))
    if image is None:
        raise ValueError(f"Unreadable image: {source}")
    if representation == "clahe":
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
        image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    elif representation == "gray":
        gray = cv2.equalizeHist(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
        image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    cv2.imwrite(str(destination), image)


def hard_stems(mode: str, assignments: dict[str, str]) -> set[str]:
    if not V2_EVAL.exists():
        return set()
    previous = json.loads(V2_EVAL.read_text(encoding="utf-8"))
    return {
        row["stem"] for row in previous.get(mode, {}).get("per_image", [])
        if assignments.get(row["stem"]) == "train" and (int(row["fn"]) > 0 or int(row["fp"]) > 0)
    }


def materialize_detector(samples: list[Sample], assignments: dict[str, str], experiment: DetectorExperiment) -> Path:
    target = WORK / "detectors" / experiment.name
    yaml_path = target / "data.yaml"
    if yaml_path.exists():
        return yaml_path
    class_ids = {"scratch": 0, "missing_tooth": 1} if experiment.mode == "joint" else {experiment.mode: 0}
    difficult = hard_stems(experiment.mode, assignments) if experiment.mode in DEFECTS else set()
    for sample in samples:
        split = assignments[sample.stem]
        image_dir, label_dir = target / "images" / split, target / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        boxes = sample.boxes if experiment.mode == "joint" else tuple(box for box in sample.boxes if box[0] == experiment.mode)
        lines = [yolo_line(box, sample, class_ids) for box in boxes]
        copies = [(sample.stem, "original")]
        if split == "train" and experiment.representation != "original":
            copies.append((f"{sample.stem}_{experiment.representation}", experiment.representation))
        if split == "train" and sample.stem in difficult:
            copies.extend((f"{sample.stem}_hard{index}", experiment.representation if experiment.representation != "original" else "original") for index in range(1, 3))
        for name, representation in copies:
            destination = image_dir / f"{name}.jpg"
            if representation == "original":
                shutil.copy2(sample.image, destination)
            else:
                transform_image(sample.image, destination, representation)
            (label_dir / f"{name}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="ascii")
    names = "\n".join(f"  {index}: {name}" for name, index in class_ids.items())
    yaml_path.write_text(f"path: {target.as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n", encoding="ascii")
    return yaml_path


def materialize_classification(samples: list[Sample], assignments: dict[str, str]) -> Path:
    target = WORK / "classification"
    marker = target / "complete.flag"
    if marker.exists():
        return target
    for sample in samples:
        destination = target / assignments[sample.stem] / sample.category
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sample.image, destination / sample.image.name)
    marker.write_text("complete\n", encoding="ascii")
    return target


def detector_model(architecture: str) -> YOLO:
    if architecture == "standard":
        return YOLO(OFFICIAL)
    yaml = ROOT / ".venv" / "Lib" / "site-packages" / "ultralytics" / "cfg" / "models" / "26" / "yolo26-p2.yaml"
    return YOLO(yaml).load(OFFICIAL)


def train_detector(experiment: DetectorExperiment, data: Path, deadline: float) -> Path | None:
    run = RUNS / experiment.name
    best = run / "weights" / "best.pt"
    if best.exists() and (run / "complete.flag").exists():
        return best
    if time.monotonic() >= deadline:
        return None
    model = detector_model(experiment.architecture)
    batch = 16 if experiment.architecture == "standard" else 8
    try:
        model.train(
            data=str(data), epochs=experiment.epochs, patience=10 if experiment.epochs <= 30 else 20,
            imgsz=IMAGE_SIZE, batch=batch, workers=4, device=0, amp=True, cache="ram",
            project=str(RUNS), name=experiment.name, exist_ok=False, optimizer="AdamW",
            lr0=0.001 if experiment.epochs <= 30 else 0.0007, weight_decay=0.0005,
            mosaic=0.0, degrees=2.0, translate=0.02, scale=0.08, fliplr=0.5, flipud=0.5,
            hsv_h=0.003, hsv_s=0.10, hsv_v=0.10, seed=experiment.seed,
            deterministic=False, plots=True,
        )
    except torch.OutOfMemoryError:
        torch.cuda.empty_cache()
        model = detector_model(experiment.architecture)
        model.train(
            data=str(data), epochs=experiment.epochs, patience=10, imgsz=IMAGE_SIZE,
            batch=max(2, batch // 2), workers=4, device=0, amp=True, cache="ram",
            project=str(RUNS), name=experiment.name, exist_ok=True, optimizer="AdamW",
            lr0=0.0007, mosaic=0.0, seed=experiment.seed, deterministic=False, plots=True,
        )
    (run / "complete.flag").write_text("complete\n", encoding="ascii")
    return best if best.exists() else None


def evaluate_detector(weights: Path, data: Path, mode: str, split: str = "val") -> dict[str, object]:
    model = YOLO(weights)
    names = list(DEFECTS) if mode == "joint" else [mode]
    selected = {name: {"precision": 0.0, "recall": 0.0, "map50": 0.0, "map5095": 0.0, "conf": 0.0} for name in names}
    for conf in CONF_GRID:
        metrics = model.val(data=str(data), split=split, conf=conf, iou=0.7, imgsz=IMAGE_SIZE, batch=8, workers=4, device=0, plots=False, verbose=False, project=str(OUTPUT / "metric_runs"), name=f"{mode}_{split}", exist_ok=True)
        for index, name in enumerate(names):
            current = {"precision": float(metrics.box.p[index]), "recall": float(metrics.box.r[index]), "map50": float(metrics.box.ap50[index]), "map5095": float(metrics.box.ap[index]), "conf": conf}
            old = selected[name]
            valid, old_valid = current["precision"] >= 0.5, old["precision"] >= 0.5
            if (valid and not old_valid) or (valid == old_valid and (current["recall"], current["map50"]) > (old["recall"], old["map50"])):
                selected[name] = current
    del model
    gc.collect()
    torch.cuda.empty_cache()
    valid = all(item["precision"] >= 0.5 for item in selected.values())
    return {"classes": selected, "eligible": valid, "score": min(item["recall"] for item in selected.values()) if valid else -1.0}


class GearClassificationDataset(Dataset):
    def __init__(self, samples: list[Sample], augment: bool) -> None:
        self.samples = samples
        operations: list[object] = [transforms.Resize((320, 320), antialias=True)]
        if augment:
            operations += [
                transforms.RandomHorizontalFlip(), transforms.RandomVerticalFlip(),
                transforms.RandomApply([transforms.ColorJitter(brightness=0.18, contrast=0.18, saturation=0.08)], p=0.7),
                transforms.RandomApply([transforms.GaussianBlur(3, sigma=(0.1, 1.0))], p=0.15),
                transforms.RandomAffine(3, translate=(0.02, 0.02), scale=(0.95, 1.05), fill=240),
            ]
        operations += [transforms.ToTensor(), transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))]
        self.transform = transforms.Compose(operations)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        sample = self.samples[index]
        with Image.open(sample.image) as image:
            tensor = self.transform(image.convert("RGB"))
        return tensor, CLASSES.index(sample.category)


def train_resnet(samples: list[Sample], assignments: dict[str, str], deadline: float) -> Path | None:
    output = RUNS / "classifier_resnet18" / "best.pt"
    if output.exists():
        return output
    if time.monotonic() >= deadline:
        return None
    train_samples = [sample for sample in samples if assignments[sample.stem] == "train"]
    val_samples = [sample for sample in samples if assignments[sample.stem] == "val"]
    train_data = GearClassificationDataset(train_samples, augment=True)
    val_data = GearClassificationDataset(val_samples, augment=False)
    counts = Counter(sample.category for sample in train_samples)
    sample_weights = [1.0 / counts[sample.category] for sample in train_samples]
    sampler = WeightedRandomSampler(sample_weights, len(sample_weights), replacement=True)
    train_loader = DataLoader(train_data, batch_size=32, sampler=sampler, num_workers=4, pin_memory=True, persistent_workers=True)
    val_loader = DataLoader(val_data, batch_size=32, shuffle=False, num_workers=4, pin_memory=True, persistent_workers=True)
    network = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    network.fc = nn.Linear(network.fc.in_features, len(CLASSES))
    network.cuda()
    optimizer = torch.optim.AdamW(network.parameters(), lr=3e-4, weight_decay=5e-4)
    scaler = torch.amp.GradScaler("cuda")
    class_weights = torch.tensor([len(train_samples) / (len(CLASSES) * counts[name]) for name in CLASSES], device="cuda")
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    output.parent.mkdir(parents=True, exist_ok=True)
    best_score, stale, history = -1.0, 0, []
    for epoch in range(1, 51):
        if time.monotonic() >= deadline:
            break
        network.train()
        losses = []
        for images, labels in train_loader:
            images, labels = images.cuda(non_blocking=True), labels.cuda(non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.float16):
                logits = network(images)
                loss = criterion(logits, labels)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            losses.append(float(loss.detach()))
        network.eval()
        correct = Counter()
        total = Counter()
        with torch.no_grad():
            for images, labels in val_loader:
                predicted = network(images.cuda(non_blocking=True)).argmax(1).cpu()
                for actual, guess in zip(labels.tolist(), predicted.tolist()):
                    total[actual] += 1
                    correct[actual] += int(actual == guess)
        recalls = [correct[index] / max(1, total[index]) for index in range(len(CLASSES))]
        score = min(recalls[1:]) + 0.2 * recalls[0]
        history.append({"epoch": epoch, "loss": sum(losses) / max(1, len(losses)), "recalls": recalls, "score": score})
        if score > best_score:
            best_score, stale = score, 0
            torch.save({"model": network.state_dict(), "classes": CLASSES, "history": history}, output)
        else:
            stale += 1
        print(f"resnet epoch={epoch} score={score:.4f} recalls={recalls}")
        if stale >= 12:
            break
    (output.parent / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    del network, train_loader, val_loader
    gc.collect()
    torch.cuda.empty_cache()
    return output if output.exists() else None


def load_resnet(weights: Path) -> nn.Module:
    checkpoint = torch.load(weights, map_location="cpu", weights_only=False)
    network = models.resnet18(weights=None)
    network.fc = nn.Linear(network.fc.in_features, len(CLASSES))
    network.load_state_dict(checkpoint["model"])
    return network.cuda().eval()


def train_yolo_classifier(data: Path, deadline: float) -> Path | None:
    run = RUNS / "classifier_yolo26n"
    best = run / "weights" / "best.pt"
    if best.exists() and (run / "complete.flag").exists():
        return best
    if time.monotonic() >= deadline:
        return None
    model = YOLO("yolo26n-cls.pt")
    model.train(
        data=str(data), epochs=60, patience=15, imgsz=320, batch=32, workers=4,
        device=0, amp=True, cache="ram", project=str(RUNS), name="classifier_yolo26n",
        exist_ok=False, optimizer="AdamW", lr0=0.0007, weight_decay=0.0005,
        scale=0.0, degrees=3.0, translate=0.02, fliplr=0.5, flipud=0.5,
        hsv_h=0.003, hsv_s=0.10, hsv_v=0.12, erasing=0.0, auto_augment=None,
        seed=42, deterministic=False, plots=True,
    )
    (run / "complete.flag").write_text("complete\n", encoding="ascii")
    return best if best.exists() else None


def predict_resnet(network: nn.Module, samples: list[Sample]) -> dict[str, list[float]]:
    dataset = GearClassificationDataset(samples, augment=False)
    loader = DataLoader(dataset, batch_size=32, shuffle=False, num_workers=4, pin_memory=True)
    output = {}
    offset = 0
    with torch.no_grad():
        for images, _ in loader:
            probabilities = network(images.cuda(non_blocking=True)).softmax(1).cpu().tolist()
            for sample, values in zip(samples[offset:offset + len(probabilities)], probabilities):
                output[sample.stem] = values
            offset += len(probabilities)
    return output


def predict_yolo_classifier(weights: Path, samples: list[Sample]) -> dict[str, list[float]]:
    model = YOLO(weights)
    output = {}
    for sample in samples:
        result = model.predict(str(sample.image), imgsz=320, device=0, verbose=False)[0]
        values = [0.0] * len(CLASSES)
        for index, probability in enumerate(result.probs.data.cpu().tolist()):
            name = model.names[index]
            values[CLASSES.index(name)] = float(probability)
        output[sample.stem] = values
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return output


def anomaly_scores(network: nn.Module, train: list[Sample], target: list[Sample]) -> dict[str, float]:
    feature_model = nn.Sequential(*list(network.children())[:-1]).eval()
    transform = GearClassificationDataset([], augment=False).transform

    def embeddings(items: list[Sample]) -> torch.Tensor:
        values = []
        with torch.no_grad():
            for start in range(0, len(items), 32):
                batch = []
                for sample in items[start:start + 32]:
                    with Image.open(sample.image) as image:
                        batch.append(transform(image.convert("RGB")))
                tensor = torch.stack(batch).cuda(non_blocking=True)
                values.append(nn.functional.normalize(feature_model(tensor).flatten(1), dim=1).cpu())
        return torch.cat(values)

    normal = embeddings([sample for sample in train if sample.category == "normal"])
    query = embeddings(target)
    similarities = query @ normal.T
    raw = 1 - similarities.topk(min(5, normal.shape[0]), dim=1).values.mean(1)
    reference = 1 - (normal @ normal.T).topk(min(6, normal.shape[0]), dim=1).values[:, 1:].mean(1)
    low, high = float(torch.quantile(reference, 0.50)), float(torch.quantile(reference, 0.95))
    normalized = ((raw - low) / max(1e-6, high - low)).clamp(0, 1).tolist()
    return {sample.stem: float(score) for sample, score in zip(target, normalized)}


def save_anomaly_reference(network: nn.Module, train: list[Sample], destination: Path) -> None:
    feature_model = nn.Sequential(*list(network.children())[:-1]).eval()
    transform = GearClassificationDataset([], augment=False).transform
    normal_samples = [sample for sample in train if sample.category == "normal"]
    values = []
    with torch.no_grad():
        for start in range(0, len(normal_samples), 32):
            batch = []
            for sample in normal_samples[start:start + 32]:
                with Image.open(sample.image) as image:
                    batch.append(transform(image.convert("RGB")))
            values.append(nn.functional.normalize(feature_model(torch.stack(batch).cuda()).flatten(1), dim=1).cpu())
    bank = torch.cat(values)
    reference = 1 - (bank @ bank.T).topk(min(6, bank.shape[0]), dim=1).values[:, 1:].mean(1)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"embeddings": bank, "low": float(torch.quantile(reference, 0.50)), "high": float(torch.quantile(reference, 0.95))}, destination)


def detector_image_scores(weights: Path, samples: list[Sample], mode: str) -> dict[str, list[float]]:
    model = YOLO(weights)
    output = {}
    for sample in samples:
        result = model.predict(str(sample.image), imgsz=IMAGE_SIZE, conf=0.001, iou=0.7, max_det=100, device=0, verbose=False)[0]
        scores = [0.0, 0.0, 0.0]
        if result.boxes is not None:
            for cls, conf in zip(result.boxes.cls.cpu().tolist(), result.boxes.conf.cpu().tolist()):
                name = DEFECTS[int(cls)] if mode == "joint" else mode
                index = CLASSES.index(name)
                scores[index] = max(scores[index], float(conf))
        output[sample.stem] = scores
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return output


def contour_missing_score(sample: Sample) -> float:
    if sample.view != "face":
        return 0.0
    gray = cv2.imread(str(sample.image), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return 0.0
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return 0.0
    contour = max(contours, key=cv2.contourArea)
    moments = cv2.moments(contour)
    if moments["m00"] <= 0:
        return 0.0
    cx, cy = moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]
    points = contour[:, 0, :].astype(np.float32)
    angles = (np.arctan2(points[:, 1] - cy, points[:, 0] - cx) + 2 * np.pi) % (2 * np.pi)
    radii = np.hypot(points[:, 0] - cx, points[:, 1] - cy)
    profile = np.zeros(360, dtype=np.float32)
    for angle, radius in zip(angles, radii):
        index = int(angle * 360 / (2 * np.pi)) % 360
        profile[index] = max(profile[index], radius)
    missing = profile == 0
    if missing.any():
        valid = np.where(~missing)[0]
        if len(valid) < 180:
            return 0.0
        profile[missing] = np.interp(np.where(missing)[0], valid, profile[valid], period=360)
    smooth = cv2.GaussianBlur(profile.reshape(1, -1), (0, 0), 3).reshape(-1)
    residual = smooth - cv2.GaussianBlur(profile.reshape(1, -1), (0, 0), 12).reshape(-1)
    return float(np.clip((-np.percentile(residual, 2)) / max(1.0, np.std(residual) * 3), 0, 1))


def combine_scores(
    samples: list[Sample], yolo: dict[str, list[float]], resnet: dict[str, list[float]],
    anomaly: dict[str, float], detectors: dict[str, list[float]], strategy: str,
) -> dict[str, list[float]]:
    output = {}
    for sample in samples:
        if strategy == "yolo":
            values = yolo[sample.stem][:]
        elif strategy == "resnet":
            values = resnet[sample.stem][:]
        else:
            values = [max(yolo[sample.stem][index], resnet[sample.stem][index]) for index in range(3)]
            if strategy in {"classifiers_anomaly", "all"}:
                for index in (1, 2):
                    values[index] = max(values[index], anomaly[sample.stem])
            if strategy == "all":
                for index in (1, 2):
                    values[index] = max(values[index], detectors[sample.stem][index])
                values[2] = max(values[2], contour_missing_score(sample))
        output[sample.stem] = values
    return output


def gate_metrics(samples: list[Sample], scores: dict[str, list[float]], thresholds: dict[str, float]) -> dict[str, object]:
    predictions = {}
    for sample in samples:
        predicted = {name for name in DEFECTS if scores[sample.stem][CLASSES.index(name)] >= thresholds[name]}
        predictions[sample.stem] = predicted
    normal = [sample for sample in samples if sample.category == "normal"]
    fpr = sum(bool(predictions[sample.stem]) for sample in normal) / max(1, len(normal))
    classes = {}
    for name in DEFECTS:
        positives = [sample for sample in samples if sample.category == name]
        tp = sum(name in predictions[sample.stem] for sample in positives)
        fn = len(positives) - tp
        fp = sum(name in predictions[sample.stem] for sample in samples if sample.category != name)
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = 2 * precision * recall / max(1e-9, precision + recall)
        classes[name] = {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}
    return {"normal_fpr": fpr, "classes": classes, "thresholds": thresholds}


def select_gate(samples: list[Sample], candidates: dict[str, dict[str, list[float]]]) -> dict[str, object]:
    best = None
    for strategy, scores in candidates.items():
        for scratch_threshold in GATE_GRID:
            for missing_threshold in GATE_GRID:
                result = gate_metrics(samples, scores, {"scratch": scratch_threshold, "missing_tooth": missing_threshold})
                recalls = [result["classes"][name]["recall"] for name in DEFECTS]
                key = (result["normal_fpr"] <= 0.10, min(recalls), sum(recalls), -result["normal_fpr"])
                if best is None or key > best[0]:
                    best = (key, strategy, result)
    assert best is not None
    return {"strategy": best[1], **best[2]}


def fixed_detector_metrics(weights: Path, data: Path, mode: str, conf: float) -> dict[str, object]:
    model = YOLO(weights)
    metrics = model.val(
        data=str(data), split="test", conf=conf, iou=0.7, imgsz=IMAGE_SIZE,
        batch=8, workers=4, device=0, plots=True, verbose=False,
        project=str(OUTPUT / "final_metric_runs"), name=mode, exist_ok=True,
    )
    matrix = metrics.confusion_matrix.matrix
    result = {
        "precision": float(metrics.box.p[0]), "recall": float(metrics.box.r[0]),
        "f1": float(metrics.box.f1[0]), "map50": float(metrics.box.ap50[0]),
        "map5095": float(metrics.box.ap[0]), "conf": conf,
        "tp": int(matrix[0, 0]), "fp": int(matrix[0, 1]), "fn": int(matrix[1, 0]),
    }
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return result


def localization_by_view(weights: Path, samples: list[Sample], mode: str, conf: float) -> tuple[dict[str, object], dict[str, list[tuple[tuple[float, ...], float]]]]:
    model = YOLO(weights)
    predictions = {}
    for sample in samples:
        result = model.predict(str(sample.image), imgsz=IMAGE_SIZE, conf=conf, iou=0.7, max_det=300, device=0, verbose=False)[0]
        predictions[sample.stem] = [(tuple(box), float(score)) for box, score in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist())]

    def box_iou(left: tuple[float, ...], right: tuple[float, ...]) -> float:
        x1, y1, x2, y2 = max(left[0], right[0]), max(left[1], right[1]), min(left[2], right[2]), min(left[3], right[3])
        intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        area_left = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
        area_right = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
        return intersection / max(1e-9, area_left + area_right - intersection)

    output = {}
    for view in ("face", "oblique", "side"):
        subset = [sample for sample in samples if sample.view == view]
        view_result = {}
        for match_iou in (0.3, 0.5):
            tp = fp = fn = 0
            for sample in subset:
                truth = [tuple(box[1:]) for box in sample.boxes if box[0] == mode]
                unmatched = set(range(len(truth)))
                for box, _ in sorted(predictions[sample.stem], key=lambda item: item[1], reverse=True):
                    matches = [(box_iou(box, truth[index]), index) for index in unmatched]
                    value, index = max(matches, default=(0.0, -1))
                    if value >= match_iou:
                        tp += 1
                        unmatched.remove(index)
                    else:
                        fp += 1
                fn += len(unmatched)
            view_result[f"iou_{match_iou}"] = {"recall": tp / max(1, tp + fn), "precision": tp / max(1, tp + fp), "tp": tp, "fp": fp, "fn": fn}
        output[view] = view_result
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return output, predictions


def render_final(samples: list[Sample], gate_scores: dict[str, list[float]], gate: dict[str, object], detector_predictions: dict[str, dict[str, list[tuple[tuple[float, ...], float]]]]) -> None:
    output = OUTPUT / "final_visuals"
    output.mkdir(parents=True, exist_ok=True)
    thresholds = gate["thresholds"]
    for sample in samples:
        with Image.open(sample.image) as source:
            image = source.convert("RGB")
        draw = ImageDraw.Draw(image)
        for name, x1, y1, x2, y2 in sample.boxes:
            draw.rectangle((x1, y1, x2, y2), outline=(0, 220, 80), width=3)
        for mode, color in (("scratch", (255, 50, 50)), ("missing_tooth", (255, 180, 0))):
            for box, confidence in detector_predictions[mode][sample.stem]:
                draw.rectangle(box, outline=color, width=3)
                draw.text((box[0], max(18, box[1] - 12)), f"{mode}:{confidence:.2f}", fill=color)
        scratch_score = gate_scores[sample.stem][1]
        missing_score = gate_scores[sample.stem][2]
        rejected = scratch_score >= thresholds["scratch"] or missing_score >= thresholds["missing_tooth"]
        draw.text((8, 8), f"gate={'REJECT' if rejected else 'PASS'} s={scratch_score:.2f} m={missing_score:.2f}", fill=(255, 30, 30) if rejected else (0, 180, 60))
        image.save(output / f"{sample.stem}.jpg", quality=95)


def write_leaderboard(rows: list[dict[str, object]]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "leaderboard.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with (OUTPUT / "leaderboard.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("name", "mode", "stage", "score", "details"))
        writer.writeheader()
        for row in rows:
            writer.writerow({**{key: row[key] for key in ("name", "mode", "stage", "score")}, "details": json.dumps(row["details"])})


def validate_materialized(data: Path) -> None:
    root = data.parent
    for split in ("train", "val", "test"):
        images = sorted((root / "images" / split).glob("*.jpg"))
        labels = sorted((root / "labels" / split).glob("*.txt"))
        if len(images) != len(labels):
            raise ValueError(f"Image-label mismatch in {root} {split}")
        for label in labels:
            for line in label.read_text(encoding="ascii").splitlines():
                parts = line.split()
                if len(parts) != 5 or not all(0 <= float(value) <= 1 for value in parts[1:]):
                    raise ValueError(f"Invalid label: {label}: {line}")


def main() -> None:
    parser = argparse.ArgumentParser(description="V3 two-stage recall-first defect optimization")
    parser.add_argument("--hours", type=float, default=6.0)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required")
    if not OFFICIAL.exists():
        raise FileNotFoundError(OFFICIAL)
    final_report = OUTPUT / "final_report.json"
    if final_report.exists():
        print(final_report.read_text(encoding="utf-8"))
        return
    started = time.monotonic()
    deadline = started + args.hours * 3600
    OUTPUT.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    samples = load_samples()
    assignments, groups = make_split(samples)
    write_split(samples, assignments, groups)
    write_review_queue(samples, assignments)
    classification_data = materialize_classification(samples, assignments)
    train_samples = [sample for sample in samples if assignments[sample.stem] == "train"]
    val_samples = [sample for sample in samples if assignments[sample.stem] == "val"]
    test_samples = [sample for sample in samples if assignments[sample.stem] == "test"]

    yolo_classifier = train_yolo_classifier(classification_data, deadline)
    resnet_weights = train_resnet(samples, assignments, deadline)
    if yolo_classifier is None or resnet_weights is None:
        raise RuntimeError("Classification training did not finish within the time budget")
    resnet_model = load_resnet(resnet_weights)
    anomaly_reference = OUTPUT / "anomaly_reference.pt"
    save_anomaly_reference(resnet_model, train_samples, anomaly_reference)
    yolo_val = predict_yolo_classifier(yolo_classifier, val_samples)
    resnet_val = predict_resnet(resnet_model, val_samples)
    anomaly_val = anomaly_scores(resnet_model, train_samples, val_samples)

    pilots = [
        DetectorExperiment("p_s_standard_original", "scratch", "standard", "original", 25),
        DetectorExperiment("p_s_p2_original", "scratch", "p2", "original", 25),
        DetectorExperiment("p_s_p2_clahe", "scratch", "p2", "clahe", 25),
        DetectorExperiment("p_s_p2_gray", "scratch", "p2", "gray", 25),
        DetectorExperiment("p_m_standard_original", "missing_tooth", "standard", "original", 25),
        DetectorExperiment("p_m_p2_original", "missing_tooth", "p2", "original", 25),
        DetectorExperiment("p_m_p2_clahe", "missing_tooth", "p2", "clahe", 25),
        DetectorExperiment("p_joint_standard_original", "joint", "standard", "original", 25),
    ]
    rows = []
    pilot_results: dict[str, list[tuple[DetectorExperiment, dict[str, object]]]] = {"scratch": [], "missing_tooth": [], "joint": []}
    for experiment in pilots:
        data = materialize_detector(samples, assignments, experiment)
        validate_materialized(data)
        weights = train_detector(experiment, data, deadline)
        if weights is None:
            break
        result = evaluate_detector(weights, data, experiment.mode)
        pilot_results[experiment.mode].append((experiment, result))
        rows.append({"name": experiment.name, "mode": experiment.mode, "stage": "pilot", "score": result["score"], "details": result})
        write_leaderboard(rows)

    finalists = []
    for mode in DEFECTS:
        ranked = sorted(pilot_results[mode], key=lambda item: float(item[1]["score"]), reverse=True)
        if not ranked:
            continue
        winner = ranked[0][0]
        finalists.append(DetectorExperiment(f"f_{mode}_{winner.architecture}_{winner.representation}_seed42", mode, winner.architecture, winner.representation, 90))
    final_detectors = {}
    for experiment in finalists:
        data = materialize_detector(samples, assignments, experiment)
        validate_materialized(data)
        weights = train_detector(experiment, data, deadline)
        if weights is None:
            break
        result = evaluate_detector(weights, data, experiment.mode)
        final_detectors[experiment.mode] = {"experiment": experiment, "data": data, "weights": weights, "validation": result}
        rows.append({"name": experiment.name, "mode": experiment.mode, "stage": "full", "score": result["score"], "details": result})
        write_leaderboard(rows)
    if set(final_detectors) != set(DEFECTS):
        raise RuntimeError("Both final localization models are required")

    detector_val = {sample.stem: [0.0, 0.0, 0.0] for sample in val_samples}
    for mode in DEFECTS:
        scores = detector_image_scores(final_detectors[mode]["weights"], val_samples, mode)
        index = CLASSES.index(mode)
        for stem in detector_val:
            detector_val[stem][index] = scores[stem][index]
    strategies = {}
    for strategy in ("yolo", "resnet", "classifiers", "classifiers_anomaly", "all"):
        strategies[strategy] = combine_scores(val_samples, yolo_val, resnet_val, anomaly_val, detector_val, strategy)
    gate = select_gate(val_samples, strategies)
    (OUTPUT / "validation_gate.json").write_text(json.dumps(gate, indent=2), encoding="utf-8")

    # From this point onward the locked test set is evaluated exactly once.
    test_lock = OUTPUT / "test_evaluation_started.lock"
    if test_lock.exists():
        raise RuntimeError("Locked test evaluation was already started; inspect outputs before retrying")
    test_lock.write_text("started\n", encoding="ascii")
    yolo_test = predict_yolo_classifier(yolo_classifier, test_samples)
    resnet_test = predict_resnet(resnet_model, test_samples)
    anomaly_test = anomaly_scores(resnet_model, train_samples, test_samples)
    detector_test_scores = {sample.stem: [0.0, 0.0, 0.0] for sample in test_samples}
    detector_predictions = {}
    localization = {}
    for mode in DEFECTS:
        item = final_detectors[mode]
        class_metrics = item["validation"]["classes"][mode]
        conf = float(class_metrics["conf"])
        scores = detector_image_scores(item["weights"], test_samples, mode)
        index = CLASSES.index(mode)
        for stem in detector_test_scores:
            detector_test_scores[stem][index] = scores[stem][index]
        fixed = fixed_detector_metrics(item["weights"], item["data"], mode, conf)
        views, predictions = localization_by_view(item["weights"], test_samples, mode, conf)
        localization[mode] = {"overall": fixed, "by_view": views, "weights": str(item["weights"])}
        detector_predictions[mode] = predictions
    selected_scores = combine_scores(test_samples, yolo_test, resnet_test, anomaly_test, detector_test_scores, gate["strategy"])
    gate_test = gate_metrics(test_samples, selected_scores, gate["thresholds"])
    gate_test["by_view"] = {
        view: gate_metrics([sample for sample in test_samples if sample.view == view], selected_scores, gate["thresholds"])
        for view in ("face", "oblique", "side")
    }
    render_final(test_samples, selected_scores, gate, detector_predictions)

    final_dir = OUTPUT / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(yolo_classifier, final_dir / "gate_yolo26n_cls.pt")
    shutil.copy2(resnet_weights, final_dir / "gate_resnet18.pt")
    shutil.copy2(anomaly_reference, final_dir / "anomaly_reference.pt")
    for mode in DEFECTS:
        destination = final_dir / f"{mode}_localizer.pt"
        shutil.copy2(final_detectors[mode]["weights"], destination)
        localization[mode]["weights"] = str(destination)
    config = {
        "gate": {"strategy": gate["strategy"], "thresholds": gate["thresholds"], "normal_fpr_limit": 0.10, "yolo_classifier": str(final_dir / "gate_yolo26n_cls.pt"), "resnet_classifier": str(final_dir / "gate_resnet18.pt"), "anomaly_reference": str(final_dir / "anomaly_reference.pt")},
        "localizers": {mode: {"weights": localization[mode]["weights"], "confidence": localization[mode]["overall"]["conf"], "nms_iou": 0.7, "imgsz": IMAGE_SIZE} for mode in DEFECTS},
        "decision": "reject if either calibrated defect gate score reaches its class threshold; localizers are explanatory",
    }
    (OUTPUT / "inference_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    report = {
        "gpu": torch.cuda.get_device_name(0), "elapsed_hours": (time.monotonic() - started) / 3600,
        "split_preflight": json.loads((WORK / "preflight.json").read_text(encoding="utf-8")),
        "gate_validation": gate, "gate_test": gate_test, "localization_test": localization,
        "targets": {"scratch_image_recall": 0.90, "missing_tooth_image_recall": 0.90, "normal_fpr_max": 0.10, "box_recall": 0.70, "box_precision_floor": 0.50},
        "gate_target_met": gate_test["normal_fpr"] <= 0.10 and all(gate_test["classes"][name]["recall"] >= 0.90 for name in DEFECTS),
    }
    final_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUTPUT / "test_evaluation_complete.flag").write_text("complete\n", encoding="ascii")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
