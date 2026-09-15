from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from infer_scratch_v5 import fuse as fuse_scratch
from infer_scratch_v5 import predict_classifier as predict_scratch_classifier
from infer_scratch_v5 import predict_detector as predict_scratch_detector
from missing_hole_runtime import predict_config
from train_scratch_v5 import binary_auc, undo_temperature


ROOT = Path(__file__).resolve().parent
WORK = ROOT / "dataset_defects" / "missing_hole_v1"
DEFAULT_CONFIG = ROOT / "outputs" / "missing_hole_v1" / "inference_config.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "missing_hole_v1" / "test"
DEFAULT_SCRATCH_CONFIG = ROOT / "outputs" / "scratch_v5" / "inference_config.json"
DEFAULT_UNIFIED_CONFIG = ROOT / "outputs" / "unified_defect_v1" / "inference_config.json"


@dataclass(frozen=True)
class TruthBox:
    name: str
    difficult: bool
    xyxy: tuple[float, float, float, float]


@dataclass(frozen=True)
class TestSample:
    stem: str
    image: Path
    boxes: tuple[TruthBox, ...]

    @property
    def defect(self) -> bool:
        return bool(self.boxes)

    @property
    def has_difficult(self) -> bool:
        return any(box.difficult for box in self.boxes)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-shot locked Missing Hole V1 test")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scratch-config", type=Path, default=DEFAULT_SCRATCH_CONFIG)
    parser.add_argument("--unified-config", type=Path, default=DEFAULT_UNIFIED_CONFIG)
    parser.add_argument("--device", default="0")
    parser.add_argument("--final", action="store_true", help="Required acknowledgement that test is final")
    parser.add_argument("--reuse-predictions", action="store_true")
    return parser.parse_args()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load_test() -> list[TestSample]:
    image_dir = ROOT / "dataset_defects" / "images" / "test_missing_tooth"
    annotation_dir = ROOT / "dataset_defects" / "annotations" / "test_missing_tooth"
    samples = []
    for image in sorted(image_dir.glob("*")):
        if image.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}:
            continue
        xml = annotation_dir / f"{image.stem}.xml"
        boxes = []
        if xml.is_file():
            root = ET.parse(xml).getroot()
            for obj in root.findall("object"):
                node = obj.find("bndbox")
                if node is None:
                    continue
                boxes.append(TruthBox(obj.findtext("name", "").strip(), obj.findtext("difficult", "0").strip() == "1", tuple(float(node.findtext(key, "0")) for key in ("xmin", "ymin", "xmax", "ymax"))))
        samples.append(TestSample(image.stem, image, tuple(boxes)))
    if len(samples) != 150 or sum(sample.defect for sample in samples) != 44 or sum(len(sample.boxes) for sample in samples) != 168:
        raise RuntimeError("Unexpected locked test set")
    return samples


def image_metrics(samples: list[TestSample], probabilities: list[float], threshold: float, mode: str) -> dict[str, object]:
    indexes = []
    labels = []
    for index, sample in enumerate(samples):
        if mode == "ignore_difficult":
            non_difficult = [box for box in sample.boxes if not box.difficult]
            if sample.boxes and not non_difficult:
                continue
            label = int(bool(non_difficult))
        elif mode == "easy_only":
            if sample.has_difficult:
                continue
            label = int(sample.defect)
        else:
            label = int(sample.defect)
        indexes.append(index)
        labels.append(label)
    guesses = [probabilities[index] >= threshold for index in indexes]
    tp = sum(label and guess for label, guess in zip(labels, guesses))
    fp = sum(not label and guess for label, guess in zip(labels, guesses))
    tn = sum(not label and not guess for label, guess in zip(labels, guesses))
    fn = sum(label and not guess for label, guess in zip(labels, guesses))
    recall = tp / max(1, tp + fn)
    precision = tp / max(1, tp + fp)
    fpr = fp / max(1, fp + tn)
    auroc, auprc = binary_auc(labels, [probabilities[index] for index in indexes])
    groups = {}
    for name in ("bottom", "oblique", "side"):
        group = [index for index in indexes if any(box.name == name and (mode == "all" or not box.difficult) for box in samples[index].boxes)]
        groups[name] = {"images": len(group), "recall": sum(probabilities[index] >= threshold for index in group) / max(1, len(group))}
    return {"images": len(indexes), "positives": sum(labels), "negatives": len(labels) - sum(labels), "threshold": threshold, "recall": recall, "precision": precision, "f1": 2 * precision * recall / max(1e-9, precision + recall), "fpr": fpr, "specificity": 1 - fpr, "npv": tn / max(1, tn + fn), "auroc": auroc, "auprc": auprc, "tp": tp, "fp": fp, "tn": tn, "fn": fn, "groups": groups}


def iou(left: tuple[float, float, float, float], right: list[float]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    return intersection / max(1e-9, left_area + right_area - intersection)


def class_matches(name: str, class_id: int, scheme: str) -> bool:
    scheme = scheme.removeprefix("refined_")
    if scheme == "one_class":
        return True
    if scheme == "two_class":
        return class_id == (1 if name == "side" else 0)
    return class_id == {"bottom": 0, "oblique": 1, "side": 2}[name]


def box_metrics(samples: list[TestSample], predictions: list[list[dict[str, object]]], confidence: float, threshold: float, ignore_difficult: bool, class_aware: bool, scheme: str) -> dict[str, object]:
    tp = fp = fn = ignored = 0
    for sample, candidates in zip(samples, predictions):
        truths = list(sample.boxes)
        matched = set()
        for candidate in sorted((item for item in candidates if float(item["confidence"]) >= confidence), key=lambda item: float(item["confidence"]), reverse=True):
            best = None
            for index, truth in enumerate(truths):
                if index in matched or (class_aware and not class_matches(truth.name, int(candidate["class_id"]), scheme)):
                    continue
                overlap = iou(truth.xyxy, candidate["xyxy"])
                if overlap >= threshold and (best is None or overlap > best[0]):
                    best = (overlap, index)
            if best is not None:
                truth = truths[best[1]]
                if ignore_difficult and truth.difficult:
                    ignored += 1
                else:
                    tp += 1
                matched.add(best[1])
            else:
                fp += 1
        fn += sum(index not in matched and not (ignore_difficult and truth.difficult) for index, truth in enumerate(truths))
    recall = tp / max(1, tp + fn)
    precision = tp / max(1, tp + fp)
    return {"iou": threshold, "confidence": confidence, "class_aware": class_aware, "ignore_difficult": ignore_difficult, "recall": recall, "precision": precision, "f1": 2 * precision * recall / max(1e-9, precision + recall), "tp": tp, "fp": fp, "fn": fn, "ignored": ignored}


def truth_class_id(name: str, scheme: str) -> int:
    scheme = scheme.removeprefix("refined_")
    if scheme == "one_class":
        return 0
    if scheme == "two_class":
        return 1 if name == "side" else 0
    return {"bottom": 0, "oblique": 1, "side": 2}[name]


def average_precision(recalls: np.ndarray, precisions: np.ndarray) -> float:
    recall = np.concatenate(([0.0], recalls, [1.0]))
    precision = np.concatenate(([1.0], precisions, [0.0]))
    precision = np.maximum.accumulate(precision[::-1])[::-1]
    points = np.where(recall[1:] != recall[:-1])[0]
    return float(np.sum((recall[points + 1] - recall[points]) * precision[points + 1]))


def class_ap(samples: list[TestSample], predictions: list[list[dict[str, object]]], class_id: int, overlap: float, scheme: str) -> float | None:
    truths: dict[int, list[TruthBox]] = {}
    difficult: dict[int, list[TruthBox]] = {}
    total = 0
    for image_index, sample in enumerate(samples):
        truths[image_index] = [box for box in sample.boxes if not box.difficult and truth_class_id(box.name, scheme) == class_id]
        difficult[image_index] = [box for box in sample.boxes if box.difficult and truth_class_id(box.name, scheme) == class_id]
        total += len(truths[image_index])
    if total == 0:
        return None
    candidates = sorted(
        (
            (float(candidate["confidence"]), image_index, candidate["xyxy"])
            for image_index, image_predictions in enumerate(predictions)
            for candidate in image_predictions
            if int(candidate["class_id"]) == class_id
        ),
        reverse=True,
    )
    matched: dict[int, set[int]] = {index: set() for index in range(len(samples))}
    tp: list[int] = []
    fp: list[int] = []
    for _, image_index, coordinates in candidates:
        choices = [
            (iou(box.xyxy, coordinates), index)
            for index, box in enumerate(truths[image_index])
            if index not in matched[image_index]
        ]
        best = max(choices, default=(0.0, -1))
        if best[0] >= overlap:
            matched[image_index].add(best[1])
            tp.append(1)
            fp.append(0)
        elif any(iou(box.xyxy, coordinates) >= overlap for box in difficult[image_index]):
            continue
        else:
            tp.append(0)
            fp.append(1)
    if not tp:
        return 0.0
    cumulative_tp = np.cumsum(tp)
    cumulative_fp = np.cumsum(fp)
    recalls = cumulative_tp / total
    precisions = cumulative_tp / np.maximum(1, cumulative_tp + cumulative_fp)
    return average_precision(recalls, precisions)


def map_metrics(samples: list[TestSample], predictions: list[list[dict[str, object]]], scheme: str) -> dict[str, object]:
    scheme = scheme.removeprefix("refined_")
    class_count = {"one_class": 1, "two_class": 2, "three_class": 3}[scheme]
    by_iou: dict[str, float] = {}
    by_class: dict[str, dict[str, float]] = {str(class_id): {} for class_id in range(class_count)}
    for overlap in np.arange(0.5, 0.96, 0.05):
        values = []
        for class_id in range(class_count):
            value = class_ap(samples, predictions, class_id, float(overlap), scheme)
            if value is not None:
                values.append(value)
                by_class[str(class_id)][f"{overlap:.2f}"] = value
        by_iou[f"{overlap:.2f}"] = float(np.mean(values)) if values else 0.0
    return {"mAP50": by_iou["0.50"], "mAP50_95": float(np.mean(list(by_iou.values()))), "by_iou": by_iou, "by_class": by_class, "difficult_policy": "ignore"}


def save_visualizations(output: Path, samples: list[TestSample], probabilities: list[float], predictions: list[list[dict[str, object]]], detector_confidence: float, decision_threshold: float) -> list[dict[str, str]]:
    scratch = scratch_labels(samples)
    selectors = {
        "normal": lambda sample, index: not sample.defect and not scratch[index],
        "bottom": lambda sample, index: any(box.name == "bottom" for box in sample.boxes),
        "oblique": lambda sample, index: any(box.name == "oblique" for box in sample.boxes),
        "side": lambda sample, index: any(box.name == "side" for box in sample.boxes),
        "mixed": lambda sample, index: len({box.name for box in sample.boxes}) > 1,
        "difficult": lambda sample, index: sample.has_difficult,
        "scratch_and_missing": lambda sample, index: sample.defect and bool(scratch[index]),
    }
    visual_dir = output / "visualizations"
    visual_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for category, selector in selectors.items():
        selected = next(((index, sample) for index, sample in enumerate(samples) if selector(sample, index)), None)
        if selected is None:
            continue
        index, sample = selected
        with Image.open(sample.image) as opened:
            image = opened.convert("RGB")
        draw = ImageDraw.Draw(image)
        for box in sample.boxes:
            color = "#f4b400" if box.difficult else "#22c55e"
            draw.rectangle(box.xyxy, outline=color, width=4)
            draw.text((box.xyxy[0] + 3, max(0, box.xyxy[1] - 14)), f"GT {box.name}{' difficult' if box.difficult else ''}", fill=color)
        for candidate in predictions[index]:
            if float(candidate["confidence"]) < detector_confidence:
                continue
            coordinates = candidate["xyxy"]
            draw.rectangle(coordinates, outline="#ef4444", width=3)
            draw.text((coordinates[0] + 3, coordinates[1] + 3), f"P {float(candidate['confidence']):.3f}", fill="#ef4444")
        decision = "REJECT" if probabilities[index] >= decision_threshold else "PASS"
        draw.rectangle((0, 0, min(image.width, 480), 28), fill="black")
        draw.text((6, 7), f"{category} | p={probabilities[index]:.4f} | {decision}", fill="white")
        destination = visual_dir / f"{category}_{sample.image.name}"
        image.save(destination)
        saved.append({"category": category, "image": str(destination.resolve()), "source": str(sample.image.resolve())})
    return saved


def labels_metrics(labels: list[int], probabilities: list[float], threshold: float) -> dict[str, object]:
    guesses = [value >= threshold for value in probabilities]
    tp = sum(label and guess for label, guess in zip(labels, guesses))
    fp = sum(not label and guess for label, guess in zip(labels, guesses))
    tn = sum(not label and not guess for label, guess in zip(labels, guesses))
    fn = sum(label and not guess for label, guess in zip(labels, guesses))
    recall, precision = tp / max(1, tp + fn), tp / max(1, tp + fp)
    fpr = fp / max(1, fp + tn)
    return {"recall": recall, "precision": precision, "f1": 2 * precision * recall / max(1e-9, precision + recall), "fpr": fpr, "tp": tp, "fp": fp, "tn": tn, "fn": fn}


def scratch_labels(samples: list[TestSample]) -> list[int]:
    annotation_dir = ROOT / "dataset_defects" / "annotations" / "test_scratch"
    return [int((annotation_dir / f"{sample.stem}.xml").is_file()) for sample in samples]


def main() -> None:
    args = parse_args()
    if not args.final:
        raise RuntimeError("Refusing to read locked test set without --final")
    args.output.mkdir(parents=True, exist_ok=True)
    lock = args.output / "evaluation_lock.json"
    prediction_file = args.output / "raw_predictions.json"
    if lock.exists() and not args.reuse_predictions:
        raise FileExistsError("Test was already evaluated; use --reuse-predictions to rebuild reports without inference")
    samples = load_test()
    paths = [sample.image for sample in samples]
    if args.reuse_predictions:
        stored = json.loads(prediction_file.read_text(encoding="utf-8"))
        probabilities, boxes = stored["probabilities"], stored["boxes"]
        config = json.loads(args.config.read_text(encoding="utf-8"))
    else:
        probabilities, _, boxes, config = predict_config(args.config.resolve(), paths, args.device, keep_boxes=True)
        prediction_file.write_text(json.dumps({"probabilities": probabilities, "boxes": boxes}), encoding="utf-8")
    threshold = float(config["default_threshold"])
    metrics = {mode: image_metrics(samples, probabilities, threshold, mode) for mode in ("all", "ignore_difficult", "easy_only")}
    detector = next((model for model in config["models"] if model["kind"] == "detector"), None)
    box_results = []
    detector_map = None
    raw_confidence = 1.0
    if detector:
        scheme = str(detector.get("scheme") or "one_class")
        calibrated_confidence = float(detector.get("operating_points", {}).get("0.2", {}).get("threshold", 0.001))
        raw_confidence = undo_temperature(calibrated_confidence, float(detector.get("temperature", 1.0)))
        for overlap in (0.3, 0.5):
            for ignored in (False, True):
                for aware in (False, True):
                    box_results.append(box_metrics(samples, boxes, raw_confidence, overlap, ignored, aware, scheme))
        detector_map = map_metrics(samples, boxes, scheme)
    rows = []
    for sample, probability in zip(samples, probabilities):
        rows.append({"image": sample.image, "truth": "missing_hole" if sample.defect else "normal_for_missing_hole", "classes": "+".join(sorted({box.name for box in sample.boxes})), "has_difficult": sample.has_difficult, "probability": probability, "threshold": threshold, "prediction": "REJECT" if probability >= threshold else "PASS"})
    with (args.output / "test_predictions.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    combined = None
    if not args.reuse_predictions and args.scratch_config.is_file() and args.unified_config.is_file():
        scratch_config = json.loads(args.scratch_config.read_text(encoding="utf-8"))
        classifier_scores = {str(model["name"]): predict_scratch_classifier(model, paths, args.device) for model in scratch_config["classifiers"]}
        detector_scores, _ = predict_scratch_detector(scratch_config["detector"], paths, args.device)
        scratch_probabilities, _ = fuse_scratch(scratch_config, classifier_scores, detector_scores)
        unified_probabilities, _, _, unified_config = predict_config(args.unified_config.resolve(), paths, args.device, keep_boxes=False)
        scratch_truth = scratch_labels(samples)
        missing_truth = [int(sample.defect) for sample in samples]
        any_truth = [int(scratch or missing) for scratch, missing in zip(scratch_truth, missing_truth)]
        specialist_guess = [scratch >= float(scratch_config["default_threshold"]) or missing >= threshold for scratch, missing in zip(scratch_probabilities, probabilities)]
        specialist_probability = [float(guess) for guess in specialist_guess]
        combined = {
            "counts": {"scratch": sum(scratch_truth), "missing_hole": sum(missing_truth), "any_defect": sum(any_truth), "both": sum(a and b for a, b in zip(scratch_truth, missing_truth)), "normal": sum(not value for value in any_truth)},
            "specialist_or": labels_metrics(any_truth, specialist_probability, 0.5),
            "specialist_scratch_recall": sum(truth and guess for truth, guess in zip(scratch_truth, specialist_guess)) / max(1, sum(scratch_truth)),
            "specialist_missing_recall": sum(truth and guess for truth, guess in zip(missing_truth, specialist_guess)) / max(1, sum(missing_truth)),
            "unified_single_model": labels_metrics(any_truth, unified_probabilities, float(unified_config["default_threshold"])),
        }
        prediction_file.write_text(json.dumps({"probabilities": probabilities, "boxes": boxes, "scratch_probabilities": scratch_probabilities, "unified_probabilities": unified_probabilities, "combined": combined}), encoding="utf-8")
    elif args.reuse_predictions:
        combined = json.loads(prediction_file.read_text(encoding="utf-8")).get("combined")
    visualizations = save_visualizations(args.output, samples, probabilities, boxes, raw_confidence, threshold)
    report = {"version": "missing_hole_v1", "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "config": str(args.config.resolve()), "config_sha256": digest(args.config), "test_manifest_sha256": digest(WORK / "master_manifest.csv"), "weights_and_threshold_selected_without_test": True, "image_metrics": metrics, "box_metrics": box_results, "detector_map": detector_map, "visualizations": visualizations, "combined_systems": combined, "target": {"recall_min": 0.95, "fpr_max": 0.20}, "target_met": metrics["all"]["recall"] >= 0.95 and metrics["all"]["fpr"] <= 0.20}
    (args.output / "test_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lock.write_text(json.dumps({"config_sha256": report["config_sha256"], "test_manifest_sha256": report["test_manifest_sha256"], "created": report["evaluated_at"]}, indent=2), encoding="utf-8")
    all_metrics = metrics["all"]
    lines = ["# Missing Hole V1 独立测试结果", "", "test 在模型、融合和阈值锁定后一次性评估。", "", "| 口径 | Recall | Precision | F1 | FPR | TP/FP/TN/FN |", "|---|---:|---:|---:|---:|---:|"]
    for mode, title in (("all", "包含 difficult"), ("ignore_difficult", "忽略 difficult"), ("easy_only", "纯易样本")):
        item = metrics[mode]
        lines.append(f"| {title} | {item['recall']:.4f} | {item['precision']:.4f} | {item['f1']:.4f} | {item['fpr']:.4f} | {item['tp']}/{item['fp']}/{item['tn']}/{item['fn']} |")
    lines += ["", f"主目标 Recall>=95% 且 FPR<=20%：`{'达到' if report['target_met'] else '未达到'}`", "", "## 位置分组", "", "| 位置 | 图片 | Recall |", "|---|---:|---:|"]
    for name, item in all_metrics["groups"].items():
        lines.append(f"| {name} | {item['images']} | {item['recall']:.4f} |")
    if detector_map:
        lines += ["", "## 定位指标", "", f"- class-aware mAP50: `{detector_map['mAP50']:.4f}`", f"- class-aware mAP50-95: `{detector_map['mAP50_95']:.4f}`"]
    if combined:
        lines += ["", "## Scratch + Missing Hole", "", "| 系统 | 任意缺陷 Recall | Precision | FPR | TP/FP/TN/FN |", "|---|---:|---:|---:|---:|"]
        for key, title in (("specialist_or", "双专项 OR"), ("unified_single_model", "统一单模型")):
            item = combined[key]
            lines.append(f"| {title} | {item['recall']:.4f} | {item['precision']:.4f} | {item['fpr']:.4f} | {item['tp']}/{item['fp']}/{item['tn']}/{item['fn']} |")
    lines.append("")
    (args.output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
