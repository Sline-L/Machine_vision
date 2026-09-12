from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import os
import random
import shutil
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from PIL import Image
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "dataset_defects"
WORK = SOURCE / "auto_search_v2"
RUNS = ROOT / "runs" / "defect_search_v2"
OUTPUT = ROOT / "outputs" / "defect_search_v2"
OFFICIAL = ROOT / "yolo26n.pt"
GEAR = ROOT / "runs" / "gear_yolo26n_496train_50val_fixed" / "weights" / "best.pt"
OLD_DEFECT = ROOT / "runs" / "defect_yolo26n_140_v1_gpu" / "weights" / "best.pt"
CLASSES = ("scratch", "missing_tooth")
SPLIT_TARGETS = {
    "scratch": {"train": 55, "val": 12, "test": 12},
    "missing_tooth": {"train": 92, "val": 20, "test": 20},
    "negative": {"train": 92, "val": 20, "test": 20},
}
CONF_THRESHOLDS = (0.01, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40)


@dataclass(frozen=True)
class Sample:
    stem: str
    image: Path
    xml: Path | None
    category: str
    width: int
    height: int
    boxes: tuple[tuple[str, float, float, float, float], ...]
    dhash: int


@dataclass(frozen=True)
class Experiment:
    name: str
    mode: str
    weights: Path
    negative_ratio: float
    imgsz: int
    augmentation: str
    epochs: int = 30
    seed: int = 42
    eligible: bool = True


def parse_xml(path: Path) -> tuple[int, int, tuple[tuple[str, float, float, float, float], ...]]:
    root = ET.parse(path).getroot()
    size = root.find("size")
    if size is None:
        raise ValueError(f"Missing size: {path}")
    width, height = int(size.findtext("width", "0")), int(size.findtext("height", "0"))
    boxes = []
    for obj in root.findall("object"):
        name = obj.findtext("name", "").strip()
        box = obj.find("bndbox")
        if name not in CLASSES or box is None:
            raise ValueError(f"Invalid object: {path}")
        values = tuple(float(box.findtext(key, "0")) for key in ("xmin", "ymin", "xmax", "ymax"))
        if not (0 <= values[0] < values[2] <= width and 0 <= values[1] < values[3] <= height):
            raise ValueError(f"Invalid box: {path} {values}")
        boxes.append((name, *values))
    return width, height, tuple(boxes)


def image_dhash(path: Path) -> int:
    with Image.open(path) as image:
        pixels = list(image.convert("L").resize((9, 8), Image.Resampling.LANCZOS).getdata())
    value = 0
    for row in range(8):
        for col in range(8):
            value = (value << 1) | int(pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return value


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
                raise ValueError(f"Expected one source category in {xml}: {names}")
            category = next(iter(names))
            xml_path: Path | None = xml
        else:
            with Image.open(image) as source_image:
                width, height = source_image.size
            boxes, category, xml_path = (), "negative", None
        samples.append(Sample(stem, image, xml_path, category, width, height, boxes, image_dhash(image)))
    counts = {name: sum(sample.category == name for sample in samples) for name in (*CLASSES, "negative")}
    if counts != {"scratch": 79, "missing_tooth": 132, "negative": 132}:
        raise ValueError(f"Unexpected source counts: {counts}")
    return samples


def connected_groups(samples: list[Sample], distance: int = 4) -> list[list[Sample]]:
    parent = list(range(len(samples)))

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left in range(len(samples)):
        for right in range(left + 1, len(samples)):
            if (samples[left].dhash ^ samples[right].dhash).bit_count() <= distance:
                union(left, right)
    groups: dict[int, list[Sample]] = {}
    for index, sample in enumerate(samples):
        groups.setdefault(find(index), []).append(sample)
    return list(groups.values())


def make_split(samples: list[Sample]) -> dict[str, str]:
    groups = connected_groups(samples, distance=1)
    splits = ("train", "val", "test")
    categories = (*CLASSES, "negative")
    best_error = math.inf
    best_assignments: dict[str, str] = {}
    rng = random.Random(42)
    for _ in range(1000):
        rng.shuffle(groups)
        ordered = sorted(groups, key=len, reverse=True)
        counts = {split: {category: 0 for category in categories} for split in splits}
        assignments: dict[str, str] = {}
        for group in ordered:
            additions = {category: sum(sample.category == category for sample in group) for category in categories}

            def placement_cost(split: str) -> float:
                cost = 0.0
                for category in categories:
                    target = SPLIT_TARGETS[category][split]
                    new_count = counts[split][category] + additions[category]
                    cost += ((new_count - target) / target) ** 2
                    if new_count > target:
                        cost += 10 * (new_count - target)
                return cost

            chosen = min(splits, key=placement_cost)
            for category in categories:
                counts[chosen][category] += additions[category]
            for sample in group:
                assignments[sample.stem] = chosen
        error = sum(
            abs(counts[split][category] - SPLIT_TARGETS[category][split])
            for split in splits for category in categories
        )
        if error < best_error:
            best_error, best_assignments = error, assignments
        if error == 0:
            break
    return best_assignments


def yolo_line(box: tuple[str, float, float, float, float], sample: Sample, class_ids: dict[str, int]) -> str:
    name, xmin, ymin, xmax, ymax = box
    center_x, center_y = (xmin + xmax) / (2 * sample.width), (ymin + ymax) / (2 * sample.height)
    width, height = (xmax - xmin) / sample.width, (ymax - ymin) / sample.height
    return f"{class_ids[name]} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}"


def selected_samples(samples: list[Sample], assignments: dict[str, str], mode: str, ratio: float, seed: int) -> list[Sample]:
    if mode == "joint":
        return samples
    positives = [sample for sample in samples if sample.category == mode]
    negatives = [sample for sample in samples if sample.category != mode]
    selected = [sample for sample in negatives if assignments[sample.stem] != "train"]
    train_negatives = [sample for sample in negatives if assignments[sample.stem] == "train"]
    train_positives = [sample for sample in positives if assignments[sample.stem] == "train"]
    limit = len(train_negatives) if math.isinf(ratio) else min(len(train_negatives), round(len(train_positives) * ratio))
    random.Random(seed).shuffle(train_negatives)
    return positives + selected + train_negatives[:limit]


def materialize_dataset(samples: list[Sample], assignments: dict[str, str], experiment: Experiment) -> Path:
    target = WORK / "datasets" / experiment.name
    yaml_path = target / "data.yaml"
    if yaml_path.exists():
        return yaml_path
    class_ids = {"scratch": 0, "missing_tooth": 1} if experiment.mode == "joint" else {experiment.mode: 0}
    chosen = selected_samples(samples, assignments, experiment.mode, experiment.negative_ratio, experiment.seed)
    for sample in chosen:
        split = assignments[sample.stem]
        image_dir, label_dir = target / "images" / split, target / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sample.image, image_dir / sample.image.name)
        boxes = sample.boxes if experiment.mode == "joint" else tuple(box for box in sample.boxes if box[0] == experiment.mode)
        lines = [yolo_line(box, sample, class_ids) for box in boxes]
        (label_dir / f"{sample.stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="ascii")
    names = "\n".join(f"  {index}: {name}" for name, index in class_ids.items())
    yaml_path.write_text(
        f"path: {target.as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n",
        encoding="ascii",
    )
    return yaml_path


def augmentation_args(level: str) -> dict[str, float]:
    if level == "none":
        return dict(mosaic=0.0, degrees=0.0, translate=0.0, scale=0.0, fliplr=0.0, flipud=0.0, hsv_h=0.0, hsv_s=0.0, hsv_v=0.0)
    return dict(mosaic=0.0, degrees=2.0, translate=0.02, scale=0.10, fliplr=0.5, flipud=0.5, hsv_h=0.005, hsv_s=0.15, hsv_v=0.12)


def train_experiment(experiment: Experiment, data: Path, deadline: float) -> Path | None:
    run_dir = RUNS / experiment.name
    best = run_dir / "weights" / "best.pt"
    if best.exists() and (run_dir / "complete.flag").exists():
        return best
    if best.exists() and best.stat().st_size < 10_000_000 and (run_dir / "results.csv").exists():
        return best
    if time.monotonic() >= deadline:
        return None
    model = YOLO(experiment.weights)
    batch = 16 if experiment.imgsz == 960 else 8
    try:
        model.train(
            data=str(data), epochs=experiment.epochs, patience=12 if experiment.epochs <= 30 else 25,
            imgsz=experiment.imgsz, batch=batch, workers=4,
            device=0, amp=True, cache="ram", project=str(RUNS), name=experiment.name, exist_ok=False,
            optimizer="AdamW", lr0=0.001 if experiment.epochs <= 30 else 0.0007,
            weight_decay=0.0005, close_mosaic=0, seed=experiment.seed, deterministic=False,
            plots=True, **augmentation_args(experiment.augmentation),
        )
    except torch.OutOfMemoryError:
        torch.cuda.empty_cache()
        model = YOLO(experiment.weights)
        model.train(
            data=str(data), epochs=experiment.epochs, patience=12, imgsz=experiment.imgsz,
            batch=max(2, batch // 2), workers=4, device=0, amp=True, cache="ram",
            project=str(RUNS), name=experiment.name, exist_ok=True, optimizer="AdamW", lr0=0.001,
            seed=experiment.seed, deterministic=False, plots=True, **augmentation_args(experiment.augmentation),
        )
    (run_dir / "complete.flag").write_text("completed\n", encoding="ascii")
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return best if best.exists() else None


def evaluate(weights: Path, data: Path, split: str, mode: str, imgsz: int) -> dict[str, object]:
    model = YOLO(weights)
    class_names = list(CLASSES) if mode == "joint" else [mode]
    best_by_class: dict[str, dict[str, float]] = {name: {"precision": 0.0, "recall": 0.0, "map50": 0.0, "map5095": 0.0, "conf": 0.0} for name in class_names}
    for conf in CONF_THRESHOLDS:
        metrics = model.val(
            data=str(data), split=split, conf=conf, iou=0.7, imgsz=imgsz,
            batch=16 if imgsz == 960 else 8, device=0, workers=4, plots=False, verbose=False,
        )
        for index, name in enumerate(class_names):
            current = {
                "precision": float(metrics.box.p[index]), "recall": float(metrics.box.r[index]),
                "map50": float(metrics.box.ap50[index]), "map5095": float(metrics.box.ap[index]), "conf": conf,
            }
            best = best_by_class[name]
            current_ok, best_ok = current["precision"] >= 0.50, best["precision"] >= 0.50
            if (current_ok and not best_ok) or (current_ok == best_ok and (current["recall"], current["map50"]) > (best["recall"], best["map50"])):
                best_by_class[name] = current
    del model
    gc.collect()
    torch.cuda.empty_cache()
    recalls = [value["recall"] for value in best_by_class.values()]
    eligible = all(value["precision"] >= 0.50 for value in best_by_class.values())
    return {"classes": best_by_class, "eligible": eligible, "score": min(recalls) if eligible else -1.0}


def write_state(rows: list[dict[str, object]]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "leaderboard.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with (OUTPUT / "leaderboard.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("name", "mode", "stage", "score", "eligible", "details"))
        writer.writeheader()
        for row in rows:
            writer.writerow({**{key: row[key] for key in ("name", "mode", "stage", "score", "eligible")}, "details": json.dumps(row["details"])})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run recall-first defect detector experiments.")
    parser.add_argument("--hours", type=float, default=6.0)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required")
    for path in (OFFICIAL, GEAR, OLD_DEFECT):
        if not path.is_file():
            raise FileNotFoundError(path)
    started, deadline = time.monotonic(), time.monotonic() + args.hours * 3600
    samples = load_samples()
    assignments = make_split(samples)
    WORK.mkdir(parents=True, exist_ok=True)
    split_rows = [{"stem": sample.stem, "category": sample.category, "split": assignments[sample.stem], "dhash": f"{sample.dhash:016x}"} for sample in samples]
    (WORK / "split.json").write_text(json.dumps(split_rows, indent=2), encoding="ascii")

    pilots = [
        Experiment("p_s_off_bal_none", "scratch", OFFICIAL, 1.0, 960, "none"),
        Experiment("p_s_off_2x_light", "scratch", OFFICIAL, 2.0, 960, "light"),
        Experiment("p_s_off_all_1280", "scratch", OFFICIAL, math.inf, 1280, "light"),
        Experiment("p_s_gear_bal_light", "scratch", GEAR, 1.0, 960, "light", eligible=False),
        Experiment("p_m_off_bal_light", "missing_tooth", OFFICIAL, 1.0, 960, "light"),
        Experiment("p_m_off_2x_light", "missing_tooth", OFFICIAL, 2.0, 960, "light"),
        Experiment("p_joint_off_light", "joint", OFFICIAL, math.inf, 960, "light"),
        Experiment("p_joint_old_light", "joint", OLD_DEFECT, math.inf, 960, "light", eligible=False),
    ]
    rows: list[dict[str, object]] = []
    pilot_results: dict[str, list[tuple[Experiment, float]]] = {"scratch": [], "missing_tooth": [], "joint": []}
    for experiment in pilots:
        data = materialize_dataset(samples, assignments, experiment)
        weights = train_experiment(experiment, data, deadline)
        if weights is None:
            break
        result = evaluate(weights, data, "val", experiment.mode, experiment.imgsz)
        score = float(result["score"]) if experiment.eligible else -1.0
        pilot_results[experiment.mode].append((experiment, score))
        rows.append({"name": experiment.name, "mode": experiment.mode, "stage": "pilot", "score": score, "eligible": experiment.eligible and bool(result["eligible"]), "details": result})
        write_state(rows)

    finalists: list[Experiment] = []
    for mode in ("scratch", "missing_tooth", "joint"):
        eligible = [(experiment, score) for experiment, score in pilot_results[mode] if experiment.eligible]
        if not eligible:
            continue
        winner = max(eligible, key=lambda item: item[1])[0]
        finalists.append(Experiment(f"f_{mode}_{winner.augmentation}_{winner.imgsz}_seed42", mode, OFFICIAL, winner.negative_ratio, winner.imgsz, winner.augmentation, 100, 42))

    final_results: list[tuple[Experiment, Path, Path, dict[str, object]]] = []
    for experiment in finalists:
        data = materialize_dataset(samples, assignments, experiment)
        weights = train_experiment(experiment, data, deadline)
        if weights is None:
            break
        result = evaluate(weights, data, "val", experiment.mode, experiment.imgsz)
        final_results.append((experiment, data, weights, result))
        rows.append({"name": experiment.name, "mode": experiment.mode, "stage": "full", "score": result["score"], "eligible": result["eligible"], "details": result})
        write_state(rows)

    separate = [item for item in final_results if item[0].mode in CLASSES]
    joint = [item for item in final_results if item[0].mode == "joint"]
    chosen: list[tuple[Experiment, Path, Path, dict[str, object]]]
    if len(separate) == 2 and (not joint or min(float(item[3]["score"]) for item in separate) > float(joint[0][3]["score"]) + 0.03):
        chosen = separate
    else:
        chosen = joint or separate

    confirmed = []
    for experiment, _, _, result in chosen:
        if float(result["score"]) < 0.70 or time.monotonic() >= deadline:
            continue
        repeat = Experiment(
            f"c_{experiment.mode}_{experiment.augmentation}_{experiment.imgsz}_seed123",
            experiment.mode, OFFICIAL, experiment.negative_ratio, experiment.imgsz,
            experiment.augmentation, 100, 123,
        )
        data = materialize_dataset(samples, assignments, repeat)
        weights = train_experiment(repeat, data, deadline)
        if weights is not None:
            repeat_result = evaluate(weights, data, "val", repeat.mode, repeat.imgsz)
            rows.append({"name": repeat.name, "mode": repeat.mode, "stage": "confirm", "score": repeat_result["score"], "eligible": repeat_result["eligible"], "details": repeat_result})
            write_state(rows)
            if float(repeat_result["score"]) >= 0.70:
                confirmed.append((repeat, data, weights, repeat_result))
    if confirmed and len(confirmed) == len(chosen):
        chosen = confirmed

    final_dir = OUTPUT / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    test_results = []
    for experiment, data, weights, _ in chosen:
        test = evaluate(weights, data, "test", experiment.mode, experiment.imgsz)
        destination = final_dir / f"{experiment.mode}_best.pt"
        shutil.copy2(weights, destination)
        test_results.append({"mode": experiment.mode, "weights": str(destination), "metrics": test})
    summary = {
        "gpu": torch.cuda.get_device_name(0), "elapsed_hours": (time.monotonic() - started) / 3600,
        "target": {"recall": 0.70, "precision_floor": 0.50}, "selected": test_results,
        "target_met": bool(test_results) and all(
            all(value["recall"] >= 0.70 and value["precision"] >= 0.50 for value in item["metrics"]["classes"].values())
            for item in test_results
        ),
    }
    (OUTPUT / "final_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
