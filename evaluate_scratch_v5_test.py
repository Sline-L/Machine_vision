from __future__ import annotations

import argparse
import csv
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

from infer_scratch_v5 import fuse, predict_classifier, predict_detector, resolve_config_paths
from prepare_scratch_v5 import image_dhash
from train_scratch_v5 import binary_auc


ROOT = Path(__file__).resolve().parent
DEFAULT_IMAGES = ROOT / "dataset_defects" / "images" / "test_scratch"
DEFAULT_ANNOTATIONS = ROOT / "dataset_defects" / "annotations" / "test_scratch"
DEFAULT_CONFIG = ROOT / "outputs" / "scratch_v5" / "inference_config.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "scratch_v5" / "test_scratch"
REFERENCE_IMAGES = (
    ROOT / "dataset_defects" / "images" / "train_scratch",
    ROOT / "dataset_defects" / "images" / "val_scratch",
)
EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the locked Scratch V5 test set once")
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", default="0")
    parser.add_argument("--force", action="store_true", help="Replace an existing test report")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_ground_truth(images: Path, annotations: Path) -> tuple[list[Path], list[int], dict[str, int]]:
    paths = sorted(path for path in images.iterdir() if path.is_file() and path.suffix.lower() in EXTENSIONS)
    if not paths:
        raise FileNotFoundError(f"No test images found in {images}")
    if len({path.stem for path in paths}) != len(paths):
        raise ValueError("Duplicate test image stems")

    image_stems = {path.stem for path in paths}
    orphan_xml = sorted(path.name for path in annotations.glob("*.xml") if path.stem not in image_stems)
    if orphan_xml:
        raise FileNotFoundError(f"Test XML without image: {orphan_xml}")

    labels: list[int] = []
    box_count = 0
    for path in paths:
        xml_path = annotations / f"{path.stem}.xml"
        if not xml_path.is_file():
            labels.append(0)
            continue
        root = ET.parse(xml_path).getroot()
        size = root.find("size")
        if size is None:
            raise ValueError(f"Missing size in {xml_path}")
        expected_size = (int(size.findtext("width", "0")), int(size.findtext("height", "0")))
        with Image.open(path) as image:
            actual_size = image.size
        if actual_size != expected_size:
            raise ValueError(f"Image/XML size mismatch for {path.name}: {actual_size} != {expected_size}")
        objects = root.findall("object")
        if not objects:
            raise ValueError(f"Annotated test XML contains no boxes: {xml_path}")
        for obj in objects:
            if obj.findtext("name", "").strip() != "scratch":
                raise ValueError(f"Unexpected class in {xml_path}")
            box = obj.find("bndbox")
            if box is None:
                raise ValueError(f"Missing box in {xml_path}")
            xmin, ymin = float(box.findtext("xmin", "nan")), float(box.findtext("ymin", "nan"))
            xmax, ymax = float(box.findtext("xmax", "nan")), float(box.findtext("ymax", "nan"))
            if not (0 <= xmin < xmax <= actual_size[0] and 0 <= ymin < ymax <= actual_size[1]):
                raise ValueError(f"Invalid box in {xml_path}: {(xmin, ymin, xmax, ymax)}")
            box_count += 1
        labels.append(1)
    return paths, labels, {
        "images": len(paths),
        "scratch_images": sum(labels),
        "normal_images": len(labels) - sum(labels),
        "scratch_boxes": box_count,
    }


def leakage_check(paths: list[Path]) -> dict[str, object]:
    references = [
        path
        for directory in REFERENCE_IMAGES
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in EXTENSIONS
    ]
    test_signatures = [(path, sha256(path), image_dhash(path)) for path in paths]
    reference_signatures = [(path, sha256(path), image_dhash(path)) for path in references]
    exact = []
    near = []
    for test_path, test_sha, test_hash in test_signatures:
        for reference_path, reference_sha, reference_hash in reference_signatures:
            distance = (test_hash ^ reference_hash).bit_count()
            if test_sha == reference_sha:
                exact.append((test_path.name, reference_path.name))
            if distance <= 2:
                near.append((test_path.name, reference_path.name, distance))
    return {
        "reference_images": len(references),
        "exact_cross_pairs": len(exact),
        "dhash_le_2_cross_pairs": len(near),
        "dhash_warning": bool(near),
        "examples": near[:20],
    }


def metrics(labels: list[int], probabilities: list[float], threshold: float) -> dict[str, float | int]:
    guesses = [probability >= threshold for probability in probabilities]
    tp = sum(actual == 1 and guess for actual, guess in zip(labels, guesses))
    fp = sum(actual == 0 and guess for actual, guess in zip(labels, guesses))
    tn = sum(actual == 0 and not guess for actual, guess in zip(labels, guesses))
    fn = sum(actual == 1 and not guess for actual, guess in zip(labels, guesses))
    recall = tp / max(1, tp + fn)
    precision = tp / max(1, tp + fp)
    fpr = fp / max(1, fp + tn)
    auroc, auprc = binary_auc(labels, probabilities)
    return {
        "threshold": threshold,
        "recall": recall,
        "precision": precision,
        "f1": 2 * precision * recall / max(1e-9, precision + recall),
        "fpr": fpr,
        "specificity": 1 - fpr,
        "npv": tn / max(1, tn + fn),
        "auroc": auroc,
        "auprc": auprc,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def main() -> None:
    args = parse_args()
    report_path = args.output / "test_report.json"
    if report_path.exists() and not args.force:
        raise FileExistsError(f"Locked test report already exists: {report_path}; use --force only intentionally")

    paths, labels, counts = load_ground_truth(args.images, args.annotations)
    config_path = args.config.expanduser().resolve()
    config = resolve_config_paths(json.loads(config_path.read_text(encoding="utf-8")), config_path)
    threshold = float(config["default_threshold"])
    classifier_scores = {
        str(model["name"]): predict_classifier(model, paths, args.device)
        for model in config["classifiers"]
    }
    detector_scores = None
    if config.get("detector"):
        detector_scores, _ = predict_detector(config["detector"], paths, args.device)
    probabilities, classifier_values = fuse(config, classifier_scores, detector_scores)
    result_metrics = metrics(labels, probabilities, threshold)
    leakage = leakage_check(paths)

    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, path in enumerate(paths):
        predicted = int(probabilities[index] >= threshold)
        rows.append({
            "image": str(path),
            "truth": "scratch" if labels[index] else "normal",
            "prediction": "REJECT" if predicted else "PASS",
            "correct": int(predicted == labels[index]),
            "scratch_probability": probabilities[index],
            "classifier_probability": classifier_values[index],
            "detector_probability": detector_scores[index] if detector_scores is not None else "",
            "threshold": threshold,
        })
    with (args.output / "test_predictions.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    errors = [row for row in rows if not row["correct"]]
    with (args.output / "test_errors.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(errors)

    report = {
        "locked_evaluation": True,
        "config": str(args.config),
        "weights_and_threshold_selected_without_test": True,
        "counts": counts,
        "metrics": result_metrics,
        "leakage_check": leakage,
        "target": {"scratch_recall": 0.95, "normal_fpr_max": 0.20},
        "target_met": result_metrics["recall"] >= 0.95 and result_metrics["fpr"] <= 0.20,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = [
        "# Scratch V5 独立测试结果",
        "",
        f"- 测试图片：`{counts['images']}`（划痕 {counts['scratch_images']}，正常 {counts['normal_images']}）",
        f"- 固定阈值：`{threshold:.6f}`",
        f"- Recall：`{result_metrics['recall']:.3f}`",
        f"- Precision：`{result_metrics['precision']:.3f}`",
        f"- F1：`{result_metrics['f1']:.3f}`",
        f"- 正常误报率：`{result_metrics['fpr']:.3f}`",
        f"- TP/FP/TN/FN：`{result_metrics['tp']}/{result_metrics['fp']}/{result_metrics['tn']}/{result_metrics['fn']}`",
        f"- AUROC/AUPRC：`{result_metrics['auroc']:.3f}/{result_metrics['auprc']:.3f}`",
        f"- 是否达标：`{'是' if report['target_met'] else '否'}`",
        "",
        "阈值和模型均在运行本测试前锁定，本测试结果未用于调参。",
        f"精确重复跨集合为 {leakage['exact_cross_pairs']} 对；dHash 距离 <=2 为 {leakage['dhash_le_2_cross_pairs']} 对，后者需要结合图像复核，不能单独认定为重复。",
    ]
    (args.output / "README.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
