from __future__ import annotations

import argparse
import csv
import gc
import json
import os
import random
import shutil
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageEnhance, ImageFilter
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import transforms
from ultralytics import YOLO

from train_scratch_v5 import (
    FocalBCE,
    apply_temperature,
    binary_auc,
    build_network,
    choose_threshold,
    clahe,
    jpeg_compress,
    square_image,
    temperature_scale,
)


ROOT = Path(__file__).resolve().parent
WORK = ROOT / "dataset_defects" / "missing_hole_v1"
RUNS = ROOT / "runs" / "missing_hole_v1"
OUTPUT = ROOT / "outputs" / "missing_hole_v1"
DOCS = ROOT / "docs" / "missing_hole_v1"
OFFICIAL_DETECTOR = ROOT / "yolo26n.pt"
OFFICIAL_CLASSIFIER = ROOT / "yolo26n-cls.pt"
P2_YAML = ROOT / ".venv" / "Lib" / "site-packages" / "ultralytics" / "cfg" / "models" / "26" / "yolo26-p2.yaml"
SEED = 20260913
FPR_CAPS = (0.10, 0.20, 0.30, 0.50)
PRIMARY_FPR = 0.20


@dataclass(frozen=True)
class Sample:
    stem: str
    split: str
    label: int
    image: Path
    classes: tuple[str, ...]
    has_difficult: bool
    all_difficult: bool
    width: int
    height: int

    @property
    def group(self) -> str:
        return "+".join(self.classes) if self.classes else "normal"


@dataclass(frozen=True)
class DetectorExperiment:
    name: str
    scheme: str
    difficult_policy: str
    architecture: str
    imgsz: int
    epochs: int
    stage: str
    seed: int = SEED


@dataclass(frozen=True)
class ClassifierExperiment:
    name: str
    family: str
    imgsz: int
    difficult_policy: str
    epochs: int
    stage: str
    seed: int = SEED


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated Missing Hole V1 high-recall search")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--pilots-only", action="store_true")
    parser.add_argument("--finalize-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def workers(requested: int) -> int:
    return min(8, requested) if requested > 0 else min(8, max(2, (os.cpu_count() or 4) - 2))


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def load_samples() -> list[Sample]:
    path = WORK / "master_manifest.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Run prepare_missing_hole_v1.py first: {path}")
    samples = []
    with path.open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["source_split"] != "train":
                continue
            samples.append(Sample(
                stem=row["stem"], split=row["split"], label=int(row["defect"]), image=Path(row["image"]),
                classes=tuple(value for value in row["classes"].split("+") if value),
                has_difficult=bool(int(row["has_difficult"])), all_difficult=bool(int(row["all_difficult"])),
                width=int(row["width"]), height=int(row["height"]),
            ))
    if len(samples) != 496 or Counter(sample.split for sample in samples) != Counter({"train": 397, "val": 99}):
        raise RuntimeError("Unexpected Missing Hole V1 manifest")
    return samples


def point_metrics(labels: list[int], probabilities: list[float], threshold: float) -> dict[str, float | int]:
    guesses = [probability >= threshold for probability in probabilities]
    tp = sum(label == 1 and guess for label, guess in zip(labels, guesses))
    fp = sum(label == 0 and guess for label, guess in zip(labels, guesses))
    tn = sum(label == 0 and not guess for label, guess in zip(labels, guesses))
    fn = sum(label == 1 and not guess for label, guess in zip(labels, guesses))
    recall = tp / max(1, tp + fn)
    precision = tp / max(1, tp + fp)
    fpr = fp / max(1, fp + tn)
    return {"threshold": threshold, "recall": recall, "precision": precision, "f1": 2 * precision * recall / max(1e-9, precision + recall), "fpr": fpr, "specificity": 1 - fpr, "npv": tn / max(1, tn + fn), "tp": tp, "fp": fp, "tn": tn, "fn": fn}


def evaluate_probabilities(samples: list[Sample], probabilities: list[float]) -> dict[str, object]:
    labels = [sample.label for sample in samples]
    temperature = temperature_scale(labels, probabilities)
    calibrated = apply_temperature(probabilities, temperature)
    points = {str(cap): choose_threshold(labels, calibrated, cap) for cap in FPR_CAPS}
    primary = points[str(PRIMARY_FPR)]
    auroc, auprc = binary_auc(labels, calibrated)
    groups = {}
    for name in ("bottom", "oblique", "side"):
        indexes = [index for index, sample in enumerate(samples) if name in sample.classes]
        groups[name] = {"images": len(indexes), "recall": sum(calibrated[index] >= primary["threshold"] for index in indexes) / max(1, len(indexes))}
    difficult_indexes = [index for index, sample in enumerate(samples) if sample.has_difficult]
    groups["difficult"] = {"images": len(difficult_indexes), "recall": sum(calibrated[index] >= primary["threshold"] for index in difficult_indexes) / max(1, len(difficult_indexes))}
    return {"temperature": temperature, "operating_points": points, "primary": primary, "auroc": auroc, "auprc": auprc, "groups": groups, "probabilities": calibrated}


def rank_key(row: dict[str, object]) -> tuple[float, ...]:
    point = row["primary"]
    groups = row.get("groups", {})
    recalls = [float(groups[name]["recall"]) for name in ("bottom", "oblique", "side") if name in groups and groups[name]["images"]]
    return (float(point["fpr"] <= PRIMARY_FPR), float(point["recall"]), min(recalls, default=0.0), -float(point["fpr"]), float(row.get("auprc", 0.0)))


def save_leaderboard(rows: list[dict[str, object]]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "leaderboard.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    flat = []
    for row in rows:
        primary = row.get("primary", {})
        flat.append({
            "name": row.get("name", ""), "kind": row.get("kind", ""), "stage": row.get("stage", ""),
            "scheme": row.get("scheme", ""), "difficult_policy": row.get("difficult_policy", ""),
            "architecture_family": row.get("architecture", row.get("family", "")), "imgsz": row.get("imgsz", ""),
            "epochs": row.get("epochs", ""), "recall": primary.get("recall", ""), "precision": primary.get("precision", ""),
            "fpr": primary.get("fpr", ""), "f1": primary.get("f1", ""), "auroc": row.get("auroc", ""),
            "auprc": row.get("auprc", ""), "weights": row.get("weights", ""), "error": row.get("error", ""),
        })
    with (OUTPUT / "leaderboard.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat[0]) if flat else ["name"])
        writer.writeheader()
        writer.writerows(flat)


def write_experiment_doc(row: dict[str, object]) -> None:
    directory = DOCS / "experiments"
    directory.mkdir(parents=True, exist_ok=True)
    point = row.get("primary", {})
    lines = [
        f"# {row['name']}", "", f"- 状态：`{'失败' if row.get('error') else '完成'}`",
        f"- 类型：`{row.get('kind', '')}`", f"- 阶段：`{row.get('stage', '')}`",
        f"- difficult 策略：`{row.get('difficult_policy', '')}`", f"- 输入尺寸：`{row.get('imgsz', '')}`",
        f"- 计划轮数：`{row.get('epochs', '')}`", f"- 权重：`{row.get('weights', '')}`", "",
    ]
    if row.get("error"):
        lines += ["## 错误", "", f"```text\n{row['error']}\n```", ""]
    else:
        lines += [
            "## 验证集主工作点", "",
            "| Recall | Precision | F1 | FPR | TP/FP/TN/FN | AUROC | AUPRC |",
            "|---:|---:|---:|---:|---:|---:|---:|",
            f"| {point.get('recall', 0):.4f} | {point.get('precision', 0):.4f} | {point.get('f1', 0):.4f} | {point.get('fpr', 0):.4f} | {point.get('tp', 0)}/{point.get('fp', 0)}/{point.get('tn', 0)}/{point.get('fn', 0)} | {row.get('auroc', 0):.4f} | {row.get('auprc', 0):.4f} |",
            "", "主工作点由验证集在 FPR 不超过 20% 时最大化图像级 Recall 得到。test 未被读取。", "",
            "## 配置", "", "```json", json.dumps({key: value for key, value in row.items() if key not in {"probabilities"}}, ensure_ascii=False, indent=2), "```", "",
        ]
    (directory / f"{row['name']}.md").write_text("\n".join(lines), encoding="utf-8")
    completed = sorted(directory.glob("*.md"))
    index = ["# Missing Hole V1 实验记录", "", f"已记录实验：{len(completed)}", ""] + [f"- [{path.stem}](experiments/{path.name})" for path in completed]
    (DOCS / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")


def detector_model(architecture: str) -> YOLO:
    if architecture == "standard":
        return YOLO(OFFICIAL_DETECTOR)
    if architecture == "p2":
        return YOLO(P2_YAML).load(OFFICIAL_DETECTOR)
    raise ValueError(architecture)


def train_detector(experiment: DetectorExperiment, worker_count: int) -> Path:
    run = RUNS / experiment.name
    best = run / "weights" / "best.pt"
    marker = run / "complete.flag"
    if best.is_file() and marker.is_file():
        return best
    data = WORK / "yolo" / f"{experiment.scheme}_{experiment.difficult_policy}" / "data.yaml"
    batch = 8 if experiment.imgsz <= 960 else 4
    cache: str | bool = "ram"
    workers = min(worker_count, 4) if experiment.imgsz > 960 else worker_count
    for attempt in range(10):
        try:
            model = detector_model(experiment.architecture)
            model.train(
                data=str(data), epochs=experiment.epochs, patience=12 if experiment.stage == "pilot" else 25,
                imgsz=experiment.imgsz, batch=batch, workers=workers, device=0, amp=True, cache=cache,
                project=str(RUNS), name=experiment.name, exist_ok=True, optimizer="AdamW", lr0=7e-4,
                weight_decay=5e-4, mosaic=0.0, mixup=0.0, copy_paste=0.0, degrees=8.0,
                translate=0.03, scale=0.08, fliplr=0.5, flipud=0.5, hsv_h=0.003, hsv_s=0.08,
                hsv_v=0.18, close_mosaic=0, seed=experiment.seed, deterministic=False, plots=True,
            )
            marker.write_text("complete\n", encoding="ascii")
            return best
        except (RuntimeError, OSError) as error:
            if isinstance(error, OSError) and error.errno == 22:
                if workers > 0:
                    workers = workers // 2
                    continue
                if cache == "ram":
                    cache = False
                    continue
            if "out of memory" in str(error).lower() and batch > 1:
                batch = max(1, batch // 2)
                torch.cuda.empty_cache()
                continue
            raise
    raise RuntimeError(f"Unable to train {experiment.name}")


def materialize_refined_detector(base_row: dict[str, object], samples: list[Sample]) -> str:
    base_scheme = str(base_row["scheme"])
    policy = str(base_row["difficult_policy"])
    refined_scheme = f"refined_{base_scheme}"
    source = WORK / "yolo" / f"{base_scheme}_{policy}"
    target = WORK / "yolo" / f"{refined_scheme}_{policy}"
    marker = target / "complete.flag"
    if marker.is_file():
        return refined_scheme
    for split in ("train", "val"):
        for image in (source / "images" / split).glob("*"):
            destination = target / "images" / split / image.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(image, destination)
            except OSError:
                shutil.copy2(image, destination)
        for label in (source / "labels" / split).glob("*.txt"):
            destination = target / "labels" / split / label.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(label, destination)
    train_samples = [sample for sample in samples if sample.split == "train" and (source / "images" / "train" / sample.image.name).is_file()]
    raw = predict_detector(Path(base_row["weights"]), train_samples, int(base_row["imgsz"]))
    calibrated = apply_temperature(raw, float(base_row["temperature"]))
    threshold = float(base_row["primary"]["threshold"])
    for sample, probability in zip(train_samples, calibrated):
        label = source / "labels" / "train" / f"{sample.stem}.txt"
        copies = 2 if sample.label and probability < threshold else 1 if not sample.label and probability >= threshold else 0
        if sample.label:
            copies = max(copies, 1)
        for index in range(copies):
            suffix = "clahe" if index == 0 and sample.label else f"hard{index + 1}"
            image_destination = target / "images" / "train" / f"{sample.stem}_{suffix}{sample.image.suffix}"
            if suffix == "clahe":
                with Image.open(sample.image) as opened:
                    clahe(opened.convert("RGB")).save(image_destination, quality=95)
            else:
                try:
                    os.link(sample.image, image_destination)
                except OSError:
                    shutil.copy2(sample.image, image_destination)
            shutil.copy2(label, target / "labels" / "train" / f"{sample.stem}_{suffix}.txt")
    yaml = (source / "data.yaml").read_text(encoding="ascii").splitlines()
    yaml[0] = f"path: {target.as_posix()}"
    (target / "data.yaml").write_text("\n".join(yaml) + "\n", encoding="ascii")
    marker.write_text("complete\n", encoding="ascii")
    return refined_scheme


def predict_detector(weights: Path, samples: list[Sample], imgsz: int) -> list[float]:
    model = YOLO(weights)
    output = []
    for sample in samples:
        result = model.predict(str(sample.image), imgsz=imgsz, conf=0.001, iou=0.7, device=0, verbose=False)[0]
        output.append(float(result.boxes.conf.max().item()) if result.boxes is not None and len(result.boxes) else 0.0)
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return output


class BinaryDataset(Dataset):
    def __init__(self, samples: list[Sample], size: int, augment: bool) -> None:
        self.samples, self.size, self.augment = samples, size, augment
        self.tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))])

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, float]:
        sample = self.samples[index]
        with Image.open(sample.image) as opened:
            image = opened.convert("RGB")
        if self.augment:
            if random.random() < 0.75:
                image = image.transpose(random.choice((Image.Transpose.FLIP_LEFT_RIGHT, Image.Transpose.FLIP_TOP_BOTTOM, Image.Transpose.ROTATE_90, Image.Transpose.ROTATE_270)))
            if random.random() < 0.7:
                image = ImageEnhance.Brightness(image).enhance(random.uniform(0.82, 1.18))
                image = ImageEnhance.Contrast(image).enhance(random.uniform(0.80, 1.22))
            if random.random() < 0.25:
                image = clahe(image)
            if random.random() < 0.15:
                image = image.filter(ImageFilter.GaussianBlur(random.uniform(0.1, 1.0)))
            if random.random() < 0.20:
                array = np.asarray(image).astype(np.float32) + np.random.normal(0, random.uniform(1.0, 5.0), np.asarray(image).shape)
                image = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))
            if random.random() < 0.15:
                image = jpeg_compress(image, random.randint(65, 92))
        return self.tensor(square_image(image, self.size)), float(sample.label)


def variants(path: Path, size: int, tta: str) -> list[torch.Tensor]:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    images = [image]
    if tta == "flip":
        images += [image.transpose(Image.Transpose.FLIP_LEFT_RIGHT), image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)]
    elif tta == "rot90":
        images += [image.transpose(Image.Transpose.ROTATE_90), image.transpose(Image.Transpose.ROTATE_270)]
    tensor = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))])
    return [tensor(square_image(item, size)) for item in images]


def materialize_yolo_cls(experiment: ClassifierExperiment, samples: list[Sample]) -> Path:
    root = WORK / "classification" / experiment.name
    marker = root / "complete.flag"
    if marker.is_file():
        return root
    for sample in samples:
        if sample.split == "train" and experiment.difficult_policy == "exclude_difficult" and sample.all_difficult:
            continue
        destination = root / sample.split / ("missing_hole" if sample.label else "normal") / sample.image.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(sample.image, destination)
        except OSError:
            shutil.copy2(sample.image, destination)
    marker.write_text("complete\n", encoding="ascii")
    return root


def train_classifier(experiment: ClassifierExperiment, samples: list[Sample], worker_count: int) -> Path:
    run = RUNS / experiment.name
    if experiment.family == "yolo_cls":
        best = run / "weights" / "best.pt"
        marker = run / "complete.flag"
        if best.is_file() and marker.is_file():
            return best
        data = materialize_yolo_cls(experiment, samples)
        batch = 24 if experiment.imgsz == 384 else 12
        for _ in range(4):
            try:
                model = YOLO(OFFICIAL_CLASSIFIER)
                model.train(data=str(data), epochs=experiment.epochs, patience=12 if experiment.stage == "pilot" else 25, imgsz=experiment.imgsz, batch=batch, workers=worker_count, device=0, amp=True, cache="ram", project=str(RUNS), name=experiment.name, exist_ok=True, optimizer="AdamW", lr0=7e-4, weight_decay=5e-4, scale=0.0, degrees=0.0, translate=0.0, fliplr=0.5, flipud=0.5, hsv_h=0.003, hsv_s=0.08, hsv_v=0.18, erasing=0.0, auto_augment=None, seed=experiment.seed, deterministic=False, plots=True)
                marker.write_text("complete\n", encoding="ascii")
                return best
            except RuntimeError as error:
                if "out of memory" not in str(error).lower() or batch <= 1:
                    raise
                batch = max(1, batch // 2)
                torch.cuda.empty_cache()
        raise RuntimeError(f"Unable to train {experiment.name}")

    best = run / "best.pt"
    marker = run / "complete.flag"
    if best.is_file() and marker.is_file():
        return best
    run.mkdir(parents=True, exist_ok=True)
    set_seed(experiment.seed)
    train_samples = [sample for sample in samples if sample.split == "train" and not (experiment.difficult_policy == "exclude_difficult" and sample.all_difficult)]
    val_samples = [sample for sample in samples if sample.split == "val"]
    strata = Counter((sample.label, sample.group) for sample in train_samples)
    sample_weights = [1.0 / strata[(sample.label, sample.group)] for sample in train_samples]
    sampler = WeightedRandomSampler(sample_weights, len(train_samples), replacement=True)
    batch = 24 if experiment.imgsz == 384 else 12
    train_loader = DataLoader(BinaryDataset(train_samples, experiment.imgsz, True), batch_size=batch, sampler=sampler, num_workers=worker_count, pin_memory=True, persistent_workers=worker_count > 0)
    val_loader = DataLoader(BinaryDataset(val_samples, experiment.imgsz, False), batch_size=batch, shuffle=False, num_workers=worker_count, pin_memory=True, persistent_workers=worker_count > 0)
    network = build_network(experiment.family).cuda()
    optimizer = torch.optim.AdamW(network.parameters(), lr=3e-4, weight_decay=5e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=experiment.epochs, eta_min=1e-6)
    criterion = FocalBCE(2.0, gamma=1.5)
    scaler = torch.amp.GradScaler("cuda")
    best_score = (-1.0, -1.0, -1.0)
    stale = 0
    history = []
    for epoch in range(1, experiment.epochs + 1):
        network.train()
        losses = []
        for images, labels in train_loader:
            images, labels = images.cuda(non_blocking=True), labels.cuda(non_blocking=True).unsqueeze(1)
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
        probabilities, labels = [], []
        with torch.no_grad():
            for images, target in val_loader:
                probabilities.extend(network(images.cuda(non_blocking=True)).sigmoid().cpu().flatten().tolist())
                labels.extend(target.int().tolist())
        point = choose_threshold(labels, probabilities, PRIMARY_FPR)
        score = (float(point["recall"]), -float(point["fpr"]), float(point["precision"]))
        history.append({"epoch": epoch, "loss": float(np.mean(losses)), **point})
        print(f"{experiment.name} epoch={epoch} loss={np.mean(losses):.4f} recall={point['recall']:.3f} fpr={point['fpr']:.3f}", flush=True)
        if score > best_score:
            best_score, stale = score, 0
            torch.save({"model": network.state_dict(), "family": experiment.family, "size": experiment.imgsz, "seed": experiment.seed, "difficult_policy": experiment.difficult_policy}, best)
        else:
            stale += 1
        if stale >= (12 if experiment.stage == "pilot" else 25):
            break
    (run / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    marker.write_text("complete\n", encoding="ascii")
    del network
    gc.collect()
    torch.cuda.empty_cache()
    return best


def predict_classifier(weights: Path, experiment: ClassifierExperiment, samples: list[Sample], tta: str) -> list[float]:
    output = []
    if experiment.family == "yolo_cls":
        model = YOLO(weights)
        index = next(index for index, name in model.names.items() if name == "missing_hole")
        for sample in samples:
            with Image.open(sample.image) as opened:
                image = opened.convert("RGB")
            images = [image]
            if tta == "flip":
                images += [image.transpose(Image.Transpose.FLIP_LEFT_RIGHT), image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)]
            elif tta == "rot90":
                images += [image.transpose(Image.Transpose.ROTATE_90), image.transpose(Image.Transpose.ROTATE_270)]
            results = model.predict([np.asarray(square_image(item, experiment.imgsz)) for item in images], imgsz=experiment.imgsz, batch=4, device=0, verbose=False)
            output.append(float(np.mean([result.probs.data[index].item() for result in results])))
        del model
    else:
        checkpoint = torch.load(weights, map_location="cpu", weights_only=False)
        network = build_network(str(checkpoint["family"]))
        network.load_state_dict(checkpoint["model"])
        network.cuda().eval()
        with torch.no_grad():
            for sample in samples:
                batch = torch.stack(variants(sample.image, experiment.imgsz, tta)).cuda()
                output.append(float(network(batch).sigmoid().mean()))
        del network
    gc.collect()
    torch.cuda.empty_cache()
    return output


def run_experiment(experiment: DetectorExperiment | ClassifierExperiment, samples: list[Sample], worker_count: int, rows: list[dict[str, object]]) -> tuple[dict[str, object], list[float]] | None:
    existing = next((row for row in rows if row.get("name") == experiment.name and not row.get("error")), None)
    if existing:
        probability_path = OUTPUT / "probabilities" / f"{experiment.name}.json"
        if probability_path.is_file():
            return existing, json.loads(probability_path.read_text(encoding="utf-8"))
    print(f"\n=== {experiment.name} ===", flush=True)
    try:
        val = [sample for sample in samples if sample.split == "val"]
        if isinstance(experiment, DetectorExperiment):
            weights = train_detector(experiment, worker_count)
            raw = predict_detector(weights, val, experiment.imgsz)
            kind = "detector"
        else:
            weights = train_classifier(experiment, samples, worker_count)
            candidates = []
            for tta in ("none", "flip", "rot90"):
                values = predict_classifier(weights, experiment, val, tta)
                evaluation = evaluate_probabilities(val, values)
                candidates.append((rank_key(evaluation), tta, values, evaluation))
            _, selected_tta, raw, evaluation = max(candidates, key=lambda item: item[0])
            kind = "classifier"
        if isinstance(experiment, DetectorExperiment):
            evaluation = evaluate_probabilities(val, raw)
            selected_tta = "none"
        calibrated = list(evaluation.pop("probabilities"))
        row = {"name": experiment.name, "kind": kind, **asdict(experiment), "weights": str(weights), "tta": selected_tta, **evaluation}
        rows[:] = [item for item in rows if item.get("name") != experiment.name] + [row]
        probability_path = OUTPUT / "probabilities" / f"{experiment.name}.json"
        probability_path.parent.mkdir(parents=True, exist_ok=True)
        probability_path.write_text(json.dumps(calibrated), encoding="utf-8")
        save_leaderboard(rows)
        write_experiment_doc(row)
        return row, calibrated
    except Exception as error:
        row = {"name": experiment.name, "kind": "detector" if isinstance(experiment, DetectorExperiment) else "classifier", **asdict(experiment), "error": repr(error)}
        rows[:] = [item for item in rows if item.get("name") != experiment.name] + [row]
        save_leaderboard(rows)
        write_experiment_doc(row)
        print(f"FAILED {experiment.name}: {error!r}", flush=True)
        return None


def load_rows() -> list[dict[str, object]]:
    path = OUTPUT / "leaderboard.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def fusion_search(samples: list[Sample], artifacts: list[tuple[dict[str, object], list[float]]]) -> dict[str, object]:
    val = [sample for sample in samples if sample.split == "val"]
    labels = [sample.label for sample in val]
    classifiers = sorted((item for item in artifacts if item[0]["kind"] == "classifier"), key=lambda item: rank_key(item[0]), reverse=True)[:2]
    detectors = sorted((item for item in artifacts if item[0]["kind"] == "detector"), key=lambda item: rank_key(item[0]), reverse=True)[:1]
    candidates = []
    for row, probs in classifiers + detectors:
        candidates.append((row["name"], probs, {"type": row["kind"], "models": [row["name"]]}))
    if len(classifiers) >= 2:
        matrix = np.asarray([item[1] for item in classifiers])
        candidates += [("classifier_mean", matrix.mean(0).tolist(), {"type": "classifier_mean", "models": [item[0]["name"] for item in classifiers]}), ("classifier_max", matrix.max(0).tolist(), {"type": "classifier_max", "models": [item[0]["name"] for item in classifiers]})]
    classifier_candidates = list(candidates)
    if detectors:
        detector_probs = np.asarray(detectors[0][1])
        for name, probs, rule in classifier_candidates:
            if rule["type"] == "detector":
                continue
            for alpha in (0.25, 0.5, 0.75):
                values = (alpha * np.asarray(probs) + (1 - alpha) * detector_probs).tolist()
                candidates.append((f"weighted_{name}_{alpha}", values, {"type": "weighted", "alpha": alpha, "classifier": rule, "detector": detectors[0][0]["name"]}))
            candidates.append((f"soft_or_{name}", np.maximum(probs, detector_probs).tolist(), {"type": "soft_or", "classifier": rule, "detector": detectors[0][0]["name"]}))
    rows = []
    for name, probabilities, rule in candidates:
        points = {str(cap): choose_threshold(labels, probabilities, cap) for cap in FPR_CAPS}
        auroc, auprc = binary_auc(labels, probabilities)
        rows.append({"name": name, "rule": rule, "operating_points": points, "primary": points[str(PRIMARY_FPR)], "auroc": auroc, "auprc": auprc})
    best = max(rows, key=rank_key)
    (OUTPUT / "fusion_leaderboard.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return best


def finalize(samples: list[Sample], artifacts: list[tuple[dict[str, object], list[float]]]) -> None:
    if not artifacts:
        raise RuntimeError("No completed artifacts")
    best = fusion_search(samples, artifacts)
    model_rows = {row[0]["name"]: row[0] for row in artifacts}
    needed = set()
    def collect(rule: dict[str, object]) -> None:
        needed.update(rule.get("models", []))
        if "classifier" in rule:
            collect(rule["classifier"])
        if "detector" in rule:
            needed.add(rule["detector"])
    collect(best["rule"])
    final_dir = OUTPUT / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    models = []
    for index, name in enumerate(sorted(needed), start=1):
        row = model_rows[name]
        suffix = "detector" if row["kind"] == "detector" else "classifier"
        destination = final_dir / f"{suffix}_{index}.pt"
        shutil.copy2(row["weights"], destination)
        models.append({"name": name, "kind": row["kind"], "family": row.get("family", row.get("architecture")), "scheme": row.get("scheme"), "difficult_policy": row.get("difficult_policy"), "weights": str(destination), "imgsz": row["imgsz"], "tta": row.get("tta", "none"), "temperature": row["temperature"], "operating_points": row["operating_points"]})
    config = {"version": "missing_hole_v1", "models": models, "fusion": best["rule"], "default_threshold": best["primary"]["threshold"], "operating_points": best["operating_points"], "selection": "validation FPR<=0.20 then maximum image recall", "test_used": False}
    (OUTPUT / "inference_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = ["# Missing Hole V1 验证总结", "", "独立 test 尚未读取。", "", "## 最佳融合", "", f"- 方案：`{best['name']}`", f"- Recall：`{best['primary']['recall']:.4f}`", f"- Precision：`{best['primary']['precision']:.4f}`", f"- FPR：`{best['primary']['fpr']:.4f}`", f"- 阈值：`{best['primary']['threshold']:.8f}`", "", "完整实验记录见 `docs/missing_hole_v1/experiments/`。", ""]
    (OUTPUT / "README.md").write_text("\n".join(summary), encoding="utf-8")


def main() -> None:
    args = parse_args()
    os.chdir(ROOT)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    for path in (OFFICIAL_DETECTOR, OFFICIAL_CLASSIFIER, P2_YAML, WORK / "preflight_report.json"):
        if not path.is_file():
            raise FileNotFoundError(path)
    worker_count = workers(args.workers)
    samples = load_samples()
    RUNS.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    runtime = {"gpu": torch.cuda.get_device_name(0), "cuda": torch.version.cuda, "torch": torch.__version__, "workers": worker_count, "amp": True, "cache": "ram", "train": sum(s.split == "train" for s in samples), "val": sum(s.split == "val" for s in samples)}
    (OUTPUT / "runtime.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    print(json.dumps(runtime, indent=2), flush=True)
    if args.dry_run:
        detector_model("standard")
        detector_model("p2")
        build_network("resnet18")
        build_network("efficientnet_b0")
        print("dry-run passed")
        return
    rows = load_rows()
    artifacts: list[tuple[dict[str, object], list[float]]] = []
    probability_dir = OUTPUT / "probabilities"
    if args.finalize_only:
        for row in rows:
            path = probability_dir / f"{row['name']}.json"
            if not row.get("error") and path.is_file():
                artifacts.append((row, json.loads(path.read_text(encoding="utf-8"))))
        finalize(samples, artifacts)
        return
    detector_pilots = [DetectorExperiment(f"p_det_{scheme}_{policy}_{arch}_960", scheme, policy, arch, 960, 35, "pilot", args.seed) for scheme in ("three_class", "two_class", "one_class") for policy in ("include_difficult", "exclude_difficult") for arch in ("standard", "p2")]
    classifier_pilots = [ClassifierExperiment(f"p_cls_{family}_{size}_{policy}", family, size, policy, 30, "pilot", args.seed) for family in ("resnet18", "efficientnet_b0", "yolo_cls") for size in (384, 512) for policy in ("include_difficult", "exclude_difficult")]
    for experiment in detector_pilots + classifier_pilots:
        result = run_experiment(experiment, samples, worker_count, rows)
        if result:
            artifacts.append(result)
    if args.pilots_only:
        finalize(samples, artifacts)
        return
    successful_detectors = [item for item in artifacts if item[0]["kind"] == "detector"]
    full_detectors = []
    for scheme in ("three_class", "two_class", "one_class"):
        candidates = [item for item in successful_detectors if item[0]["scheme"] == scheme]
        if not candidates:
            continue
        winner = max(candidates, key=lambda item: rank_key(item[0]))[0]
        for size in (960, 1280):
            full_detectors.append(DetectorExperiment(f"f_det_{scheme}_{winner['difficult_policy']}_{winner['architecture']}_{size}", scheme, winner["difficult_policy"], winner["architecture"], size, 100, "full", args.seed))
    successful_classifiers = sorted((item for item in artifacts if item[0]["kind"] == "classifier"), key=lambda item: rank_key(item[0]), reverse=True)
    full_classifiers = [ClassifierExperiment(f"f_cls_{item[0]['family']}_{item[0]['imgsz']}_{item[0]['difficult_policy']}_s{args.seed}", item[0]["family"], int(item[0]["imgsz"]), item[0]["difficult_policy"], 100, "full", args.seed) for item in successful_classifiers[:2]]
    for experiment in full_detectors + full_classifiers:
        result = run_experiment(experiment, samples, worker_count, rows)
        if result:
            artifacts.append(result)
    detector_candidates = [item for item in artifacts if item[0]["kind"] == "detector"]
    if detector_candidates:
        best_detector = max(detector_candidates, key=lambda item: rank_key(item[0]))[0]
        refined_scheme = materialize_refined_detector(best_detector, samples)
        refinement = DetectorExperiment(f"refine_{best_detector['scheme']}_{best_detector['difficult_policy']}_{best_detector['architecture']}_{best_detector['imgsz']}", refined_scheme, best_detector["difficult_policy"], best_detector["architecture"], int(best_detector["imgsz"]), 100, "refinement", args.seed)
        result = run_experiment(refinement, samples, worker_count, rows)
        if result:
            artifacts.append(result)
    completed = sorted(artifacts, key=lambda item: rank_key(item[0]), reverse=True)
    if completed:
        winner = completed[0][0]
        if winner["kind"] == "detector":
            confirmation = DetectorExperiment(f"confirm_{winner['scheme']}_{winner['difficult_policy']}_{winner['architecture']}_{winner['imgsz']}_s{args.seed + 1}", winner["scheme"], winner["difficult_policy"], winner["architecture"], int(winner["imgsz"]), 100, "confirmation", args.seed + 1)
        else:
            confirmation = ClassifierExperiment(f"confirm_{winner['family']}_{winner['imgsz']}_{winner['difficult_policy']}_s{args.seed + 1}", winner["family"], int(winner["imgsz"]), winner["difficult_policy"], 100, "confirmation", args.seed + 1)
        result = run_experiment(confirmation, samples, worker_count, rows)
        if result:
            artifacts.append(result)
    finalize(samples, artifacts)


if __name__ == "__main__":
    main()
